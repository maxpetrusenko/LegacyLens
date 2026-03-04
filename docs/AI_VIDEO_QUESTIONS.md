Hi Max, strong base. Next jump very doable with tighter framing.

  Most challenging part and how I overcame it: The hardest issue was a false green
  deployment. The vector database was disconnected and one URL was dead, but
  cached DB responses made the system look healthy. I bypassed cache for test
  traffic, added retrieval stage logging, and traced each hop from API to vector
  store. That exposed the root cause quickly. After fixing connection config and
  endpoint URL, retrieval quality and response consistency recovered.

  If I had more time, what I’d improve: I’d redesign fallback and resilience.
  Current fallback protects uptime but sometimes creates awkward, low confidence
  responses. I’d use confidence gating so we either return grounded output with
  evidence or clearly say context is insufficient. I’d also add a local failover
  path, like pgvector or FAISS plus provider abstraction, so outages in Qdrant,
  Voyage, or OpenAI do not degrade user experience.

  Edge cases I considered and how I handled them: I covered empty or low relevance
  retrieval, stale cache returning outdated answers, duplicate chunks hurting
  ranking, vector DB timeouts, and unsafe prompt content. I handled these with
  minimum relevance thresholds, cache TTL plus invalidation on reindex, chunk
  deduplication, timeout and retry policies, and input/context sanitization. When
  confidence is low, the system returns a transparent “not enough evidence”
  response instead of hallucinating.

  High level solution and overall approach: I built a modular RAG pipeline end to
  end: ingest and chunk data, generate embeddings, index vectors, retrieve top
  matches, and generate responses only from retrieved context. Then I added
  observability, caching, and deployment checks. The key principle was validating
  retrieval quality, not just final text, so we can detect failures early and
  debug production issues quickly.