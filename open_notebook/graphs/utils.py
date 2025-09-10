from esperanto import LanguageModel
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from open_notebook.domain.models import model_manager
from open_notebook.utils import token_count


async def provision_langchain_model(
    content, model_id, default_type, **kwargs
) -> BaseChatModel:
    """
    Returns the best model to use based on the context size and on whether there is a specific model being requested in Config.
    If context > 105_000, returns the large_context_model
    If model_id is specified in Config, returns that model
    Otherwise, returns the default model for the given type
    """
    # tokens = token_count(content)

    # if tokens > 105_000:
    #     logger.debug(
    #         f"Using large context model because the content has {tokens} tokens"
    #     )
    #     model = await model_manager.get_default_model("large_context", **kwargs)
    # elif model_id:
    #     model = await model_manager.get_model(model_id, **kwargs)
    # else:
        
    model = await model_manager.get_default_model(default_type, **kwargs)

    logger.debug(f"Using model: {model}")
    assert isinstance(model, LanguageModel), f"Model is not a LanguageModel: {model}"
    return model.to_langchain()


def normalize_relevance_scores(text_results):
    """Normalize text search relevance scores to [0, 1] range"""
    if not text_results: return None
    scores = [r["relevance"] for r in text_results]
    min_score = min(scores)
    max_score = max(scores)
    range_score = max_score - min_score if max_score > min_score else 1e-5

    for r in text_results:
        r["relevance_normalized"] = (r["relevance"] - min_score) / range_score
    return text_results


def combine_results(text_results, vector_results, alpha_text=0.2, alpha_vector=0.8):
    text_results = normalize_relevance_scores(text_results)

    text_map = {r["id"]: r for r in (text_results or []) if r and "id" in r}
    vector_map = {r["id"]: r for r in (vector_results or []) if r and "id" in r}


    all_ids = set(text_map) | set(vector_map)
    combined = []

    for rid in all_ids:
        text = text_map.get(rid)
        vector = vector_map.get(rid)

        # Base fields
        item = {
            "id": rid,
            "title": text["title"] if text else vector.get("title", ""),
            "content": text["content"] if text else vector.get("content", ""),
            "parent_id": text["parent_id"] if text else vector.get("parent_id", ""),
        }

        # Scores
        text_score = text["relevance_normalized"] if text else 0
        vector_score = vector["similarity"] if vector else 0

        # Weighted score
        combined_score = text_score * alpha_text + vector_score * alpha_vector
        item["combined_score"] = combined_score

        # Optional: keep original scores too
        item["similarity"] = vector_score
        item["relevance_normalized"] = text_score

        combined.append(item)

    # Sort by combined score descending
    combined.sort(key=lambda x: -x["combined_score"])
    return combined

import os
from dotenv import load_dotenv
load_dotenv()

MILVUS_ADDRESS = os.getenv("MILVUS_ADDRESS", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_URI = os.getenv("MILVUS_URI", f"http://{MILVUS_ADDRESS}:{MILVUS_PORT}")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "agent_memory1")

from datetime import datetime
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import PostgresChatMessageHistory
from langchain.schema import Document

embeddings = OpenAIEmbeddings(model=os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"))
vectorstore = Milvus(
    connection_args={
        "uri": MILVUS_URI,
    },
    collection_name=MILVUS_COLLECTION,
    embedding_function=embeddings,
    index_params={
        "metric_type": "COSINE",
        "index_type": "HNSW",
        "params": {
            "M": 16,
            "efConstruction": 200
        }
    },
)

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "notebook")
POSTGRES_ADDRESS = os.getenv("POSTGRES_ADDRESS", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")

DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_ADDRESS}:{POSTGRES_PORT}/{POSTGRES_DB}"

def get_postgres_short_memory(thread_id: str, k: int = 4) -> ConversationBufferWindowMemory:
    return ConversationBufferWindowMemory(
        k=k,
        memory_key="chat_history",
        return_messages=True,
        chat_memory=PostgresChatMessageHistory(
            connection_string=DB_URI,
            session_id=thread_id,
            table_name="lc_message_history"
        )
    )

def upsert_long_term_memory(user_text: str, ai_text: str, thread_id: str):
    """Gộp 1 lượt chat thành 1 chunk và lưu vào Milvus."""
    ts = datetime.utcnow().isoformat()
    text = f"[Turn @ {ts} UTC]\nUser({thread_id}): {user_text}\nAssistant: {ai_text}"
    doc = Document(
        page_content=text,
        metadata={"thread_id": thread_id, "ts": ts, "type": "chat_turn"}
    )
    vectorstore.add_documents([doc])