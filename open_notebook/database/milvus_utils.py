from pymilvus import MilvusClient, DataType, Function,FunctionType, AnnSearchRequest, RRFRanker
from typing import List

import os
from dotenv import load_dotenv
load_dotenv()

MILVUS_ADDRESS = os.getenv("MILVUS_ADDRESS", "192.168.20.156")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_URI = os.getenv("MILVUS_URI", f"http://{MILVUS_ADDRESS}:{MILVUS_PORT}")

async def insert_data(collection_name: str, data: dict):
    client = MilvusClient(
        uri=MILVUS_URI,
        token="root:Milvus"
    )
    client.insert(
        collection_name=collection_name,
        data=data
    )
    
async def hybrid_search(
        collection_name: str, 
        # query: dict, 
        query_vector, 
        query_keyword,
        limit: int, 
        notebook_id: str, 
        source_ids: List[str] = []):
    
    client = MilvusClient(
        uri=MILVUS_URI,
        token="root:Milvus"
    )

    if source_ids == []:
        filter = f'notebook_id == "{notebook_id}"'
    else:
        filter = f'source_id IN {source_ids}'
    # text semantic search (dense)
    # print(f"\n\nQuery vector {query_vector}")
    print(f"Keyword: {query_keyword}")
    print("Filter", filter)
    search_param_1 = {
        "data": query_vector,
        "anns_field": "dense_vector",
        "param": {"nprobe": 10},
        "limit": limit,
        "expr": filter
    }
    request_1 = AnnSearchRequest(**search_param_1)

    # full-text search (sparse)
    search_param_2 = {
        "data": query_keyword,
        "anns_field": "sparse_vector",
        "param": {"drop_ratio_search": 0.2},
        "limit": limit,
        "expr": filter
    }
    request_2 = AnnSearchRequest(**search_param_2)
    reqs = [request_1, request_2]
    ranker = RRFRanker(100) # parameter k in range (50 - 100)
    
    res = client.hybrid_search(
        collection_name=collection_name,
        reqs=reqs,
        ranker=ranker,
        output_fields=['primary_key', 'content'],
        limit=limit
    )

    results = {}
    # res is a list of HybridHits, so loop over each HybridHits
    for hits in res:
        for hit in hits:  # each hit is a single result
            primary_key = f"source_embedding:{hit.entity.get('primary_key')}"
            content = hit.entity.get("content")
            results[primary_key] = content
            print(f"ID: {hit.id}, Distance: {hit.distance}, Primary Key: {primary_key}, Content: {content}")

    return results


def milvus_migration():
    client = MilvusClient(
        uri=MILVUS_URI,
        token="root:Milvus"
    )
    try:
        client.drop_collection(
            collection_name="source_embedding"
        )
    except:
        pass
    schema = MilvusClient.create_schema(
        auto_id=True,
        enable_dynamic_field=False,
    )
    schema.add_field(field_name="primary_key", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=1536)
    schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field(field_name="content", datatype=DataType.VARCHAR, enable_analyzer=True,max_length=3500)
    schema.add_field(field_name="order", datatype=DataType.INT64)
    schema.add_field(field_name="source_id", datatype=DataType.VARCHAR, max_length=40)
    schema.add_field(field_name="notebook_id", datatype=DataType.VARCHAR, max_length=40)

    
    # Add function to schema
    bm25_function = Function(
        name="text_bm25_emb",
        input_field_names=["content"],
        output_field_names=["sparse_vector"],
        function_type=FunctionType.BM25,
    )
    schema.add_function(bm25_function)

    index_params = client.prepare_index_params()

    index_params.add_index(
        field_name="dense_vector",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )

    index_params.add_index(
        field_name="sparse_vector",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
        params={"inverted_index_algo": "DAAT_MAXSCORE"},
    )
    index_params.add_index(
        field_name="source_id",
        index_type="INVERTED"   # recommended for VARCHAR/INT fields used in filters
    )
    index_params.add_index(
        field_name="notebook_id",
        index_type="INVERTED"   # recommended for VARCHAR/INT fields used in filters
    )
    client.create_collection(
        collection_name="source_embedding",
        schema=schema,
        index_params=index_params
    )
