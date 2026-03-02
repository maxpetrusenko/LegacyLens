Here's the final pre-search doc incorporating all the reviewed improvements:
markdown# LegacyLens — Pre-Search Document (Final)
**Project:** RAG System for Legacy Enterprise Codebases  
**Author:** Max Petrusenko | GFA Submission

---

## Phase 1 — Constraints

| Dimension | Decision |
|---|---|
| Codebase | GnuCOBOL (~50–80 COBOL files, ~30–50k LOC indexed) |
| Latency target | <3s end-to-end |
| Ingestion | Batch one-time + optional incremental |
| Dev budget | <$10 total estimated |
| Data sensitivity | Open-source GPL — safe for external APIs |
| Team | Solo |



**Must-haves:** chunking with citations, retrieval with file/line refs, answer generation, deployment  
**Nice-to-haves:** streaming, UI polish, multi-repo  
**Framework:** LlamaIndex — lowest boilerplate for doc-centric RAG

---

## Phase 2 — Architecture Decisions

### Vector DB: Qdrant
Docker for local dev → Qdrant Cloud free tier for deployment. Clean dev loop, expressive metadata filters and payload indexing, same behavior local and cloud. No Pinecone tier surprises during iteration.

### Embeddings: Voyage Code 2
1536-dim, purpose-built for code retrieval, 16k context window, ~14–17% better than general-purpose models on code search benchmarks. Same model for ingestion and query — required for vector space consistency. Fallback: `text-embedding-3-small` if Voyage access isn't available at MVP start.

**Cost estimate:** tracked from actual ingestion run. Formula:
```
embed_cost = (total_tokens_embedded / 1_000_000) * price_per_1M
```
Logged per ingestion run, not hardcoded.

### Chunking: COBOL Structural Boundaries

**Primary:** DIVISION → SECTION → PARAGRAPH (inside PROCEDURE DIVISION only)

**Paragraph detection rules (all must match):**
1. Line ends with `.`
2. Label is 1–4 tokens, all-caps or hyphenated-caps
3. Label is NOT a COBOL reserved keyword: `MOVE IF PERFORM OPEN READ WRITE CLOSE STOP EVALUATE ADD SUBTRACT MULTIPLY DIVIDE COMPUTE DISPLAY ACCEPT`
4. ⚠️ **Context is PROCEDURE DIVISION** — do not detect paragraphs in DATA DIVISION or ENVIRONMENT DIVISION

**Fallback:** 80-line fixed + 15-line overlap for regions where paragraph detection fails

**Ingestion health check:**
```python
if fallback_chunks / total_chunks > 0.30:
    log.warning("Parser misfiring — >30% fallback chunks. Check DIVISION guard.")
```

**Metadata per chunk:**
```json
{
  "file_path": "src/cobc/parser.cob",
  "line_start": 142,
  "line_end": 187,
  "symbol_type": "paragraph | section | division | fallback",
  "symbol_name": "CALCULATE-INTEREST",
  "division": "PROCEDURE DIVISION",
  "section": "ACCOUNTING-SECTION",
  "symbols_used": ["PERFORM VALIDATE-INPUT", "CALL 'LIBCALC'"],
  "tags": ["io", "error_handling", "entry_candidate"],
  "language": "cobol"
}
```

**Deterministic tag assignment (ingestion, no LLM):**
- `io`: `OPEN|READ|WRITE|CLOSE|SELECT|FD`
- `error_handling`: `ON ERROR|INVALID KEY|AT END|NOT AT END|EXCEPTION`
- `entry_candidate`: first SECTION of PROCEDURE DIVISION OR contains `STOP RUN`

**Encoding:**
```python
open(file, encoding="utf-8", errors="replace")
```
Log per-file encoding issues. Never renumber lines after normalization — citation accuracy depends on original line numbers.

### Retrieval Pipeline
```
query
  → Voyage Code 2 embed  (~50ms)
  → Qdrant similarity search top_k=10  (~10–50ms)
  → IF top1_score < 0.65 OR (top1_score - top5_score) < 0.15:
        ripgrep keyword fallback → merge + dedupe by file_path+line_start
  → top 5 chunks selected
  → expand ±10 lines from raw file (NOT re-embedded — avoids embedding contamination)
  → send expanded context to LLM  (~1–2s)
```

**Hybrid fallback rationale:** Flat score distribution = low semantic confidence. Symbol-dominant queries ("find all CALL statements", "main entry point") are keyword-dominant, not semantic. ripgrep handles these cheaply with zero additional infra.

