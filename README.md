# LegacyLens

LegacyLens is a RAG system for legacy COBOL codebases with citation-grounded answers, dependency mapping, and explicit fallback UX.

## Live Demo
- App: `<DEPLOYED_URL>`
- Video: `<DEMO_VIDEO_URL>`

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Full Setup
- See `docs/SETUP.md` for env vars, local Qdrant setup, ingest commands, and validation gates.

## Architecture Overview
- See `docs/ARCHITECTURE.md` for full flow.
- Key path:
  - syntax-aware chunking
  - OpenAI embeddings (`text-embedding-3-small`)
  - Qdrant semantic retrieval + keyword fallback
  - answer generation + citations-only fallback
  - SSE streaming endpoint (`POST /query/stream`)

## Query Examples (Required Scenarios)
1. Main entry point: `Where is the main entry point?`
2. CUSTOMER-RECORD modifiers: `Where is CUSTOMER-RECORD modified?`
3. CALCULATE-INTEREST explanation: `Explain CALCULATE-INTEREST flow.`
4. File I/O operations: `Where is file I/O handled?`
5. MODULE-X dependencies: `What depends on MODULE-X?`
6. Error handling patterns: `Show error handling patterns.`

## Tech Stack
- FastAPI
- Qdrant
- OpenAI embeddings (`text-embedding-3-small` by default)
- OpenAI LLM answer generation
- COBOL corpus under `data/` and `src/legacylens/sample_codebase/`

## Deployment Link
- `<DEPLOYED_URL>`

## Testing

```bash
pytest -q
python scripts/validate_corpus.py --codebase data
python scripts/validate_traceability.py
```
