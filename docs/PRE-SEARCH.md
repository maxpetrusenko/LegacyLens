# LegacyLens Pre-Search (Phase 1-3)

## Phase 1: Constraints
1. Scale and load: corpus currently 96 files and 249k+ LOC, target query latency <3s.
2. Budget and ceiling: keep embedding/model choices in low-to-mid spend tiers.
3. Time to ship: enforce tests first, prioritize required deliverables over polish.
4. Data sensitivity: open source corpus, external API usage acceptable.
5. Team constraints: solo execution, low-ops path favored.

## Phase 2: Architecture Discovery
6. Vector DB: Qdrant selected for metadata filtering and straightforward hosting options.
7. Embeddings: `text-embedding-3-small` default, precision gate controls upgrade path.
8. Chunking: syntax-aware COBOL chunking with deterministic fallback window chunks.
9. Retrieval pipeline: semantic-first, keyword fallback, confidence diagnostics.
10. Answer generation: citation-grounded generation + SSE streaming endpoint.
11. Framework choice: custom FastAPI pipeline for explicit fallback and test control.

## Phase 3: Post-Stack Refinement
12. Failure modes: explicit fallback reason codes, UI degradation banner.
13. Evaluation strategy: precision gate tests + scenario fixtures + requirements gate.
14. Performance optimization: query embedding cache, configurable timeouts.
15. Observability: structured diagnostics payload surfaced in API/UI.
16. Deployment and DevOps: Railway deploy script + submission gate checklist.

## Decision Alignment
- Runtime config and tests now align with:
  - Qdrant vector retrieval
  - OpenAI small embeddings default
  - safe fallback path (keyword and citations-only)
