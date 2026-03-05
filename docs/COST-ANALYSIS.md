# LegacyLens Cost Analysis

## Assumptions
- Embedding model default: `text-embedding-3-small`
- LLM model default: `gpt-4o-mini`
- Query traffic bands:
  - Small: 100 queries/day
  - Medium: 1,000 queries/day
  - Large: 10,000 queries/day
- Average retrieved context per query: low-to-mid token volume

## Development Spend (Estimated)
- Initial build and tuning: low double-digit USD range, primarily LLM prompt iteration and embedding experiments.
- Deterministic tests and offline fallbacks reduce repeated API spend during CI.

## Monthly Projection (Directional)
- Small traffic: low two-digit USD/month
- Medium traffic: low-to-mid three-digit USD/month
- Large traffic: high three-digit to low four-digit USD/month

## Model Decision Impact
- `text-embedding-3-large` has materially higher embedding cost than `text-embedding-3-small`.
- Precision gate policy:
  - keep `3-small` if precision@5 >= 70%
  - switch to `3-large` only if gate fails
- Current decision is documented in `docs/EMBEDDING-DECISION.md`.

## Infrastructure
- Qdrant self-hosted for dev, managed/hosted path for production.
- Railway deployment used for managed API hosting.

## Cost Controls
- In-process query embedding cache
- Keyword retrieval fallback avoids hard query failures
- Configurable timeouts to cap runaway API latency/cost
- Explicit quality degradation signaling to users
