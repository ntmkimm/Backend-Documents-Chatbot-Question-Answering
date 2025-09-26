from esperanto import LanguageModel
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger
import json

from open_notebook.domain.models import model_manager
from open_notebook.utils import token_count
from typing import List

async def provision_langchain_model(
    content, model_id, default_type, **kwargs
) -> BaseChatModel:
    model = await model_manager.get_default_model(default_type, **kwargs)

    logger.debug(f"Using model: {model}")
    assert isinstance(model, LanguageModel), f"Model is not a LanguageModel: {model}"
    return model.to_langchain()

import os, logging
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import PostgresChatMessageHistory
from pymilvus import (
    connections, FieldSchema, CollectionSchema, DataType, Collection, utility
)

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "notebook")
POSTGRES_ADDRESS = os.getenv("POSTGRES_ADDRESS", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")

DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_ADDRESS}:{POSTGRES_PORT}/{POSTGRES_DB}"
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    BaseMessage,
    message_to_dict,
    messages_from_dict,
)

class NotebookPostgresChatMessageHistory(BaseChatMessageHistory):
    """Chat message history stored in a Postgres database.

    **DEPRECATED**: This class is deprecated and will be removed in a future version.

    Use the `PostgresChatMessageHistory` implementation in `langchain_postgres`.
    """

    def __init__(
        self,
        session_id: str,
        connection_string: str = DB_URI,
        table_name: str = "lc_message_history",
    ):
        import psycopg
        from psycopg.rows import dict_row

        try:
            self.connection = psycopg.connect(connection_string)
            self.cursor = self.connection.cursor(row_factory=dict_row)
        except psycopg.OperationalError as error:
            logger.error(error)

        self.session_id = session_id
        self.table_name = table_name

        self._create_table_if_not_exists()

    def _create_table_if_not_exists(self) -> None:
        create_table_query = f"""CREATE TABLE IF NOT EXISTS {self.table_name} (
            id SERIAL PRIMARY KEY,
            session_id UUID NOT NULL,
            message JSONB NOT NULL,
            CONSTRAINT fk_session_id
                FOREIGN KEY (session_id)
                REFERENCES chat_session(id)
                ON DELETE CASCADE
        );"""
        self.cursor.execute(create_table_query)
        self.connection.commit()

    @property
    def messages(self) -> List[BaseMessage]:  # type: ignore
        """Retrieve the messages from PostgreSQL"""
        query = (
            f"SELECT message FROM {self.table_name} WHERE session_id = %s ORDER BY id;"
        )
        self.cursor.execute(query, (self.session_id,))
        items = [record["message"] for record in self.cursor.fetchall()]
        messages = messages_from_dict(items)
        return messages

    def add_message(self, message: BaseMessage) -> None:
        """Append the message to the record in PostgreSQL"""
        from psycopg import sql

        query = sql.SQL("INSERT INTO {} (session_id, message) VALUES (%s, %s);").format(
            sql.Identifier(self.table_name)
        )
        self.cursor.execute(
            query, (self.session_id, json.dumps(message_to_dict(message)))
        )
        self.connection.commit()

    def clear(self) -> None:
        """Clear session memory from PostgreSQL"""
        query = f"DELETE FROM {self.table_name} WHERE session_id = %s;"
        self.cursor.execute(query, (self.session_id,))
        self.connection.commit()

    def __del__(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

def get_postgres_short_memory(thread_id: str, k: int = 4) -> ConversationBufferWindowMemory:
    return ConversationBufferWindowMemory(
        k=k,
        memory_key="chat_history",
        return_messages=True,
        chat_memory=NotebookPostgresChatMessageHistory(
            connection_string=DB_URI,
            session_id=thread_id,
            table_name="lc_message_history"
        )
    )

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
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=32768),
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
    
    def delete(self, thread_id: str):
        """
        Delete all entries belonging to a specific thread_id.
        """
        try:
            # Build expression for deletion
            expr = f'thread_id == "{thread_id}"'

            # Perform delete
            self.collection.delete(expr)

            # Flush to make sure deletion is applied
            self.collection.flush()

            logger.info(f"Deleted all records with thread_id={thread_id} from {self.collection_name}")
        except Exception as e:
            logger.error(f"Error deleting records for thread_id={thread_id}: {str(e)}")
            raise

# Singleton instance
_memory_agent_milvus = MemoryAgentMilvus()