# LegacyLens MVP

RAG pipeline for legacy COBOL codebases with:
- COBOL-aware chunking (PROCEDURE DIVISION paragraph boundaries + fallback windows)
- Embeddings (Voyage Code 2 or OpenAI fallback)
- Embeddings (Voyage Code 2, OpenAI, or built-in local hash fallback)
- Qdrant vector search
- Hybrid fallback search via `rg`
- Query answering with file/line citations
- CLI and FastAPI interfaces

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Environment

Set one embedding provider:

```bash
export VOYAGE_API_KEY=...
# or
export OPENAI_API_KEY=...
```

If no key is configured, LegacyLens uses a local hash-based embedding model so ingestion/query still runs for MVP demos.

Optional:

```bash
export QDRANT_URL=http://localhost:6333
export QDRANT_COLLECTION=legacylens_chunks
export CODEBASE_PATH=/absolute/path/to/cobol/repo
```

## Run Qdrant

```bash
docker run -p 6333:6333 qdrant/qdrant
```

## CLI

```bash
python -m legacylens ingest --codebase /path/to/cobol
python -m legacylens query "where is file IO handled?" --codebase /path/to/cobol
```

## API

```bash
uvicorn legacylens.api:app --reload
```

Then:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "content-type: application/json" \
  -d '{"query":"what paragraphs call LIBCALC?","codebase_path":"/path/to/cobol"}'
```

## Tests

```bash
pytest -q
```
