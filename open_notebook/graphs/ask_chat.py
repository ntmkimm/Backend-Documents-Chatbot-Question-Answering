
# open_notebook/graphs/ask_chat.py
from __future__ import annotations
import json
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

from langchain.memory import ConversationBufferWindowMemory
from open_notebook.graphs.utils import (
    provision_langchain_model, 
    _memory_agent_milvus,
    get_postgres_short_memory,
)

from open_notebook.domain.notebook import (
    hybrid_search_in_notebook,
    Notebook,
)
from open_notebook.utils import clean_thinking_content, time_node
from langchain_core.output_parsers.pydantic import PydanticOutputParser

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import OperationalError
import asyncio

async def run_in_thread(func, *args, **kwargs):
    sem = asyncio.Semaphore(10)  # limit concurrency (adjust as needed)
    async with sem:  # ensure only N run at the same time
        return await asyncio.to_thread(func, *args, **kwargs)

class RerankItem(BaseModel):
    id: str = Field(..., description="ID của chunk")
    score: float = Field(..., description="Điểm liên quan, từ 0 đến 10")

class RerankResult(BaseModel):
    items: List[RerankItem]

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
    strategy: Optional[Strategy]
    retrieval_limit: int = 5
    chat_history: Optional[List] = []
    
    reflection: Optional[Reflection]
    ai_message: Optional[str]
    
    retry: int = 0
    
class Reflection(BaseModel):
    need_more: bool = Field(..., description="Whether we should try another search turn")
    reasons: str = Field(..., description="Short rationale")

@time_node
async def retrieve_chat_history(state: ThreadState, config: RunnableConfig):
    """
    Node lấy chat history
    """
    thread_id = config.get("configurable", {}).get("thread_id")
    
    short_memory = get_postgres_short_memory(
        thread_id=thread_id,
        k=4,
    )
    
    search_results = await _memory_agent_milvus.search_long_term_memory(query=state.get("message", HumanMessage(content="")).content, top_k=4, thread_id=thread_id)
    chat_history = search_results + short_memory.buffer
    return {"chat_history": chat_history}

@time_node
async def plan_strategy(state: ThreadState, config: RunnableConfig) -> dict:
    """LLM tạo chiến lược và các search terms trước khi build context."""
    print("retry: ", state.get("retry", 0))
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
    yield {"end_node": "plan_strategy", "strategy": strategy}

@time_node
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
            "return_score": True,
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


    chunks_text = "\n\n".join(
        [f"ID: {cid}\nCONTENT: {data['content']}" for cid, data in context_dict.items()]
    )
    system_prompt = Prompter(prompt_template="ask/rerank").render(
        data={"question": state.get("message", HumanMessage(content="")),
              "chunks": chunks_text}
    )
    model = await provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("model_id"),
        "tools",
        max_tokens=2000,
        structured=RerankResult,
    )
    messages = [SystemMessage(content=system_prompt)]
    result = await model.ainvoke(messages)
    ranked_context_str = ""
    ranked_ids = []
    try:
        raw_output = result.content.strip("` \n")  
        parsed = json.loads(raw_output)
        rerank_result = RerankResult(items=[RerankItem(**item) for item in parsed])
    except Exception  as e:
        rerank_result = None

    if rerank_result:
        scored_chunks = []

        for item in rerank_result.items:
            chunk_id = item.id
            score_rerank = item.score / 10  # đưa về 0–1
            score_retrieve = context_dict.get(chunk_id, {}).get("score", 0.0)

            final_score = 0.6 * score_retrieve + 0.4 * score_rerank

            scored_chunks.append({
                "id": chunk_id,
                "final_score": final_score
            })

        # Sắp xếp giảm dần theo final_score
        scored_chunks.sort(key=lambda x: x["final_score"], reverse=True)

    else:
        # === Case 2: Không có rerank, fallback theo score gốc ===
        scored_chunks = [
            {"id": cid, "final_score": data.get("score", 0.0)}
            for cid, data in context_dict.items()
        ]
        scored_chunks.sort(key=lambda x: x["final_score"], reverse=True)


    # === Build ranked string and id list ===
    for rank, item in enumerate(scored_chunks, start=1):
        cid = item["id"]
        content = context_dict.get(cid, {}).get("content", "").strip()
        ranked_ids.append(cid)
        ranked_context_str += f"{rank}. [ID: {cid}] {content}\n\n"

    return {
        "context": {
            "id": ranked_ids,
            "content": ranked_context_str.strip()
        }
    }


