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
from open_notebook.domain.notebook import vector_search_in_notebook, text_search_in_notebook

from open_notebook.utils import parse_thinking_content, token_count
from pages.stream_app.utils import convert_source_references

router = APIRouter()

from uuid import uuid4

@router.post("/notebooks/chat")
async def send_message(chat_request: ChatRequest):
    """Send a message to a notebook and get a complete response."""
    try:
        context = None
            
        async for obj in build_context(
            notebook_id=chat_request.notebook_id,
            keyword=chat_request.chat_message,
            limit=5,
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
            "message": HumanMessage(content=chat_request.chat_message),
            "context": context
        }
        
        data_end = {
            'event_type': StreamEvent.STREAM_END, 
        }

        async for event in graph.astream_events(input_payload, config):
            kind = event["event"]
            if kind == "on_chain_stream":
                chunk = event["data"]["chunk"]
                
                end_node = chunk.get("end_node", "")
                if end_node == "chat_agent":
                    reference_sources = await get_source_references(chunk["cleaned_content"])
                    data_end['reference_sources'] = reference_sources
                    data_end['ai_message'] = chunk["cleaned_content"]
                    # await graph.aupdate_state(
                    #     config,
                    #     {"messages": [AIMessage(content=chunk["cleaned_content"])]}
                    # )
                          
            elif kind == 'on_chain_start':
                data_end['session_id'] = event['metadata']['thread_id']
        
        await current_session.save()      

        return ChatResponse(
            ai_message=data_end['ai_message'],
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
                keyword=chat_request.chat_message,
                limit=5,
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
                "message": HumanMessage(content=chat_request.chat_message),
                "context": context
            }
            
            data_end = {
                'event_type': StreamEvent.STREAM_END, 
            }
            
            async for event in graph.astream_events(input_payload, config):
                kind = event["event"]
                if kind == "on_chain_stream":
                    chunk = event["data"]["chunk"]
                    
                    end_node = chunk.get("end_node", "")
                    if end_node == "chat_agent":
                        reference_sources = await get_source_references(chunk["cleaned_content"])
                        data_end['reference'] = reference_sources
                        data_end['answer'] = chunk["cleaned_content"]
                        # await graph.aupdate_state(
                        #     config,
                        #     {"messages": [AIMessage(content=chunk["cleaned_content"])]}
                        # )
                    
                    if event['name'] == "chat_agent":
                        text = chunk.get("content", "")
                        if text:
                            yield f"data: {json.dumps({'event_type': StreamEvent.TEXT_GENERATION, 'content': text, 'thinking': False})}\n\n"
                
                elif kind == 'on_chain_start' and event['name'] == 'LangGraph':
                    data = {'event_type': StreamEvent.STREAM_START, 'session_id': event['metadata']['thread_id']}
                    data_end['session_id'] = event['metadata']['thread_id']
                    yield f"data: {json.dumps(data)}\n\n"

            
            await current_session.save()      
            yield f"data: {json.dumps(data_end)}\n\n"

        except Exception as e:
            logger.exception(f"Error in chat streaming: {str(e)}")
            error_data = {"type": "error", "message": "An error occurred during the chat stream."}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def build_context(notebook_id: str, keyword: str, limit=5):
    """Build context for the notebook."""

    context_data = await vector_search_in_notebook(
        notebook_id=notebook_id,
        keyword=keyword,
        results=limit,
        source=True,
        note=True,
        minimum_score=0.2
    )
    final_context = {}
    for item in context_data:
        final_context[item["id"]] = item["content"]
        
    yield final_context

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
    if session_id and 'chat_session:' not in session_id:
        session_id = 'chat_session:' + session_id

    chat_session: Union[ChatSession, None] = None
    sessions: List[ChatSession] = []  # Define sessions early

    if session_id:
        try:
            chat_session = await ChatSession.get(session_id)
        except Exception as e:
            logger.warning(f"Could not fetch ChatSession {session_id}: {str(e)}")
    
    if not chat_session:
        try:
            chat_session = await create_session_for_notebook(current_notebook.id, None)
            sessions = await current_notebook.get_chat_sessions()
            if sessions:
                logger.debug(f"Multiple sessions found: {len(sessions)}. Using the last updated session.")
                chat_session = sessions[0]
        except Exception as e:
            logger.warning(f"Could not fetch chat sessions for notebook {current_notebook.id}: {str(e)}")

        logger.debug("Creating new chat session")
    else:
        # Don't use `sessions` here -just log the current session
        logger.debug(f"Using existing session: {chat_session.id}")

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
    pattern = r"\[((?:source_insight|note|source_embedding|source):[\w\d]+)\]"
    matches = re.findall(pattern, text or "")
    return list(set(matches))
