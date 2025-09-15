import os
from dotenv import load_dotenv
load_dotenv()

MILVUS_ADDRESS = os.getenv("MILVUS_ADDRESS", "192.168.20.156")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_URI = os.getenv("MILVUS_URI", f"http://{MILVUS_ADDRESS}:{MILVUS_PORT}")
from typing import List, Dict, Union
from pymilvus import MilvusClient, DataType, AnnSearchRequest, RRFRanker, Function, FunctionType
from api.models import SourceEmbeddingResponse

class MilvusService:
    _client = MilvusClient(uri=MILVUS_URI, token="root:Milvus")

    @classmethod
    async def get_source_embedding_byid(cls, collection_name: str, key: Union[str, List[str]]):
        if isinstance(key, str):
            key = [key]
        key = [int(s.split(":", 1)[1]) if ":" in s else s for s in key]
        print("Key:", key)
        res = cls._client.get(
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

    @classmethod
    async def delete_embedding(cls, source_id: str):
        return cls._client.delete(
            collection_name="source_embedding",
            filter=f'source_id == "{source_id}"'
        )

    @classmethod
    async def insert_data(cls, collection_name: str, data: dict):
        cls._client.insert(
            collection_name=collection_name,
            data=data
        )

    @classmethod
    async def hybrid_search(
        cls,
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

        print(f"Keyword: {query_keyword}")
        print("Filter:", filter_expr)

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
        res = cls._client.hybrid_search(
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
                print(f"ID: {hit.id}, Distance: {hit.distance}, Primary Key: {primary_key}, Content: {content}")
        return results

    @classmethod
    def migrate(cls):
        collec_name = "source_embedding"
        if cls._client.has_collection(collec_name):
            print(f"{collec_name} is already exist.")
            return

        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("primary_key", DataType.INT64, is_primary=True)
        schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=1536)
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

        index_params = cls._client.prepare_index_params()
        index_params.add_index("dense_vector", "AUTOINDEX", metric_type="COSINE")
        index_params.add_index("sparse_vector", "SPARSE_INVERTED_INDEX", metric_type="BM25",
                               params={"inverted_index_algo": "DAAT_MAXSCORE"})
        index_params.add_index("source_id", "INVERTED")
        index_params.add_index("notebook_id", "INVERTED")

        cls._client.create_collection(
            collection_name=collec_name,
            schema=schema,
            index_params=index_params
        )

        print("Milvus migrate sucessfull")