@time_node
async def chat_agent(state: ThreadState, config: RunnableConfig):
    """
    Node sinh câu trả lời và STREAM từng token ra ngoài.
    - GIỮ nguyên cách yield {"content": "..."} để router đang dùng 'on_chain_stream' nhận được.
    """
    chat_history = state.get("chat_history")
    
    searches = state.get("strategy", {}).searches if state.get("strategy") else []
    context = state.get("context", {})
    search = searches[0] if searches else Search(term="default", instructions="")
    strategy = state.get("strategy", {})
    # print("context", context)
    system_prompt = Prompter(prompt_template="ask/chat").render(
        data={
            "question": state.get("message", HumanMessage(content="")).content,
            "term": search.term,
            "instruction": strategy.reasoning,
            "results": context["content"] if context else {},
            "ids": context["id"] if context else [],
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
    # update memory if done
    
    message = state.get("message", HumanMessage(content=""))
    thread_id = config.get("configurable", {}).get("thread_id")
    short_memory = get_postgres_short_memory(
        thread_id=thread_id,
        k=4,
    )
    await _memory_agent_milvus.upsert_long_term_memory(user_text=message.content, ai_text=cleaned, thread_id=thread_id)
    short_memory.chat_memory.add_user_message(message=message)
    short_memory.chat_memory.add_ai_message(message=cleaned)
    
    yield {"end_node": "chat_agent", "ai_message": cleaned}
    
@time_node
async def reflect_answer(state: ThreadState, config: RunnableConfig) -> dict:
    """
    Reflection by LLM
    """
    context = state.get("context", {})
    searches = state.get("strategy", {}).searches if state.get("strategy") else []
    search = searches[0] if searches else Search(term="default", instructions="")
    strategy = state.get("strategy", {})
    
    parser = PydanticOutputParser(pydantic_object=Reflection)

    system_prompt = Prompter(prompt_template="ask/reflect", parser=parser).render(
        data={
            "question": state.get("message", HumanMessage(content="")).content,
            "results": context if context else [],
            "ids": context.keys() if context else {},
            "term": search.term,
            "instruction": strategy.reasoning,
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
        yield {"content": content}
    
    raw = "".join(parts)
    cleaned = clean_thinking_content(raw)
    reflection = parser.parse(cleaned)
    
    yield {"end_node": "reflect_answer", "reflection": reflection}

async def route_after_reflection(state: ThreadState, config: RunnableConfig) -> str:
    max_tries = 3
    
    retry = int(state.get("retry", 0))
    need_more = state.get("reflection").need_more

    # print(state)
    
    # only retry if reflection wants more AND we still have unused searches
    if need_more and (retry + 1) < max_tries:
        return "retry"
    return "done"

async def inc_retry(state: ThreadState, config: RunnableConfig) -> dict:
    return {"retry": int(state.get("retry", 0)) + 1}

_checkpointer: Optional[AsyncPostgresSaver] = None
_pool: Optional[AsyncConnectionPool] = None  

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
    agent_state.add_node("retrieve_chat_history", retrieve_chat_history)
    agent_state.add_node("plan_strategy", plan_strategy)
    agent_state.add_node("retrieve_context", retrieve_context)
    agent_state.add_node("chat_agent", chat_agent)
    agent_state.add_node("reflect_answer", reflect_answer)
    agent_state.add_node("inc_retry", inc_retry)

    # Flow:
    agent_state.add_edge(START, "retrieve_chat_history")
    agent_state.add_edge("retrieve_chat_history", "plan_strategy")
    
    # after build strategy, check whether we need to retrieve 
    agent_state.add_conditional_edges(
        "plan_strategy",
        lambda state: "chat_agent" if not state["strategy"].searches else "retrieve_context"
    )
    # after retrieval, run reflection
    agent_state.add_edge("retrieve_context", "reflect_answer")

    # conditional routing with the retry guard
    
    agent_state.add_conditional_edges(
        "reflect_answer",
        route_after_reflection,
        {
            "retry": "inc_retry",
            "done": "chat_agent",
        },
    )
    # if retrying, bump retry then go back to chat_agent
    agent_state.add_edge("inc_retry", "plan_strategy")
    # if not retrying, bump to chat agent -> end
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
