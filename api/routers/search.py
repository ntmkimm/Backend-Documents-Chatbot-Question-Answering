import asyncio
from typing import AsyncGenerator, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from api.models import SearchRequest, SearchResponse
from open_notebook.domain.models import Model, model_manager
from open_notebook.domain.notebook import hybrid_search_in_notebook, text_search_in_notebook, semantic_search_in_notebook
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(search_request: SearchRequest):
    """Search the knowledge base using text or vector search."""
    try:     
        if search_request.type == "semantic":
            # Text search
            results = await semantic_search_in_notebook(
                keyword=search_request.query,
                results=search_request.limit,
                source_ids=search_request.source_ids,
                notebook_id=search_request.notebook_id,
            )
            
        elif search_request.type == "hybrid":
            results = await hybrid_search_in_notebook(
                keyword=search_request.query,
                results=search_request.limit,
                source_ids=search_request.source_ids,
                notebook_id=search_request.notebook_id,
            )


        elif search_request.type == "text":
            results = await text_search_in_notebook(
                keyword=search_request.query,
                results=search_request.limit,
                source_ids=search_request.source_ids,
                notebook_id=search_request.notebook_id,
            )
        tmp = []
        for k, v in results.items():
            tmp.append({"id": k, "content": v})
        results = tmp
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
