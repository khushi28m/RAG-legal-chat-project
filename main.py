# backend/app/main.py
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.agents import retrieval_agent  # retrieval only (safe import)

# logging
logger = logging.getLogger("rag_backend")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
logger.addHandler(handler)

app = FastAPI(title="RAG Legal Chat - Backend")

# CORS - limit to local dev sites; avoid wildcard * in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "RAG Legal Chat - Backend",
        "status": "running",
        "endpoints": ["/health", "/retrieve", "/chat"],
    }


class Message(BaseModel):
    role: Optional[str] = None
    text: str


class ChatMessage(BaseModel):
    session_id: Optional[str] = None
    messages: List[Message]
    mode: Optional[str] = "default"


@app.post("/retrieve")
async def retrieve(payload: Dict[str, Any]):
    q = payload.get("query") or ""
    try:
        k = int(payload.get("k", 5))
    except Exception:
        k = 5

    # clamp k to reasonable bounds
    k = max(1, min(k, 25))

    if not q:
        return {"results": []}

    try:
        results = retrieval_agent.retrieve(q, top_k=k)
        return {"results": results}
    except Exception as e:
        logger.exception("Retrieval failed for query=%s", q)
        # don't leak internal trace to client
        raise HTTPException(status_code=500, detail="Retrieval failed. See server logs for details.")


@app.post("/chat")
async def chat(payload: ChatMessage):
    """
    1) Run retrieval on the latest user message.
    2) Lazily import response_agent (so server can start even if LLM not configured).
    3) Attempt to generate RAG answer; on failure return retrieved docs + debug short info.
    """
    # validate payload
    if not payload.messages or len(payload.messages) == 0:
        raise HTTPException(status_code=400, detail="`messages` (non-empty list) is required")

    user_latest = payload.messages[-1].text.strip() if payload.messages else ""
    if not user_latest:
        raise HTTPException(status_code=400, detail="Latest message text is empty")

    # retrieve
    try:
        retrieved = retrieval_agent.retrieve(user_latest, top_k=4)
    except Exception as e:
        logger.exception("Retrieval error for chat: %s", e)
        raise HTTPException(status_code=500, detail="Retrieval error. See server logs.")

    # lazy import response agent to avoid startup failure if LLM not configured
    try:
        from app.agents import response_agent  # type: ignore
    except Exception as e:
        logger.warning("response_agent import failed: %s", e)
        # Return retrieval-only response, with brief debug message
        return {
            "reply": "LLM not configured or unavailable. Returning retrieved documents only.",
            "citations": [
                {
                    "source_id": r.get("source_id"),
                    "title": r.get("title"),
                    "chunk_index": r.get("chunk_index"),
                    "excerpt": r.get("excerpt")[:400],
                }
                for r in retrieved
            ],
            "debug": {"retrieved_count": len(retrieved), "llm_import_error": str(e)},
        }

    # generate answer with safe error handling
    try:
        rag_result = response_agent.generate_answer(user_latest, retrieved)
        # Ensure keys exist and normalize reply field
        reply_text = rag_result.get("answer") or rag_result.get("reply") or ""
        citations = rag_result.get("citations") or []
        debug = rag_result.get("debug") or {"retrieved_count": len(retrieved)}
        return {"reply": reply_text, "citations": citations, "debug": debug}
    except Exception as e:
        logger.exception("LLM generation failed: %s", e)
        return {
            "reply": "Error while generating answer. Returning retrieved documents and error info.",
            "citations": [
                {
                    "source_id": r.get("source_id"),
                    "title": r.get("title"),
                    "chunk_index": r.get("chunk_index"),
                    "excerpt": r.get("excerpt")[:400],
                }
                for r in retrieved
            ],
            "debug": {"retrieved_count": len(retrieved), "llm_error": str(e)},
        }
