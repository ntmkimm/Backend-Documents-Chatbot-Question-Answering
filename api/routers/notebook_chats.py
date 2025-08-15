from fastapi import APIRouter, HTTPException
from langchain_core.runnables import RunnableConfig
from fastapi.responses import StreamingResponse
from typing import List, Union, AsyncGenerator, Dict, Optional, Tuple
from datetime import datetime
from loguru import logger
import asyncio
import re
import json
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk

from api.models import ErrorResponse, StreamEvent
from open_notebook.exceptions import DatabaseOperationError
from open_notebook.domain.notebook import ChatSession, Notebook, Source
from api.context_service import context_service
from api.models import ChatRequest, ChatResponse

from open_notebook.graphs.chat import get_conversation_graph

from open_notebook.utils import parse_thinking_content, token_count
from pages.stream_app.utils import convert_source_references

router = APIRouter()

async def token_stream(text: str):
    for token in text:
        yield f"{token}"
        # await asyncio.sleep(0.02)

from uuid import uuid4
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

def _content(msg) -> str:
    if hasattr(msg, "content"):
        return msg.content or ""
    if isinstance(msg, tuple) and len(msg) >= 2:
        return str(msg[1] or "")
    if isinstance(msg, dict) and "content" in msg:
        return str(msg["content"] or "")
    return str(msg or "")

# def _chunk_text(chunk) -> str:

#     if hasattr(chunk, "content"):
#         return chunk.content or ""
  
#     if isinstance(chunk, dict):
#         if "content" in chunk and chunk["content"]:
#             return chunk["content"]
#         if "messages" in chunk and chunk["messages"]:
#             last = chunk["messages"][-1]
#             return _content(last)
#     return ""

def _chunk_text(chunk) -> str:
    # Trường hợp model stream trả về AIMessageChunk
    if isinstance(chunk, AIMessageChunk):
        return ""
    if hasattr(chunk, "content"):
        return getattr(chunk, "content", "") or ""

    # Trường hợp LangGraph trả dict {"messages": [AIMessageChunk(...)]}
    if isinstance(chunk, dict):
        if "content" in chunk and chunk["content"]:
            return str(chunk["content"])
        if "messages" in chunk and chunk["messages"]:
            return _content(chunk["messages"][-1])

    # Chuỗi/bytes
    if isinstance(chunk, (str, bytes)):
        return chunk.decode() if isinstance(chunk, bytes) else chunk

    return ""


