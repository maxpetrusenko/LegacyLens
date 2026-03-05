# Requirements Traceability Matrix

| Req# | Requirement | Task | Test File | Artifact Link | Status |
|---|---|---|---|---|---|
| MVP-1 | Ingest legacy codebase | 7.1 | tests/test_corpus_size.py | docs/CORPUS.md | ☑ |
| MVP-2 | Syntax-aware chunking | 5.4 | tests/test_chunking.py | docs/ARCHITECTURE.md | ☑ |
| MVP-3 | Generate embeddings | 4.2 | tests/test_embedding_precision.py | docs/EMBEDDING-DECISION.md | ☑ |
| MVP-4 | Vector storage | 5.4 | tests/test_vector_store.py | docs/ARCHITECTURE.md | ☑ |
| MVP-5 | Semantic search retrieval | 1.2 | tests/test_retrieval.py | docs/ARCHITECTURE.md | ☑ |
| MVP-6 | NL query interface | 5.7 | tests/test_query_interface.py | README.md | ☑ |
| MVP-7 | Citations in results | 5.3 | tests/test_e2e_queries.py | README.md | ☑ |
| MVP-8 | LLM answer generation | 1.3 | tests/test_answer.py | docs/ARCHITECTURE.md | ☑ |
| MVP-9 | Public deployment access | 8.1 | tests/test_requirements_gate.py | docs/SUBMISSION-GATE.md | ☐ |
| ING-1 | Corpus minimum size | 7.1 | tests/test_corpus_size.py | docs/CORPUS.md | ☑ |
| ING-2 | Ingestion throughput | 7.2 | tests/test_ingest_perf.py | scripts/benchmark_ingest.py | ☑ |
| RET-1 | Safe fallback policy | 1.1 | tests/test_fallback.py | docs/ARCHITECTURE.md | ☑ |
| RET-2 | Retrieval fallback chain | 1.2 | tests/test_fallback.py | src/legacylens/retrieval.py | ☑ |
| RET-3 | Citations-only fallback | 1.3 | tests/test_fallback.py | src/legacylens/answer.py | ☑ |
| STR-1 | SSE streaming endpoint | 2.2 | tests/test_streaming.py | src/legacylens/api.py | ☑ |
| STR-2 | Streaming UI behavior | 2.3 | tests/test_web_ui_contract.py | src/legacylens/web/app.js | ☑ |
| UX-1 | Fallback banner UX | 3.2 | tests/test_web_ui_contract.py | src/legacylens/web/index.html | ☑ |
| UX-2 | Low-confidence guidance | 3.3 | tests/test_fallback.py | src/legacylens/web/ui.js | ☑ |
| CFG-1 | Timeout/model config validation | 4.1 | tests/test_config.py | src/legacylens/config.py | ☑ |
| PERF-1 | Latency + precision gates | 5.5 | tests/test_perf_coverage.py | docs/EMBEDDING-DECISION.md | ☑ |
| CODE-1 | Dependency mapping | 5.8 | tests/test_code_understanding.py | src/legacylens/dependency_graph.py | ☑ |
| DOC-1 | Architecture documentation | 5.6 | tests/test_requirements_gate.py | docs/ARCHITECTURE.md | ☑ |
| DOC-2 | Cost documentation | 5.6 | tests/test_requirements_gate.py | docs/COST-ANALYSIS.md | ☑ |
| SUB-1 | Setup guide | 9.1 | tests/test_requirements_gate.py | docs/SETUP.md | ☑ |
| SUB-2 | Demo script | 9.2 | tests/test_requirements_gate.py | docs/demo-script.md | ☑ |
| SUB-3 | Social draft | 9.3 | tests/test_requirements_gate.py | docs/SOCIAL-POST.md | ☑ |