**τ and δ starting values:** `τ=0.65`, `δ=0.15` — calibrated after first test run, logged per query.

**Context expansion note:** Embed only the paragraph chunk. After retrieval, pull ±10 raw lines from the source file for LLM context. Expanded context is never embedded — keeps vector index clean.

### LLM: Claude Sonnet  4.6 or codex 5.3

**Prompt:**
```
You are a COBOL codebase expert. Answer using ONLY the retrieved chunks below.

Rules:
- Always cite sources as: [file_path:line_start-line_end]
- If context is insufficient, say exactly what is missing and suggest a follow-up query
- Keep answers concise and developer-focused

Question: {query}

Retrieved context:
{expanded_chunks_with_citations}

Answer:
```

**Query embedding cache:** Identical queries return cached embedding — reduces latency and API cost on repeated queries.

### Framework: LlamaIndex
Custom `NodeParser` for COBOL-aware chunking, `QdrantVectorStore`, `RetrieverQueryEngine` with custom prompt template.

---

## Phase 3 — Failure Modes, Eval, Deploy

### Failure Handling

| Failure | Response |
|---|---|
| Low vector scores | ripgrep fallback; if still empty → "No confident match. Try: [suggestion]" |
| Ambiguous query | Return top 3 candidates with symbol names, let user pick |
| Cross-file dependencies | Pre-built PERFORM/CALL graph supplements retrieval |
| >30% fallback chunks | Warning logged — parser check required |
| API rate limit | Exponential backoff retry, surface partial results |
| Encoding errors | Log per file, continue with `errors="replace"` |

### Evaluation Strategy
- **Ground truth set:** 20 queries — 6 spec scenarios + 14 developer-style
- **Metric:** Precision@5 — % relevant chunks in top-5 results, manually labeled
- **Target:** ≥70%
- **Tooling:** Python eval script, y/n label per chunk, auto-computes P@5
- **Logged per query:** `timestamp | latency_ms | top1_score | chunks_returned | hybrid_triggered`

### Performance Targets

| Metric | Target |
|---|---|
| Query latency | <3s end-to-end |
| Retrieval P@5 | ≥70% |
| Codebase coverage | 100% COBOL files indexed |
| Ingestion speed | 10k+ LOC in <5 min |

### Deployment
- **Local:** `docker run -p 6333:6333 qdrant/qdrant`
- **Production:** Qdrant Cloud free tier + Railway (FastAPI) + Vercel or Railway (frontend)
- **Secrets:** `.env` local, Railway env vars in prod
- **Interface:** CLI (MVP gate) → FastAPI + bare HTML (final)

---

## Architecture Summary

| Layer | Choice | Rationale |
|---|---|---|
| Codebase | GnuCOBOL | Clean PARAGRAPH structure, strong legacy signal |
| Vector DB | Qdrant | Expressive metadata filters, clean local→cloud dev loop |
| Embeddings | Voyage Code 2 | Code-optimized, interview-defensible |
| LLM | Claude 4.6 or COdex 5.3| Strong citation instruction-following |
| Framework | LlamaIndex | Lowest boilerplate for doc-centric RAG |
| Hybrid fallback | ripgrep | Covers symbol/keyword queries at low vector confidence |
| Backend | FastAPI | Async, Railway-friendly |
| Frontend | CLI → bare HTML | CLI clears gate; no React unless time allows |
| Deployment | Railway + Qdrant Cloud | One surface, free tiers |
| Evaluation | Manual labeled set (20 queries) | Precision@5 ≥70% |

“Retrieval quality is treated as the primary system constraint; LLM synthesis quality is secondary.”

---

## 4 Code Understanding Features

### Deterministic (work regardless of retrieval quality):
1. **File I/O Finder** — filter `tags:io` + retrieval. Zero LLM dependency.
2. **Dependency Mapping** — PERFORM/CALL graph built at ingestion. "What calls X" = graph lookup + retrieval for surrounding context.

### LLM-powered:
3. **Code Explanation** — retrieve paragraph → "Explain in plain English, list key variables, max 5 sentences"
4. **Impact Analysis** — symbol X → call sites via dep graph + retrieval → summarize blast radius

---

## Do Not Cut (interview differentiators)
- Correct file/line citations in every result
- Dependency graph (built at ingestion)
- Precision@5 evaluation with logged results
- Deterministic tag assignment

## Cut First If Time Runs Short
- React frontend (bare HTML is enough)
- Score threshold tuning beyond first calibration
- LLM feature polish
- Streaming responses

---

*Stack locked. No second-guessing mid-week.*