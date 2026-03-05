# Strict Retrieval-Only Requirements Enforcement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce the LegacyLens contract that answers are generated only from retrieved context with file/line citations, with deterministic fallback when evidence is insufficient.

**Architecture:** Keep retrieval as the single source of truth. Implement Presearch pipeline exactly: intent/entity parsing, semantic search, low-confidence detection, ripgrep fallback, merge/dedupe, top-k selection, context expansion, and grounded answer synthesis. Add explicit grounding state in diagnostics and API responses so UI and tests can detect when an answer must be withheld.

**Tech Stack:** Python 3.11, FastAPI, Pydantic/dataclasses, pytest, vanilla JS frontend.

---

### Task 1: Align Retrieval Pipeline to Presearch Spec

**Files:**
- Modify: `src/legacylens/retrieval.py`
- Modify: `src/legacylens/models.py`
- Test: `tests/test_retrieval.py`

**Step 1: Write the failing tests**

```python
def test_retrieve_triggers_keyword_fallback_on_low_confidence(monkeypatch, tmp_path):
    # semantic top1 below threshold -> fallback should run
    ...
    assert result.diagnostics.hybrid_triggered is True
    assert result.diagnostics.fallback_hits > 0


def test_retrieve_sets_query_intent_and_entities():
    intent, entities, expanded = parse_query_intent_entities("where is file i/o handled?")
    assert intent == "io"
    assert len(entities) >= 1
    assert expanded
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_retrieval.py::test_retrieve_triggers_keyword_fallback_on_low_confidence tests/test_retrieval.py::test_retrieve_sets_query_intent_and_entities -v`
Expected: FAIL because current retrieval path does not run low-confidence fallback and diagnostics always report `query_intent="semantic"`.

**Step 3: Write minimal implementation**

```python
intent, entities, expanded_query = parse_query_intent_entities(query)
semantic_hits = _semantic_search(expanded_query)
hybrid_triggered = is_low_confidence(semantic_hits, settings.fallback_score_threshold, settings.fallback_gap_threshold)
fallback_hits = keyword_fallback(expanded_query, effective_codebase) if hybrid_triggered else []
merged = dedupe_hits(semantic_hits + fallback_hits)
reranked = rerank_hits(merged, query, intent, entities)
final_hits = reranked[: settings.answer_k]
```

Also extend diagnostics with explicit grounding metadata:

```python
grounding_mode: str = "retrieval_only"
grounding_status: str = "grounded"  # or "insufficient_context"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_retrieval.py -v`
Expected: PASS for retrieval fallback, intent/entity, and diagnostics regression tests.

**Step 5: Commit**

```bash
committer "feat: align retrieval pipeline with presearch confidence fallback" src/legacylens/retrieval.py src/legacylens/models.py tests/test_retrieval.py
```

### Task 2: Enforce Grounded Answer Contract

**Files:**
- Modify: `src/legacylens/answer.py`
- Create: `tests/test_answer.py`

**Step 1: Write the failing tests**

```python
def test_generate_answer_refuses_empty_hits(settings):
    with pytest.raises(ValueError, match="No retrieval hits"):
        generate_answer("what is cobol?", [], settings)


def test_generate_answer_low_confidence_returns_insufficient_context_message(settings, hits):
    answer = generate_answer("entry point?", hits, settings, confidence_level="low")
    assert "insufficient context" in answer.lower()
    assert "[" in answer and ":" in answer  # citation hints in response guidance
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_answer.py -v`
Expected: FAIL because low-confidence currently still calls the LLM and appends a generic confidence suffix.

**Step 3: Write minimal implementation**

```python
if confidence_level == "low":
    return (
        "Insufficient context to answer from retrieved code only. "
        "Try narrowing to a symbol/file name and re-run. "
        "Top evidence: ...citations..."
    )
```

Keep prompt strict:
- `Answer using ONLY retrieved chunks`
- `Always cite [file:start-end]`
- `If missing evidence, state what is missing`

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_answer.py -v`
Expected: PASS for low-confidence guardrails and deterministic fallback text.

**Step 5: Commit**

```bash
committer "fix: enforce retrieval-only answer gating and insufficient-context fallback" src/legacylens/answer.py tests/test_answer.py
```

### Task 3: API Contract for Insufficient Evidence

**Files:**
- Modify: `src/legacylens/api.py`
- Modify: `tests/test_api.py`

**Step 1: Write the failing tests**

```python
def test_query_returns_422_when_grounding_status_is_insufficient(monkeypatch):
    # retrieval returns low-confidence + no grounded context
    ...
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "Insufficient grounded context"


