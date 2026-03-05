# Implementation Plan: Complete Requirements (All Tasks Required)

**Status**: 10/10 coverage. All REQUIREMENTS.md deliverables mapped to tasks with tests, artifacts, and owner/dates.

## Execution Policy

- All tasks in this plan are required.
- No MVP-only shortcuts.
- Every task must include passing tests before completion.
- Fallback must be visible to users in the UI and API.

## Fallback Policy (Required)

Fallback exists to preserve partial utility during dependency failure while keeping trust.

**Runtime policy**:
- `safe` only: keyword retrieval fallback + citations-only answer fallback.
- No local-embeddings fallback in production path.

**Fallback exposure contract**:

```json
{
  "fallback": {
    "active": true,
    "mode": "keyword|citations_only",
    "reason": "qdrant_timeout|qdrant_error|embedding_timeout|embedding_error|llm_timeout|llm_error|empty_vector_results",
    "severity": "info|error",
    "degraded_quality": true
  }
}
```

UI must show a banner whenever `fallback.active=true`.

---

## Part 1: Fallback Strategy Integration

### Task 1.1: Safe-Only Fallback Policy
**Priority: 5/10** | **Files**: `src/legacylens/config.py`, `src/legacylens/embeddings.py`, `src/legacylens/api.py`

**Goal**:
- Enforce safe-only fallback path.
- Prevent local embeddings fallback in production runtime.

**Acceptance Criteria**:
- Retrieval failures can fall back to keyword search.
- LLM failures can fall back to citations-only answers.
- Local embeddings are not selected in query path.
- Fallback payload is always present and accurate when active.

**Testing**:
- Unit: embedding provider selection prevents local fallback in query runtime.
- API contract: safe fallback payload appears for fallback responses.
- Failure injection: no API keys does not silently route to local embeddings for query path.
- Regression: normal healthy-path query behavior unchanged.

---

### Task 1.2: Retrieval Fallback Chain
**Priority: 7/10** | **Files**: `src/legacylens/retrieval.py`, `src/legacylens/api.py`

**Goal**:
- Wire fallback chain for retrieval failures and empty vector results.
- Set deterministic reason codes.

**Fallback chain**:
1. Vector retrieval (primary)
2. Keyword fallback (`ripgrep`/python scan)
3. Error response only when fallback also fails

**Acceptance Criteria**:
- Qdrant timeout/error triggers keyword fallback.
- Empty vector results can trigger keyword fallback.
- Diagnostics and API response include fallback reason and severity.
- API returns `200` when fallback produces hits.

**Testing**:
- Unit: retrieval diagnostics sets `hybrid_triggered`, fallback counts, reason.
- API contract: `200` + fallback payload when keyword fallback succeeds.
- Failure injection: simulated qdrant timeout and connection error.
- Performance: fallback path latency measured and logged.

---

### Task 1.3: Citations-Only Answer Fallback
**Priority: 5/10** | **Files**: `src/legacylens/answer.py`, `src/legacylens/api.py`

**Goal**:
- On LLM failure, return citations-only output (if retrieval hits exist).

**Acceptance Criteria**:
- LLM failures return `200` with citations-only answer when hits exist.
- Response sets `fallback.active=true`, `mode=citations_only`, proper reason.
- No synthesized prose in citations-only mode.

**Testing**:
- Unit: `generate_citations_only()` formatting and empty-hit behavior.
- API contract: fallback payload for LLM timeout/error.
- Failure injection: mocked LLM exceptions and timeout paths.
- UI integration: frontend renders citations-only state correctly.

---

## Part 2: Streaming Answer Generation

### Task 2.1: Streaming Support in Answer Module
**Priority: 5/10** | **File**: `src/legacylens/answer.py`

**Goal**:
- Implement token streaming generator for answer output.

**Acceptance Criteria**:
- Tokens stream in-order.
- Final metadata includes finish reason and token usage when available.
- Mid-stream failures propagate with clear error event.

**Testing**:
- Unit: stream parser handles token chunks and terminal events.
- Unit: malformed stream lines are safely ignored/logged.
- Failure injection: forced mid-stream API error.
- Regression: non-streaming answer path unchanged.

---

### Task 2.2: SSE Endpoint
**Priority: 5/10** | **File**: `src/legacylens/api.py`

**Goal**:
- Add `/query/stream` endpoint using SSE over POST (`fetch` reader).

**Acceptance Criteria**:
- Event format: token events + final done event + error event.
- Stream closes cleanly on completion and on error.
- `/query` remains backward compatible.

