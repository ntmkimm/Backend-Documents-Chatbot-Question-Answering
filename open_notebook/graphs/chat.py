
from typing import Annotated, Optional

from ai_prompter import Prompter
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, AIMessage, AIMessageChunk
from open_notebook.domain.notebook import Notebook
from open_notebook.graphs.utils import provision_langchain_model
# from langgraph.checkpoint.postgres import PostgresSaver
# from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from dotenv import load_dotenv
load_dotenv()
import os

# Singleton 
# _checkpointer: Optional[AsyncSqliteSaver] = None

# async def get_checkpointer() -> AsyncSqliteSaver:
#     """Get or create the checkpointer instance with async SQLite connection"""
#     global _checkpointer
#     if _checkpointer is None:

#         conn = await aiosqlite.connect(
#             './data/sqlite-db/memory.sqlite',
#             timeout=30, 
#         )
        
#         await conn.execute('PRAGMA journal_mode=WAL')
#         await conn.execute('PRAGMA busy_timeout=30000')  
#         await conn.execute('PRAGMA synchronous=NORMAL')  
        
#         _checkpointer = AsyncSqliteSaver(conn)
#     return _checkpointer 

_checkpointer: Optional[AsyncPostgresSaver] = None
_pool: Optional[AsyncConnectionPool] = None  # Optional global to keep the pool alive

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": None,
}

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "notebook")
POSTGRES_ADDRESS = os.getenv("POSTGRES_ADDRESS", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")

DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_ADDRESS}:{POSTGRES_PORT}/{POSTGRES_DB}"

async def get_checkpointer() -> AsyncPostgresSaver:
    global _checkpointer, _pool
    if _checkpointer is None:
        _pool = AsyncConnectionPool(DB_URI, kwargs=connection_kwargs)
        checkpointer = AsyncPostgresSaver(_pool)
        await checkpointer.setup()
        _checkpointer = checkpointer
    return _checkpointer


class ThreadState(TypedDict):
    messages: Annotated[list, add_messages]
    notebook: Optional[Notebook]
    context: Optional[str]
    context_config: Optional[dict]

async def call_model_with_messages(state: ThreadState, config: RunnableConfig):
    """Async node that streams tokens and then returns the final message."""
    system_prompt = Prompter(prompt_template="chat").render(data=state)
    payload = [SystemMessage(content=system_prompt)] + state.get("messages", [])

    model = await provision_langchain_model(
        str(payload),
        config.get("configurable", {}).get("model_id"),
        "chat",
        max_tokens=10000,
    )

    # parts = []
    async for chunk in model.astream(payload):
        content = getattr(chunk, "content", None)
        if not content:
            continue

        # parts.append(content)
        yield {"content": content}

async def create_conversation_graph(state: ThreadState, config: RunnableConfig):
    agent_state = StateGraph(ThreadState)
    agent_state.add_node("agent", call_model_with_messages) # Use the async version
    agent_state.add_edge(START, "agent")
    agent_state.add_edge("agent", END)
    checkpointer = await get_checkpointer()
    return agent_state.compile(checkpointer=checkpointer)

_conversation_graph = None

async def get_conversation_graph(state: ThreadState, config: RunnableConfig):
    global _conversation_graph
    if _conversation_graph is None:
        _conversation_graph = await create_conversation_graph(state, config)
    print(f"Debug - _conversation_graph: {_conversation_graph}")
    return _conversation_graph
