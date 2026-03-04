# LegacyLens MVP

RAG pipeline for legacy COBOL codebases with:
- COBOL-aware chunking (PROCEDURE DIVISION paragraph boundaries + fallback windows)
- Embeddings (Voyage Code 2 or OpenAI)
- Qdrant vector search
- Hybrid fallback search via `rg`
- Query embedding cache (in-process LRU)
- Dependency graph generation (`PERFORM`/`CALL`) for caller lookup
- Precision@k evaluation harness with per-query logs
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

Optional:

```bash
export QDRANT_URL=http://localhost:6333
export QDRANT_COLLECTION=legacylens_chunks_dev
export CODEBASE_PATH=/absolute/path/to/cobol/repo
```

If `QDRANT_URL` points to an unreachable host, `/query` will fail with `503` and a retrieval error cause.

Use different collections per environment when sharing one Qdrant instance:
- `legacylens_chunks_dev` for local/dev
- `legacylens_chunks_prod` for production

## Run Qdrant

```bash
docker run -p 6333:6333 qdrant/qdrant
```

## CLI

```bash
python -m legacylens ingest --codebase /path/to/cobol
python -m legacylens query "where is file IO handled?" --codebase /path/to/cobol
python -m legacylens callers READ-FILE --codebase /path/to/cobol
python -m legacylens eval --dataset eval/ground_truth.jsonl --codebase /path/to/cobol --k 5 --out eval/results.jsonl
```

## API

```bash
uvicorn legacylens.api:app --reload
```

Then:

```bash
open http://127.0.0.1:8000/

curl -X POST http://127.0.0.1:8000/query \
  -H "content-type: application/json" \
  -d '{"query":"what paragraphs call LIBCALC?","codebase_path":"/path/to/cobol"}'

curl http://127.0.0.1:8000/callers/READ-FILE?codebase_path=/path/to/cobol
```

## Evaluation Dataset Format

Each line in the JSONL dataset should be:

```json
{"query":"where is file I/O handled?","relevant_files":["tests/testsuite.src/numeric-dump.cob"]}
```

or with exact citations:

```json
{"query":"where is STOP RUN used?","relevant_citations":["[tests/testsuite.src/numeric-dump.cob:455-455]"]}
```

## Web Console UI

The LegacyLens console provides visual parity with the CLI for interactive demos and live exploration:

- Dataset strip: Horizontal selector for indexed codebases with current dataset label
- KPI chips: Top-level metrics (Retrieved, Latency, Top Score, Files) updated per-query
- Source cards: Expandable code snippets with score bars, citation tags, Copy button
- Dependency graph: Cytoscape-powered caller/callee visualization with legend (PERFORM/CALL/Unknown) and node/edge counters
- Analytics panel: Five charts (Similarity Distribution, Division Breakdown, Chunk Type Mix, Hit Distribution, Score Bands)
- Query log: Session history with timestamps (max 50 entries, newest first)

Keyboard shortcuts:
- `/` focus query input
- `Enter` run query

## Tests

```bash
pytest -q
```