**Testing**:
- API integration: incremental events received in order.
- API contract: done/error event schema validated.
- Failure injection: retrieval and generation failures on stream path.
- Resource checks: no hanging responses or leaked workers.

---

### Task 2.3: Frontend Streaming UI
**Priority: 5/10** | **Files**: `src/legacylens/web/api-client.js`, `src/legacylens/web/app.js`, `src/legacylens/web/styles.css`, `src/legacylens/web/index.html`

**Goal**:
- Render streamed answer progressively.
- Show generation indicator and handle completion/error states.

**Acceptance Criteria**:
- Answer text updates while tokens arrive.
- Generating indicator visible only during active stream.
- Graceful fallback to non-streaming request on stream failure.

**Testing**:
- UI integration: token append behavior, completion state, error state.
- UI regression: no layout jump during stream.
- API-client unit tests: SSE line parsing robustness.
- Accessibility: status updates exposed to assistive tech.

---

## Part 3: Fallback UI and Confidence UX

### Task 3.1: API Fallback Contract
**Priority: 4/10** | **Files**: `src/legacylens/api.py`, `src/legacylens/models.py`

**Goal**:
- Extend response schema with fallback object and reason/severity.

**Acceptance Criteria**:
- `fallback` field always present (`active=false` when unused).
- Enumerated reason and mode values only.
- Existing clients remain compatible.

**Testing**:
- API schema tests for all fallback states.
- Unit: mapping diagnostics to fallback payload.
- Backward compatibility: old response fields unchanged.
- Snapshot tests for representative responses.

---

### Task 3.2: Fallback Banner Component
**Priority: 4/10** | **Files**: `src/legacylens/web/ui.js`, `src/legacylens/web/app.js`, `src/legacylens/web/styles.css`, `src/legacylens/web/index.html`

**Goal**:
- Show persistent fallback banner when degraded mode active.

**Severity mapping**:
- `info`: keyword fallback
- `error`: citations-only

**Acceptance Criteria**:
- Banner shown for all fallback states.
- Message includes reason code and plain-language impact.
- Dismiss behavior does not hide future fallback events.

**Testing**:
- UI tests: render by severity and reason.
- UI tests: dismiss and re-show behavior.
- Accessibility tests: role/aria and keyboard focus.
- Visual regression: banner does not overlap inputs/content.

---

### Task 3.3: Low-Confidence Handling
**Priority: 5/10** | **Files**: `src/legacylens/api.py`, `src/legacylens/web/app.js`

**Goal**:
- Improve low-confidence/no-context UX with actionable guidance.

**Acceptance Criteria**:
- `422` includes suggestions and retry hints.
- UI displays structured guidance, not generic error string.
- Optional retry path supports relaxed thresholds (explicit user action).

**Testing**:
- API tests: `422` schema includes suggestions and confidence level.
- UI tests: low-confidence panel rendering and retry action.
- Failure injection: empty retrieval and low-score retrieval cases.
- Regression: normal high-confidence queries unaffected.

---

## Part 4: Configuration and Model Runtime

### Task 4.1: Model Pinning + Timeout Controls
**Priority: 4/10** | **Files**: `src/legacylens/config.py`, `src/legacylens/answer.py`, `src/legacylens/embeddings.py`, `src/legacylens/retrieval.py`

**Goal**:
- Pin production embedding model to `text-embedding-3-small` (default, subject to Task 4.2 gate).
- Add configurable HTTP and retrieval timeouts.

**Required config**:
- `OPENAI_EMBED_MODEL=text-embedding-3-small` (validated, may be overridden by 4.2)
- `QDRANT_TIMEOUT`
- `SEMANTIC_TIMEOUT`
- `EMBEDDING_TIMEOUT`
- `LLM_TIMEOUT`

**Acceptance Criteria**:
- Invalid model values rejected with explicit message.
- Timeouts configurable per environment.
- Timeout values applied consistently in all request paths.

**Testing**:
- Unit: config validation and defaults.
- Integration: timeout values actually enforce deadlines.
- Failure injection: per-timeout branch triggers expected fallback/error.
- Regression: ingest and query still work with default config.

---

### Task 4.2: Embedding Model Precision Gate (See Full Spec Below)
**Priority: 9/10** | **Files**: `tests/test_embedding_precision.py` (new), `docs/EMBEDDING-DECISION.md` (new)

**Decision rule**:
```
IF precision@5 >= 70% WITH text-embedding-3-small:
    → PASS: Use small model, document tradeoff
ELSE:
    → FAIL: Switch to text-embedding-3-large
    → Rerun precision test
    → Update cost projections
    → Document forced switch reason
```

