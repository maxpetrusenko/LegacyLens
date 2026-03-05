from fastapi.testclient import TestClient
import pytest

from legacylens.api import app
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult
from tests.fixtures.sample_queries import REQUIRED_QUERY_SCENARIOS

client = TestClient(app)


def _fake_retrieve(query, settings, codebase_path):
    normalized = query.lower().replace(" ", "_")
    hit = RetrievalHit(
        file_path=f"{normalized}.cob",
        line_start=20,
        line_end=24,
        text="PROCEDURE DIVISION.\nSTOP RUN.",
        score=0.86,
        metadata={"symbol_name": "MAIN-PARA"},
    )
    return RetrievalResult(
        hits=[hit],
        diagnostics=RetrievalDiagnostics(
            latency_ms=120,
            top1_score=0.86,
            chunks_returned=1,
            hybrid_triggered=False,
            semantic_hits=1,
            fallback_hits=0,
            confidence_level="high",
        ),
    )


@pytest.mark.parametrize("scenario", REQUIRED_QUERY_SCENARIOS, ids=[s["id"] for s in REQUIRED_QUERY_SCENARIOS])
def test_required_query_scenarios_have_citations(monkeypatch, scenario) -> None:
    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", _fake_retrieve)
    monkeypatch.setattr("legacylens.api.generate_answer", lambda *args, **kwargs: "answer with citations")
    response = client.post("/query", json={"query": scenario["query"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"], "expected retrieval sources"
    source = payload["sources"][0]
    assert source["file_path"].endswith(".cob")
    assert source["line_start"] >= 1
    assert source["line_end"] >= source["line_start"]
    assert source["citation"].startswith("[")
