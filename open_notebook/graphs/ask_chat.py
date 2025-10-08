
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
from open_notebook.config import DB_URI, connection_kwargs, POOL_TIMEOUT, POOL_SIZE

from langchain.chains import ConversationalRetrievalChain
from open_notebook.graphs.utils import (
    provision_langchain_model, 
    _memory_agent_milvus,
    get_postgres_short_memory,
)

from open_notebook.domain.notebook import (
    hybrid_search_in_notebook,
    Notebook,
)
from open_notebook.utils import clean_thinking_content 
from langchain_core.output_parsers.pydantic import PydanticOutputParser

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import OperationalError
import asyncio

async def run_in_thread(func, *args, **kwargs):
    sem = asyncio.Semaphore(10)  # limit concurrency (adjust as needed)
    async with sem:  # ensure only N run at the same time
        return await asyncio.to_thread(func, *args, **kwargs)
    
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
    
    reflection: Optional[Reflection]
    ai_message: Optional[str]
    
    retry: int = 0
    
class Reflection(BaseModel):
    need_more: bool = Field(..., description="Whether we should try another search turn")
    reasons: str = Field(..., description="Short rationale")


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
    params_list = [
        {
            "keyword": term,
            "results": k,
            "source_ids": [str(sid) for sid in source_ids] if source_ids else [],
            "notebook_id": str(nb_id),
        }
        for term in terms
    ]

    # Launch all searches concurrently
    tasks = [hybrid_search_in_notebook(**param) for param in params_list]
    results_list = await asyncio.gather(*tasks)
    
    # Merge all results into one dict
    context_dict = {}
    for res in results_list:
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
    
    searches = state.get("strategy", {}).searches if state.get("strategy") else []
    retry = state.get("retry", 0)
    context = state.get("context", {})
    search = searches[retry] if searches else Search(term="default", instructions="")
    
    system_prompt = Prompter(prompt_template="ask/chat").render(
        data={
            "question": state.get("message", HumanMessage(content="")).content,
            "term": search.term,
            "instruction": search.instructions,
            "results": context if context else {},
            "ids": context.keys() if context else [],
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

    cleaned = clean_thinking_content(raw)
    # await _memory_agent_milvus.upsert_long_term_memory(user_text=state.get("message", HumanMessage(content="")).content, ai_text=cleaned, thread_id=thread_id)
    # short_memory.chat_memory.add_user_message(message=state.get("message"))
    # short_memory.chat_memory.add_ai_message(message=AIMessage(content=cleaned))
    
    yield {"end_node": "chat_agent", "cleaned_content": cleaned}
    
async def reflect_answer(state: ThreadState, config: RunnableConfig) -> dict:
    """
    Reflection by LLM
    """
    ai_answer = state.get("cleaned_content", "")
    
    context = state.get("context", {})
    
    parser = PydanticOutputParser(pydantic_object=Reflection)

    system_prompt = Prompter(prompt_template="ask/reflect", parser=parser).render(
        data={
            "question": state.get("message", HumanMessage(content="")).content,
            "results": context if context else [],
            "ids": context.keys() if context else {},
            "chat_history": [],
            "answer": ai_answer
        }
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
        print(content)
        yield {"content": content}
    
    raw = "".join(parts)
    cleaned = clean_thinking_content(raw)
    reflection = parser.parse(cleaned)
    print("reflection: ", reflection)
    
    yield {"end_node": "reflect_answer", "reflection": reflection}

def route_after_reflection(state: ThreadState) -> str:
    max_tries = 5

    retry = int(state.get("retry", 0))
    need_more = state.get("reflection").need_more

    # only retry if reflection wants more AND we still have unused searches
    if need_more and (retry + 1) < max_tries:
        return "retry"
    return "done"

async def inc_retry(state: ThreadState, config: RunnableConfig) -> dict:
    return {"retry": int(state.get("retry", 0)) + 1}

_checkpointer: Optional[AsyncPostgresSaver] = None
_pool: Optional[AsyncConnectionPool] = None  # Optional global to keep the pool alive

async def get_checkpointer(retries: int = 3, delay: int = 2) -> AsyncPostgresSaver:
    """
    Tạo hoặc lấy checkpointer, retry nếu connection fail.
    :param retries: số lần thử lại
    :param delay: thời gian chờ giữa các lần thử
    """
    global _checkpointer, _pool

    for attempt in range(retries):
        try:
            if _checkpointer is None:
                _pool = AsyncConnectionPool(
                    DB_URI,
                    min_size=1,
                    max_size=POOL_SIZE,
                    kwargs=connection_kwargs,
                    timeout=POOL_TIMEOUT,
                )
                checkpointer = AsyncPostgresSaver(_pool)
                await checkpointer.setup()
                _checkpointer = checkpointer
            return _checkpointer

        except OperationalError as e:
            print(f"[get_checkpointer] OperationalError: {e}. Attempt {attempt+1}/{retries}")
            _checkpointer = None
            _pool = None
            if attempt < retries - 1:
                await asyncio.sleep(delay)
            else:
                raise  # ném lỗi ra ngoài nếu retry thất bại

async def build_ask_chat_graph(state: ThreadState, config: RunnableConfig) -> StateGraph:
    agent_state = StateGraph(ThreadState)
    agent_state.add_node("plan_strategy", plan_strategy)
    agent_state.add_node("retrieve_context", retrieve_context)
    agent_state.add_node("chat_agent", chat_agent)

    # NEW nodes
    agent_state.add_node("reflect_answer", reflect_answer)
    agent_state.add_node("inc_retry", inc_retry)

    # Flow: plan -> retrieve -> chat -> reflect -> (retry -> inc_retry -> plan) / (done -> END)
    agent_state.add_edge(START, "plan_strategy")
    agent_state.add_edge("plan_strategy", "retrieve_context")
    agent_state.add_edge("retrieve_context", "chat_agent")

    # after chat, run reflection
    agent_state.add_edge("chat_agent", "reflect_answer")

    # conditional routing with the retry guard
    agent_state.add_conditional_edges(
        "reflect_answer",
        route_after_reflection,
        {
            "retry": "inc_retry",
            "done": END,
        },
    )
    # if retrying, bump retry then go back to chat_agent
    agent_state.add_edge("inc_retry", "plan_strategy")

    checkpointer = await get_checkpointer()
    return agent_state.compile(checkpointer=checkpointer)

_conversation_graph = None

async def get_conversation_graph(state: ThreadState, config: RunnableConfig):
    global _conversation_graph
    if _conversation_graph is None:
        _conversation_graph = await build_ask_chat_graph(state, config)
    # print(f"Debug - _conversation_graph: {_conversation_graph}")
    return _conversation_graph