def test_query_response_includes_grounding_fields(monkeypatch):
    ...
    assert payload["diagnostics"]["grounding_mode"] == "retrieval_only"
    assert payload["diagnostics"]["grounding_status"] == "grounded"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_query_returns_422_when_grounding_status_is_insufficient tests/test_api.py::test_query_response_includes_grounding_fields -v`
Expected: FAIL because API does not currently branch on grounding status fields.

**Step 3: Write minimal implementation**

```python
if retrieval.diagnostics.grounding_status != "grounded":
    raise HTTPException(
        status_code=422,
        detail={
            "error": "Insufficient grounded context",
            "action": "Refine query with symbol/file hints or verify index coverage.",
        },
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: PASS for new insufficiency and diagnostics contract tests.

**Step 5: Commit**

```bash
committer "feat: expose grounding contract in query API responses" src/legacylens/api.py tests/test_api.py
```

### Task 4: UI Consistency for Grounding and Dataset State

**Files:**
- Modify: `src/legacylens/web/ui.js`
- Modify: `src/legacylens/web/app.js`
- Modify: `src/legacylens/web/index.html`

**Step 1: Write the failing tests**

```text
Manual verification checklist (current behavior fails):
1) Query with low confidence still shows synthesized answer block.
2) Dataset strip can show "None loaded" while retrieval already returned sources.
```

**Step 2: Run verification to confirm failure**

Run:
- `uv run uvicorn legacylens.api:app --reload`
- Open web app and execute low-confidence query
Expected: UI inconsistency visible.

**Step 3: Write minimal implementation**

- Render explicit non-answer state when API returns 422 insufficient grounded context.
- Use `/meta.default_codebase` or `query_meta.qdrant_collection` consistently; remove stale `"None loaded"` default once metadata is available.
- Keep top score visible but label low-confidence state clearly.

**Step 4: Run verification to confirm pass**

Run:
- `uv run uvicorn legacylens.api:app --reload`
- Repeat low-confidence and normal grounded queries
Expected: no synthesized answer on insufficient evidence, dataset strip remains consistent with active backend metadata.

**Step 5: Commit**

```bash
committer "fix: align UI states with retrieval-only grounding contract" src/legacylens/web/ui.js src/legacylens/web/app.js src/legacylens/web/index.html
```

### Task 5: Requirements and Operator Docs Sync

**Files:**
- Modify: `README.md`
- Modify: `docs/PRESEARCH.md`
- Modify: `docs/REQUIREMENTS.md`
- Modify: `docs/demo.md`

**Step 1: Write doc assertions to validate**

```text
- Query behavior states "retrieval-only answers with citations"
- Low-confidence path documented as "insufficient grounded context"
- API 422 contract documented for client handling
```

**Step 2: Validate current docs are incomplete**

Run: `rg -n "insufficient grounded context|retrieval-only|grounding_status|422" README.md docs/PRESEARCH.md docs/REQUIREMENTS.md docs/demo.md`
Expected: Missing or partial coverage.

**Step 3: Write minimal implementation**

- Add explicit contract language and one request/response example for insufficient context.
- Add UI behavior note so reviewers understand why no synthesized answer is returned.

**Step 4: Run doc validation**

Run: `rg -n "insufficient grounded context|retrieval-only|grounding_status|422" README.md docs/PRESEARCH.md docs/REQUIREMENTS.md docs/demo.md`
Expected: PASS with explicit references in all docs.

**Step 5: Commit**

```bash
committer "docs: document strict retrieval-only grounding contract and fallback behavior" README.md docs/PRESEARCH.md docs/REQUIREMENTS.md docs/demo.md
```

### Task 6: Full Verification Gate

**Files:**
- No source edits expected

**Step 1: Run quality gate**

Run:
- `uv run ruff check .`
- `uv run pytest -q`

Expected: PASS.

**Step 2: Run focused smoke checks**

Run:
- `uv run python -m legacylens.cli query "Where is file I/O handled?"`
- `uv run python -m legacylens.cli query "what is cobol?"`

Expected:
- First query returns grounded answer with citations.
- Second query returns insufficient grounded context guidance unless indexed chunks explicitly define COBOL.

**Step 3: Validate API behavior**

Run:
- `uv run uvicorn legacylens.api:app --reload`
- `curl -s -X POST http://127.0.0.1:8000/query -H "content-type: application/json" -d '{"query":"what is cobol?"}'`

Expected: HTTP 422 with `Insufficient grounded context` when evidence is missing.

**Step 4: Commit verification artifacts (if needed)**

```bash
git status
```

Expected: clean working tree except intended tracked files.

**Step 5: Final commit (if Task 6 produced tracked updates)**

```bash
committer "test: verify strict retrieval-only contract end to end" <changed-paths-if-any>
```

---

## References

- `docs/PRESEARCH.md` retrieval/LLM contract:
  - low-confidence fallback trigger (`top1 < 0.65` or `top1-top5 < 0.15`)
  - answer only from retrieved context
  - always cite `[file_path:start-end]`
  - explicit insufficient-context response
- `docs/REQUIREMENTS.md` MVP retrieval + answer generation expectations

