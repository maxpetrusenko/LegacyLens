from fastapi.testclient import TestClient

from legacylens.api import app
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult

client = TestClient(app)


def _parse_sse_events(raw: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    for frame in [chunk for chunk in raw.split("\n\n") if chunk.strip()]:
        name = "message"
        data = ""
        for line in frame.splitlines():
            if line.startswith("event: "):
                name = line.split("event: ", 1)[1].strip()
            if line.startswith("data: "):
                data = line.split("data: ", 1)[1].strip()
        events.append((name, data))
    return events


def _retrieval_result() -> RetrievalResult:
    return RetrievalResult(
        hits=[
            RetrievalHit(
                file_path="sample.cob",
                line_start=2,
                line_end=4,
                text="PROCEDURE DIVISION.\nSTOP RUN.",
                score=0.9,
                metadata={},
            )
        ],
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


def test_query_stream_emits_tokens_and_done(monkeypatch) -> None:
    monkeypatch.setattr("legacylens.api._has_indexed_vectors", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", lambda *_args, **_kwargs: _retrieval_result())

    def fake_stream(*_args, **_kwargs):
        yield {"type": "token", "token": "Hello "}
        yield {"type": "token", "token": "world"}
        yield {"type": "done", "finish_reason": "stop", "usage": {"total_tokens": 5}}

    monkeypatch.setattr("legacylens.api.stream_answer_tokens", fake_stream)
    response = client.post("/query/stream", json={"query": "test"})
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events[0][0] == "context"
    assert '"sources":' in events[0][1]
    assert events[1][0] == "token"
    assert events[2][0] == "token"
    assert events[-1][0] == "done"
    assert '"answer_id": "ans_' in events[-1][1]
    assert '"answer": "Hello world"' in events[-1][1]


def test_query_stream_emits_error_when_retrieval_fails(monkeypatch) -> None:
    monkeypatch.setattr("legacylens.api._has_indexed_vectors", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "legacylens.api.retrieve_with_diagnostics",
        lambda *_args, **_kwargs: RetrievalResult(
            hits=[],
            diagnostics=RetrievalDiagnostics(
                latency_ms=100,
                top1_score=0.0,
                chunks_returned=0,
                hybrid_triggered=False,
                semantic_hits=0,
                fallback_hits=0,
                confidence_level="low",
                retrieval_error="qdrant down",
            ),
        ),
    )

    response = client.post("/query/stream", json={"query": "test"})
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events and events[0][0] == "error"
    assert "Retrieval failed" in events[0][1]


def test_query_stream_emits_error_on_midstream_generation_failure(monkeypatch) -> None:
    monkeypatch.setattr("legacylens.api._has_indexed_vectors", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("legacylens.api.retrieve_with_diagnostics", lambda *_args, **_kwargs: _retrieval_result())

    def fake_stream(*_args, **_kwargs):
        yield {"type": "token", "token": "Hello "}
        raise RuntimeError("midstream failure")

    monkeypatch.setattr("legacylens.api.stream_answer_tokens", fake_stream)
    response = client.post("/query/stream", json={"query": "test"})
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    names = [name for name, _ in events]
    assert "token" in names
    assert "error" in names


def test_query_stream_rejects_vague_chitchat() -> None:
    response = client.post("/query/stream", json={"query": "hello there"})
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events and events[0][0] == "error"
    assert "Query too vague" in events[0][1]


def test_query_stream_blocks_when_no_dataset_indexed(monkeypatch) -> None:
    monkeypatch.setattr("legacylens.api._has_indexed_vectors", lambda *_args, **_kwargs: False)
    response = client.post("/query/stream", json={"query": "where stop run"})
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events and events[0][0] == "error"
    assert "No datasets indexed" in events[0][1]


def test_query_stream_abstains_on_low_signal_weak_evidence(monkeypatch) -> None:
    monkeypatch.setattr("legacylens.api._has_indexed_vectors", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "legacylens.api.retrieve_with_diagnostics",
        lambda *_args, **_kwargs: RetrievalResult(
            hits=[
                RetrievalHit(
                    file_path="sample.cob",
                    line_start=1,
                    line_end=2,
                    text="DISPLAY X",
                    score=0.26,
                    metadata={},
                ),
                RetrievalHit(
                    file_path="sample.cob",
                    line_start=3,
                    line_end=4,
                    text="DISPLAY Y",
                    score=0.255,
                    metadata={},
                ),
            ],
            diagnostics=RetrievalDiagnostics(
                latency_ms=80,
                top1_score=0.26,
                chunks_returned=2,
                hybrid_triggered=False,
                semantic_hits=2,
                fallback_hits=0,
                top2_score=0.255,
                score_gap=0.005,
                confidence_level="medium",
                query_intent="general",
                query_entities=0,
                rerank_applied=True,
            ),
        ),
    )

    response = client.post("/query/stream", json={"query": "alpha beta gamma"})
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events and events[0][0] == "error"
    assert "Not enough evidence for a reliable answer" in events[0][1]


def test_query_stream_relaxed_thresholds_allows_low_signal_answer(monkeypatch) -> None:
    monkeypatch.setattr("legacylens.api._has_indexed_vectors", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "legacylens.api.retrieve_with_diagnostics",
        lambda *_args, **_kwargs: RetrievalResult(
            hits=[
                RetrievalHit(
                    file_path="sample.cob",
                    line_start=1,
                    line_end=2,
                    text="DISPLAY X",
                    score=0.3518,
                    metadata={},
                ),
                RetrievalHit(
                    file_path="sample.cob",
                    line_start=3,
                    line_end=4,
                    text="DISPLAY Y",
                    score=0.3377,
                    metadata={},
                ),
            ],
            diagnostics=RetrievalDiagnostics(
                latency_ms=80,
                top1_score=0.3518,
                chunks_returned=2,
                hybrid_triggered=False,
                semantic_hits=2,
                fallback_hits=0,
                top2_score=0.3377,
                score_gap=0.0141,
                confidence_level="high",
                query_intent="general",
                query_entities=0,
                rerank_applied=True,
            ),
        ),
    )

    def fake_stream(*_args, **_kwargs):
        yield {"type": "token", "token": "Relaxed "}
        yield {"type": "token", "token": "answer"}
        yield {"type": "done", "finish_reason": "stop", "usage": {"total_tokens": 5}}

    monkeypatch.setattr("legacylens.api.stream_answer_tokens", fake_stream)
    response = client.post("/query/stream", json={"query": "alpha beta gamma", "relaxed_thresholds": True})
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events[-1][0] == "done"
    assert '"answer": "Relaxed answer"' in events[-1][1]
