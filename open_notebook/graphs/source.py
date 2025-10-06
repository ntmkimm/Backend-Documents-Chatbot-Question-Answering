import operator
from typing import Any, Dict, List, Optional
import json

from content_core import extract_content
from content_core.common import ProcessSourceState
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from loguru import logger
from typing_extensions import Annotated, TypedDict

from open_notebook.database.repository import transaction
from open_notebook.domain.content_settings import ContentSettings
from open_notebook.domain.notebook import Asset, Source
from open_notebook.domain.transformation import Transformation
from open_notebook.graphs.transformation import graph as transform_graph


class SourceState(TypedDict):
    content_state: ProcessSourceState
    apply_transformations: List[Transformation]
    notebook_id: str
    source: Source
    transformation: Annotated[list, operator.add]
    embed: bool
    source_id: str
    title: Optional[str]


class TransformationState(TypedDict):
    source: Source
    transformation: Transformation


async def content_process(state: SourceState) -> dict:
    content_settings = ContentSettings()
    content_state: Dict[str, Any] = state["content_state"]

    content_state["url_engine"] = (
        content_settings.default_content_processing_engine_url or "auto"
    )
    content_state["document_engine"] = (
        content_settings.default_content_processing_engine_doc or "auto"
    )
    content_state["output_format"] = "markdown"

    processed_state = await extract_content(content_state)
    return {"content_state": processed_state}


async def save_source(state: SourceState) -> dict:
    content_state = state["content_state"]
    # Serialize the Asset object to a JSON string
    asset_json = json.dumps(Asset(url=content_state.url, file_path=content_state.file_path).model_dump())

    source = Source(
        asset=asset_json,  # Pass the serialized JSON string
        full_text=content_state.content,
        title=state["title"],
        id=state["source_id"],
        notebook_id=state["notebook_id"]
    )


    if state["notebook_id"]:
        logger.debug(f"Adding source to notebook {state['notebook_id']}")
        # await source.add_to_notebook(state["notebook_id"])

    if state["embed"]:
        logger.debug("Embedding content for vector search")
        try:
            embeddings_chunk = await source.vectorize(state["notebook_id"])
            
            source.n_embedding_chunks = len(embeddings_chunk)

        except Exception as e:
            raise RuntimeError("Vectorize process error") from e
    try:
        await source.save(provided_id=True)
        await source.save_embedding_ids(embeddings_chunk)
    except Exception as e:
        await source.delete()
        raise RuntimeError(f"Error save source {e}") 

    return {"source": source}


def trigger_transformations(state: SourceState, config: RunnableConfig) -> List[Send]:
    if len(state["apply_transformations"]) == 0:
        return []

    to_apply = state["apply_transformations"]
    logger.debug(f"Applying transformations {to_apply}")

    return [
        Send(
            "transform_content",
            {
                "source": state["source"],
                "transformation": t,
            },
        )
        for t in to_apply
    ]


async def transform_content(state: TransformationState) -> Optional[dict]:
    source = state["source"]
    content = source.full_text
    if not content:
        return None
    transformation: Transformation = state["transformation"]

    logger.debug(f"Applying transformation {transformation.name}")
    result = await transform_graph.ainvoke(
        dict(input_text=content, transformation=transformation)
    )
    await source.add_insight(transformation.title, result["output"])
    return {
        "transformation": [
            {
                "output": result["output"],
                "transformation_name": transformation.name,
            }
        ]
    }


# Create and compile the workflow
workflow = StateGraph(SourceState)

# Add nodes
workflow.add_node("content_process", content_process)
workflow.add_node("save_source", save_source)
workflow.add_node("transform_content", transform_content)
# Define the graph edges
workflow.add_edge(START, "content_process")
workflow.add_edge("content_process", "save_source")
workflow.add_edge("save_source", END)
workflow.add_conditional_edges(
    "save_source", trigger_transformations, ["transform_content"]
)
workflow.add_edge("transform_content", END)

# Compile the graph
source_graph = workflow.compile()
