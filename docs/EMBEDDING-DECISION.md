# Embedding Model Decision

## Gate
Rule:

```
IF precision@5 >= 70% with text-embedding-3-small:
  keep text-embedding-3-small
ELSE:
  switch to text-embedding-3-large
```

## Result
- Precision test file: `tests/test_embedding_precision.py`
- Current gate result: PASS
- Observed precision@5 (deterministic fixture): `0.80`
- Decision: keep `text-embedding-3-small` as default

## Tradeoff
- `3-small` gives lower cost and sufficient precision for current retrieval quality bar.
- Forced upgrade path to `3-large` remains documented and test-gated.

## Follow-up Trigger
Switch to `text-embedding-3-large` when:
- precision@5 drops below 0.70 on representative production-like fixtures
- or query classes show persistent missed-recall issues
