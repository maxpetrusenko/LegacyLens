from legacylens.answer import _build_answer_prompt, generate_answer, generate_citations_only, stream_answer_tokens
from legacylens.config import Settings
from legacylens.models import RetrievalHit


def _hits() -> list[RetrievalHit]:
    return [
        RetrievalHit(
            file_path="sample.cob",
            line_start=4,
            line_end=7,
            text="PERFORM WORK-PARA.",
            score=0.8,
            metadata={},
        )
    ]


def test_generate_citations_only_formats_output() -> None:
    assert generate_citations_only(_hits()) == "[sample.cob:4-7]"


def test_generate_citations_only_returns_empty_for_empty_hits() -> None:
    assert generate_citations_only([]) == ""


def test_stream_answer_tokens_yields_provider_events(monkeypatch) -> None:
    settings = Settings()

    def fake_openai_stream(*_args, **_kwargs):
        yield {"type": "token", "token": "a"}
        yield {"type": "done", "finish_reason": "stop", "usage": {"total_tokens": 1}}

    monkeypatch.setattr("legacylens.answer._openai_stream_answer", fake_openai_stream)
    events = list(stream_answer_tokens("q", _hits(), settings))
    assert events[0] == {"type": "token", "token": "a"}
    assert events[1]["type"] == "token"
    assert "Evidence:" in events[1]["token"]
    assert events[2]["type"] == "done"


def test_stream_answer_tokens_emits_synthesis_span_with_full_context(monkeypatch) -> None:
    spans: list[dict] = []
    settings = Settings()

    class _ObservedSpan:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            spans.append(self.payload)
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def set_outputs(self, outputs: dict) -> None:
            self.payload["outputs"] = outputs

    def fake_openai_stream(*_args, **_kwargs):
        yield {"type": "token", "token": "alpha "}
        yield {"type": "token", "token": "beta"}
        yield {"type": "done", "finish_reason": "stop", "usage": {"total_tokens": 2}}

    monkeypatch.setattr("legacylens.answer.observe_model_call", lambda **kwargs: _ObservedSpan(kwargs))
    monkeypatch.setattr("legacylens.answer._openai_stream_answer", fake_openai_stream)

    events = list(stream_answer_tokens("How?", _hits(), settings, confidence_level="high"))
    assert events[-1]["type"] == "done"
    assert len(spans) == 1
    assert spans[0]["name"] == "synthesis.answer_stream"
    assert spans[0]["inputs"]["query"] == "How?"
    assert spans[0]["inputs"]["retrieved_context"].startswith("[sample.cob:4-7]")
    assert spans[0]["outputs"]["answer"].startswith("alpha beta")
    assert "Evidence:" in spans[0]["outputs"]["answer"]


def test_prompt_requires_detailed_grounded_answer() -> None:
    prompt = _build_answer_prompt("How does STOP RUN terminate processing?", "ctx")
    assert "Explain behavior and control flow in detail" in prompt
    assert "Do not mention chunk counts, source counts" in prompt


def test_generate_answer_emits_synthesis_span_with_full_context(monkeypatch) -> None:
    spans: list[dict] = []
    settings = Settings(openai_api_key="k")

    class _ObservedSpan:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            spans.append(self.payload)
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def set_outputs(self, outputs: dict) -> None:
            self.payload["outputs"] = outputs

    monkeypatch.setattr("legacylens.answer.observe_model_call", lambda **kwargs: _ObservedSpan(kwargs))
    monkeypatch.setattr("legacylens.answer._openai_answer", lambda *_args, **_kwargs: "final")

    result = generate_answer("What?", _hits(), settings, confidence_level="medium")
    assert result.startswith("final")
    assert "Evidence:" in result
    assert len(spans) == 1
    assert spans[0]["name"] == "synthesis.answer"
    assert spans[0]["inputs"]["query"] == "What?"
    assert spans[0]["inputs"]["retrieved_context"].startswith("[sample.cob:4-7]")
    assert spans[0]["outputs"]["answer"].startswith("final")


def test_generate_answer_appends_evidence_when_model_omits_citations(monkeypatch) -> None:
    settings = Settings(openai_api_key="k")
    monkeypatch.setattr("legacylens.answer._openai_answer", lambda *_args, **_kwargs: "No citations in this answer.")
    result = generate_answer("What?", _hits(), settings)
    assert "Evidence:" in result
    assert "[sample.cob:4-7]" in result


def test_stream_answer_tokens_appends_evidence_token_when_model_omits_citations(monkeypatch) -> None:
    settings = Settings()

    def fake_openai_stream(*_args, **_kwargs):
        yield {"type": "token", "token": "No citations in stream."}
        yield {"type": "done", "finish_reason": "stop", "usage": {"total_tokens": 1}}

    monkeypatch.setattr("legacylens.answer._openai_stream_answer", fake_openai_stream)
    events = list(stream_answer_tokens("q", _hits(), settings))
    assert events[0] == {"type": "token", "token": "No citations in stream."}
    assert events[1]["type"] == "token"
    assert "Evidence:" in events[1]["token"]
    assert "[sample.cob:4-7]" in events[1]["token"]
    assert events[2]["type"] == "done"
