# Requirements Checklist

| Req# | Requirement | Evidence Test | Artifact | Status |
|---|---|---|---|---|
| MVP-1 | Ingest legacy codebase | `tests/test_ingest.py` | `docs/CORPUS.md` | ☑ |
| MVP-2 | Syntax-aware chunking | `tests/test_chunking.py` | `docs/ARCHITECTURE.md` | ☑ |
| MVP-3 | Generate embeddings | `tests/test_embedding_precision.py` | `docs/EMBEDDING-DECISION.md` | ☑ |
| MVP-4 | Vector storage | `tests/test_vector_store.py` | `docs/ARCHITECTURE.md` | ☑ |
| MVP-5 | Semantic retrieval | `tests/test_retrieval.py` | `docs/ARCHITECTURE.md` | ☑ |
| MVP-6 | Natural language query API | `tests/test_api.py` | `README.md` | ☑ |
| MVP-7 | File/line citations | `tests/test_query_interface.py` | `README.md` | ☑ |
| MVP-8 | LLM answer generation | `tests/test_answer.py` | `docs/ARCHITECTURE.md` | ☑ |
| MVP-9 | Public deployment readiness | `tests/test_requirements_gate.py` | `docs/SUBMISSION-GATE.md` | ☐ |

## Notes
- Deployment row remains pending until production URL + smoke checks are attached.
- The rest of MVP rows are covered by executable tests and local artifacts.