**Owner**: [Assignee] | **Due**: [After Task 5.5 completes]

---

## Part 5: Testing and Validation

### Task 5.1: Fallback Integration Tests
**Priority: 6/10** | **Files**: `tests/test_api.py`, `tests/test_retrieval.py`, `tests/test_fallback.py` (new)

**Goal**:
- Validate end-to-end fallback behavior across modes.

**Acceptance Criteria**:
- Safe fallback behavior verified across failure modes.
- Keyword fallback and citations-only paths fully covered.
- Fallback payload correctness verified.

**Testing**:
- This task is the testing implementation task itself.
- Must include failure injection fixtures for qdrant/embed/llm outages.
- Must include negative tests proving local embeddings are not used in query fallback path.

---

### Task 5.2: Streaming Tests
**Priority: 5/10** | **Files**: `tests/test_streaming.py` (new), `tests/test_answer.py` (new)

**Goal**:
- Validate streaming protocol, ordering, and cleanup.

**Acceptance Criteria**:
- Token order preserved.
- Done/error events emitted correctly.
- Stream resources cleaned up.

**Testing**:
- This task is the testing implementation task itself.
- Include normal, timeout, malformed-event, and disconnect scenarios.

---

### Task 5.3: E2E Query Scenario Validation
**Priority: 7/10** | **Files**: `tests/test_e2e_queries.py` (new), `tests/fixtures/sample_queries.py` (new)

**Goal**:
- Validate required query scenarios with deterministic fixtures.

**Required scenarios**:
1. Main entry point
2. CUSTOMER-RECORD modifiers
3. CALCULATE-INTEREST explanation
4. File I/O operations
5. MODULE-X dependencies
6. Error handling patterns

**Acceptance Criteria**:
- Queries return citations with file/line fields.
- Precision@5 threshold validation wired.
- Fixtures deterministic in CI.

**Testing**:
- This task is the testing implementation task itself.
- Include deterministic expected-file assertions and confidence checks.

---

### Task 5.4: Core Requirements Verification Suite
**Priority: 6/10** | **Files**: `tests/test_requirements_gate.py` (new), `docs/REQUIREMENTS-CHECKLIST.md` (new)

**Goal**:
- Verify all 9 core requirements through executable checks + checklist evidence.

**Core requirements covered**:
- Ingestion, chunking, embeddings, vector storage, semantic search
- NL query interface, citations, LLM answer generation
- Public deployment accessibility

**Acceptance Criteria**:
- One test/evidence mapping for each requirement.
- Checklist and tests match one-to-one.
- Suite runs in CI.

**Testing**:
- This task is the testing implementation task itself.
- Include remote health check for deployed URL (configurable env).

---

### Task 5.5: Performance and Coverage Validation
**Priority: 6/10** | **Files**: `tests/test_perf_coverage.py` (new)

**Goal**:
- Enforce performance and indexing targets.

**Targets**:
- Query latency < 3s
- Precision@5 > 70%
- Indexed coverage 100% for configured corpus

**Acceptance Criteria**:
- Thresholds verified on deterministic workload.
- Failures provide actionable diagnostics.

**Testing**:
- This task is the testing implementation task itself.
- Include percentile latency checks and precision metric output.

---

### Task 5.6: Documentation Deliverables
**Priority: 3/10** | **Files**: `docs/ARCHITECTURE.md` (new), `docs/COST-ANALYSIS.md` (new)

**Goal**:
- Produce required docs with selected stack documented: Qdrant + `text-embedding-3-small` + COBOL.

**Acceptance Criteria**:
- Architecture doc includes vector DB rationale, embedding strategy, chunking, retrieval pipeline, failure modes, measured performance.
- Cost doc includes dev spend and monthly projections by scale.
- All examples and numbers are consistent with selected stack.

**Testing**:
- Lint/check docs for broken references.
- Cross-check docs against current config defaults.
- Verify no Voyage-specific assumptions remain.

---

### Task 5.7: Query Interface Feature Verification
**Priority: 4/10** | **Files**: `tests/test_query_interface.py` (new), `tests/test_web_ui_contract.py`

**Goal**:
- Verify 6 query interface features end-to-end.

**Features**:
1. Natural language input
2. Syntax-highlighted snippets
3. File path + line numbers
4. Confidence/relevance scores
5. LLM-generated explanations
6. Drill-down context behavior

**Acceptance Criteria**:
- All six features have explicit automated checks.
- Visual/manual checklist attached for UI-only expectations.

**Testing**:
- This task is the testing implementation task itself.
- Include DOM-level checks for syntax highlight hooks/classes.

---

