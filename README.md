RAG Legal Chat – AI-Powered Legal Assistant

This project implements a Retrieval-Augmented Generation (RAG) system that answers legal queries using actual statutory text and other reference documents. The system retrieves the most relevant text chunks from the indexed legal corpus and generates concise, citation-grounded responses using an LLM (Gemini by default, OpenAI as optional fallback).

Features
1. Legal Document Processing

Accepts PDF and text files.

Cleans, normalizes, and chunks long documents (default: 1200 characters with 200 overlap).

Stores chunks as .jsonl with metadata (source_id, chunk_index, title, full text).

2. Vector Embeddings and Semantic Search

Uses SentenceTransformers (all-MiniLM-L6-v2) to create embeddings.

Uses FAISS (IndexFlatIP) for fast semantic search.

Returns top-k relevant chunks with metadata required for RAG.

3. RAG Answer Generation

Uses a unified LLM client supporting:

Gemini models (primary)

OpenAI models (fallback if configured)

Produces:

A short, plain-language answer

Clear citations in the format: source_id:chunk_index

No hallucinated content (strict grounding in retrieved text)

4. Backend (FastAPI)

Endpoints:

GET /health – status check

POST /retrieve – semantic document search

POST /chat – full RAG pipeline (retrieval + LLM answer)

5. Frontend (React + Vite)

Chat-style UI

Shows conversation history

Handles streaming or standard responses

Easy to deploy on Vercel / Netlify

6. Deployment-Ready

Backend deployable to Render, Railway, or any cloud

Frontend deployable to Vercel or Netlify

Environment-variable driven configuration
