
# open_notebook/graphs/ask_chat.py
from __future__ import annotations

import operator
from typing import Annotated, List, Optional, Dict, Any

from ai_prompter import Prompter
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langgraph.graph import START, END, StateGraph
from langgraph.types import Send
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AIMessageChunk

from langchain.chains import ConversationalRetrievalChain
from open_notebook.graphs.utils import (
    provision_langchain_model, 
    _memory_agent_milvus,
    get_postgres_short_memory,
)

from open_notebook.domain.notebook import (
    vector_search_in_notebook,
    text_search_in_notebook,
    Notebook,
)
from open_notebook.utils import clean_thinking_content 
from langchain_core.output_parsers.pydantic import PydanticOutputParser

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from dotenv import load_dotenv
load_dotenv()
import os

class Search(BaseModel):
    term: str
    instructions: str = Field(
        description="Tell the answering LLM what info to extract from this search"
    )

class Strategy(BaseModel):
    reasoning: str
    searches: List[Search] = Field(default_factory=list, description="<= 5 searches")

class ThreadState(TypedDict, total=False):
    # messages: Annotated[list, operator.add]
    message: Optional[HumanMessage]
    notebook: Optional[Notebook]  
    notebook_id: Optional[str]
    context: Optional[Dict[str, str]]
    context_config: Optional[dict]
    source_ids: Optional[List[str]]
    # fields for strategy & retrieval
    strategy: Strategy
    retrieval_limit: int


async def plan_strategy(state: ThreadState, config: RunnableConfig) -> dict:
    """LLM tạo chiến lược và các search terms trước khi build context."""
    parser = PydanticOutputParser(pydantic_object=Strategy)
    system_prompt = Prompter(prompt_template="ask/entry", parser=parser).render(
        data={"question": state.get("message", HumanMessage(content=""))}
    )
    model = await provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("model_id"),
        "tools",
        max_tokens=2000,
        structured=dict(type="json"),
    )

    parts = []
    async for chunk in model.astream(system_prompt):
        content = getattr(chunk, "content", None)
        if not content:
            continue

        parts.append(content)
        yield {"content": content}
        
    raw = "".join(parts)
    cleaned = clean_thinking_content(raw)
    strategy = parser.parse(cleaned)
    # print(strategy)
    terms = [s.term.strip() for s in strategy.searches if s.term.strip()][:5]
    yield {"end_node": "plan_strategy", "strategy": strategy}


async def retrieve_context(state: ThreadState, config: RunnableConfig) -> dict:
    """Thực thi text+vector search theo search_terms và build context dict."""
    strategy = state.get("strategy")
    source_ids = state.get("source_ids")

    k = int(state.get("retrieval_limit") or 5)
    terms = [s.term.strip() for s in strategy.searches if s.term.strip()][:k]
    
    nb_id = state.get("notebook_id") or (state.get("notebook").id if state.get("notebook") else None)

    if not terms or not nb_id:
        return {"context": {}}

    # aggregated: list[dict] = []
    context_dict = {}
    for term in terms:
        param = {
            "keyword": term,
            "results": k,
            "source_ids": source_ids,
            "notebook_id":nb_id,
        }
        res = await vector_search_in_notebook(
            **param
        )
        context_dict.update(res)

    return {"context": context_dict}



async def chat_agent(state: ThreadState, config: RunnableConfig):
    """
    Node sinh câu trả lời và STREAM từng token ra ngoài.
    - GIỮ nguyên cách yield {"content": "..."} để router đang dùng 'on_chain_stream' nhận được.
    """
    thread_id = config.get("configurable", {}).get("thread_id")
    
    short_memory = get_postgres_short_memory(
        thread_id=thread_id,
        k=4,
    )
    
    search_results = await _memory_agent_milvus.search_long_term_memory(query=state.get("message", HumanMessage(content="")).content, top_k=4, thread_id=thread_id)
    chat_history = search_results + short_memory.buffer
    print("chat history:", chat_history)
    
    searches = state.get("strategy", {}).searches if state.get("strategy") else []
    first_search = searches[0] if searches else Search(term="default", instructions="")
    system_prompt = Prompter(prompt_template="ask/chat").render(
        data={
            "question": state.get("message", HumanMessage(content="")).content,
            "term": first_search.term,
            "instruction": first_search.instructions,
            "results": state.get("context"),
            "ids": state.get("context").keys(),
            "chat_history": chat_history
        }
    )

    model = await provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("model_id"),
        "chat",
        max_tokens=10000,
    )

    parts = []
    async for chunk in model.astream(system_prompt):
        content = getattr(chunk, "content", None)
        if not content:
            continue

        parts.append(content)
        yield {"content": content}

    raw = "".join(parts)
    print("last: ", raw)
    cleaned = clean_thinking_content(raw)
    await _memory_agent_milvus.upsert_long_term_memory(user_text=state.get("message", HumanMessage(content="")).content, ai_text=cleaned, thread_id=thread_id)
    short_memory.chat_memory.add_user_message(message=state.get("message"))
    short_memory.chat_memory.add_ai_message(message=AIMessage(content=cleaned))
    
    yield {"end_node": "chat_agent", "cleaned_content": cleaned}

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

async def build_ask_chat_graph(state: ThreadState, config: RunnableConfig) -> StateGraph:
    agent_state = StateGraph(ThreadState)
    agent_state.add_node("plan_strategy", plan_strategy)
    agent_state.add_node("retrieve_context", retrieve_context)
    agent_state.add_node("chat_agent", chat_agent)

    agent_state.add_edge(START, "plan_strategy")
    agent_state.add_edge("plan_strategy", "retrieve_context")
    agent_state.add_edge("retrieve_context", "chat_agent")
    agent_state.add_edge("chat_agent", END)
    checkpointer = await get_checkpointer()
    return agent_state.compile(checkpointer=checkpointer)

_conversation_graph = None

async def get_conversation_graph(state: ThreadState, config: RunnableConfig):
    global _conversation_graph
    if _conversation_graph is None:
        _conversation_graph = await build_ask_chat_graph(state, config)
    # print(f"Debug - _conversation_graph: {_conversation_graph}")
    return _conversation_graph
