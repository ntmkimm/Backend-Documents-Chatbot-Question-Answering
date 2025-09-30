from pymilvus import MilvusClient
from pymilvus import MilvusClient, DataType, AnnSearchRequest, RRFRanker, Function, FunctionType

import os
from open_notebook.config import MILVUS_URI


milvus_client: MilvusClient | None = None

def init_new_milvus_collection(client):
    collec_name = "source_embedding"

    if client.has_collection(collec_name):
        print(f"{collec_name} is already exist.")
        return

    schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("primary_key", DataType.INT64, is_primary=True)
    schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=int(os.getenv("EMBEDDING_DIMENSION", "1536")))
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field("content", DataType.VARCHAR, enable_analyzer=True, max_length=32768)
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
def get_milvus_client() -> MilvusClient:
    global milvus_client
    if milvus_client is None:
        milvus_client = MilvusClient(uri=MILVUS_URI,
                                     token="root:Milvus")
        init_new_milvus_collection(milvus_client)
    return milvus_client

def close_milvus_client():
    global milvus_client
    if milvus_client:
        milvus_client.close()
        milvus_client = None
