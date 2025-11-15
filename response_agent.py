# backend/app/agents/response_agent.py

from typing import List, Dict, Any
import traceback
import logging
import re
import html

from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# LLM model
llm = LLMClient(model="gemini-2.5-flash", prefer="gemini")


def _clean_reply_text(s: str) -> str:
    """
    Clean and normalize LLM output text.
    Removes mojibake like 'â', but KEEP spaces!
    """
    if s is None:
        return ""

    # Fix quotes
    try:
        s = s.replace("\\u0027", "'").replace("\\u2019", "'")
    except:
        pass

    # HTML unescape
    try:
        s = html.unescape(s)
    except:
        pass

    # IMPORTANT FIX: Remove ONLY mojibake, DO NOT REMOVE SPACES!
    s = s.replace("â", "")

    # Normal whitespace cleanup
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s.strip()


def _fallback_summary(user_question: str, retrieved: List[Dict[str, Any]]) -> str:
    """
    Fallback answer using retrieved text if LLM fails.
    """
    if not retrieved:
        return "No supporting documents were found to answer the question."

    pieces = []
    for r in retrieved[:3]:
        txt = r.get("excerpt", "") or ""
        first_sent = txt.split(".")

        if first_sent and first_sent[0].strip():
            pieces.append(first_sent[0].strip() + ".")
        else:
            pieces.append(txt[:160].strip())

    summary = " ".join(pieces).strip()
    return f"(Fallback summary from retrieved documents) {summary}" if summary else "No usable text in retrieved documents."


def build_prompt(user_question: str, retrieved: List[Dict[str, Any]]) -> str:
    intro = (
        "You are a legal assistant. Answer the user's question ONLY using the provided source excerpts. "
        "Provide a short, plain-language answer (2–6 sentences). "
        "Then list citations referencing source_id and chunk_index. "
        "If the answer is not in the sources, say so and do not hallucinate."
    )

    docs_section = "SOURCE EXCERPTS:\n"
    for i, r in enumerate(retrieved, start=1):
        docs_section += (
            f"[{i}] source_id={r.get('source_id')} "
            f"chunk_index={r.get('chunk_index')} "
            f"title={r.get('title')}\n"
            f"{r.get('excerpt')}\n\n"
        )

    user_section = f"QUESTION:\n{user_question}\n\n"

    instructions = (
        "RESPONSE FORMAT:\n"
        "1) Short answer in plain language.\n"
        "2) CITATIONS:\n"
        "   source_id:chunk_index — <short supporting quote>\n"
        "Begin your answer below:"
    )

    return f"{intro}\n\n{docs_section}{user_section}{instructions}"


def generate_answer(user_question: str, retrieved: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a RAG-based answer from LLMClient.
    Returns both `reply` and `answer` for frontend compatibility.
    """

    prompt = build_prompt(user_question, retrieved)

    system_msg = {"role": "system", "content": "You are a precise legal assistant. Cite sources exactly."}
    user_msg = {"role": "user", "content": prompt}

    try:
        resp_text = llm.chat_completion(
            [system_msg, user_msg],
            temperature=0.1,
            max_tokens=2048
        )

        cleaned_text = _clean_reply_text(resp_text)

        if not cleaned_text:
            raise RuntimeError("LLM returned empty text.")

        return {
            "reply": cleaned_text,
            "answer": cleaned_text,
            "citations": [
                {
                    "source_id": r.get("source_id"),
                    "chunk_index": r.get("chunk_index"),
                    "title": r.get("title")
                }
                for r in retrieved
            ],
            "debug": {"retrieved_count": len(retrieved)}
        }

    except Exception as exc:
        tb = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        logger.exception("LLM generation failed: %s", exc)

        fallback = _fallback_summary(user_question, retrieved)

        return {
            "reply": f"LLM failed to produce an answer. {fallback}",
            "answer": f"LLM failed to produce an answer. {fallback}",
            "citations": [
                {
                    "source_id": r.get("source_id"),
                    "chunk_index": r.get("chunk_index"),
                    "title": r.get("title")
                }
                for r in retrieved
            ],
            "debug": {"retrieved_count": len(retrieved), "llm_error": tb}
        }