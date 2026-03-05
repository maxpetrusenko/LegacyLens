# Plan: Runtime Behavior Retrieval Improvements

**Date**: 2026-03-04
**Status**: Draft
**Priority**: Medium

## Problem

Query: "How does STOP RUN terminate processing?"

**Current behavior**: LegacyLens finds `STOP RUN` code instances but cannot explain the termination mechanism (runtime behavior, not code usage).

**Root causes**:
1. Vector store only contains ingested code (`tests/testsuite.src`)
2. No external documentation sources (GnuCOBOL manual, runtime specs)
3. Query intent parser (`parse_query_intent_entities`) doesn't recognize "how does X work" as documentation-needing
4. Keyword fallback searches code, not docs

## Research Findings

**STOP RUN mechanism** (from GnuCOBOL docs):
- Calls `cob_stop_run()` in libcob runtime
- Terminates entire run unit (not just current program)
- Returns control to operating system
- Different from `GOBACK` (returns to caller) and `EXIT PROGRAM` (subprograms only)
- Should not be used in stored procedures

This information lives in documentation, not in the codebase itself.

## Proposed Solutions

### 1. Documentation Ingestion (High Value)

**Approach**: Ingest GnuCOBOL documentation into vector store with source tagging.

**Changes**:
- Add new source type to `RetrievalHit.metadata`: `{"source": "documentation"}`
- Ingest GnuCOBOL manual pages (https://gnucobol.sourceforge.io/documen/)
- Tag doc chunks with `source: "gnucobol_doc"` and relevant keywords

**Files to modify**:
- `src/legacylens/models.py` - add doc source type
- `src/legacylens/ingest.py` - add doc ingestion path
- `src/legacylens/vector_store.py` - ensure source tagging preserved

### 2. Query Intent Extension

**Approach**: Detect "how does/why does/explain" patterns as `runtime_behavior` intent.

**Changes** (`src/legacylens/retrieval.py`):
```python
def parse_query_intent_entities(query: str) -> tuple[str, list[str], str]:
    # Existing: dependency, io, error_handling, location
    # Add:
    if any(word in lowered for word in (
        "how does", "how do", "why does", "why do", "explain",
        "what happens when", "mechanism", "how is", "how are"
    )):
        intent = "runtime_behavior"
```

### 3. Hybrid Retrieval for Behavior Questions

**Approach**: When `runtime_behavior` intent, combine code + doc hits.

**Changes** (`src/legacylens/retrieval.py`):
```python
def retrieve_with_diagnostics(...):
    if intent == "runtime_behavior":
        # Search both code and documentation
        code_hits = store.search(vector, limit=5, filter={"source": "code"})
        doc_hits = store.search(vector, limit=5, filter={"source": "documentation"})
        hits = dedupe_hits(code_hits + doc_hits)
    # ... existing logic
```

### 4. Answer Generation Enhancement

**Approach**: Preface behavior answers with runtime context.

**Changes** (`src/legacylens/answer.py`):
- Detect when `doc_hits` dominate results
- Include source attribution: "Based on GnuCOBOL documentation..."

## Acceptance Criteria

- Query "How does STOP RUN terminate" → explains `cob_stop_run()`, run unit concept
- Query "What's the difference between STOP RUN and GOBACK" → contrasts both
- Runtime behavior queries return doc-backed answers with clear source attribution
- Code-only queries unchanged (no regression)

## Implementation Order

1. Add `documentation` source type to models
2. Extend query intent detection for `runtime_behavior`
3. Ingest GnuCOBOL documentation
4. Implement hybrid retrieval (code + docs)
5. Update answer generation for source attribution
6. Add tests for behavior queries

## Tech Notes

**STOP RUN facts**:
- `cob_stop_run()` in libcob
- Terminates entire run unit
- Returns to OS
- Contrast: `GOBACK` returns to caller, `EXIT PROGRAM` for subprograms

**GnuCOBOL docs**: https://gnucobol.sourceforge.io/documentation.html

**Related code**:
- `src/legacylens/retrieval.py:58` - `parse_query_intent_entities()`
- `src/legacylens/retrieval.py:277` - `retrieve_with_diagnostics()`
- `src/legacylens/answer.py:57` - `generate_answer()`
