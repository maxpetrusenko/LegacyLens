# LegacyLens UI Parity Console Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring the current web UI to feature parity with the provided screenshots, including connected dependency graph rendering, expandable source snippets, and full analytics/telemetry surfaces.

**Architecture:** Extend API response contracts first so UI can render source metadata, graph edge types, and console telemetry without brittle parsing. Then rebuild the web shell into screenshot-matching sections and wire stateful client modules (`app.js`, `ui.js`, `graph.js`, `charts.js`) to consume those contracts. Keep graph + analytics logic deterministic in small helpers so we can test backend contracts and manually verify frontend behavior quickly.

**Tech Stack:** FastAPI, Pydantic, Python dataclasses, vanilla JS modules, Cytoscape, Chart.js, Prism.js, pytest.

---

### Scope Checklist (Screenshot Parity Targets)

- Live badge + codebase metadata strip + details toggle
- Search row with action button + fusion state toggle
- Query KPI chips (`retrieved`, `latency`, `top score`, `files hit`, `divisions`)
- AI explanation panel with model/source count label
- Source match cards with score bars, tags, and expandable snippets
- Dependency graph panel with connected edges, node/link counts, legend
- Analytics panel (`avg similarity`, `files`, `queries`) + charts toggle affordance
- Similarity chart, division breakdown donut, chunk-type donut, files coverage bar
- Session query log list (newest first)

### Task 1: API Contract for UI Metadata

**Files:**
- Modify: `src/legacylens/api.py`
- Modify: `src/legacylens/models.py`
- Test: `tests/test_api.py`

**Step 1: Write the failing test**

```python
def test_query_response_includes_source_metadata_and_confidence(monkeypatch):
    ...
    payload = response.json()
    source = payload["sources"][0]
    assert source["file_path"] == "sample.cob"
    assert source["line_start"] == 10
    assert source["line_end"] == 12
    assert source["division"] == "PROCEDURE DIVISION"
    assert source["symbol_type"] == "paragraph"
    assert source["tags"] == ["io"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_query_response_includes_source_metadata_and_confidence -v`  
Expected: FAIL because response source objects currently only expose `citation`, `score`, `text`.

**Step 3: Write minimal implementation**

- Expand `SourceRef` to include:
  - `file_path`, `line_start`, `line_end`
  - `division`, `section`, `symbol_type`, `symbol_name`, `tags`, `language`
- Preserve existing fields (`citation`, `score`, `text`) for backward compatibility.
- Add a lightweight `query_meta` block in `QueryResponse` with:
  - `llm_model`
  - `embed_provider`
  - `embed_model`
  - `qdrant_collection`
- Populate fields from `RetrievalHit` metadata + `Settings`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py::test_query_response_includes_source_metadata_and_confidence -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/api.py src/legacylens/models.py tests/test_api.py
git commit -m "feat: expose source metadata and query meta for ui parity"
```

### Task 2: Graph Edge Typing + Connected Neighborhood

**Files:**
- Modify: `src/legacylens/dependency_graph.py`
- Modify: `src/legacylens/api.py`
- Test: `tests/test_api.py`

**Step 1: Write the failing test**

```python
def test_graph_endpoint_returns_typed_edges_and_connected_nodes(tmp_path):
    ...
    payload = response.json()
    assert any(edge["relation"] in {"perform", "call", "unknown"} for edge in payload["edges"])
    assert payload["summary"]["node_count"] == len(payload["nodes"])
    assert payload["summary"]["edge_count"] == len(payload["edges"])
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_graph_endpoint_returns_typed_edges_and_connected_nodes -v`  
Expected: FAIL because graph edges do not have relation type or summary counts.

**Step 3: Write minimal implementation**

- Add typed edge builder in `dependency_graph.py` that preserves relation:
  - `perform` for `PERFORM X`
  - `call` for `CALL 'X'`
  - `unknown` for index-only fallback edges
- Update graph neighborhood selection to ensure target-centered connected output (one-hop + bridged edges, bounded by `max_edges`).
- Extend `GraphEdge` with `relation`.
- Extend `GraphResponse` with `summary` (`node_count`, `edge_count`).

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py::test_graph_endpoint_returns_typed_edges_and_connected_nodes -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/dependency_graph.py src/legacylens/api.py tests/test_api.py
git commit -m "feat: return typed graph edges with connected summary"
```

### Task 3: Web Shell Structure Parity

**Files:**
- Modify: `src/legacylens/web/index.html`
- Modify: `src/legacylens/web/styles.css`
- Test: `tests/test_web_ui_contract.py` (new)

**Step 1: Write the failing test**

```python
def test_web_shell_contains_screenshot_sections():
    html = Path("src/legacylens/web/index.html").read_text(encoding="utf-8")
    assert 'id="dataset-strip"' in html
    assert 'id="query-kpis"' in html
    assert 'id="analytics-panel"' in html
    assert 'id="query-log-list"' in html
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_ui_contract.py::test_web_shell_contains_screenshot_sections -v`  
Expected: FAIL because those section IDs do not exist yet.

**Step 3: Write minimal implementation**

- Restructure `index.html` into screenshot-aligned sections:
  - top live badge row
  - dataset strip + details disclosure
  - query input/action row + fusion state pill
  - KPI chip strip
  - AI explanation + source code cards split
  - dependency graph panel with legend and counters
  - analytics panel with charts + query log
- Update CSS theme/layout to match dark console visual language and mobile behavior.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_ui_contract.py::test_web_shell_contains_screenshot_sections -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/web/index.html src/legacylens/web/styles.css tests/test_web_ui_contract.py
git commit -m "feat: align web shell structure with screenshot console layout"
```

### Task 4: Query State Wiring + KPI Chips

**Files:**
- Modify: `src/legacylens/web/app.js`
- Modify: `src/legacylens/web/api-client.js`
- Modify: `src/legacylens/web/ui.js`

**Step 1: Write the failing test**

```python
def test_query_meta_is_serialized_for_ui(monkeypatch):
    ...
    payload = response.json()
    assert payload["query_meta"]["llm_model"]
    assert payload["query_meta"]["embed_model"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_query_meta_is_serialized_for_ui -v`  
Expected: FAIL until `query_meta` is wired end-to-end.

**Step 3: Write minimal implementation**

- In `app.js`:
  - fetch `/meta` on load
  - hydrate live strip fields (`vectors`, `dims`, `metric`, `model`)
  - maintain session state (`queryCount`, `scoreSum`, `filesSeen`)
- In `ui.js`:
  - render KPI pills from `diagnostics` + `sources`
  - render AI explanation header (`model`, `source count`)
  - toggle details/fusion UI chips
- In `api-client.js`:
  - normalize API errors so UI surfaces actionable messages.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py::test_query_meta_is_serialized_for_ui -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/web/app.js src/legacylens/web/api-client.js src/legacylens/web/ui.js tests/test_api.py
git commit -m "feat: wire query metadata and kpi state into ui"
```

### Task 5: Expandable Source Snippet Cards

**Files:**
- Modify: `src/legacylens/web/ui.js`
- Modify: `src/legacylens/web/styles.css`

**Step 1: Write the failing test**

```python
def test_query_response_contains_source_text_for_expandable_cards(monkeypatch):
    ...
    assert payload["sources"][0]["text"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_query_response_contains_source_text_for_expandable_cards -v`  
Expected: FAIL if contract regresses during refactor.

**Step 3: Write minimal implementation**

- Replace plain list items with source cards:
  - header: file path + line range + division/symbol tag
  - score progress bar + percentage
  - actions: `Expand/Collapse`, `Copy`
  - body: syntax-highlighted COBOL snippet (`<pre><code class="language-cobol">`)
- Default collapsed for all except top match.
- Persist expand/collapse state during rerenders by source key.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py::test_query_response_contains_source_text_for_expandable_cards -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/web/ui.js src/legacylens/web/styles.css tests/test_api.py
git commit -m "feat: add expandable source cards with score bars"
```

### Task 6: Dependency Graph Rendering Fixes

**Files:**
- Modify: `src/legacylens/web/graph.js`
- Modify: `src/legacylens/web/ui.js`
- Modify: `src/legacylens/web/styles.css`

**Step 1: Write the failing test**

```python
def test_graph_response_summary_matches_payload_shape(tmp_path):
    ...
    assert payload["summary"]["edge_count"] >= 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_graph_response_summary_matches_payload_shape -v`  
Expected: FAIL if summary contract not yet available.

**Step 3: Write minimal implementation**

- In `graph.js`:
  - render node roles and edge relation colors (`perform` vs `call`)
  - use deterministic layout (`breadthfirst` from target) to avoid visual disconnection
  - add interactive focus on node click
- In `ui.js`:
  - show node/link counters from `graph.summary`
  - show legend chips and empty-state reason text

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py::test_graph_response_summary_matches_payload_shape -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/web/graph.js src/legacylens/web/ui.js src/legacylens/web/styles.css tests/test_api.py
git commit -m "fix: render connected dependency graph with typed legend"
```

### Task 7: Analytics Charts + Session Query Log

**Files:**
- Modify: `src/legacylens/web/charts.js`
- Modify: `src/legacylens/web/ui.js`
- Modify: `src/legacylens/web/index.html`
- Modify: `src/legacylens/web/styles.css`

**Step 1: Write the failing test**

```python
def test_web_shell_contains_analytics_chart_mounts():
    html = Path("src/legacylens/web/index.html").read_text(encoding="utf-8")
    assert 'id="similarity-chart"' in html
    assert 'id="division-chart"' in html
    assert 'id="chunk-type-chart"' in html
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_ui_contract.py::test_web_shell_contains_analytics_chart_mounts -v`  
Expected: FAIL until chart containers are added.

**Step 3: Write minimal implementation**

- Replace current 2-chart model with screenshot parity analytics:
  - Similarity bars per retrieved chunk
  - Division breakdown donut
  - Chunk-type donut (`paragraph` vs `fallback`)
  - Files retrieved progress + total lines covered
- Add query log list with timestamp, query text, top score.
- Update summary row (`avg similarity`, `files`, `queries`) from session state.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_ui_contract.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/legacylens/web/charts.js src/legacylens/web/ui.js src/legacylens/web/index.html src/legacylens/web/styles.css tests/test_web_ui_contract.py
git commit -m "feat: add analytics dashboard charts and session query log"
```

### Task 8: End-to-End Verification + Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/demo.md`

**Step 1: Run full tests**

Run: `pytest -q`  
Expected: PASS.

**Step 2: Run local console smoke**

Run:
- `uvicorn legacylens.api:app --reload`
- Open `http://127.0.0.1:8000/`
- Execute 3 queries:
  - `What does CBL_OC_DUMP do?`
  - `Where is file I/O handled?`
  - `What calls READ-FILE?`

Expected:
- Source cards expand/collapse correctly
- Graph renders with connected edges + counts
- Analytics + query log update per run

**Step 3: Validate responsive layout**

Run browser responsive check at `1280px`, `768px`, `390px`.  
Expected: no overflow clipping in source cards, graph, or analytics charts.

**Step 4: Update docs**

- Add screenshot parity feature list + usage notes in `README.md`
- Add demo script notes in `docs/demo.md` for new UI sections

**Step 5: Commit**

```bash
git add README.md docs/demo.md
git commit -m "docs: document screenshot-parity console workflow"
```

