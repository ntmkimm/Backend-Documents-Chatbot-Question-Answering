import asyncio
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple
from datetime import datetime, timezone
import uuid

from loguru import logger
from pydantic import BaseModel, Field, field_validator

from open_notebook.database.repository import ensure_record_id, repo_query, repo_create
from open_notebook.domain.base import ObjectModel
from open_notebook.domain.models import model_manager
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError
from open_notebook.utils import split_text
from open_notebook.database import milvus_services


class Notebook(ObjectModel):
    table_name: ClassVar[str] = "notebook"
    name: str
    description: str
    archived: Optional[bool] = False

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise InvalidInputError("Notebook name cannot be empty")
        return v

    async def get_sources(self) -> List["Source"]:
        try:
            q = """
                SELECT s.* 
                FROM source s
                WHERE s.notebook_id = :id
                ORDER BY s.updated DESC
            """
            srcs = await repo_query(q, {"id": ensure_record_id(self.id)})
            return [Source(**src) for src in srcs] if srcs else []
        except Exception as e:
            logger.error(f"Error fetching sources for notebook {self.id}: {str(e)}")
            raise DatabaseOperationError(e)

    async def get_chat_sessions(self) -> List["ChatSession"]:
        try:
            q = """
                SELECT s.* 
                FROM chat_session s
                WHERE s.notebook_id = :id
                ORDER BY s.updated DESC
            """
            rows = await repo_query(q, {"id": ensure_record_id(self.id)})
            return [ChatSession(**row) for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching chat sessions for notebook {self.id}: {str(e)}")
            raise DatabaseOperationError(e)


class Asset(BaseModel):
    file_path: Optional[str] = None
    url: Optional[str] = None

class SourceInsight(ObjectModel):
    table_name: ClassVar[str] = "source_insight"
    insight_type: str
    content: str
    source_id: str

    async def get_source(self) -> "Source":
        try:
            q = "SELECT * FROM source WHERE id = :id"
            rows = await repo_query(q, {"id": ensure_record_id(self.source_id)})
            return Source(**rows[0]) if rows else None
        except Exception as e:
            logger.error(f"Error fetching source for insight {self.id}: {str(e)}")
            raise DatabaseOperationError(e)


class Source(ObjectModel):
    notebook_id: Optional[str] = None
    table_name: ClassVar[str] = "source"
    asset: Optional[Any] = None
    title: Optional[str] = None
    topics: Optional[List[str]] = Field(default_factory=list)
    full_text: Optional[str] = None

    async def get_context(self, context_size: Literal["short", "long"] = "short") -> Dict[str, Any]:
        insights_list = await self.get_insights()
        insights = [insight.model_dump() for insight in insights_list]
        if context_size == "long":
            return dict(
                id=self.id,
                title=self.title,
                insights=insights,
                full_text=self.full_text,
            )
        else:
            return dict(id=self.id, title=self.title, insights=insights)

    async def get_embedded_chunks(self) -> int:
        try:
            return milvus_services.get_number_embeddings_ofsource(
                collection_name="source_embedding",
                source_id=self.id
            )
        except Exception as e:
            logger.error(f"Error fetching chunks count for source {self.id}: {str(e)}")
            raise DatabaseOperationError(f"Failed to count chunks for source: {str(e)}")

    async def get_insights(self) -> List[SourceInsight]:
        try:
            q = "SELECT * FROM source_insight WHERE source_id = :id"
            result = await repo_query(q, {"id": ensure_record_id(self.id)})
            return [SourceInsight(**insight) for insight in result]
        except Exception as e:
            logger.error(f"Error fetching insights for source {self.id}: {str(e)}")
            raise DatabaseOperationError("Failed to fetch insights for source")

    async def add_insight(self, insight_type: str, content: str) -> Any:
        if not insight_type or not content:
            raise InvalidInputError("Insight type and content must be provided")
        try:
            return await repo_create(
                "source_insight",
                {
                    "source_id": ensure_record_id(self.id),
                    "insight_type": insight_type,
                    "content": content,
                },
                set_id=True
            )
        except Exception as e:
            logger.error(f"Error adding insight to source {self.id}: {str(e)}")
            raise DatabaseOperationError(e)

    async def vectorize(self, notebook_id: str) -> None:
        print("func vectorize")
        logger.info(f"Starting vectorization for source {self.id}")
        EMBEDDING_MODEL = await model_manager.get_embedding_model()

        try:
            if not self.full_text:
                logger.warning(f"No text to vectorize for source {self.id}")
                return

            chunks = split_text(self.full_text)
            if not chunks:
                logger.warning("No chunks created after splitting")
                return

            async def process_chunk(idx: int, chunk: str) -> Tuple[int, List[float], str]:
                try:
                    embedding = (await EMBEDDING_MODEL.aembed([chunk]))[0]
                    return (idx, embedding, chunk)
                except Exception as e:
                    logger.error(f"Error processing chunk {idx}: {str(e)}")
                    raise

            results = await asyncio.gather(*[process_chunk(i, c) for i, c in enumerate(chunks)])
            for idx, embedding, content in results:
                data = {
                    "dense_vector": embedding,
                    "content": content,
                    "order": idx,
                    "source_id": self.id,
                    "notebook_id": notebook_id,
                }
                milvus_services.insert_data(collection_name="source_embedding", data=data)

            logger.info(f"Vectorization complete for source {self.id}")

        except Exception as e:
            logger.error(f"Error vectorizing source {self.id}: {str(e)}")
            raise DatabaseOperationError(e)


class ChatSession(ObjectModel):
    id: Optional[str] = None
    notebook_id: Optional[str] = None
    table_name: ClassVar[str] = "chat_session"
    title: Optional[str] = None


async def hybrid_search_in_notebook(
    keyword: str, 
    results: int,
    notebook_id: str, 
    source_ids: List[str] = [],
):
    if not keyword:
        raise InvalidInputError("Search keyword cannot be empty")
    if not ensure_record_id(notebook_id):
        raise InvalidInputError("Search notebook_id may be wrong")
    try:
        EMBEDDING_MODEL = await model_manager.get_embedding_model()
        embed = (await EMBEDDING_MODEL.aembed([keyword]))[0]
        params = {
            "collection_name": "source_embedding",
            "query_keyword": [keyword],
            "query_vector": [embed],
            "notebook_id": notebook_id,
            "limit": results,
            "source_ids": source_ids,
        }
        results = milvus_services.hybrid_search(**params)
        return results
    except Exception as e:
        logger.error(f"Error performing hybrid search: {str(e)}")
        logger.exception(e)
        raise DatabaseOperationError(e)
    
async def text_search_in_notebook(
    keyword: str, 
    results: int,
    notebook_id: str, 
    source_ids: List[str] = [],
):
    if not keyword:
        raise InvalidInputError("Search keyword cannot be empty")
    if not ensure_record_id(notebook_id):
        raise InvalidInputError("Search notebook_id may be wrong")
    try:

        params = {
            "collection_name": "source_embedding",
            "query_keyword": [keyword],
            "notebook_id": notebook_id,
            "limit": results,
            "source_ids": source_ids,
        }
        results = milvus_services.full_text_search(**params)
        return results
    except Exception as e:
        logger.error(f"Error performing full text search: {str(e)}")
        logger.exception(e)
        raise DatabaseOperationError(e)
    
async def semantic_search_in_notebook(
    keyword: str, 
    results: int,
    notebook_id: str, 
    source_ids: List[str] = [],
):
    if not keyword:
        raise InvalidInputError("Search keyword cannot be empty")
    if not ensure_record_id(notebook_id):
        raise InvalidInputError("Search notebook_id may be wrong")
    try:

        EMBEDDING_MODEL = await model_manager.get_embedding_model()
        embed = (await EMBEDDING_MODEL.aembed([keyword]))[0]
        params = {
            "collection_name": "source_embedding",
            "query_vector": [embed],
            "notebook_id": notebook_id,
            "limit": results,
            "source_ids": source_ids,
        }
        results = milvus_services.semantic_vector_search(**params)
        return results
    except Exception as e:
        logger.error(f"Error performing full text search: {str(e)}")
        logger.exception(e)
        raise DatabaseOperationError(e)