@router.post("/notebooks/chat")
async def send_message(chat_request: ChatRequest):
    """Send a message to a notebook and get a complete response."""
    try:
        context = None
            
        async for obj in build_context(
            notebook_id=chat_request.notebook_id,
            source_ids=chat_request.source_ids or []
        ):
            context = obj

        if context is None:
            error_data = {"type": "error", "message": f"No context found for notebook {chat_request.notebook_id}"}
            return
        
        current_notebook = await Notebook.get(chat_request.notebook_id)
        current_session, current_state = await get_session(current_notebook, chat_request.session_id)
        thread_id = current_session.id
        
        config = RunnableConfig(configurable={"thread_id": thread_id})

        graph = await get_conversation_graph(state={}, config=config)

        input_payload = {
            "messages": [HumanMessage(content=chat_request.chat_message)],
            "context": context
        }
        
        data_end = {
            'event_type': StreamEvent.STREAM_END, 
        }
        parts = []
        async for event in graph.astream_events(input_payload, config):
            kind = event["event"]

            if kind == "on_chain_stream":
                chunk = event["data"]["chunk"]

                text = _chunk_text(chunk)
                parts.append(text)
            
            elif kind == 'on_chain_start':
                data_end['session_id'] = event['metadata']['thread_id']
                
        final_messages = "".join(parts)
        ai_text = _content(final_messages)
        _, cleaned_content = parse_thinking_content(ai_text)
        data_end['final_messages'] = cleaned_content
        reference_sources = await get_source_references(cleaned_content)
        data_end['reference_sources'] = reference_sources
        
        await current_session.save()      

        return ChatResponse(
            ai_message=data_end['final_messages'],
            reference_sources=data_end['reference_sources'],
            session_id=data_end['session_id'],
            notebook_id=chat_request.notebook_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat operation failed: {str(e)}")


@router.post("/notebooks/chat/stream")
async def stream_chat(chat_request: ChatRequest):

    async def event_generator():
        try:
            context = None
            
            async for obj in build_context(
                notebook_id=chat_request.notebook_id,
                source_ids=chat_request.source_ids or []
            ):
                context = obj

            if context is None:
                error_data = {"type": "error", "message": f"No context found for notebook {chat_request.notebook_id}"}
                yield f"data: {json.dumps(error_data)}\n\n"
                return
            
            current_notebook = await Notebook.get(chat_request.notebook_id)
            current_session, current_state = await get_session(current_notebook, chat_request.session_id)
            thread_id = current_session.id
            
            config = RunnableConfig(configurable={"thread_id": thread_id})

            graph = await get_conversation_graph(state={}, config=config)

            input_payload = {
                "messages": [HumanMessage(content=chat_request.chat_message)],
                "context": context
            }
            
            data_end = {
                'event_type': StreamEvent.STREAM_END, 
            }
            parts = []
            start = False
            async for event in graph.astream_events(input_payload, config):
                kind = event["event"]
                # print(kind)
                # if kind in ("on_chat_model_stream", "on_chain_stream"):
                if kind == 'on_chain_stream':
                    chunk = event["data"]["chunk"]
                    # print(event)
                    text = _chunk_text(chunk)
                    parts.append(text)
                    if text:
                        yield f"data: {json.dumps({'event_type': StreamEvent.TEXT_GENERATION, 'content': text, 'thinking': False})}\n\n"
                
                elif not start and kind == 'on_chain_start':
                    data = {'event_type': StreamEvent.STREAM_START, 'session_id': event['metadata']['thread_id']}
                    data_end['session_id'] = event['metadata']['thread_id']
                    yield f"data: {json.dumps(data)}\n\n"
                    start = True
                    
            final_messages = "".join(parts)
            ai_text = _content(final_messages)
            _, cleaned_content = parse_thinking_content(ai_text)
            data_end['answer'] = cleaned_content
            reference_sources = await get_source_references(cleaned_content)
            data_end['reference'] = reference_sources
            
            await current_session.save()      
            yield f"data: {json.dumps(data_end)}\n\n"

        except Exception as e:
            logger.exception(f"Error in chat streaming: {str(e)}")
            error_data = {"type": "error", "message": "An error occurred during the chat stream."}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def build_context(notebook_id: str, source_ids: List[str] = []):
    """Build context for the notebook."""
    notebook: Notebook = await Notebook.get(notebook_id)

    context_config = {"sources": {}, "notes": {}}
    sources = await notebook.get_sources()
    for source in sources:
        context_config["sources"][source.id] = "full content"

    context_data = {"note": [], "source": []}

    if len(source_ids) > 0 and not any(source_id in context_config['sources'].keys() for source_id in source_ids):
        yield None

    for source_id, status in context_config['sources'].items():
        if len(source_ids) > 0 and source_id not in source_ids:
            continue
        if "not in" in status:
            continue

        try:
            full_source_id = source_id if source_id.startswith("source:") else f"source:{source_id}"
            try:
                source = await Source.get(full_source_id)
            except Exception:
                continue

            if "insights" in status:
                source_context = await source.get_context(context_size="short")
                context_data["source"].append(source_context)
            elif "full content" in status:
                source_context = await source.get_context(context_size="long")
                context_data["source"].append(source_context)

        except Exception as e:
            logger.warning(f"Error processing source {source_id}: {str(e)}")
            continue

    yield context_data

async def create_session_for_notebook(notebook_id: str, session_name: str = None):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"Chat Session {current_time}" if not session_name else session_name
    chat_session = ChatSession(title=title)
    await chat_session.save()
    await chat_session.relate_to_notebook(notebook_id)
    return chat_session

async def _get_graph_state(graph, thread_id: str):
    """
    Try async state first; fall back to sync get_state for compatibility.
    """
    try:
        snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    except AttributeError:
        snap = graph.get_state({"configurable": {"thread_id": thread_id}})
    return getattr(snap, "values", {}) if snap else {}

async def get_session(current_notebook: Notebook, session_id) -> Union[ChatSession, None]:
    """Get the current chat session for the notebook."""
    if session_id and 'chat_session:' not in session_id: session_id = 'chat_session:' + session_id
    chat_session: Union[ChatSession, None] = None
    if session_id:
        try:
            chat_session = await ChatSession.get(session_id)
        except Exception as e:
            # Log the error but continue
            logger.warning(f"Could not fetch ChatSession {session_id}: {str(e)}")
    
    if not chat_session:
        sessions: List[ChatSession] = []
        try:
            chat_session = await create_session_for_notebook(current_notebook.id, None)
            sessions = await  current_notebook.get_chat_sessions()
            logger.debug(f"Multiple sessions found: {len(sessions)}. Using the last updated session.")
            chat_session = sessions[0]
        except Exception as e:
            logger.warning(f"Could not fetch chat sessions for notebook {current_notebook.id}: {str(e)}")

        logger.debug("Creating new chat session")
    else:
        logger.debug(f"Multiple sessions found: {len(sessions)}. Using the last updated session.")
        chat_session = sessions[0]
    if not chat_session or chat_session.id is None:
        raise ValueError("Problem acquiring chat session")
    thread_id = session_id or f"thread-{uuid4().hex}"

    config = RunnableConfig(configurable={"thread_id": thread_id})
    graph = await get_conversation_graph(state={}, config=config)

    current_state = await _get_graph_state(graph, thread_id)
    return chat_session, current_state  


async def get_source_references(text: str):
    """
    Extract [source_insight:...], [note:...], [source:...], [source_embedding:...] IDs.
    """
    pattern = r"\[((?:source_insight|note|source|source_embedding):[\w\d]+)\]"
    matches = re.findall(pattern, text or "")
    return list(set(matches))
