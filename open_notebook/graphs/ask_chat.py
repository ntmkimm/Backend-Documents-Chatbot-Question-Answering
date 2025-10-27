
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

from open_notebook.graphs.utils import (
    provision_langchain_model, 
    _memory_agent_milvus,
    get_postgres_short_memory,
    get_checkpointer
)

from open_notebook.domain.notebook import (
    hybrid_search_in_notebook,
    Notebook,
)
from open_notebook.utils import clean_thinking_content, time_node
from langchain_core.output_parsers.pydantic import PydanticOutputParser

import asyncio
from loguru import logger
from httpcore import RemoteProtocolError
import httpx 

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
    chat_history: Optional[Dict] = {}
    
    reflection: Optional[Reflection]
    ai_message: Optional[str]
    
    retry: int = 0
    
class Reflection(BaseModel):
    need_more: bool = Field(..., description="Whether we should try another search turn")
    reasons: str = Field(..., description="Short rationale")
    
async def safe_stream(model, prompt, parts: list):
    """
    An toàn khi stream từ model.astream(prompt):
    - Không vỡ graph nếu upstream (OpenAI, Ollama, v.v.) ngắt stream.
    - Ghi log và yield partial output nếu có thể.
    """
    try:
        async for chunk in model.astream(prompt):
            content = getattr(chunk, "content", None)
            if not content:
                continue
            parts.append(content)
            yield {"content": content}

    except (httpx.RemoteProtocolError, RemoteProtocolError) as e:
        logger.warning(f"[safe_stream] RemoteProtocolError: {e}")
        if parts:
            yield {"content": "\n[⚠️ Stream ended early — partial output]"}
    except asyncio.CancelledError:
        logger.info("[safe_stream] Cancelled")
        raise
    except Exception as e:
        logger.error(f"[safe_stream] Unexpected error: {e}", exc_info=True)
        if parts:
            yield {"content": "\n[⚠️ Stream interrupted — partial output]"}
        else:
            raise

@time_node
async def retrieve_chat_history(state: ThreadState, config: RunnableConfig):
    """
    Node lấy chat history — chạy blocking DB trong thread để tránh block event loop.
    """
    thread_id = config.get("configurable", {}).get("thread_id")

    short_memory = get_postgres_short_memory(thread_id=thread_id, k=4)

    # đọc buffer trong thread để tránh blocking psycopg
    short_buffer = await asyncio.to_thread(lambda: short_memory.buffer)

    # Milvus search
    search_results = await _memory_agent_milvus.search_long_term_memory(
        query=state.get("message", HumanMessage(content="")).content,
        top_k=4,
        thread_id=thread_id
    )

    chat_history = {
        "short_memory": short_buffer,
        "long_memory": search_results
    }
    return {"chat_history": chat_history}

