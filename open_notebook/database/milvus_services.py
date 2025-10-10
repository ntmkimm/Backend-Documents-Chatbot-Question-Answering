from .milvus_init import get_milvus_client
from typing import List, Dict, Union
from pymilvus import MilvusClient, DataType, AnnSearchRequest, RRFRanker, Function, FunctionType
from api.models import SourceEmbeddingResponse


def get_valid_id(collection_name: str, key: Union[str, List[str]]) -> List[str]:
    if isinstance(key, str):
        key = [key]
    key = [int(s.split(":", 1)[1]) if ":" in s else int(s) for s in key]

    client = get_milvus_client()
    res = client.get(
        collection_name=collection_name,
        ids=key,
        output_fields=["primary_key"]
    )

    found_ids = {row["primary_key"] for row in res}

    return [f"source_embedding:{pk}" for pk in found_ids]

def get_number_embeddings_ofsource(collection_name: str, source_id: str) -> int:
    client = get_milvus_client()

    client.flush(collection_name)
    client.load_collection(collection_name)
    query = client.query(collection_name, filter=f'source_id == "{source_id}"',
                                output_fields=["primary_key"])
    num_chunks = len(query)
    return num_chunks


def get_source_embedding_byid(collection_name: str, key: Union[str, List[str]]):
    if isinstance(key, str):
        key = [key]
    key = [int(s.split(":", 1)[1]) if ":" in s else s for s in key]

    client = get_milvus_client()
    res = client.get(
        collection_name=collection_name,
        ids=key,
        output_fields=["primary_key", "order", "source_id", "content"]
    )
    documents = [
        SourceEmbeddingResponse(
            id="source_embedding:"+str(r["primary_key"]),
            source=r.get("source_id"),
            order=r.get("order"),
            content=r.get("content"),
            embedding=None  # not returned in this query
        )
        for r in res
    ]
    return documents

def delete_embedding(source_id: str):
    client = get_milvus_client()
    q = client.delete(
        collection_name="source_embedding",
        filter=f'source_id == "{source_id}"'
    )
    return q

def insert_data(collection_name: str, data: Union[Dict, List[Dict]]):
    client = get_milvus_client()
    insert_info = client.insert(
        collection_name=collection_name,
        data=data
    )
    # Trả về danh sách primary key đã insert
    return list(insert_info["ids"])

def semantic_vector_search(
    collection_name: str,
    query_vector,
    limit: int,
    notebook_id: str,
    source_ids: List[str] = []
    ) -> Dict[str, str]:
    
    filter_expr = (
        f'notebook_id == "{notebook_id}"'
        if not source_ids
        else f'source_id IN {source_ids}'
    )
    client = get_milvus_client()

    res = client.search(
        collection_name=collection_name, 
        data = query_vector,
        anns_field='dense_vector',
        output_fields=['primary_key', 'content'], # Fields to return in search results; sparse field cannot be output
        limit=limit,
        filter=filter_expr
    )
    results = {
        f"source_embedding:{hit.entity.get('primary_key')}": hit.entity.get("content")
        for hits in res
        for hit in hits
    }
    return results

def full_text_search(
    collection_name: str,
    query_keyword,
    limit: int,
    notebook_id: str,
    source_ids: List[str] = []
    ) -> Dict[str, str]:
        search_params = {
            'params': {'drop_ratio_search': 0.2},
        }
        filter_expr = (
            f'notebook_id == "{notebook_id}"'
            if not source_ids
            else f'source_id IN {source_ids}'
        )

        client = get_milvus_client()
        res = client.search(
            collection_name=collection_name, 
            data = query_keyword,
            anns_field='sparse_vector',
            output_fields=['primary_key', 'content'], # Fields to return in search results; sparse field cannot be output
            limit=limit,
            search_params=search_params,
            filter=filter_expr
        )
        results = {
            f"source_embedding:{hit.entity.get('primary_key')}": hit.entity.get("content")
            for hits in res
            for hit in hits
        }
        return results
def hybrid_search(
        collection_name: str,
        query_vector,
        query_keyword,
        limit: int,
        notebook_id: str,
        source_ids: List[str] = [],
        return_score = False,
    ):

    filter_expr = (
        f'notebook_id == "{notebook_id}"'
        if not source_ids
        else f'source_id IN {source_ids}'
    )


    # Dense search
    request_1 = AnnSearchRequest(
        data=query_vector,
        anns_field="dense_vector",
        param={"nprobe": 10},
        limit=limit,
        expr=filter_expr
    )

    # Sparse search
    request_2 = AnnSearchRequest(
        data=query_keyword,
        anns_field="sparse_vector",
        param={"drop_ratio_search": 0.2},
        limit=limit,
        expr=filter_expr
    )

    # Combine
    ranker = Function(
        name="weight",
        input_field_names=[], # Must be an empty list
        function_type=FunctionType.RERANK,
        params={
            "reranker": "weighted", 
            "weights": [0.5, 0.5],
            "norm_score": True  
        }
    )

    client = get_milvus_client()

    res = client.hybrid_search(
        collection_name=collection_name,
        reqs=[request_1, request_2],
        ranker=ranker,
        output_fields=['primary_key', 'content'],
        limit=limit
    )

    if return_score:
        results = {
            f"source_embedding:{hit.entity.get('primary_key')}": {
                "content": hit.entity.get("content"),
                "score": hit.score
            }
            for hits in res
            for hit in hits
        }
    else:
        results = {
            f"source_embedding:{hit.entity.get('primary_key')}": hit.entity.get("content")
            for hits in res
            for hit in hits
        }

    return results



def get_all_collection():
    client = get_milvus_client()  
    collections = client.list_collections()
    return collections

def drop_all_collections():
    client = get_milvus_client()  
    
    collections = client.list_collections()
    for name in collections:
        print(f"Dropping collection: {name}")
        client.drop_collection(name)
    
    print("All collections dropped.")