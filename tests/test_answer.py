from legacylens.answer import _build_answer_prompt, generate_citations_only, stream_answer_tokens
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
    assert events[1]["type"] == "done"


def test_prompt_requires_detailed_grounded_answer() -> None:
    prompt = _build_answer_prompt("How does STOP RUN terminate processing?", "ctx")
    assert "Explain behavior and control flow in detail" in prompt
    assert "Do not mention chunk counts, source counts" in prompt
