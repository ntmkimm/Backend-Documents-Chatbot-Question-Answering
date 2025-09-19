from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List
import uuid

import os
from pathlib import Path
from loguru import logger

from api.models import (
    AssetModel,
    SourceResponse,
    NotebookSourceCreateRequest
)
from open_notebook.domain.notebook import Notebook
from open_notebook.domain.transformation import Transformation
from open_notebook.exceptions import InvalidInputError
from open_notebook.graphs.source import source_graph

router = APIRouter()
UPLOAD_FOLDER = './data/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class NotebookSourceForm:
    def __init__(
        self,
        notebook_id: str = Form(...),
        source_id: str = Form(...),
        embed: bool = Form(False),
        transformations: List[str] = Form([]),
        file: UploadFile = File(...)
    ):
        self.model = NotebookSourceCreateRequest(
            notebook_id=notebook_id,
            source_id=source_id,
            transformations=transformations,
            embed=embed
        )
        self.file = file

@router.post("/notebook/sources")
async def create_source(form: NotebookSourceForm = Depends()):
    try:
        file = form.file
        model = form.model
        file_path = Path(UPLOAD_FOLDER) / Path(file.filename).name

        with open(file_path, "wb") as f:
            f.write(await file.read())

        notebook = await Notebook.get(model.notebook_id)
        sourceid = uuid.UUID(model.source_id) # if not uuid, raise error
        sourceid = sourceid.hex
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")

        # Prepare content_state for source_graph
        content_state = {}
        content_state["file_path"] = str(file_path)
        content_state["delete_source"] = True

        # Get transformations to apply
        transformations = []
        if model.transformations:
            for trans_id in model.transformations:
                transformation = await Transformation.get(trans_id)
                if not transformation:
                    raise HTTPException(
                        status_code=404, detail=f"Transformation {trans_id} not found"
                    )
                transformations.append(transformation)
        print("File name", os.path.basename(file.filename))
        print("File name", str(os.path.basename(file.filename)))
        # Process source using the source_graph
        result = await source_graph.ainvoke(
            {
                "content_state": content_state,
                "notebook_id": model.notebook_id,
                "apply_transformations": transformations,
                "embed": model.embed,
                "title": str(os.path.basename(file.filename)),
                "source_id": sourceid,
            }
        )

        source = result["source"]

        #delete file after processing
        # if model.file_path:
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {str(e)}")

        return SourceResponse(
            id=source.id,
            title=source.title,
            topics=source.topics or [],
            asset=AssetModel(
                file_path=source.asset.file_path if source.asset else None,
                url=source.asset.url if source.asset else None,
            )
            if source.asset
            else None,
            full_text=source.full_text,
            embedded_chunks=await source.get_embedded_chunks(),
            created=str(source.created),
            updated=str(source.updated),
        )
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating source: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating source: {str(e)}")