### Task 5.8: Code Understanding Feature Verification (4+)
**Priority: 6/10** | **Files**: `tests/test_code_understanding.py` (new), `src/legacylens/dependency_graph.py`, `src/legacylens/retrieval.py`, `src/legacylens/web/graph.js`

**Goal**:
- Verify at least 4 code-understanding features are implemented and testable.

**Required verified set**:
- Dependency mapping
- Pattern detection
- Code explanation
- Impact analysis

**Acceptance Criteria**:
- Each feature has concrete evidence path (endpoint/UI/test).
- At least 4 features pass automated validation.
- Partial features are not counted unless test-backed.

**Testing**:
- This task is the testing implementation task itself.
- Include one test per claimed feature.
- Include negative tests for false-positive behavior where relevant.

---

### Task 5.9: Requirements Traceability Matrix
**Priority: 6/10** | **Files**: `docs/TRACEABILITY.md` (new), `scripts/validate_traceability.py` (new)

**Goal**:
- Map every REQUIREMENTS.md requirement to: task + test + artifact link.
- One table = zero ambiguity at submission.

**Matrix format** (markdown table):

| Req# | Requirement | Task | Test File | Artifact Link | Status |
|------|-------------|------|-----------|---------------|--------|
| MVP-1 | Ingest legacy codebase | 7.1 | test_corpus_size.py | CORPUS.md | ☐ |
| MVP-2 | Syntax-aware chunking | 5.4 | test_requirements_gate.py | ARCHITECTURE.md | ☐ |
| MVP-3 | Generate embeddings | 4.2 | test_embedding_precision.py | EMBEDDING-DECISION.md | ☐ |
| ... | ... | ... | ... | ... | ... |

**Coverage required** (all REQUIREMENTS.md sections):
- MVP Requirements (9 items)
- Target Codebase (GnuCOBOL selection)
- Ingestion Pipeline (6 components)
- Retrieval Pipeline (6 components)
- Chunking Strategies (5 approaches)
- Testing Scenarios (6 required queries)
- Performance Targets (5 metrics)
- Query Interface (6 features)
- Code Understanding (min 4 of 8 features)
- Vector DB Selection rationale
- Embedding Model decision
- AI Cost Analysis (dev + projections)
- RAG Architecture Documentation
- Submission Deliverables (7 items)
- Pre-Search Checklist (16 phases)

**Acceptance Criteria**:
- Every requirement has row in matrix.
- Each row has task ID, test file, and artifact link.
- Status column shows ☑ for complete, ☐ for pending.
- No empty cells in required columns.

**Testing**:
- Script validates no missing requirements vs REQUIREMENTS.md.
- Links check: all test files and artifacts exist.
- Status consistency: all ☑ marks match actual completion.

---

## Part 6: Pre-Search Document

### Task 6.1: Pre-Search Checklist Completion
**Priority: 8/10** | **Files**: `docs/PRE-SEARCH.md` (new)

**Goal**:
- Complete Phase 1-3 Pre-Search methodology per REQUIREMENTS.md Appendix (lines 291-403).
- Document architecture decisions before final implementation.

**Required phases** (from REQUIREMENTS.md):

**Phase 1: Define Your Constraints**
1. Scale & Load Profile — GnuCOBOL corpus size, expected query volume, latency requirements
2. Budget & Cost Ceiling — Vector DB, embedding API, LLM costs
3. Time to Ship — MVP timeline, must-have vs nice-to-have
4. Data Sensitivity — Open source codebase, external API usage
5. Team & Skill Constraints — Familiarity with vector DBs, RAG frameworks, COBOL

**Phase 2: Architecture Discovery**
6. Vector Database Selection — Qdrant (self-hosted): filtering, hybrid search, scaling
7. Embedding Strategy — `text-embedding-3-small`: code vs general, dimensions, API vs local
8. Chunking Approach — Syntax-aware COBOL paragraph boundaries, optimal size, overlap
9. Retrieval Pipeline — Top-k, re-ranking, context window, multi-query
10. Answer Generation — LLM choice, prompt template, citation format, streaming
11. Framework Selection — Custom vs LangChain/LlamaIndex rationale

**Phase 3: Post-Stack Refinement**
12. Failure Mode Analysis — Empty retrieval, ambiguous queries, rate limiting
13. Evaluation Strategy — Precision measurement, ground truth, user feedback
14. Performance Optimization — Caching, index optimization, query preprocessing
15. Observability — Debug logging, metrics (latency/precision/usage), alerting
16. Deployment & DevOps — CI/CD, environment management, secrets handling

