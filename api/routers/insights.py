from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.models import SaveAsNoteRequest, SourceInsightResponse
from open_notebook.domain.notebook import SourceInsight
from open_notebook.exceptions import DatabaseOperationError, InvalidInputError

router = APIRouter()


@router.get("/insights/{insight_id}", response_model=SourceInsightResponse)
async def get_insight(insight_id: str):
    """Get a specific insight by ID."""
    try:
        insight = await SourceInsight.get(insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        # Get source ID from the insight relationship
        source = await insight.get_source()
        
        return SourceInsightResponse(
            id=insight.id,
            source_id=source.id,
            insight_type=insight.insight_type,
            content=insight.content,
            created=str(insight.created),
            updated=str(insight.updated),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching insight {insight_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching insight: {str(e)}")


@router.delete("/insights/{insight_id}")
async def delete_insight(insight_id: str):
    """Delete a specific insight."""
    try:
        insight = await SourceInsight.get(insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        
        await insight.delete()
        
        return {"message": "Insight deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting insight {insight_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting insight: {str(e)}")
