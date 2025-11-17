import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Annotated, List, Optional, Dict, Any

from dotenv import load_dotenv
from loguru import logger
from psycopg import OperationalError
from psycopg_pool import AsyncConnectionPool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    BaseMessage,
    message_to_dict,
    messages_from_dict,
)
# from langchain.memory import ConversationBufferWindowMemory
from langchain_classic.memory import ConversationBufferMemory
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pymilvus import (
    connections,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    utility,
)
from esperanto import LanguageModel

from open_notebook.config import (
    DB_URI,
    connection_kwargs,
    POOL_TIMEOUT,
    POOL_SIZE,
    MILVUS_PORT,
    MILVUS_ADDRESS,
)
from open_notebook.domain.models import model_manager
from open_notebook.utils import token_count

load_dotenv()

async def provision_langchain_model(
    content, model_id, default_type, **kwargs
) -> BaseChatModel:
    model = await model_manager.get_default_model(default_type, **kwargs)

    logger.debug(f"Using model: {model}")
    assert isinstance(model, LanguageModel), f"Model is not a LanguageModel: {model}"
    return model.to_langchain()


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

def get_postgres_short_memory(thread_id: str, k: int = 4) -> ConversationBufferMemory:
    return ConversationBufferMemory(
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

        # blocking Milvus calls chạy trong thread
        def blocking_insert():
            self.collection.insert([[embedding], [text], [thread_id], [ts]])
            self.collection.flush()

        await asyncio.to_thread(blocking_insert)

    async def search_long_term_memory(self, query: str, thread_id: str, top_k: int = 5):
        EMBEDDING_MODEL = await model_manager.get_embedding_model()
        if not EMBEDDING_MODEL:
            logger.warning("No embedding model found. Cannot search.")
            return []

        # tạo embedding
        query_vec = (await EMBEDDING_MODEL.aembed([query]))[0]

        # chạy phần blocking trong thread
        def blocking_search():
            self.collection.load()
            return self.collection.search(
                data=[query_vec],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=top_k,
                output_fields=["text"],
                expr=f'thread_id == "{thread_id}"'
            )

        results = await asyncio.to_thread(blocking_search)

        # flatten và lấy text
        flattened = [hit['entity']['text'] for batch in results for hit in batch]
        return flattened

    
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

_checkpointer: Optional[AsyncPostgresSaver] = None
_pool: Optional[AsyncConnectionPool] = None
_lock = asyncio.Lock()

async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_checkpointer(retries: int = 3, delay: int = 2) -> AsyncPostgresSaver:
    global _checkpointer, _pool

    async with _lock:
        # Reuse valid pool if available
        if _checkpointer and _pool and not _pool.closed:
            try:
                async with _pool.connection() as conn:
                    await conn.execute("SELECT 1;")
                return _checkpointer
            except Exception as e:
                print(f"[get_checkpointer] Pool invalid: {e}, recreating...")
                await close_pool()
                _checkpointer = None

        # Retry creation
        for attempt in range(retries):
            try:
                print(f"[get_checkpointer] Init pool attempt {attempt+1}/{retries}")
                _pool = AsyncConnectionPool(
                    conninfo=DB_URI,
                    min_size=1,
                    max_size=POOL_SIZE,
                    timeout=POOL_TIMEOUT,
                    kwargs=connection_kwargs,
                    open=False,
                )
                await _pool.open(wait=True)

                _checkpointer = AsyncPostgresSaver(_pool)
                await _checkpointer.setup()
                print("[get_checkpointer] Ready")
                return _checkpointer

            except OperationalError as e:
                print(f"[get_checkpointer] OperationalError: {e}")
                await close_pool()
                _checkpointer = None
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise