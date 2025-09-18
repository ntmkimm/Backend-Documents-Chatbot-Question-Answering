import asyncio
from typing import AsyncGenerator, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from api.models import SearchRequest, SearchResponse
from open_notebook.domain.models import Model, model_manager
from open_notebook.domain.notebook import text_search, vector_search, vector_search_in_notebook, text_search_in_notebook
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(search_request: SearchRequest):
    """Search the knowledge base using text or vector search."""
    try:
        # if search_request.type == "vector":
        #     # Check if embedding model is available for vector search
        #     if not await model_manager.get_embedding_model():
        #         raise HTTPException(
        #             status_code=400,
        #             detail="Vector search requires an embedding model. Please configure one in the Models section.",
        #         )

        #     results = await vector_search(
        #         keyword=search_request.query,
        #         results=search_request.limit,
        #         source=search_request.search_sources,
        #         note=search_request.search_notes,
        #         minimum_score=search_request.minimum_score,
        #     )
        
        if search_request.type == "text":
            # Text search
            results = await text_search(
                keyword=search_request.query,
                results=search_request.limit,
                source=search_request.search_sources,
                note=search_request.search_notes,
            )
            
        elif search_request.type == "notebook_vector":
            results = await vector_search_in_notebook(
                keyword=search_request.query,
                results=search_request.limit,
                source_ids=[],
                notebook_id=search_request.notebook_id,
            )
            tmp = []
            for k, v in results.items():
                tmp.append({"id": k, "content": v})
            results = tmp
        else:
            results = await text_search_in_notebook(
                keyword=search_request.query,
                results=search_request.limit,
                source=search_request.search_sources,
                note=search_request.search_notes,
                notebook_id=search_request.notebook_id,
            )

        return SearchResponse(
            results=results or [],
            total_count=len(results) if results else 0,
            search_type=search_request.type,
        )

    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseOperationError as e:
        logger.error(f"Database error during search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


async def stream_ask_response(
    question: str, 
    # strategy_model: Model, answer_model: Model, final_answer_model: Model
) -> AsyncGenerator[str, None]:
    """Stream the ask response as Server-Sent Events."""
    try:
        final_answer = None

        async for chunk in ask_graph.astream(
            input=dict(question=question),
            config=dict(
                configurable=dict()
            ),
            stream_mode="updates",
        ):
            if "agent" in chunk:
                strategy_data = {
                    "type": "strategy",
                    "reasoning": chunk["agent"]["strategy"].reasoning,
                    "searches": [
                        {"term": search.term, "instructions": search.instructions}
                        for search in chunk["agent"]["strategy"].searches
                    ],
                }
                yield f"data: {strategy_data}\n\n"

            elif "provide_answer" in chunk:
                for answer in chunk["provide_answer"]["answers"]:
                    answer_data = {"type": "answer", "content": answer}
                    yield f"data: {answer_data}\n\n"

            elif "write_final_answer" in chunk:
                final_answer = chunk["write_final_answer"]["final_answer"]
                final_data = {"type": "final_answer", "content": final_answer}
                yield f"data: {final_data}\n\n"

        # Send completion signal
        yield f"data: {{'type': 'complete', 'final_answer': '{final_answer}'}}\n\n"

    except Exception as e:
        logger.error(f"Error in ask streaming: {str(e)}")
        error_data = {"type": "error", "message": str(e)}
        yield f"data: {error_data}\n\n"
