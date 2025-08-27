
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

from open_notebook.graphs.utils import provision_langchain_model
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
    messages: Annotated[list, operator.add]
    notebook: Optional[Notebook]  
    notebook_id: Optional[str]
    context: Optional[Dict[str, str]]
    context_config: Optional[dict]

    # fields for strategy & retrieval
    question: str
    strategy: Strategy
    search_terms: List[str]
    retrieval_limit: int


async def plan_strategy(state: ThreadState, config: RunnableConfig) -> dict:
    """LLM tạo chiến lược và các search terms trước khi build context."""
    parser = PydanticOutputParser(pydantic_object=Strategy)
    system_prompt = Prompter(prompt_template="ask/entry", parser=parser).render(
        data={"question": state.get("question") or _last_user_text(state)}
    )
    model = await provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("model_id"),
        "tools",
        max_tokens=2000,
        structured=dict(type="json"),
    )
    raw = await model.ainvoke(system_prompt)
    cleaned = clean_thinking_content(getattr(raw, "content", "") or str(raw))
    strategy = parser.parse(cleaned)
    terms = [s.term.strip() for s in strategy.searches if s.term.strip()][:5]
    return {"strategy": strategy, "search_terms": terms}


async def retrieve_context(state: ThreadState, config: RunnableConfig) -> dict:
    """Thực thi text+vector search theo search_terms và build context dict."""
    terms: list[str] = state.get("search_terms", [])
    nb_id = state.get("notebook_id") or (state.get("notebook").id if state.get("notebook") else None)
    k = int(state.get("retrieval_limit") or 5)

    if not terms or not nb_id:
        return {"context": {}}

    aggregated: list[dict] = []

    for term in terms:
        text_res = await vector_search_in_notebook(
            notebook_id=nb_id, keyword=term, results=k, source=True, note=True, minimum_score=0.2
        )
        aggregated.extend(text_res[:k])

    # gộp & chọn top-k theo combined_score
    aggregated.sort(key=lambda x: -x["similarity"])
    top = []
    seen = set()
    for r in aggregated:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        top.append(r)
        if len(top) >= k:
            break

    context_dict: Dict[str, str] = {item["id"]: item["content"] for item in top if item.get("content")}
    return {"context": context_dict}


async def chat_agent(state: ThreadState, config: RunnableConfig):
    """
    Node sinh câu trả lời và STREAM từng token ra ngoài.
    - GIỮ nguyên cách yield {"content": "..."} để router đang dùng 'on_chain_stream' nhận được.
    """
    # Tạo system prompt cho chat
    system_prompt = Prompter(prompt_template="chat").render(data=state)
    payload = [SystemMessage(content=system_prompt)] + (state.get("messages") or [])

    model = await provision_langchain_model(
        str(payload),
        config.get("configurable", {}).get("model_id"),
        "chat",
        max_tokens=10000,
    )

    async for chunk in model.astream(payload):
        # STREAM token
        content = getattr(chunk, "content", None)
        if not content:
            continue

        yield {"content": content}


def _last_user_text(state: ThreadState) -> str:
    """Lấy nội dung message cuối cùng của user (nếu không truyền question)."""
    msgs = state.get("messages") or []
    for msg in reversed(msgs):
        # LangChain HumanMessage
        if isinstance(msg, HumanMessage):
            return msg.content or ""
        # dict-like
        if isinstance(msg, dict) and msg.get("type") == "human":
            return msg.get("content", "")
    return ""

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
