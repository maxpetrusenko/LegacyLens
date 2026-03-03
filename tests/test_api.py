from pathlib import Path

from fastapi.testclient import TestClient

from legacylens.api import app
from legacylens.dependency_graph import save_callers_index
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult


client = TestClient(app)


def test_meta_lists_graph_endpoint() -> None:
    response = client.get("/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["graph"] == "/graph/{symbol}"


def test_graph_endpoint_returns_nodes_and_edges(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    graph_path = repo / ".legacylens" / "dependency_graph.json"
    save_callers_index(graph_path, {"READ-FILE": ["MAIN", "WORKER"]})

    response = client.get(f"/graph/READ-FILE?codebase_path={repo}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["symbol"] == "READ-FILE"
    assert any(node["id"] == "READ-FILE" and node["role"] == "target" for node in payload["nodes"])
    assert any(edge["target"] == "READ-FILE" for edge in payload["edges"])


def test_query_returns_empty_sources_when_semantic_retrieval_times_out(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

    def fake_retrieve_with_diagnostics(query, settings, codebase_path):
        return RetrievalResult(
            hits=[],
            diagnostics=RetrievalDiagnostics(
                latency_ms=1502,
                top1_score=0,
                chunks_returned=0,
                hybrid_triggered=True,
                semantic_hits=0,
                fallback_hits=0,
                confidence_level="low",
                query_intent="general",
                query_entities=0,
                rerank_applied=False,
                retrieval_error="semantic retrieval timed out",
            ),
        )

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve_with_diagnostics)

    response = client.post("/query", json={"query": "where is file i/o handled?"})
    assert response.status_code == 200
    payload = response.json()

    assert payload == {
        "answer": "No confident match found. Try a narrower query with symbol or file hints.",
        "sources": [],
        "diagnostics": {
            "latency_ms": 1502,
            "top1_score": 0.0,
            "chunks_returned": 0,
            "hybrid_triggered": True,
            "semantic_hits": 0,
            "fallback_hits": 0,
            "confidence_level": "low",
            "query_intent": "general",
            "query_entities": 0,
            "rerank_applied": False,
            "retrieval_error": "semantic retrieval timed out",
        },
        "confidence_label": "low",
        "debug_hits": None,
    }


def test_query_debug_mode_returns_debug_hits(monkeypatch) -> None:
    def fake_retrieve_with_diagnostics(query, settings, codebase_path):
        from legacylens.models import RetrievalHit

        return RetrievalResult(
            hits=[
                RetrievalHit(
                    file_path="sample.cob",
                    line_start=10,
                    line_end=12,
                    text="STOP RUN.",
                    score=0.42,
                    metadata={},
                )
            ],
            diagnostics=RetrievalDiagnostics(
                latency_ms=210,
                top1_score=0.42,
                chunks_returned=1,
                hybrid_triggered=False,
                semantic_hits=1,
                fallback_hits=0,
                confidence_level="high",
                query_intent="general",
                query_entities=0,
                rerank_applied=True,
                retrieval_error=None,
            ),
        )

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve_with_diagnostics)
    monkeypatch.setattr("legacylens.api.generate_answer", lambda *args, **kwargs: "mock answer")

    response = client.post("/query?debug=true", json={"query": "where stop run"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["confidence_label"] == "high"
    assert payload["debug_hits"] is not None
    assert len(payload["debug_hits"]) == 1
    assert payload["debug_hits"][0]["text"] == "STOP RUN."


def test_query_structural_route_returns_entrypoint_candidates(monkeypatch) -> None:
    monkeypatch.setattr("legacylens.api.is_structural_query", lambda _query: True)
    monkeypatch.setattr(
        "legacylens.api.find_entry_point_hits",
        lambda settings, limit: [
            RetrievalHit(
                file_path="sample.cob",
                line_start=1,
                line_end=6,
                text="PROGRAM-ID. SAMPLE.\nPROCEDURE DIVISION.\nSTOP RUN.",
                score=0.62,
                metadata={"source": "structural"},
            )
        ],
    )

    response = client.post("/query", json={"query": "what is entry point"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["confidence_label"] == "high"
    assert payload["diagnostics"]["query_intent"] == "structural_entry_point"
    assert len(payload["sources"]) == 1
