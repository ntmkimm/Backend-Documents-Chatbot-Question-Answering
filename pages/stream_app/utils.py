import asyncio
import re
from datetime import datetime
from typing import List, Union

import nest_asyncio
import streamlit as st
from loguru import logger
from uuid import uuid4
nest_asyncio.apply()
from langchain_core.runnables import RunnableConfig
from open_notebook.database.migrate import MigrationManager
from open_notebook.domain.notebook import ChatSession, Notebook


def create_session_for_notebook(notebook_id: str, session_name: str = None):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"Chat Session {current_time}" if not session_name else session_name
    chat_session = ChatSession(title=title)
    asyncio.run(chat_session.save())
    asyncio.run(chat_session.relate_to_notebook(notebook_id))
    return chat_session


def convert_source_references(text):
    """
    Converts source references in brackets to markdown-style links.

    Matches patterns like [source_insight:id], [note:id], [source:id], or [source_embedding:id]
    and converts them to markdown links.

    Args:
        text (str): The input text containing source references

    Returns:
        str: Text with source references converted to markdown links

    Example:
        >>> text = "Here is a reference [source_insight:abc123]"
        >>> convert_source_references(text)
        'Here is a reference [source_insight:abc123](/?object_id=source_insight:abc123)'
    """

    # Pattern matches [type:id] where type can be source_insight, note, source, or source_embedding
    pattern = r"\[((?:source_insight|note|source|source_embedding):[\w\d]+)\]"

    def replace_match(match):
        """Helper function to create the markdown link"""
        source_ref = match.group(1)  # Gets the content inside brackets
        return f"[[{source_ref}]](/?object_id={source_ref})"

    # Replace all matches in the text
    converted_text = re.sub(pattern, replace_match, text)

    return converted_text