**Acceptance Criteria**:
- All 16 checklist items completed with concrete answers.
- AI conversation history saved as reference document.
- Answers map to actual implementation decisions in codebase.
- Document includes rationale for Qdrant + `text-embedding-3-small` + custom pipeline choices.

**Testing**:
- Peer review: each phase has decision rationale linked to requirements.
- Consistency check: Pre-Search choices match actual config defaults.
- No contradictions between Pre-Search and ARCHITECTURE.md.

---

## Part 7: Ingestion Benchmark and Corpus Validation

### Task 7.1: Minimum Corpus Validation
**Priority: 7/10** | **Files**: `tests/test_corpus_size.py` (new), `scripts/validate_corpus.py` (new)

**Goal**:
- Verify GnuCOBOL corpus meets minimum size requirements: 10,000+ LOC across 50+ files.
- Document actual corpus metrics.

**Requirements reference**: REQUIREMENTS.md lines 45, 109.

**Acceptance Criteria**:
- Corpus has 10,000+ lines of COBOL code (excluding comments/blank).
- Corpus has 50+ .cob/.cbl files indexed.
- Metrics documented in ARCHITECTURE.md or CORPUS.md.

**Testing**:
- Automated script counts LOC and files.
- Test fails if corpus below thresholds.
- CI runs validation on ingest.

---

### Task 7.2: Ingestion Throughput Benchmark
**Priority: 6/10** | **Files**: `tests/test_ingest_perf.py` (new), `scripts/benchmark_ingest.py` (new)

**Goal**:
- Validate ingestion throughput target: 10,000+ LOC in <5 minutes.

**Requirements reference**: REQUIREMENTS.md line 109.

**Acceptance Criteria**:
- Full corpus ingest completes in <5 minutes on reference hardware.
- Benchmark documented with hardware specs.
- Failure includes breakdown: file discovery, chunking, embedding, vector insert.

**Testing**:
- Benchmark script measures end-to-end ingest time.
- Test fails if ingest exceeds 300 seconds.
- Results logged for regression detection.

---

## Part 8: Deployment Execution

### Task 8.1: Production Deployment and Verification
**Priority: 8/10** | **Files**: `scripts/deploy.sh` (new), `.env.production` (configure), `fly.toml` or `vercel.json` or `railway.json`

**Goal**:
- Deploy application to public URL with rollback capability.
- Verify deployment health and accessibility.

**Requirements reference**: REQUIREMENTS.md lines 26, 254-262 (deployed accessibility).

**Deployment steps**:
1. Configure production environment (API keys, Qdrant URL, LLM model)
2. Run ingestion on deployed environment (verify corpus indexed)
3. Deploy app via chosen platform (Railway/Vercel/Fly.io)
4. Smoke test: 6 required query scenarios against deployed URL
5. Verify fallback states show in UI (trigger intentional timeout)
6. Document rollback procedure

**Rollback procedure** (must work within 5 minutes):
- `git revert` + redeploy OR platform rollback to previous release
- Verify previous version accessible
- Document incident in deployment log

**Acceptance Criteria**:
- Public URL responds with 200 for homepage and `/query` endpoint.
- Smoke test queries return valid responses with citations.
- Fallback banner visible when triggered.
- Rollback tested and documented.
- Deployment time < 10 minutes from push to live.

**Testing**:
- Automated smoke test against deployed URL.
- Health check endpoint returns corpus size and model info.
- Link checker validates all URLs in response.

**Owner**: [Assignee] | **Due**: [Date before Phase 5]

---

## Part 9: Submission Artifacts and Packaging

### Task 9.1: GitHub README and Setup Guide
**Priority: 5/10** | **Files**: `README.md` (update), `docs/SETUP.md` (new)

**Goal**:
- Complete GitHub repository with setup guide and architecture overview per submission requirements.

**Requirements reference**: REQUIREMENTS.md lines 250-262.

**Required sections**:
1. Project title and one-line description
2. Live demo link (deployed URL)
3. Quick start (3 commands to running)
4. Full setup guide (deps, env vars, local dev)
5. Architecture overview (diagram or concise description)
6. Query examples (6 required scenarios)
7. Tech stack summary (Qdrant, OpenAI embeddings, GnuCOBOL corpus)
8. Link to deployed demo

**Acceptance Criteria**:
- README renders cleanly on GitHub (markdown validated).
- New user can run locally from setup guide in <10 minutes.
- All links work (demo, docs, repo).
- Architecture overview matches ARCHITECTURE.md content.

**Testing**:
- Fresh clone test: setup from zero on clean machine.
- Link checker validates all URLs.
- Markdown linter passes.

