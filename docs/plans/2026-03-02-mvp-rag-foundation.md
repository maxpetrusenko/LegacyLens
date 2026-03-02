# LegacyLens MVP RAG Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a deployable MVP RAG system for COBOL codebases with ingestion, semantic retrieval, citations, and query answering via CLI and FastAPI.

**Architecture:** A Python `src` package with clear modules for chunking, embeddings, vector storage, retrieval, and answer generation. Ingestion parses COBOL structure and stores vectors in Qdrant with metadata. Query flow performs semantic retrieval, optional ripgrep fallback, context expansion, then answer synthesis with citations.

**Tech Stack:** Python 3.11+, FastAPI, Qdrant, httpx, Pydantic v2, pytest.

---

### Task 1: Project Skeleton and Config

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/legacylens/__init__.py`
- Create: `src/legacylens/config.py`
- Create: `src/legacylens/models.py`

**Step 1: Write the failing test**

```python
def test_settings_defaults():
    from legacylens.config import Settings
    settings = Settings()
    assert settings.qdrant_collection == "legacylens_chunks"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_defaults -v`
Expected: FAIL because module does not exist.

**Step 3: Write minimal implementation**

Add package structure and Pydantic settings model with defaults.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_settings_defaults -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml src/legacylens tests/test_config.py
git commit -m "feat: scaffold project config and models"
```

### Task 2: COBOL Chunker with Line Citations

**Files:**
- Create: `src/legacylens/chunking/cobol.py`
- Create: `src/legacylens/chunking/__init__.py`
- Create: `tests/test_chunking.py`

**Step 1: Write the failing test**

```python
def test_detects_paragraph_only_inside_procedure_division():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_chunking.py -v`
Expected: FAIL due missing chunker.

**Step 3: Write minimal implementation**

Implement DIVISION-aware chunking and fixed-size fallback.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_chunking.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/chunking tests/test_chunking.py
git commit -m "feat: add COBOL structural chunker with fallback"
```

### Task 3: Embedding + Qdrant Ingestion

**Files:**
- Create: `src/legacylens/embeddings.py`
- Create: `src/legacylens/vector_store.py`
- Create: `src/legacylens/ingest.py`

**Step 1: Write the failing test**

```python
def test_chunk_to_payload_has_required_metadata():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL due missing pipeline.

**Step 3: Write minimal implementation**

Implement file scan, chunking, embedding calls, and upsert to Qdrant.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest.py -v`
Expected: PASS for payload-level tests.

**Step 5: Commit**

```bash
git add src/legacylens/embeddings.py src/legacylens/vector_store.py src/legacylens/ingest.py
git commit -m "feat: implement ingestion to qdrant"
```

### Task 4: Retrieval + Hybrid Fallback + Answering

**Files:**
- Create: `src/legacylens/retrieval.py`
- Create: `src/legacylens/answer.py`
- Create: `tests/test_retrieval.py`

**Step 1: Write the failing test**

```python
def test_formats_citations():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_retrieval.py::test_formats_citations -v`
Expected: FAIL for missing citation formatter.

**Step 3: Write minimal implementation**

Implement top-k retrieval, low-confidence trigger, ripgrep merge/dedupe, and answer synthesis.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_retrieval.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/retrieval.py src/legacylens/answer.py tests/test_retrieval.py
git commit -m "feat: hybrid retrieval and answer assembly"
```

### Task 5: Interfaces (CLI + FastAPI)

**Files:**
- Create: `src/legacylens/cli.py`
- Create: `src/legacylens/api.py`
- Update: `README.md`

**Step 1: Write the failing test**

```python
def test_query_response_has_citations():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL due missing API.

**Step 3: Write minimal implementation**

Add CLI commands and `/query` endpoint returning answer + sources.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/cli.py src/legacylens/api.py README.md
git commit -m "feat: expose query via cli and fastapi"
```

### Task 6: Verification

**Files:**
- Update: `README.md`

**Step 1: Run test suite**

Run: `pytest -q`
Expected: PASS.

**Step 2: Run smoke commands**

Run:
- `python -m legacylens.cli ingest --codebase /path/to/cobol`
- `python -m legacylens.cli query "where is file IO handled?"`
- `uvicorn legacylens.api:app --reload`

Expected: commands run with environment variables set.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add mvp usage and verification"
```
