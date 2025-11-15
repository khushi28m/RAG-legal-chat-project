# backend/app/services/vector_client.py
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Conditional imports for FAISS and SBERT
try:
    import faiss
except Exception:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except Exception:
    TfidfVectorizer = None

import numpy as np


class VectorClient:
    """
    VectorClient backed by FAISS + SentenceTransformers.
    """

    def __init__(
        self,
        index_dir: str = "data/faiss_test",
        model_name: str = "all-MiniLM-L6-v2",
        model: Optional[object] = None,
        use_chroma_fallback: bool = False,
    ):
        self.index_dir = Path(index_dir)
        self.index_file = self.index_dir / "index.faiss"
        self.meta_file = self.index_dir / "metadata.json"
        self.model_name = model_name
        self.use_chroma_fallback = use_chroma_fallback

        if not self.index_file.exists() or not self.meta_file.exists():
            raise FileNotFoundError(
                f"Index or metadata not found in {self.index_dir}. "
                f"Expected {self.index_file} and {self.meta_file}"
            )

        if faiss is None:
            if use_chroma_fallback:
                raise RuntimeError(
                    "FAISS not available on this platform — Chroma fallback not implemented in this file."
                )
            raise RuntimeError(
                "faiss not available. On Windows, pip install may fail. Use conda or install faiss-cpu, "
                "or enable a Chroma fallback. See README for platform-specific instructions."
            )

        # Load metadata (must be a list keyed by vector index)
        with open(self.meta_file, "r", encoding="utf-8") as fh:
            self.metadata = json.load(fh)
        if not isinstance(self.metadata, list):
            logger.warning("metadata.json is not a list. Expecting list indexed by vector id.")
        logger.info("Loaded %d metadata entries", len(self.metadata))

        # Load FAISS index
        logger.info("Loading FAISS index from %s", self.index_file)
        try:
            self.index = faiss.read_index(str(self.index_file))
        except Exception as e:
            raise RuntimeError(f"Failed to load FAISS index: {e}") from e

        # Embedding model: prefer provided model -> SentenceTransformer -> TF-IDF fallback
        if model is not None:
            self.model = model
            self._embedder_mode = "injected"
            logger.info("Using injected embedding model")
        elif SentenceTransformer is not None:
            try:
                logger.info("Loading sentence-transformers model: %s", model_name)
                # load model (may download to HF cache)
                self.model = SentenceTransformer(model_name)
                self._embedder_mode = "sbert"
            except Exception as e:
                logger.warning("Failed to load SentenceTransformer('%s'): %s", model_name, e)
                # fallback to TF-IDF if available
                if TfidfVectorizer is not None:
                    logger.info("Falling back to TF-IDF embedder (for testing only).")
                    self._init_tfidf()
                else:
                    raise RuntimeError(
                        "Failed to load sentence-transformers model and TF-IDF fallback not available."
                    ) from e
        else:
            # No sentence-transformers installed
            if TfidfVectorizer is not None:
                logger.info("sentence-transformers not installed; using TF-IDF fallback for embeddings.")
                self._init_tfidf()
            else:
                raise RuntimeError(
                    "sentence-transformers not installed and TF-IDF fallback not available. "
                    "Install sentence-transformers and a compatible torch, or install scikit-learn for fallback."
                )

    def _init_tfidf(self):
        # Initialize TF-IDF vectorizer. We'll build a small corpus from metadata texts
        self._embedder_mode = "tfidf"
        texts = []
        for m in self.metadata:
            t = m.get("text") if isinstance(m, dict) else ""
            texts.append(t or "")
        # create vectorizer with limited features to keep memory low
        self._tfidf = TfidfVectorizer(max_features=1024)
        if len(texts) == 0:
            # avoid fit on empty
            self._tfidf.fit([""])
        else:
            self._tfidf.fit(texts)
        logger.info("TF-IDF fallback initialized with %d features", len(self._tfidf.get_feature_names_out()))

    def _encode(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts to numpy float32 vectors using the selected embedder.
        Returns shape (n, dim) float32.
        """
        if getattr(self, "_embedder_mode", None) == "sbert":
            # Try a couple of common parameter names to be robust against library versions
            for kwargs in ({"convert_to_numpy": True}, {"return_numpy": True}, {"convert_to_tensor": False}):
                try:
                    emb = self.model.encode(texts, **kwargs)
                    arr = np.asarray(emb, dtype="float32")
                    return arr
                except TypeError:
                    continue
            # last resort
            emb = self.model.encode(texts)
            return np.asarray(emb, dtype="float32")
        elif getattr(self, "_embedder_mode", None) == "tfidf":
            mat = self._tfidf.transform(texts).toarray().astype("float32")
            # normalize rows
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            mat = mat / norms
            return mat
        elif getattr(self, "_embedder_mode", None) == "injected":
            # user-provided model must implement encode(list[str]) -> numpy
            emb = self.model.encode(texts)
            return np.asarray(emb, dtype="float32")
        else:
            raise RuntimeError("Unknown embedder mode")

    def embed_query(self, text: str) -> np.ndarray:
        """
        Return a float32 numpy vector for the query, normalized for cosine similarity.
        Shape: (1, dim)
        """
        v = self._encode([text])
        v = v.astype("float32")
        # normalize for cosine/inner-product search (if index was built with normalized vectors)
        try:
            faiss.normalize_L2(v)
        except Exception:
            logger.debug("faiss.normalize_L2 failed; continuing without explicit normalization")
        return v

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search the index and return up to k results with metadata.
        """
        qv = self.embed_query(query)
        if k <= 0:
            k = 1
        try:
            D, I = self.index.search(qv, k)
        except Exception as e:
            raise RuntimeError(f"FAISS search failed: {e}") from e

        results: List[Dict[str, Any]] = []
        for score, idx in zip(D[0], I[0]):
            if idx is None or int(idx) < 0:
                continue
            idx = int(idx)
            if idx >= len(self.metadata):
                logger.warning(
                    "FAISS returned index %d but metadata has %d entries; skipping", idx, len(self.metadata)
                )
                continue
            meta = self.metadata[idx]
            results.append(
                {
                    "score": float(score),
                    "id": meta.get("id"),
                    "source_id": meta.get("source_id"),
                    "title": meta.get("title"),
                    "excerpt": (meta.get("text") or "")[:800],
                    "path": meta.get("path"),
                    "chunk_index": meta.get("chunk_index"),
                }
            )
        return results