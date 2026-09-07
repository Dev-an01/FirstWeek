# RAG-Builder

A small, framework-light document retrieval pipeline.

## About
RAG-Builder is a terminal-based exploration of retrieval-augmented generation. Its README describes PDF text extraction, recursive splitting, chunk creation, embeddings stored in CSV, retrieval and response generation without a high-level RAG framework or vector database.

## Technology stack

Python, Sentence Transformers, PyTorch, CSV.

## Architecture and mechanics
Python service modules separate PDF/text processing, chunk preparation, embedding and retrieval. The inspected embedding code uses the Sentence Transformers `all-mpnet-base-v2` model. `services/retrieve.py` embeds a query, uses `util.dot_score` against stored embeddings, and selects top results using `torch.topk`.

## A useful documentation distinction
The README calls retrieval cosine similarity, while the inspected code calls dot-product scoring. Dot product only matches cosine similarity when both inputs are normalized. This document does not assume normalization without verifying the complete ingestion path.

## Where to start
Follow `main.py`, `create_embeddings.py`, `services/embed_model.py`, and `services/retrieve.py`. The `llm/` directory contains local and API response paths. The README explains adding PDF input and configuring the chosen inference path.

## Current limitations
This is a local educational pipeline, not evidence of multi-tenant access control, managed ingestion or a production service. Model loading occurs at module import in the inspected retrieval implementation. No embeddings, PDFs, credentials or API keys were copied into FirstWeek.

## Ownership
Current maintenance and component owners are not recorded in the reviewed evidence.

## Architecture flow
An educational local pipeline. The inspected retriever uses dot-product scoring; normalization was not established by this review.

- PDF input → Text chunks: extract + split.
- Text chunks → Embedding CSV: embed + save.
- User question → Top-k retrieval: query vector.
- Embedding CSV → Top-k retrieval: stored vectors.
- Top-k retrieval → Response generation: retrieved context.

## Evidence
- `RAG-Builder/README.md`
- `RAG-Builder/services/retrieve.py`
- `RAG-Builder/services/embed_model.py`
- `RAG-Builder/main.py`
