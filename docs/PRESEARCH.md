# LegacyLens — Pre-Search Document (Final)

**Project:** RAG System for Legacy Enterprise Codebases  
**Author:** Max Petrusenko | GFA Submission

---

## Phase 1 — Constraints

| Dimension | Decision |
|---|---|
| Codebase | GnuCOBOL (~50-80 COBOL files, ~30-50k LOC indexed target) |
| Latency target | <3s end-to-end |
| Ingestion | Batch one-time + optional incremental |
| Dev budget | <$10 total estimated |
| Data sensitivity | Open-source GPL; external API-safe |
| Team | Solo |

**Must-haves:** chunking with citations, retrieval with file/line refs, answer generation, deployment  
**Nice-to-haves:** streaming, UI polish, multi-repo  
**Framework note:** LlamaIndex chosen initially for low boilerplate; current MVP uses direct FastAPI + Qdrant integration.

---

## Phase 2 — Architecture Decisions

### Vector DB: Qdrant
Local Docker for development and Qdrant Cloud/free tier compatible deployment path.

### Embeddings
Primary: Voyage Code 2 (1536 dim).  
Fallback: OpenAI `text-embedding-3-small`.  
MVP-safe fallback: local deterministic hash embeddings when API keys are unavailable.

### Chunking: COBOL Structural Boundaries

**COBOL:** PARAGRAPH within **PROCEDURE DIVISION** only.
Paragraph detection rules:
1. Line ends with `.`
2. Label has 1-4 tokens, uppercase/hyphen pattern
3. Label is not a COBOL reserved keyword
4. Detection active only in PROCEDURE DIVISION

Fallback chunking: fixed 80 lines + 15 line overlap.

Parser health check:
- If fallback ratio exceeds 30%, log warning for parser misfire investigation.

Metadata per chunk:
- `file_path`, `line_start`, `line_end`
- `symbol_type`, `symbol_name`, `division`, `section`
- `symbols_used`, `tags`, `language`

Deterministic tags:
**COBOL:**
- `io`: `OPEN|READ|WRITE|CLOSE|SELECT|FD`
- `error_handling`: `ON ERROR|INVALID KEY|AT END|NOT AT END|EXCEPTION`
- `entry_candidate`: first PROCEDURE section or chunk containing `STOP RUN`

Encoding:
- Read files with `encoding="utf-8", errors="replace"`
- Preserve original line indexing to protect citation integrity

### Retrieval Pipeline
1. Embed query
2. Qdrant similarity search (`top_k=10`)
3. If low confidence (`top1 < 0.65` OR `top1-top5 < 0.15`), trigger ripgrep fallback
4. Merge/dedupe by `file_path + line_start`
5. Select top 5 chunks
6. Expand context by +/-10 source lines (not re-embedded)
7. Generate answer with citations

### LLM
Primary prompt behavior:
- Answer only from retrieved context
- Always cite `[file_path:start-end]`
- If insufficient context, say what is missing and suggest follow-up query

### Query Embedding Cache
Identical queries use in-process cached embeddings to reduce latency and API cost.

---

## Phase 3 — Failure Modes, Evaluation, Deployment

### Failure Handling

| Failure | Response |
|---|---|
| Low vector confidence | Trigger ripgrep fallback; return no-confident-match guidance if still empty |
| Ambiguous query | Return top candidates with citations |
| Cross-file dependencies | Use prebuilt PERFORM/CALL dependency graph |
| >30% fallback chunks | Emit parser warning |
| API/provider failures | Graceful retrieval fallback without 500 |
| Encoding issues | Log and continue with replacement decode |

### Evaluation Strategy
- Ground truth: 20 queries target
- Metric: Precision@5
- Target: >=70%
- Tooling: JSONL dataset + eval command that computes P@k and writes per-query logs:
  - `timestamp | latency_ms | top1_score | chunks_returned | hybrid_triggered`

### Performance Targets

| Metric | Target |
|---|---|
| Query latency | <3s end-to-end |
| Retrieval P@5 | >=70% |
| Coverage | 100% target COBOL files indexed |
| Ingestion speed | 10k+ LOC in <5 minutes |

### Deployment
- Local: Qdrant Docker + FastAPI
- Public MVP: Railway-hosted FastAPI endpoint
- Production path: Railway + Qdrant Cloud

---

## Architecture Summary

| Layer | Choice | Rationale |
|---|---|---|
| Codebase | GnuCOBOL | Clear paragraph structure and legacy relevance |
| Vector DB | Qdrant | Metadata filters + smooth local-to-cloud path |
| Embeddings | Voyage/OpenAI/local hash | Quality-first with operational fallback |
| LLM | OpenAI chat completion integration | Reliable citation prompting |
| Backend | FastAPI | Async-friendly and Railway-ready |
| Hybrid fallback | ripgrep | Strong for symbol-heavy/keyword queries |
| Evaluation | P@k harness | Retrieval-first quality signal |
| Deployment | Railway | Fast public MVP delivery |

---

## Code Understanding Features

Deterministic:
1. File I/O finder using tag/retrieval signals
2. Dependency mapping from PERFORM/CALL graph (`what calls X`)

LLM-assisted:
3. Code explanation with citations
4. Impact analysis using graph + retrieval context

---

## Do Not Cut (Interview Differentiators)
- Correct file/line citations
- Dependency graph built at ingestion
- Precision@5 evaluation with logs
- Deterministic tag assignment and parser health checks

## Cut First If Time Runs Short
- React frontend polish
- Advanced threshold calibration beyond first pass
- Streaming responses