---

### Task 9.2: Demo Video (3-5 minutes)
**Priority: 7/10** | **Files**: `docs/demo-script.md` (new), `demo.mp4` (output)

**Goal**:
- Produce demo video showing query workflow, retrieval results, and answer generation.

**Requirements reference**: REQUIREMENTS.md lines 254-257.

**Required shots** (3-5 min total):
1. Intro: LegacyLens title + what it does (30s)
2. Query interface: natural language input (20s)
3. Retrieval: code snippets with syntax highlighting, file/line refs (40s)
4. Answer generation: LLM explanation with citations (40s)
5. Multiple query types: entry point, data flow, patterns (60s)
6. Fallback behavior (optional but impressive): keyword fallback (30s)
7. Outro: deployed URL + repo link (20s)

**Acceptance Criteria**:
- Video 3-5 minutes, crisp audio, visible text.
- All 6 required query scenarios demonstrated or narrated.
- Deployed URL visible and working.
- Uploaded to YouTube or Vimeo with public link.

**Testing**:
- Script review: covers all requirements.
- Video renders at 1080p+.
- Link test: public URL accessible.

---

### Task 9.3: Social Post Draft
**Priority: 3/10** | **Files**: `docs/SOCIAL-POST.md` (new)

**Goal**:
- Draft social post for X/LinkedIn per submission requirements.

**Requirements reference**: REQUIREMENTS.md line 262.

**Required content**:
- Project description: RAG for legacy COBOL codebases
- Key features: semantic search, code understanding, dependency mapping
- Demo/screenshots or video link
- Tag @GauntletAI
- Hashtags: #RAG #COBOL #LegacyCode #AI

**Platform variants**:
- X (< 280 chars): punchy description + demo link
- LinkedIn (2-3 paragraphs): more context + tech details

**Acceptance Criteria**:
- Draft ready for copy-paste to X and LinkedIn.
- Demo link included and working.
- @GauntletAI tag present.

**Testing**:
- Character count validation for X.
- Link preview test (paste in draft post).

---

## Summary

| Part | Tasks | Effort |
|------|-------|--------|
| Part 1: Fallback Strategy | 1.1, 1.2, 1.3 | ~6h |
| Part 2: Streaming | 2.1, 2.2, 2.3 | ~6h |
| Part 3: Fallback UI + Confidence | 3.1, 3.2, 3.3 | ~5h |
| Part 4: Config + Model | 4.1, 4.2 | ~3h |
| Part 5: Testing + Validation | 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9 | ~8h |
| Part 6: Pre-Search Doc | 6.1 | ~3h |
| Part 7: Ingestion Benchmark | 7.1, 7.2 | ~2h |
| Part 8: Deployment | 8.1 | ~2h |
| Part 9: Submission Artifacts | 9.1, 9.2, 9.3 | ~5h |
| Part 10: Final Gate | 10.1, 10.2 | ~2h |
| **Total** | **28 tasks** | **~42h** |

---

## Implementation Order

**Phase 1: Foundation (Parts 4, 6, 7)**
1. 4.1: lock runtime config and timeout behavior
2. 4.2: execute embedding model decision gate
3. 6.1: complete Pre-Search document (do this early while decisions are fresh)
4. 7.1: validate minimum corpus size
5. 7.2: benchmark ingestion throughput

**Phase 2: Core Features (Parts 1, 2, 3)**
6. 1.1: enforce safe-only fallback policy
7. 1.2 and 1.3: implement retrieval and answer fallback paths
8. 3.1, 3.2, 3.3: expose fallback + low-confidence UX in API/UI
9. 2.1, 2.2, 2.3: implement streaming path and client UX

**Phase 3: Validation (Part 5)**
10. 5.1-5.9: complete full test and documentation validation suite (including traceability)

**Phase 4: Deployment (Part 8)**
11. 8.1: deploy to production and verify

**Phase 5: Submission (Parts 9, 10)**
12. 9.1, 9.2, 9.3: README, demo video, social post (with owner/dates)
13. 10.1, 10.2: traceability matrix, final submission gate

---

## Global Definition of Done

A task is complete only when:
- Code implemented and merged with no TODO placeholders.
- Task-specific `Testing` block is fully green in CI.
- Fallback states, when triggered, are visible in API and UI.
- Non-fallback path behavior remains backward compatible.
- Documentation artifacts match implementation (no drift).
- Manual artifacts (video, social) have owner assigned and due date.

---

## Embedding Model Decision Rule (Hard Gate)

