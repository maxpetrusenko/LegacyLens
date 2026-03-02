from legacylens.models import RetrievalHit
from legacylens.retrieval import dedupe_hits, format_citation, is_low_confidence


def test_formats_citations() -> None:
    assert format_citation("src/main.cob", 10, 22) == "[src/main.cob:10-22]"


def test_dedupe_keeps_highest_score() -> None:
    hits = [
        RetrievalHit("a.cob", 10, 20, "x", 0.2, {}),
        RetrievalHit("a.cob", 10, 20, "y", 0.8, {}),
        RetrievalHit("b.cob", 2, 3, "z", 0.5, {}),
    ]
    deduped = dedupe_hits(hits)
    assert len(deduped) == 2
    assert deduped[0].score == 0.8


def test_low_confidence_with_flat_scores() -> None:
    hits = [
        RetrievalHit("a.cob", 1, 1, "", 0.70, {}),
        RetrievalHit("b.cob", 1, 1, "", 0.68, {}),
        RetrievalHit("c.cob", 1, 1, "", 0.67, {}),
        RetrievalHit("d.cob", 1, 1, "", 0.66, {}),
        RetrievalHit("e.cob", 1, 1, "", 0.65, {}),
    ]
    assert is_low_confidence(hits, tau=0.65, delta=0.15) is True
