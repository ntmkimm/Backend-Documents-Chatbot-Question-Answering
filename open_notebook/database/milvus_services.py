from .milvus_init import get_milvus_client
from typing import List, Dict, Union
from pymilvus import MilvusClient, DataType, AnnSearchRequest, RRFRanker, Function, FunctionType
from api.models import SourceEmbeddingResponse
import os

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