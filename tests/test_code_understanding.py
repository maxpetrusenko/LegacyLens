from pathlib import Path

from fastapi.testclient import TestClient

from legacylens.api import app
from legacylens.dependency_graph import build_callers_index, find_symbol_neighborhood
from legacylens.models import CodeChunk, RetrievalDiagnostics, RetrievalHit, RetrievalResult
from legacylens.retrieval import parse_query_intent_entities

client = TestClient(app)


def test_dependency_mapping_builds_callers_index() -> None:
    chunks = [
        CodeChunk(
            file_path="a.cob",
            line_start=1,
            line_end=4,
            text="PERFORM READ-FILE.",
            symbol_type="paragraph",
            symbol_name="MAIN-PARA",
            division="PROCEDURE DIVISION",
            section=None,
            symbols_used=["PERFORM READ-FILE"],
            tags=[],
        )
    ]
    callers = build_callers_index(chunks)
    assert callers["READ-FILE"] == ["MAIN-PARA"]


def test_pattern_detection_identifies_dependency_intent() -> None:
    intent, entities, _ = parse_query_intent_entities("what calls READ-FILE")
    assert intent == "dependency"
    assert "READ-FILE" in entities


def test_code_explanation_feature_returns_answer(monkeypatch) -> None:
    monkeypatch.setattr(
        "legacylens.api.retrieve_with_diagnostics",
        lambda *_args, **_kwargs: RetrievalResult(
            hits=[RetrievalHit("a.cob", 1, 1, "STOP RUN.", 0.9, {})],
            diagnostics=RetrievalDiagnostics(
                latency_ms=50,
                top1_score=0.9,
                chunks_returned=1,
                hybrid_triggered=False,
                semantic_hits=1,
                fallback_hits=0,
                confidence_level="high",
            ),
        ),
    )
    monkeypatch.setattr("legacylens.api.generate_answer", lambda *_args, **_kwargs: "Explanation")
    response = client.post("/query", json={"query": "explain stop run"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Explanation"


def test_impact_analysis_exposes_graph_neighborhood() -> None:
    nodes, edges = find_symbol_neighborhood("TARGET", [("CALLER-A", "TARGET"), ("TARGET", "CALLEE-B")])
    assert "TARGET" in nodes
    assert ("CALLER-A", "TARGET") in edges
    assert ("TARGET", "CALLEE-B") in edges
