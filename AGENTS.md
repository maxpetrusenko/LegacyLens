# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

LegacyLens is a Python RAG pipeline for legacy COBOL codebases. It exposes a FastAPI web API (with a browser-based console UI) and a CLI. See `README.md` for setup and usage commands.

### Running services

- **Dev server:** `source .venv/bin/activate && uvicorn legacylens.api:app --reload` (port 8000)
- The web console UI is served at `/`, API docs at `/docs`, health check at `/health`.
- The `/query` endpoint requires `OPENAI_API_KEY` (or `VOYAGE_API_KEY`) and a running Qdrant instance with ingested data. Without these, queries return 503 — this is expected behavior, not a bug.
- The dependency graph endpoint (`/graph/{symbol}`) works without API keys, using the bundled `sample_codebase/` data.

### Testing

- `pytest -q` runs all tests. Most tests use mocks/monkeypatching and need no external services.
- `tests/test_health.py` contains smoke tests that hit a live Qdrant instance. These will fail without a configured Qdrant Cloud connection. Exclude with `pytest --ignore=tests/test_health.py`.
- No linter is configured in the project (no ruff, flake8, mypy, etc.).

### Gotchas

- The venv requires `python3.12-venv` system package on Ubuntu (`sudo apt-get install -y python3.12-venv`). The VM snapshot includes this already.
- The `sample_codebase/` directory is bundled inside the package at `src/legacylens/sample_codebase/` and is auto-detected by the API as the default codebase path.
