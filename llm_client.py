# backend/app/services/llm_client.py
import os
import time
import traceback
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from dotenv import load_dotenv
try:
    backend_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=backend_env)
except Exception:
    load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    from google import genai  # type: ignore
    from google.genai import types # Import types for Configuration
except Exception:
    genai = None
    types = None

try:
    import openai  # type: ignore
except Exception:
    openai = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class LLMClient:
    """
    Unified LLM client configured for RAG.
    """
    def __init__(self, model: str = "gemini-2.5-flash", prefer: str = "gemini"):
        # FIX: Using the confirmed stable model ID
        self.model = model 
        self.prefer = (prefer or "gemini").lower()
        self.backend: Optional[str] = None
        self._gclient = None
        
        self.can_gemini = (genai is not None and types is not None and GEMINI_API_KEY is not None)
        self.can_openai = (openai is not None and OPENAI_API_KEY is not None)

        if self.can_gemini:
            try:
                self._gclient = genai.Client(api_key=GEMINI_API_KEY)
                self.backend = "gemini"
            except Exception as e:
                logger.warning("Failed to configure Gemini SDK: %s", e)
                self.can_gemini = False
                self._gclient = None
                self.backend = None

        if not self.backend:
            if self.can_openai and self.prefer == "openai":
                openai.api_key = OPENAI_API_KEY
                self.backend = "openai"
            elif self.can_gemini:
                self.backend = "gemini"
            else:
                raise RuntimeError(
                    "No LLM backend configured. Set GEMINI_API_KEY or OPENAI_API_KEY in .env."
                )

    def _extract_system_and_user_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Separates system instruction and user prompt for structured API calls."""
        system_instruction = ""
        user_prompt = ""

        for m in messages:
            role = (m.get("role") or "user").lower()
            content = m.get("content") or m.get("text") or ""
            if role == "system":
                system_instruction = content
            elif role == "user":
                user_prompt = content 
        
        if not user_prompt:
            raise ValueError("User prompt not found in messages list.")
            
        return {"system_instruction": system_instruction, "user_prompt": user_prompt}

    def _extract_text_from_genai_response(self, resp: Any) -> str:
        """Robustly extracts text from the Gemini response object."""
        try:
            return resp.text
        except Exception:
            try:
                return str(resp)
            except Exception:
                return ""

    def chat_completion(self, messages: List[Dict[str, Any]], temperature: float = 0.0, max_tokens: int = 512) -> str:
        last_exc = None

        for attempt in range(3):
            try:
                if self.backend == "gemini":
                    
                    parts = self._extract_system_and_user_messages(messages)
                    system_instruction = parts["system_instruction"]
                    prompt = parts["user_prompt"]

                    if self._gclient is None:
                        self._gclient = genai.Client(api_key=GEMINI_API_KEY)

                    # FIX: Build configuration using types and necessary parameters
                    config_kwargs = {
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    }
                    if system_instruction:
                        config_kwargs["system_instruction"] = system_instruction
                            
                    config = types.GenerateContentConfig(**config_kwargs)
                    contents = [prompt] 
                    resp = None
                    models_obj = getattr(self._gclient, "models", None)
                        
                    if models_obj and hasattr(models_obj, "generate_content"):
                        resp = models_obj.generate_content(model=self.model, contents=contents, config=config)
                    elif hasattr(self._gclient, "generate_content"):
                        resp = self._gclient.generate_content(model=self.model, contents=contents, config=config)
                    
                    if resp is None:
                        raise AttributeError("No supported genai client method found on this SDK build.")
                        
                    text = self._extract_text_from_genai_response(resp)
                    return text

                elif self.backend == "openai":
                    # Basic OpenAI handling for older clients (like v0.28.0 found in logs)
                    resp = openai.ChatCompletion.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    return resp["choices"][0]["message"]["content"]

                else:
                    raise RuntimeError("No LLM backend available")

            except Exception as e:
                last_exc = e
                logger.warning("LLM client call failed attempt %d: %s", attempt + 1, e)
                time.sleep(2 ** attempt)
                continue

        tb = "".join(traceback.format_exception_only(type(last_exc), last_exc))
        raise RuntimeError(f"LLM call failed after retries: {tb}")