**Task 4.2: Embedding Model Precision Gate**
**Priority: 9/10** | **Files**: `tests/test_embedding_precision.py` (new), `docs/EMBEDDING-DECISION.md` (new)

**Goal**:
- Execute hard decision rule for embedding model selection.
- Pass/fail criterion with forced switch condition.

**Decision rule**:
```
IF precision@5 >= 70% WITH text-embedding-3-small:
    → PASS: Use small model, document tradeoff
ELSE:
    → FAIL: Switch to text-embedding-3-large
    → Rerun precision test
    → Update cost projections
    → Document forced switch reason
```

**Acceptance Criteria**:
- Precision@5 test passes with chosen model OR switch executed and documented.
- EMBEDDING-DECISION.md contains: test results, decision, tradeoff analysis.
- ARCHITECTURE.md and COST-ANALYSIS.md reflect actual model used.

**Testing**:
- Test file `test_embedding_precision.py` runs 6 required scenarios.
- Precision@5 calculated as: (relevant results in top-5) / (total queries).
- Test must fail entire suite if threshold not met with current model.

**Forced switch condition**:
If small model fails threshold:
1. Update `OPENAI_EMBED_MODEL=text-embedding-3-large` in config
2. Re-run precision test (must pass or fail submission)
3. Update cost projections (large = 10x embedding cost)
4. Document in EMBEDDING-DECISION.md: why small failed, large results

---

## Part 9: Submission Artifacts and Packaging

### Task 9.1: GitHub README and Setup Guide
**Priority: 5/10** | **Files**: `README.md` (update), `docs/SETUP.md` (new)

**Goal**:
- Complete GitHub repository with setup guide and architecture overview per submission requirements.

**Requirements reference**: REQUIREMENTS.md lines 250-262.

**Required sections**:
1. Project title and one-line description
2. Live demo link (deployed URL)
3. Quick start (3 commands to running)
4. Full setup guide (deps, env vars, local dev)
5. Architecture overview (diagram or concise description)
6. Query examples (6 required scenarios)
7. Tech stack summary (Qdrant, OpenAI embeddings, GnuCOBOL corpus)
8. Link to deployed demo

**Acceptance Criteria**:
- README renders cleanly on GitHub (markdown validated).
- New user can run locally from setup guide in <10 minutes.
- All links work (demo, docs, repo).
- Architecture overview matches ARCHITECTURE.md content.

**Testing**:
- Fresh clone test: setup from zero on clean machine.
- Link checker validates all URLs.
- Markdown linter passes.

**Owner**: [Assignee] | **Due**: [Date]

---

### Task 9.2: Demo Video (3-5 minutes)
**Priority: 7/10** | **Files**: `docs/demo-script.md` (new), `demo.mp4` (output)

**Goal**:
- Produce demo video showing query workflow, retrieval results, and answer generation.

**Requirements reference**: REQUIREMENTS.md lines 254-257.

**Required shots** (3-5 min total):
1. Intro: LegacyLens title + what it does (30s)
2. Query interface: natural language input (20s)
3. Retrieval: code snippets with syntax highlighting, file/line refs (40s)
4. Answer generation: LLM explanation with citations (40s)
5. Multiple query types: entry point, data flow, patterns (60s)
6. Fallback behavior (optional but impressive): keyword fallback (30s)
7. Outro: deployed URL + repo link (20s)

**Acceptance Criteria**:
- Video 3-5 minutes, crisp audio, visible text.
- All 6 required query scenarios demonstrated or narrated.
- Deployed URL visible and working.
- Uploaded to YouTube or Vimeo with public link.

**Testing**:
- Script review: covers all requirements.
- Video renders at 1080p+.
- Link test: public URL accessible.

**Owner**: [Assignee] | **Due**: [Date - must be complete 24h before submission]

---

### Task 9.3: Social Post Draft
**Priority: 3/10** | **Files**: `docs/SOCIAL-POST.md` (new)

**Goal**:
- Draft social post for X/LinkedIn per submission requirements.

**Requirements reference**: REQUIREMENTS.md line 262.

**Required content**:
- Project description: RAG for legacy COBOL codebases
- Key features: semantic search, code understanding, dependency mapping
- Demo/screenshots or video link
- Tag @GauntletAI
- Hashtags: #RAG #COBOL #LegacyCode #AI

**Platform variants**:
- X (< 280 chars): punchy description + demo link
- LinkedIn (2-3 paragraphs): more context + tech details

**Acceptance Criteria**:
- Draft ready for copy-paste to X and LinkedIn.
- Demo link included and working.
- @GauntletAI tag present.

**Testing**:
- Character count validation for X.
- Link preview test (paste in draft post).

