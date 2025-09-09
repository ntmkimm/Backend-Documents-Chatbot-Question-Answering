
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
    combine_results,
    upsert_long_term_memory,
    vectorstore,
    short_memory
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
    print(strategy)
    terms = [s.term.strip() for s in strategy.searches if s.term.strip()][:5]
    yield {"end_node": "plan_strategy", "strategy": strategy}


async def retrieve_context(state: ThreadState, config: RunnableConfig) -> dict:
    """Thực thi text+vector search theo search_terms và build context dict."""
    strategy = state.get("strategy")
    k = int(state.get("retrieval_limit") or 5)
    terms = [s.term.strip() for s in strategy.searches if s.term.strip()][:k]
    
    nb_id = state.get("notebook_id") or (state.get("notebook").id if state.get("notebook") else None)

    if not terms or not nb_id:
        return {"context": {}}

    aggregated: list[dict] = []

    for term in terms:
        vector_results = await vector_search_in_notebook(
            notebook_id=nb_id, keyword=term, results=k, source=True, note=True, minimum_score=0.2
        )
        text_results = await text_search_in_notebook(
            notebook_id=nb_id, keyword=term, results=k, source=True, note=True
        )
        results = combine_results(
            text_results=text_results, 
            vector_results=vector_results, 
            alpha_text=0.2, 
            alpha_vector=0.8
        )
        aggregated.extend(results[:k])

    # gộp & chọn top-k theo combined_score
    aggregated.sort(key=lambda x: -x["combined_score"])
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
    system_prompt = Prompter(prompt_template="ask/query_process").render(
        data={
            "question": state.get("message", HumanMessage(content="")),
            "term": state.get("strategy").searches[0].term,
            "instruction": state.get("strategy").searches[0].instructions,
            "results": state.get("context"),
            "ids": state.get("context").keys(),
        }
    )
    payload = [SystemMessage(content=system_prompt)] 
    thread_id = config.get("configurable", {}).get("thread_id")

    model = await provision_langchain_model(
        str(payload),
        config.get("configurable", {}).get("model_id"),
        "chat",
        max_tokens=10000,
    )
    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 4,
            "expr": f"thread_id == '{thread_id}'"  # đảm bảo chỉ lấy memory của đúng user
        }
    )
    
    qa = ConversationalRetrievalChain.from_llm(
        llm=model,
        retriever=retriever,   
        memory=short_memory,  
        verbose=False,
    )
    raw = ""

    async for msg in qa.astream_events({"question": str(payload)}):
        if msg.get("event", "") == 'on_chat_model_stream':
            yield { "content": msg.get("data", {}).get("chunk").content }
        elif msg.get("event", "") == 'on_chat_model_end':
            raw = msg.get("data", {}).get("output").content
        else:
            print("chunk: ", msg)

    cleaned = clean_thinking_content(raw)
    upsert_long_term_memory(user_text=state.get("message", HumanMessage(content="")).content, ai_text=cleaned, thread_id=thread_id)
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
