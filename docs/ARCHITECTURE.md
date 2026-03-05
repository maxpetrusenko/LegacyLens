# LegacyLens Architecture

## Stack
- API: FastAPI
- Vector DB: Qdrant
- Embeddings: OpenAI `text-embedding-3-small` (default)
- LLM: OpenAI chat completions
- Corpus: GnuCOBOL-oriented sources in `data/` and `src/legacylens/sample_codebase/`

## Pipeline
1. Discover COBOL files (`.cob`, `.cbl`, `.cpy`, `.cobol`, `.at`).
2. Syntax-aware chunking with fallback window chunking.
3. Embed chunks and upsert to Qdrant.
4. Query path:
   - semantic retrieval (primary)
   - keyword fallback on semantic failure/empty result
   - answer generation with citations
5. Dependency graph path:
   - build caller index from `PERFORM` and `CALL`
   - expose `/callers/{symbol}` and `/graph/{symbol}`

## Retrieval and Fallback
- Fallback contract is explicit in API responses:
  - `mode=keyword` for retrieval degradation
  - `mode=citations_only` for LLM degradation
- Reason codes:
  - `qdrant_timeout`, `qdrant_error`
  - `embedding_timeout`, `embedding_error`
  - `llm_timeout`, `llm_error`
  - `empty_vector_results`
- UI shows persistent fallback banner while degraded mode is active.

## Streaming
- `POST /query/stream` emits SSE events:
  - `token` events with incremental text
  - `done` event with full payload (`answer_id`, `answer`, `sources`, diagnostics) and stream metadata
  - `error` event for retrieval failure or mid-stream generation failure

## Answer Traceability
- Query responses (`POST /query` and stream `done`) include `answer_id`.
- UI surfaces `answer_id` with one-click copy in both:
  - current answer panel
  - per-query history entries
- Query history stores short answer summary + top evidence line range for each question.

## Observability
- Retrieval diagnostics include:
  - `latency_ms`, `top1_score`, `chunks_returned`
  - semantic/fallback hit mix
  - confidence label
  - fallback fields (`reason`, `mode`, `severity`, `degraded_quality`)
- Every embedding call and LLM call emits structured model-call logs.
- If `LANGCHAIN_API_KEY` is set, model-call spans are exported to LangSmith.

## Measured Baseline
- Local test suite validates:
  - query latency gate `< 3s`
  - precision gate `>= 70%` (deterministic evaluation fixture)
  - corpus size target `>= 50 files` and `>= 10,000 LOC`
- Current corpus metrics are documented in `docs/CORPUS.md`.
