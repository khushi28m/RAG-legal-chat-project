# backend/app/agents/retrieval_agent.py
from typing import List, Dict, Any
from app.services.vector_client import VectorClient
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_client = None


def get_client():
    """
    Lazily create and cache the VectorClient.
    """
    global _client

    if _client is not None:
        return _client

    try:
        logger.info("Initializing VectorClient...")
        _client = VectorClient(
            index_dir="data/faiss_test",
            model_name="all-MiniLM-L6-v2",
            use_chroma_fallback=False
        )
        logger.info("VectorClient loaded successfully.")
    except Exception as e:
        logger.error("Failed to initialize VectorClient: %s", e)
        raise RuntimeError(
            f"VectorClient failed to load.\n"
            f"Check your FAISS index + metadata and ensure sentence-transformers or TF-IDF fallback works.\n"
            f"Error: {e}"
        )

    return _client


def retrieve(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Run vector search and format the results for downstream RAG.
    """
    try:
        client = get_client()
    except Exception as e:
        logger.error("Could not get VectorClient: %s", e)
        return [{
            "score": 0,
            "source_id": None,
            "title": "ERROR",
            "excerpt": f"VectorClient initialization failed: {e}",
            "path": None,
            "chunk_index": None
        }]

    try:
        results = client.search(query, k=top_k)
    except Exception as e:
        logger.error("Vector search failed: %s", e)
        return [{
            "score": 0,
            "source_id": None,
            "title": "ERROR",
            "excerpt": f"Vector search failed: {e}",
            "path": None,
            "chunk_index": None
        }]

    out: List[Dict[str, Any]] = []
    for r in results:
        out.append({
            "score": r.get("score"),
            "source_id": r.get("source_id"),
            "title": r.get("title"),
            "excerpt": r.get("excerpt"),
            "path": r.get("path"),
            "chunk_index": r.get("chunk_index"),
        })

    return out