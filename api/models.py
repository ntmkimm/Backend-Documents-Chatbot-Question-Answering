from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict
import os
import uuid
from dotenv import load_dotenv
load_dotenv()

from enum import Enum
class StreamEvent(str, Enum):
    STREAM_START = "stream-start"
    TEXT_GENERATION = "text-generation"
    TOOL_INPUT = "tool-input"
    TOOL_RESULT = "tool-result"
    CITATION_GENERATION = "citation-generation"
    STREAM_END = "stream-end"

# Notebook models
class NotebookCreate(BaseModel):
    notebook_id: str
    name: str = Field(..., description="Name of the notebook")
    description: str = Field(default="", description="Description of the notebook")


class NotebookUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Name of the notebook")
    description: Optional[str] = Field(None, description="Description of the notebook")
    archived: Optional[bool] = Field(None, description="Whether the notebook is archived")

class NotebookResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    archived: bool
    created: str
    updated: str

# Search models
class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    notebook_id: str = Field(..., description="Notebook id")
    source_ids: List[str] = Field([], description="Source ids will be searched in, if [] then search all")
    type: Literal["semantic", "text", "hybrid"] = Field("text", description="Search type")
    limit: int = Field(100, description="Maximum number of results", le=1000)



class SearchResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total number of results")
    search_type: str = Field(..., description="Type of search performed")

class ChatRequest(BaseModel):
    notebook_id: uuid.UUID = Field(..., description="ID of the notebook")
    session_id: Optional[str] = Field(None, description="ID of the chat session")
    source_ids: Optional[List[uuid.UUID]] = Field(None, description="List of source IDs to include in the chat context")
    chat_message: str = Field(..., description="Message content")

class ChatResponse(BaseModel):
    notebook_id: str = Field(..., description="ID of the notebook")
    session_id: str = Field(..., description="ID of the chat session")
    ai_message: str = Field(..., description="AI-generated message content")
    reference_sources: Optional[List[str]] = Field(..., description="List of source references used in the response")

class NotebookSourceCreateRequest(BaseModel):
    notebook_id: str = Field(..., description="ID of the notebook to create a session for")
    source_id: str = Field(..., description="ID for creating new source")
    title: Optional[str] = Field(None, description="Source title")
    transformations: Optional[List[str]] = Field(default_factory=list, description="Transformation IDs to apply")
    embed: bool = Field(False, description="Whether to embed content for vector search")


# Transformations API models
class TransformationCreate(BaseModel):
    name: str = Field(..., description="Transformation name")
    title: str = Field(..., description="Display title for the transformation")
    description: str = Field(..., description="Description of what this transformation does")
    prompt: str = Field(..., description="The transformation prompt")
    apply_default: bool = Field(False, description="Whether to apply this transformation by default")


class TransformationUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Transformation name")
    title: Optional[str] = Field(None, description="Display title for the transformation")
    description: Optional[str] = Field(None, description="Description of what this transformation does")
    prompt: Optional[str] = Field(None, description="The transformation prompt")
    apply_default: Optional[bool] = Field(None, description="Whether to apply this transformation by default")


class TransformationResponse(BaseModel):
    id: uuid.UUID
    name: str
    title: str
    description: str
    prompt: str
    apply_default: bool
    created: str
    updated: str


class TransformationExecuteRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    transformation_id: str = Field(..., description="ID of the transformation to execute")
    input_text: str = Field(..., description="Text to transform")
    # model_id: str = Field(..., description="Model ID to use for the transformation")


class TransformationExecuteResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    output: str = Field(..., description="Transformed text")
    transformation_id: str = Field(..., description="ID of the transformation used")
    # model_id: str = Field(..., description="Model ID used")



# Embedding API models
class EmbedRequest(BaseModel):
    item_id: str = Field(..., description="ID of the item to embed")
    item_type: str = Field(..., description="Type of item (source, note)")


class EmbedResponse(BaseModel):
    success: bool = Field(..., description="Whether embedding was successful")
    message: str = Field(..., description="Result message")
    item_id: str = Field(..., description="ID of the item that was embedded")
    item_type: str = Field(..., description="Type of item that was embedded")


# Sources API models
class AssetModel(BaseModel):
    file_path: Optional[str] = None
    url: Optional[str] = None


class SourceCreate(BaseModel):
    source_id: str
    notebook_id: str = Field(..., description="Notebook ID to add the source to")
    type: str = Field(..., description="Source type: link, upload, or text")
    url: Optional[str] = Field(None, description="URL for link type")
    file_path: Optional[str] = Field(None, description="File path for upload type")
    content: Optional[str] = Field(None, description="Text content for text type")
    title: Optional[str] = Field(None, description="Source title")
    transformations: Optional[List[str]] = Field(default_factory=list, description="Transformation IDs to apply")
    embed: bool = Field(False, description="Whether to embed content for vector search")
    delete_source: bool = Field(False, description="Whether to delete uploaded file after processing")


class SourceUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Source title")
    topics: Optional[List[str]] = Field(None, description="Source topics")

class SourceEmbeddingResponse(BaseModel):
    id: str
    source: Optional[str] = Field(None, description="Source id")
    order: Optional[int] = None
    content: Optional[str] = None
    embedding: Optional[List[float]] = None

class SourceResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    topics: Optional[List[str]]
    asset: Optional[AssetModel]
    full_text: Optional[str]
    embedded_chunks: int
    created: str
    updated: str


class SourceListResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    topics: Optional[List[str]]
    asset: Optional[AssetModel]
    embedded_chunks: int
    insights_count: int
    created: str
    updated: str


# Context API models
class ContextConfig(BaseModel):
    sources: Dict[str, str] = Field(default_factory=dict, description="Source inclusion config {source_id: level}")
    notes: Dict[str, str] = Field(default_factory=dict, description="Note inclusion config {note_id: level}")


class ContextRequest(BaseModel):
    notebook_id: str = Field(..., description="Notebook ID to get context for")
    context_config: Optional[ContextConfig] = Field(None, description="Context configuration")


class ContextResponse(BaseModel):
    notebook_id: str
    sources: List[Dict[str, Any]] = Field(..., description="Source context data")
    notes: List[Dict[str, Any]] = Field(..., description="Note context data")
    total_tokens: Optional[int] = Field(None, description="Estimated token count")


# Insights API models
class SourceInsightResponse(BaseModel):
    id: uuid.UUID
    source_id: str
    insight_type: str
    content: str
    created: str
    updated: str


class SaveAsNoteRequest(BaseModel):
    notebook_id: Optional[str] = Field(None, description="Notebook ID to add note to")


class CreateSourceInsightRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    transformation_id: str = Field(..., description="ID of transformation to apply")
    model_id: Optional[str] = Field(None, description="Model ID (uses default if not provided)")


# Error response
class ErrorResponse(BaseModel):
    error: str
    message: str