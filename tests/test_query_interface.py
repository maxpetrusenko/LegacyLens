from pathlib import Path

from fastapi.testclient import TestClient

from legacylens.api import app
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult

client = TestClient(app)


def _html() -> str:
    path = Path(__file__).resolve().parents[1] / "src" / "legacylens" / "web" / "index.html"
    return path.read_text(encoding="utf-8")


def _app_js() -> str:
    path = Path(__file__).resolve().parents[1] / "src" / "legacylens" / "web" / "app.js"
    return path.read_text(encoding="utf-8")


def test_query_interface_has_natural_language_input() -> None:
    html = _html()
    assert 'id="query-input"' in html
    assert "Ask about file I/O" in html


def test_query_interface_has_syntax_highlight_hooks() -> None:
    html = _html()
    assert "prism-cobol" in html
    css = (Path(__file__).resolve().parents[1] / "src" / "legacylens" / "web" / "styles.css").read_text(
        encoding="utf-8"
    )
    assert ".source-code" in css


def test_query_interface_returns_scores_and_citations(monkeypatch) -> None:
    monkeypatch.setattr(
        "legacylens.api.retrieve_with_diagnostics",
        lambda *_args, **_kwargs: RetrievalResult(
            hits=[RetrievalHit("a.cob", 4, 6, "PERFORM X.", 0.88, {})],
            diagnostics=RetrievalDiagnostics(
                latency_ms=80,
                top1_score=0.88,
                chunks_returned=1,
                hybrid_triggered=False,
                semantic_hits=1,
                fallback_hits=0,
                confidence_level="high",
            ),
        ),
    )
    monkeypatch.setattr("legacylens.api.generate_answer", lambda *_args, **_kwargs: "Explanation with citations.")
    response = client.post("/query", json={"query": "explain perform x"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]
    assert payload["confidence_label"] == "high"
    assert payload["sources"][0]["citation"] == "[a.cob:4-6]"
    assert payload["sources"][0]["score"] == 0.88


def test_query_interface_has_drill_down_controls() -> None:
    html = _html()
    assert 'id="graph-form"' in html
    assert 'id="symbol-input"' in html
    assert 'id="graph-view"' in html
    assert 'id="answer-id"' in html
    assert 'id="copy-answer-id"' in html


def test_streaming_answer_does_not_seed_no_answer_placeholder() -> None:
    app_js = _app_js()
    assert 'renderAnswer("")' not in app_js
    assert "const finalAnswer = payload.answer || streamedAnswer;" in app_js