@time_node
async def plan_strategy(state: ThreadState, config: RunnableConfig) -> dict:
    """LLM tạo chiến lược và các search terms trước khi build context."""
    print("retry: ", state.get("retry", 0))
    parser = PydanticOutputParser(pydantic_object=Strategy)
    system_prompt = Prompter(prompt_template="ask/entry", parser=parser).render(
        data={
            "question": state.get("message", HumanMessage(content="")),
            "short_memory": state.get("chat_history", {}).get("short_memory", [])
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
    async for chunk in safe_stream(model, system_prompt, parts):
        yield chunk
        
    raw = "".join(parts)
    cleaned = clean_thinking_content(raw)
    cleaned = cleaned.replace("```json", "").replace("```", "")
    try:
        parsed = json.loads(cleaned)
        strategy = Strategy(**parsed)
    except Exception as e:
        logger.error(f"Parse Strategy failed: {e}\nRaw={cleaned}")
        # fallback an empty Strategy to continue graph
        strategy = Strategy(reasoning=f"Phương hướng tìm kiếm cho câu hỏi chưa hợp lệ, cần kiểm tra lại.", searches=[])
        
    # print(strategy)
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

    return { "context": context_dict }

@time_node
async def chat_agent(state: ThreadState, config: RunnableConfig):
    """
    Node sinh câu trả lời và STREAM từng token ra ngoài.
    """
    chat_history = state.get("chat_history", {})
    searches = state.get("strategy", {}).searches if state.get("strategy") else []
    context = state.get("context", {})
    if state.get("reflection") and state.get("reflection").need_more:
        context = {}

    search = searches[0] if searches else Search(term="default", instructions="")
    strategy = state.get("strategy", {})

    system_prompt = Prompter(prompt_template="ask/chat").render(
        data={
            "question": state.get("message", HumanMessage(content="")).content,
            "term": search.term,
            "instruction": strategy.reasoning,
            "results": context if context else {},
            "ids": list(context.keys()) if context else [],
            "short_memory": chat_history.get("short_memory", []),
            "long_memory": chat_history.get("long_memory", []),
        }
    )

    model = await provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("model_id"),
        "chat",
        max_tokens=10000,
    )

    parts = []

    async for chunk in safe_stream(model, system_prompt, parts):
        yield chunk

    raw = "".join(parts)
    cleaned = clean_thinking_content(raw)

    message = state.get("message", HumanMessage(content=""))
    thread_id = config.get("configurable", {}).get("thread_id")
    short_memory = get_postgres_short_memory(thread_id=thread_id, k=4)

    # Milvus upsert (blocking) -> chạy trong thread
    await _memory_agent_milvus.upsert_long_term_memory(
        user_text=message.content,
        ai_text=cleaned,
        thread_id=thread_id,
    )

    # Ghi vào Postgres short memory (blocking -> thread)
    await asyncio.to_thread(short_memory.chat_memory.add_user_message, message)
    ai_msg = AIMessage(content=cleaned)
    await asyncio.to_thread(short_memory.chat_memory.add_ai_message, ai_msg)

    yield {"end_node": "chat_agent", "ai_message": cleaned}
    
    
@time_node
async def reflect_answer(state: ThreadState, config: RunnableConfig) -> dict:
    """
    Reflection by LLM, có try/except để tránh vỡ stream.
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
            "ids": list(context.keys()) if context else [],
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
    async for chunk in safe_stream(model, system_prompt, parts):
        yield chunk

    raw = "".join(parts)
    cleaned = clean_thinking_content(raw)
    cleaned = cleaned.replace("```json", "").replace("```", "")
    
    try:
        parsed = json.loads(cleaned)
        reflection = Reflection(**parsed)
    except Exception as e:
        logger.error(f"Parse Reflection failed: {e}\nRaw={cleaned}")
        # fallback an empty Reflection để tiếp tục pipeline
        reflection = Reflection(need_more=True, reasons="Không thể parse phản hồi hợp lệ")

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

_agent_state = None

async def get_conversation_graph(state: ThreadState, config: RunnableConfig) -> StateGraph:
    global _agent_state
    if _agent_state is None:
        _agent_state = StateGraph(ThreadState)
        _agent_state.add_node("retrieve_chat_history", retrieve_chat_history)
        _agent_state.add_node("plan_strategy", plan_strategy)
        _agent_state.add_node("retrieve_context", retrieve_context)
        _agent_state.add_node("chat_agent", chat_agent)
        _agent_state.add_node("reflect_answer", reflect_answer)
        _agent_state.add_node("inc_retry", inc_retry)

        # Flow:
        _agent_state.add_edge(START, "retrieve_chat_history")
        _agent_state.add_edge("retrieve_chat_history", "plan_strategy")
        
        # after build strategy, check whether we need to retrieve 
        _agent_state.add_conditional_edges(
            "plan_strategy",
            lambda state: "chat_agent" if not state["strategy"].searches else "retrieve_context"
        )
        # after retrieval, run reflection
        _agent_state.add_edge("retrieve_context", "reflect_answer")

        # conditional routing with the retry guard
        
        _agent_state.add_conditional_edges(
            "reflect_answer",
            route_after_reflection,
            {
                "retry": "inc_retry",
                "done": "chat_agent",
            },
        )
        # if retrying, bump retry then go back to chat_agent
        _agent_state.add_edge("inc_retry", "plan_strategy")
        # if not retrying, bump to chat agent -> end
        _agent_state.add_edge("chat_agent", END)

    checkpointer = await get_checkpointer()
    return _agent_state.compile(checkpointer=checkpointer)

