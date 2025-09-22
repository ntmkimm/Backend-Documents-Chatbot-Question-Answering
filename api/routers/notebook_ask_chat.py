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

from open_notebook.graphs.ask_chat import get_conversation_graph
from open_notebook.domain.notebook import hybrid_search_in_notebook, text_search_in_notebook

from open_notebook.utils import parse_thinking_content, token_count
from pages.stream_app.utils import convert_source_references

router = APIRouter()

from uuid import uuid4

@router.post("/notebooks/ask_chat")
async def send_message(chat_request: ChatRequest):
    try:
        # LẤY notebook & session như cũ
        current_notebook = await Notebook.get(chat_request.notebook_id)

        # Check valid of source_ids
        list_sources_in_nb = await current_notebook.get_sources()
        list_sources_in_nb = [source.id for source in list_sources_in_nb]
        if chat_request.source_ids:
            if not set(chat_request.source_ids).issubset(set(list_sources_in_nb)):
                raise Exception(
                    f"Invalid source_ids: {chat_request.source_ids}. They do not belong to notebook {chat_request.notebook_id}."
                )
        current_session, current_state = await get_session(current_notebook, chat_request.session_id)
        thread_id = current_session.id
        config = RunnableConfig(configurable={"thread_id": thread_id})

        graph = await get_conversation_graph(state={}, config=config)
        print("Request ids", chat_request.source_ids)
        input_payload = {
            "message": HumanMessage(content=chat_request.chat_message),
            "notebook_id": chat_request.notebook_id,
            "retrieval_limit": 5,
            "source_ids": chat_request.source_ids,  
        }

        data_end = {'event_type': StreamEvent.STREAM_END}
        async for event in graph.astream_events(input_payload, config):
                kind = event["event"]
                if kind == 'on_chain_stream':
                    chunk = event["data"]["chunk"]
                    
                    # check end_node
                    end_node = chunk.get("end_node", "")
                    if end_node == "plan_strategy":
                        data_end['strategy'] = chunk["strategy"].dict() 
                        await graph.aupdate_state(
                            config,
                            {"strategy": chunk["strategy"]}
                        )
                    elif end_node == "chat_agent":
                        reference_sources = await get_source_references(chunk["cleaned_content"])
                        data_end['reference'] = reference_sources
                        data_end['answer'] = chunk["cleaned_content"]
                        # await graph.aupdate_state(
                        #     config,
                        #     {"messages": [AIMessage(content=chunk["cleaned_content"])]}
                        # )

                elif kind == 'on_chain_start' and event['name'] == 'LangGraph':
                    data_end['session_id'] = event['metadata']['thread_id']
                 

        await current_session.save()

        return ChatResponse(
            ai_message=data_end['answer'],
            reference_sources=data_end['reference'],
            session_id=data_end['session_id'],
            notebook_id=chat_request.notebook_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat operation failed: {str(e)}")


@router.post("/notebooks/ask_chat/stream")
async def stream_chat(chat_request: ChatRequest):
    async def event_generator():
        try:
            current_notebook = await Notebook.get(chat_request.notebook_id)
            current_session, current_state = await get_session(current_notebook, chat_request.session_id)
            thread_id = current_session.id
            # Check valid of source_ids
            list_sources_in_nb = await current_notebook.get_sources()
            list_sources_in_nb = [source.id for source in list_sources_in_nb]
            if chat_request.source_ids:
                if not set(chat_request.source_ids).issubset(set(list_sources_in_nb)):
                    raise Exception(
                        f"Invalid source_ids: {chat_request.source_ids}. They do not belong to notebook {chat_request.notebook_id}."
                    )
            config = RunnableConfig(configurable={"thread_id": thread_id})
            graph = await get_conversation_graph(state={}, config=config)

            input_payload = {
                "message": HumanMessage(content=chat_request.chat_message),
                "notebook_id": chat_request.notebook_id,
                "retrieval_limit": 5,
                "source_ids": chat_request.source_ids,  
            }

            data_end = {'event_type': StreamEvent.STREAM_END}

            async for event in graph.astream_events(input_payload, config):
                kind = event["event"]
                # print(event, "\n\n")
                if kind == 'on_chain_stream':
                    chunk = event["data"]["chunk"]
                    
                    # check end_node
                    end_node = chunk.get("end_node", "")
                    if end_node == "plan_strategy":
                        data_end['strategy'] = chunk["strategy"].dict() 
                        await graph.aupdate_state(
                            config,
                            {"strategy": chunk["strategy"]}
                        )
                    elif end_node == "chat_agent":
                        reference_sources = await get_source_references(chunk["cleaned_content"])
                        data_end['reference'] = reference_sources
                        data_end['answer'] = chunk["cleaned_content"]
                        # await graph.aupdate_state(
                        #     config,
                        #     {"messages": [AIMessage(content=chunk["cleaned_content"])]}
                        # )
                        
                    if event['name'] == 'chat_agent':
                        text = chunk.get("content", "")
                        if text:
                            yield f"data: {json.dumps({'event_type': StreamEvent.TEXT_GENERATION, 'content': text, 'thinking': False})}\n\n"
                    
                    if event['name'] == 'plan_strategy':
                        text = chunk.get("content", "")
                        if text:
                            yield f"data: {json.dumps({'event_type': StreamEvent.TEXT_GENERATION, 'content': text, 'thinking': True})}\n\n"

                elif kind == 'on_chain_start' and event['name'] == 'LangGraph':
                    data = {'event_type': StreamEvent.STREAM_START, 'session_id': event['metadata']['thread_id']}
                    data_end['session_id'] = event['metadata']['thread_id']
                    yield f"data: {json.dumps(data)}\n\n"
                    
                elif kind == 'on_chain_start' and event['name'] == 'retrieve_context':
                    data = {'event_type': StreamEvent.TOOL_INPUT, 'content': "Building context by searching in notebook..."}
                    yield f"data: {json.dumps(data)}\n\n"
                    
                # else: 
                #     print(event, "\n\n")

            await current_session.save()
            yield f"data: {json.dumps(data_end)}\n\n"

        except Exception as e:
            logger.exception(f"Error in chat streaming: {str(e)}")
            error_data = {"type": "error", "message": "An error occurred during the chat stream."}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def create_session_for_notebook(notebook_id: str, session_id: str):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"Chat Session {current_time}" 
    chat_session = ChatSession(id=session_id, title=title, notebook_id=notebook_id)
    await chat_session.save(provided_id=True)
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

async def get_session(current_notebook: Notebook, session_id: str) -> Union[ChatSession, None]:
    """Get the current chat session for the notebook."""
    print("session_id : ", session_id)
    chat_session: Union[ChatSession, None] = None

    if session_id:
        try:
            chat_session = await ChatSession.get(session_id)
            print("chat session existed: ", session_id)
        except Exception as e:
            chat_session = await create_session_for_notebook(str(current_notebook.id), session_id=session_id)
            logger.warning(f"Could not fetch ChatSession {session_id}: {str(e)}")
    
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
