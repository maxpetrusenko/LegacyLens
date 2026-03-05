# Setup Guide

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Required Env Vars
- `OPENAI_API_KEY` for embeddings + answer generation
- `QDRANT_URL` (default `http://localhost:6333`)
- `QDRANT_COLLECTION` (default `legacylens_chunks`)

Optional:
- `QDRANT_API_KEY`
- `OPENAI_EMBED_MODEL` (`text-embedding-3-small` or `text-embedding-3-large`)
- `QDRANT_TIMEOUT`, `SEMANTIC_TIMEOUT`, `EMBEDDING_TIMEOUT`, `LLM_TIMEOUT`
- `LANGCHAIN_API_KEY` for LangSmith tracing
- `LANGSMITH_WORKSPACE_ID` only if you must target a non-default workspace
- `OBSERVABILITY_ENABLED` (default `true`) and `OBSERVABILITY_PROJECT` (default `LegacyLens`)

## Local Run

```bash
docker run -p 6333:6333 qdrant/qdrant
uvicorn legacylens.api:app --reload
```

## Ingest + Query

```bash
python -m legacylens ingest --codebase data
curl -X POST http://127.0.0.1:8000/query -H "content-type: application/json" -d '{"query":"Where is file I/O handled?"}'
```

## Test Gate

```bash
pytest -q
python scripts/validate_corpus.py --codebase data
python scripts/validate_traceability.py
```
