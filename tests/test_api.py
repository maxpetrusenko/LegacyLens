from pathlib import Path

from fastapi.testclient import TestClient

from legacylens.api import app
from legacylens.config import Settings
from legacylens.dependency_graph import save_callers_index
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult


client = TestClient(app)


def _default_query_meta() -> dict:
    settings = Settings()
    use_voyage_model = settings.embed_provider == "voyage" or (
        settings.embed_provider == "auto" and bool(settings.voyage_api_key)
    )
    return {
        "llm_model": settings.llm_model,
        "embed_provider": settings.embed_provider,
        "embed_model": settings.voyage_model if use_voyage_model else settings.openai_embed_model,
        "qdrant_collection": settings.qdrant_collection,
    }


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
    # Summary counts consistency
    assert payload["summary"]["node_count"] == len(payload["nodes"])
    assert payload["summary"]["edge_count"] == len(payload["edges"])
    # Edges have relation field
    for edge in payload["edges"]:
        assert "relation" in edge


def test_query_returns_empty_sources_when_semantic_retrieval_times_out(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

    def fake_retrieve_with_diagnostics(query, settings, codebase_path):
        return RetrievalResult(
            hits=[],
            diagnostics=RetrievalDiagnostics(
                latency_ms=1502,
                top1_score=0,
                chunks_returned=0,
                hybrid_triggered=False,
                semantic_hits=0,
                fallback_hits=0,
                confidence_level="low",
                query_intent="semantic",
                query_entities=0,
                rerank_applied=False,
                retrieval_error="semantic retrieval timed out",
            ),
        )

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve_with_diagnostics)

    response = client.post("/query", json={"query": "where is file i/o handled?"})
    assert response.status_code == 503
    payload = response.json()
    assert payload == {
        "detail": {
            "error": "Retrieval failed",
            "cause": "semantic retrieval timed out",
            "action": "Check embedding provider credentials, vector store connectivity, and ingestion status.",
        }
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
    assert payload["query_meta"] == _default_query_meta()


def test_query_entry_point_uses_semantic_retrieval(monkeypatch) -> None:
    def fake_retrieve_with_diagnostics(query, settings, codebase_path):
        return RetrievalResult(
            hits=[
                RetrievalHit(
                    file_path="sample.cob",
                    line_start=1,
                    line_end=3,
                    text="PROGRAM-ID. SAMPLE.\nPROCEDURE DIVISION.\nSTOP RUN.",
                    score=0.62,
                    metadata={"source": "semantic"},
                )
            ],
            diagnostics=RetrievalDiagnostics(
                latency_ms=110,
                top1_score=0.62,
                chunks_returned=1,
                hybrid_triggered=False,
                semantic_hits=1,
                fallback_hits=0,
                confidence_level="high",
                query_intent="semantic",
                query_entities=0,
                rerank_applied=False,
                retrieval_error=None,
            ),
        )

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve_with_diagnostics)
    monkeypatch.setattr("legacylens.api.generate_answer", lambda *args, **kwargs: "semantic answer")

    response = client.post("/query", json={"query": "what is entry point"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "semantic answer"
    assert payload["answer_id"].startswith("ans_")
    assert payload["diagnostics"]["query_intent"] == "semantic"
    assert len(payload["sources"]) == 1
    assert payload["query_meta"] == _default_query_meta()


def test_query_source_includes_metadata_fields(monkeypatch) -> None:
    """Test that source includes new metadata fields from RetrievalHit."""
    def fake_retrieve_with_diagnostics(query, settings, codebase_path):
        from legacylens.models import RetrievalHit

        return RetrievalResult(
            hits=[
                RetrievalHit(
                    file_path="test.cob",
                    line_start=42,
                    line_end=45,
                    text="PERFORM READ-FILE.",
                    score=0.85,
                    metadata={
                        "division": "PROCEDURE DIVISION",
                        "section": "MAIN-SECTION",
                        "symbol_type": "paragraph",
                        "symbol_name": "MAIN-PARA",
                        "tags": ["io", "file-handle"],
                        "language": "cobol",
                    },
                )
            ],
            diagnostics=RetrievalDiagnostics(
                latency_ms=100,
                top1_score=0.85,
                chunks_returned=1,
                hybrid_triggered=False,
                semantic_hits=1,
                fallback_hits=0,
                confidence_level="high",
                query_intent="semantic",
                query_entities=0,
                rerank_applied=False,
                retrieval_error=None,
            ),
        )

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve_with_diagnostics)
    monkeypatch.setattr("legacylens.api.generate_answer", lambda *args, **kwargs: "test answer")

    response = client.post("/query", json={"query": "test"})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["file_path"] == "test.cob"
    assert source["line_start"] == 42
    assert source["line_end"] == 45
    assert source["division"] == "PROCEDURE DIVISION"
    assert source["section"] == "MAIN-SECTION"
    assert source["symbol_type"] == "paragraph"
    assert source["symbol_name"] == "MAIN-PARA"
    assert source["tags"] == ["io", "file-handle"]
    assert source["language"] == "cobol"
    assert payload["query_meta"] == _default_query_meta()


def test_query_sources_dedupe_repo_prefixed_paths(monkeypatch) -> None:
    def fake_retrieve_with_diagnostics(query, settings, codebase_path):
        return RetrievalResult(
            hits=[
                RetrievalHit(
                    file_path="repos/gnucobol/tests/testsuite.src/numeric-dump.cob",
                    line_start=170,
                    line_end=171,
                    text="CALL \"dump\" USING G-3",
                    score=0.65,
                    metadata={},
                ),
                RetrievalHit(
                    file_path="gnucobol/tests/testsuite.src/numeric-dump.cob",
                    line_start=170,
                    line_end=171,
                    text="CALL \"dump\" USING G-3",
                    score=0.61,
                    metadata={},
                ),
            ],
            diagnostics=RetrievalDiagnostics(
                latency_ms=100,
                top1_score=0.65,
                chunks_returned=2,
                hybrid_triggered=False,
                semantic_hits=2,
                fallback_hits=0,
                confidence_level="high",
                query_intent="dependency",
                query_entities=1,
                rerank_applied=False,
                retrieval_error=None,
            ),
        )

    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", fake_retrieve_with_diagnostics)
    monkeypatch.setattr("legacylens.api.generate_answer", lambda *args, **kwargs: "test answer")

    response = client.post("/query", json={"query": "What calls dump?"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["file_path"] == "gnucobol/tests/testsuite.src/numeric-dump.cob"


def test_graph_typed_edges_with_perform_and_call(tmp_path: Path, monkeypatch) -> None:
    """Test that graph returns typed edges (perform/call/unknown)."""

    repo = tmp_path / "repo"
    repo.mkdir()

    # Mock QdrantStore to return payloads with typed symbols_used
    class MockStore:
        def __init__(self, settings):
            pass

        def iter_payloads(self):
            return [
                {
                    "symbol_name": "CALLER-1",
                    "symbols_used": ["PERFORM CALLEE-A", "CALL 'CALLEE-B'"],
                },
                {
                    "symbol_name": "CALLER-2",
                    "symbols_used": ["PERFORM CALLEE-A", "UNKNOWN-FORMAT"],
                },
            ]

    monkeypatch.setattr("legacylens.api.QdrantStore", MockStore)

    response = client.get(f"/graph/CALLEE-A?codebase_path={repo}")
    assert response.status_code == 200
    payload = response.json()

    # Check that we have edges and relations
    edges = payload["edges"]
    assert len(edges) > 0, "Expected at least one edge"

    # At least one edge should have a typed relation (not unknown)
    # Note: some edges from the graph index might be "unknown" by default
    non_unknown_edges = [e for e in edges if e["relation"] != "unknown"]
    assert len(non_unknown_edges) > 0, "Expected at least one non-unknown relation edge"

    # Summary consistency
    assert payload["summary"]["node_count"] == len(payload["nodes"])
    assert payload["summary"]["edge_count"] == len(payload["edges"])
