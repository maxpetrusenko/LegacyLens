from pathlib import Path

from fastapi.testclient import TestClient

from legacylens.api import app
from legacylens.config import Settings
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult
from legacylens.retrieval import retrieve_with_diagnostics

client = TestClient(app)


def _hit() -> RetrievalHit:
    return RetrievalHit(
        file_path="sample.cob",
        line_start=10,
        line_end=12,
        text="STOP RUN.",
        score=0.31,
        metadata={"symbol_name": "MAIN-PARA"},
    )


def test_query_returns_keyword_fallback_payload(monkeypatch) -> None:
    def fake_retrieve(*_args, **_kwargs):
        return RetrievalResult(
            hits=[_hit()],
            diagnostics=RetrievalDiagnostics(
                latency_ms=122,
                top1_score=0.31,
                chunks_returned=1,
                hybrid_triggered=True,
                semantic_hits=0,
                fallback_hits=1,
                confidence_level="low",
                query_intent="general",
                query_entities=0,
                rerank_applied=True,
                retrieval_error="qdrant timeout",
                fallback_reason="qdrant_timeout",
                fallback_mode="keyword",
                fallback_severity="info",
                degraded_quality=True,
            ),
        )

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve)
    monkeypatch.setattr("legacylens.api.generate_answer", lambda *args, **kwargs: "fallback answer")
    response = client.post("/query", json={"query": "where stop run"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback"] == {
        "active": True,
        "mode": "keyword",
        "reason": "qdrant_timeout",
        "severity": "info",
        "degraded_quality": True,
    }


def test_query_returns_citations_only_on_llm_error(monkeypatch) -> None:
    def fake_retrieve(*_args, **_kwargs):
        return RetrievalResult(
            hits=[_hit()],
            diagnostics=RetrievalDiagnostics(
                latency_ms=100,
                top1_score=0.9,
                chunks_returned=1,
                hybrid_triggered=False,
                semantic_hits=1,
                fallback_hits=0,
                confidence_level="high",
            ),
        )

    def _raise(*_args, **_kwargs):
        raise TimeoutError("LLM timed out")

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve)
    monkeypatch.setattr("legacylens.api.generate_answer", _raise)

    response = client.post("/query", json={"query": "where stop run"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback"]["active"] is True
    assert payload["fallback"]["mode"] == "citations_only"
    assert payload["fallback"]["reason"] == "llm_timeout"
    assert payload["fallback"]["severity"] == "error"
    assert "[sample.cob:10-12]" in payload["answer"]


def test_query_422_contains_low_confidence_guidance(monkeypatch) -> None:
    def fake_retrieve(*_args, **_kwargs):
        return RetrievalResult(
            hits=[],
            diagnostics=RetrievalDiagnostics(
                latency_ms=97,
                top1_score=0.0,
                chunks_returned=0,
                hybrid_triggered=False,
                semantic_hits=0,
                fallback_hits=0,
                confidence_level="low",
            ),
        )

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve)
    response = client.post("/query", json={"query": "unclear"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail["suggestions"], list)
    assert len(detail["suggestions"]) >= 3
    assert detail["retry"]["relaxed_thresholds"] is True


def test_no_local_embedding_fallback_in_query_runtime(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    codebase = tmp_path / "repo"
    codebase.mkdir()
    (codebase / "demo.cob").write_text("PROCEDURE DIVISION.\nSTOP RUN.\n", encoding="utf-8")

    settings = Settings(codebase_path=str(codebase), embed_provider="openai")
    result = retrieve_with_diagnostics("STOP RUN", settings, codebase)
    assert result.diagnostics.fallback_mode == "keyword"
    assert result.diagnostics.fallback_reason == "embedding_error"
    assert result.hits
