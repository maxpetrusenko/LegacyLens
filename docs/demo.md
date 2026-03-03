



  LegacyLens is a retrieval-augmented system for legacy
  enterprise code, especially COBOL. The problem is simple:
  teams depend on old codebases, but it takes too long to
  understand where business logic lives. This MVP gives
  developers a natural-language way to ask questions and get
  grounded answers with citations.


  First, ingestion. We ingest a real legacy codebase at
  meaningful size, over 10,000 lines across more than 50 files.
  The pipeline scans files recursively, normalizes text, and
  applies syntax-aware chunking. For COBOL, chunks follow
  Procedure Division paragraph boundaries, and we use fallback
  windows when structure is unclear. For every chunk, we
  generate embeddings and attach metadata such as file path and
  line numbers. Those vectors are stored in Qdrant so the
  codebase is searchable at scale.

  Second, retrieval and answer generation. When a user asks a
  question, we embed the query with the same model used at
  ingestion and run semantic search against the vector database.
  We return the most relevant chunks, assemble context, and
  generate an answer grounded in retrieved code. Every response
  includes file and line citations, so users can verify exactly
  where the answer came from. We also support hybrid fallback
  search to keep recall strong when vector similarity is weak.

    “At this point, I open the LegacyLens web console and run a
  live query. In the Answer panel, you see the synthesized
  response in plain language. In Matched Sources, you see
  exactly which snippets were used, with file and line citations
  for verification. In Hit Distribution, you see how retrieval
  is spread across returned results, so we can quickly judge
  whether the system found strong concentrated matches or weaker
  scattered hits.”

 Third, interface and deployment. For the MVP I exposed a FastAPI endpoint so engineers can integrate
  through HTTP. The system is deployed and publicly accessible, which satisfies the MVP deployment
  gate.

  So end to end, this MVP covers the full RAG loop: ingest,
  chunk, embed, store, retrieve, cite, and answer. We
  prioritized retrieval quality and trust first, so the next
  phase can focus on stronger reranking, deeper dependency
  analysis, and broader evaluation.