**Owner**: [Assignee] | **Due**: [Date - must be complete 12h before submission]

---

## Part 10: Final Submission Gate

### Task 10.1: Requirements Traceability Matrix
**Priority: 6/10** | **Files**: `docs/TRACEABILITY.md` (new)

**Goal**:
- Map every REQUIREMENTS.md requirement to: task + test + artifact link.
- One table = zero ambiguity at submission.

**Matrix format** (markdown table):

| Req# | Requirement | Task | Test File | Artifact Link | Status |
|------|-------------|------|-----------|---------------|--------|
| MVP-1 | Ingest legacy codebase | 7.1 | test_corpus_size.py | CORPUS.md | ☐ |
| MVP-2 | Syntax-aware chunking | 5.4 | test_requirements_gate.py | ARCHITECTURE.md | ☐ |
| MVP-3 | Generate embeddings | 4.2 | test_embedding_precision.py | EMBEDDING-DECISION.md | ☐ |
| ... | ... | ... | ... | ... | ... |

**Coverage** (all REQUIREMENTS.md sections):
- MVP Requirements (9 items, lines 29-41)
- Target Codebase (lines 45-53)
- Ingestion Pipeline components (lines 57-66)
- Retrieval Pipeline components (lines 68-77)
- Chunking Strategies (lines 79-89)
- Testing Scenarios (lines 91-101, 6 queries)
- Performance Targets (lines 103-110, 5 metrics)
- Query Interface features (lines 113-123, 6 features)
- Code Understanding features (lines 125-139, min 4 of 8)
- Vector DB Selection (lines 140-151)
- Embedding Models (lines 153-163)
- AI Cost Analysis (lines 165-189)
- RAG Architecture Documentation (lines 191-202)
- Submission Deliverables (lines 250-262, 7 items)
- Pre-Search Checklist (lines 291-403, 16 phases)

**Acceptance Criteria**:
- Every requirement has row in matrix.
- Each row has task ID, test file, and artifact link.
- Status column shows ☑ for complete, ☐ for pending.
- No empty cells in required columns.

**Testing**:
- Script validates no missing requirements.
- Links check: all test files and artifacts exist.
- Status consistency: all ☑ marks match actual completion.

**Owner**: [Assignee] | **Due**: [Date - must be complete 6h before submission]

---

### Task 10.2: Final Submission Checklist
**Priority: 9/10** | **Files**: `docs/SUBMISSION-GATE.md` (new)

**Goal**:
- Single checklist with concrete URLs/files for all submission deliverables.
- Zero ambiguity gate before Sunday 10:59 PM CT.

**Checklist** (all items required):

**Code Repository**
- ☐ GitHub repo public and accessible
- ☐ README.md complete with all 8 sections
- ☐ Setup guide tested from fresh clone
- ☐ All CI tests passing on main branch

**Deployed Application**
- ☐ Public URL: _________________
- ☐ Health check returns 200: _________________
- ☐ Smoke test passed (6 query scenarios)
- ☐ Fallback banner verified visible

**Demo Video**
- ☐ Video length: 3-5 minutes
- ☐ Public URL: _________________
- ☐ All 6 query scenarios covered
- ☐ Deployed URL visible in video

**Documentation**
- ☐ Pre-Search doc: docs/PRE-SEARCH.md
- ☐ Architecture doc: docs/ARCHITECTURE.md
- ☐ Cost analysis: docs/COST-ANALYSIS.md
- ☐ Traceability matrix: docs/TRACEABILITY.md
- ☐ Embedding decision: docs/EMBEDDING-DECISION.md

**Social Post**
- ☐ X draft ready (< 280 chars): docs/SOCIAL-POST.md
- ☐ LinkedIn draft ready: docs/SOCIAL-POST.md
- ☐ @GauntletAI tag included
- ☐ Posted on X or LinkedIn (link): _________________

**Performance Gates**
- ☐ Query latency < 3s (p95): _____ ms
- ☐ Precision@5 > 70%: _____ %
- ☐ Corpus coverage 100%: _____ files indexed
- ☐ Ingestion throughput < 5min for 10k LOC: _____ seconds

**Acceptance Criteria**:
- All checkboxes checked with concrete URLs filled in.
- Performance values meet thresholds (or documented exception).
- Social post actually posted (link provided).

**Testing**:
- Automated script checks all artifact files exist.
- Health check validates deployed URL.
- Performance gates run from test suite.

**Submission time**: Sunday 10:59 PM CT — buffer 2 hours for final upload.

**Owner**: [Assignee] | **Due**: [Date - 2h before deadline]
