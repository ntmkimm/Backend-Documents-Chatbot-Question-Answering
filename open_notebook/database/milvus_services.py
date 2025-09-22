from .milvus_init import get_milvus_client
from typing import List, Dict, Union
from pymilvus import MilvusClient, DataType, AnnSearchRequest, RRFRanker, Function, FunctionType
from api.models import SourceEmbeddingResponse
import os

def get_number_embeddings_ofsource(collection_name: str, source_id: str) -> int:
    client = get_milvus_client()
    return len(client.query(collection_name, filter=f'source_id == "{source_id}"',
                                output_fields=[]))

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
    
    return client.delete(
        collection_name="source_embedding",
        filter=f'source_id == "{source_id}"'
    )

def insert_data(collection_name: str, data: dict):
    client = get_milvus_client()
    return client.insert(
        collection_name=collection_name,
        data=data
    )

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
    results = {}
    for hits in res:
        for hit in hits:
            primary_key = f"source_embedding:{hit.entity.get('primary_key')}"
            content = hit.entity.get("content")
            results[primary_key] = content
            # print(f"ID: {hit.id}, Distance: {hit.distance}, Primary Key: {primary_key}, Content: {content}")
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
        results = {}
        for hits in res:
            for hit in hits:
                primary_key = f"source_embedding:{hit.entity.get('primary_key')}"
                content = hit.entity.get("content")
                results[primary_key] = content
                # print(f"ID: {hit.id}, Distance: {hit.distance}, Primary Key: {primary_key}, Content: {content}")
        return results
def hybrid_search(
        collection_name: str,
        query_vector,
        query_keyword,
        limit: int,
        notebook_id: str,
        source_ids: List[str] = []
    ) -> Dict[str, str]:

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
    ranker = RRFRanker(100)

    client = get_milvus_client()

    res = client.hybrid_search(
        collection_name=collection_name,
        reqs=[request_1, request_2],
        ranker=ranker,
        output_fields=['primary_key', 'content'],
        limit=limit
    )

    results = {}
    for hits in res:
        for hit in hits:
            primary_key = f"source_embedding:{hit.entity.get('primary_key')}"
            content = hit.entity.get("content")
            results[primary_key] = content
            # print(f"ID: {hit.id}, Distance: {hit.distance}, Primary Key: {primary_key}, Content: {content}")
    return results

def init_new_milvus_collection():
    collec_name = "source_embedding"
    client = get_milvus_client()

    if client.has_collection(collec_name):
        print(f"{collec_name} is already exist.")
        return

    schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("primary_key", DataType.INT64, is_primary=True)
    schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=int(os.getenv("EMBEDDING_DIMENSION", "1536")))
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field("content", DataType.VARCHAR, enable_analyzer=True, max_length=3500)
    schema.add_field("order", DataType.INT64)
    schema.add_field("source_id", DataType.VARCHAR, max_length=64)
    schema.add_field("notebook_id", DataType.VARCHAR, max_length=64)

    bm25_function = Function(
        name="text_bm25_emb",
        input_field_names=["content"],
        output_field_names=["sparse_vector"],
        function_type=FunctionType.BM25,
    )
    schema.add_function(bm25_function)

    index_params = client.prepare_index_params()
    index_params.add_index("dense_vector", "AUTOINDEX", metric_type="COSINE")
    index_params.add_index("sparse_vector", "SPARSE_INVERTED_INDEX", metric_type="BM25",
                            params={"inverted_index_algo": "DAAT_MAXSCORE"})
    index_params.add_index("source_id", "INVERTED")
    index_params.add_index("notebook_id", "INVERTED")

    client.create_collection(
        collection_name=collec_name,
        schema=schema,
        index_params=index_params
    )

    print(f"Initialize Collection({collec_name}) sucessfull")