from legacylens.models import RetrievalHit
from legacylens.config import Settings
from legacylens.retrieval import (
    classify_confidence,
    dedupe_hits,
    format_citation,
    is_low_confidence,
    keyword_fallback,
    parse_query_intent_entities,
    rerank_hits,
    retrieve_with_diagnostics,
)


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


def test_classify_confidence_thresholds() -> None:
    assert classify_confidence(0.12, low_threshold=0.15, medium_threshold=0.35) == "low"
    assert classify_confidence(0.20, low_threshold=0.15, medium_threshold=0.35) == "medium"
    assert classify_confidence(0.55, low_threshold=0.15, medium_threshold=0.35) == "high"


def test_retrieve_with_diagnostics_gracefully_handles_missing_qdrant(tmp_path) -> None:
    codebase = tmp_path / "repo"
    codebase.mkdir()
    (codebase / "sample.cob").write_text("PROCEDURE DIVISION.\nSTOP RUN.\n", encoding="utf-8")
    settings = Settings(codebase_path=str(codebase), qdrant_url="http://127.0.0.1:9999")
    result = retrieve_with_diagnostics("STOP RUN", settings, codebase)
    assert result.diagnostics.hybrid_triggered is True
    assert result.diagnostics.fallback_mode == "keyword"
    assert result.diagnostics.fallback_reason in {"qdrant_error", "qdrant_timeout"}
    assert result.diagnostics.retrieval_error is not None
    assert result.diagnostics.confidence_level in {"low", "medium"}
    assert result.diagnostics.query_intent == "general"


def test_parse_query_intent_entities_dependency() -> None:
    intent, entities, expanded = parse_query_intent_entities("who calls 'READ-FILE' in sample.cob?")
    assert intent == "dependency"
    assert "READ-FILE" in entities
    assert "sample.cob" in entities
    assert "READ-FILE" in expanded


def test_parse_query_intent_entities_entry_point_expands_structural_terms() -> None:
    intent, entities, expanded = parse_query_intent_entities("what is entry point")
    assert intent == "general"
    assert "PROGRAM-ID" in entities
    assert "STOP RUN" in entities
    assert "PROGRAM-ID" in expanded


def test_rerank_hits_boosts_entity_matches() -> None:
    hits = [
        RetrievalHit("x.cob", 1, 2, "PERFORM OTHER-PARA.", 0.9, {"tags": []}),
        RetrievalHit("x.cob", 3, 4, "PERFORM READ-FILE.", 0.7, {"tags": []}),
    ]
    reranked = rerank_hits(hits, "where is READ-FILE performed?", "dependency", ["READ-FILE"])
    assert reranked[0].text == "PERFORM READ-FILE."
    assert "rerank_score" in reranked[0].metadata


def test_keyword_fallback_uses_python_scan_when_rg_missing(tmp_path, monkeypatch) -> None:
    codebase = tmp_path / "repo"
    codebase.mkdir()
    (codebase / "sample.cob").write_text("PROCEDURE DIVISION.\nSTOP RUN.\n", encoding="utf-8")

    def _raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("legacylens.retrieval.subprocess.run", _raise_file_not_found)
    hits = keyword_fallback("STOP RUN", codebase, limit=10)
    assert len(hits) == 1
    assert hits[0].file_path == "sample.cob"


def test_keyword_fallback_matches_terms_from_natural_language_query(tmp_path, monkeypatch) -> None:
    codebase = tmp_path / "repo"
    codebase.mkdir()
    (codebase / "sample.cob").write_text("PROCEDURE DIVISION.\nSTOP RUN.\n", encoding="utf-8")

    def _raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("legacylens.retrieval.subprocess.run", _raise_file_not_found)
    hits = keyword_fallback("where is STOP RUN used?", codebase, limit=10)
    assert len(hits) >= 1
    assert hits[0].text.upper().startswith("STOP RUN")
