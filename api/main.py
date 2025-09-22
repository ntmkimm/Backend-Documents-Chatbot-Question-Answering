from dotenv import load_dotenv
load_dotenv()
from contextlib import asynccontextmanager
import os
print(os.getenv("MY_VARIABLE"))

from fastapi import FastAPI
from open_notebook.database.milvus_init import get_milvus_client, close_milvus_client
from fastapi.middleware.cors import CORSMiddleware

from api.auth import PasswordAuthMiddleware
from api.routers import (
    context,
    embedding,
    insights,
    notebooks,
    search,
    sources,
    # sources_tabular,
    transformations,
    notebook_sources,
    notebook_ask_chat,
)

from loguru import logger

# Run migration on startup
from open_notebook.database.async_migrate import migrate_all
from api import init_default_transformation_function
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await migrate_all()
    get_milvus_client()
    
    # Ensure the coroutine is awaited
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # No running loop
        loop = None

    if loop and loop.is_running():
        # If there's an existing running loop, use `create_task`
        asyncio.create_task(init_default_transformation_function())
    else:
        # Otherwise, run the coroutine normally
        asyncio.run(init_default_transformation_function())
    
    yield
    close_milvus_client()

app = FastAPI(
    title="Open Notebook API",
    description="API for Open Notebook - Research Assistant",
    version="0.2.2",
    lifespan=lifespan
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add password authentication middleware
app.add_middleware(PasswordAuthMiddleware)

# Include routers
app.include_router(notebooks.router, prefix="/api", tags=["notebooks"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(transformations.router, prefix="/api", tags=["transformations"])
app.include_router(embedding.router, prefix="/api", tags=["embedding"])
app.include_router(context.router, prefix="/api", tags=["context"])
app.include_router(sources.router, prefix="/api", tags=["sources"])
# app.include_router(sources_tabular.router, prefix="/api", tags=["sources_tabular"])
app.include_router(insights.router, prefix="/api", tags=["insights"])
app.include_router(notebook_sources.router, prefix="/api", tags=["notebook-source"])
app.include_router(notebook_ask_chat.router, prefix="/api", tags=["notebook-ask-chat"])
import asyncio

@app.get("/")
async def root():
    return {"message": "Open Notebook API is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
