from esperanto import LanguageModel
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from open_notebook.domain.models import model_manager
from open_notebook.utils import token_count


async def provision_langchain_model(
    content, model_id, default_type, **kwargs
) -> BaseChatModel:
    model = await model_manager.get_default_model(default_type, **kwargs)

    logger.debug(f"Using model: {model}")
    assert isinstance(model, LanguageModel), f"Model is not a LanguageModel: {model}"
    return model.to_langchain()

import os
from dotenv import load_dotenv
load_dotenv()

MILVUS_ADDRESS = os.getenv("MILVUS_ADDRESS", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_URI = os.getenv("MILVUS_URI", f"http://{MILVUS_ADDRESS}:{MILVUS_PORT}")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "agent_memory1")

from datetime import datetime
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import PostgresChatMessageHistory
from langchain.schema import Document

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "notebook")
POSTGRES_ADDRESS = os.getenv("POSTGRES_ADDRESS", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")

DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_ADDRESS}:{POSTGRES_PORT}/{POSTGRES_DB}"

def get_postgres_short_memory(thread_id: str, k: int = 4) -> ConversationBufferWindowMemory:
    return ConversationBufferWindowMemory(
        k=k,
        memory_key="chat_history",
        return_messages=True,
        chat_memory=PostgresChatMessageHistory(
            connection_string=DB_URI,
            session_id=thread_id,
            table_name="lc_message_history"
        )
    )
    
from datetime import datetime
from pymilvus import (
    connections, FieldSchema, CollectionSchema, DataType, Collection, utility
)
import os, logging

logger = logging.getLogger(__name__)
MILVUS_ADDRESS = os.getenv("MILVUS_ADDRESS", "192.168.20.156")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))

class MemoryAgentMilvus:
    def __init__(self, collection_name: str = "agent_memory1"):
        self.collection_name = collection_name
        self.dim = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

        connections.connect(alias="default", host=MILVUS_ADDRESS, port=MILVUS_PORT)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="thread_id", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="ts", dtype=DataType.VARCHAR, max_length=64)
        ]
        schema = CollectionSchema(fields, description="Chat turns collection")

        if self.collection_name not in utility.list_collections():
            self.collection = Collection(name=self.collection_name, schema=schema)
            self.collection.create_index(
                field_name="embedding",
                index_params={
                    "index_type": "HNSW",
                    "metric_type": "COSINE",
                    "params": {"M": 16, "efConstruction": 200}
                }
            )
        else:
            self.collection = Collection(self.collection_name)

        self.collection.load()

    async def upsert_long_term_memory(self, user_text: str, ai_text: str, thread_id: str):
        ts = datetime.utcnow().isoformat()
        text = f"Human Message: {user_text}\nAI Message: {ai_text}"

        EMBEDDING_MODEL = await model_manager.get_embedding_model()
        if not EMBEDDING_MODEL:
            logger.warning("No embedding model found. Skipping insert.")
            return

        embedding = (await EMBEDDING_MODEL.aembed([text]))[0]

        self.collection.insert([
            [embedding],     
            [text],          
            [thread_id],     
            [ts], # timestamp  
        ])
        self.collection.flush()

    async def search_long_term_memory(self, query: str, thread_id: str, top_k: int = 5):
        EMBEDDING_MODEL = await model_manager.get_embedding_model()
        if not EMBEDDING_MODEL:
            logger.warning("No embedding model found. Cannot search.")
            return []

        query_vec = (await EMBEDDING_MODEL.aembed([query]))[0]

        self.collection.load()
        results = self.collection.search(
            data=[query_vec],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k,
            output_fields=["text"],
            expr=f'thread_id == "{thread_id}"'
        )
        return results

# Singleton instance
_memory_agent_milvus = MemoryAgentMilvus()