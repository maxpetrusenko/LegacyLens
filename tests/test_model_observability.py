from __future__ import annotations

from contextlib import AbstractContextManager

from legacylens.answer import _openai_answer, _openai_stream_answer
from legacylens.config import Settings
from legacylens.embeddings import OpenAIEmbeddingProvider


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _ObservedSpan(AbstractContextManager):
    def __init__(self, sink: list[dict], payload: dict) -> None:
        self._sink = sink
        self._payload = payload

    def set_outputs(self, outputs: dict) -> None:
        self._payload["outputs"] = outputs

    def __enter__(self) -> "_ObservedSpan":
        self._sink.append(self._payload)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_openai_embedding_provider_wraps_calls_with_observability(monkeypatch) -> None:
    spans: list[dict] = []
    provider = OpenAIEmbeddingProvider("test-key", "text-embedding-3-small", Settings())

    monkeypatch.setattr(
        "legacylens.embeddings.observe_model_call",
        lambda **kwargs: _ObservedSpan(spans, kwargs),
    )
    monkeypatch.setattr(
        provider._client,
        "post",
        lambda *_args, **_kwargs: _FakeResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]}),
    )

    vectors = provider.embed_texts(["MOVE A TO B."])
    assert vectors == [[0.1, 0.2, 0.3]]
    assert len(spans) == 1
    assert spans[0]["run_type"] == "embedding"
    assert spans[0]["provider"] == "openai"
    assert spans[0]["outputs"]["vector_count"] == 1


def test_sync_llm_call_wraps_with_observability(monkeypatch) -> None:
    spans: list[dict] = []
    settings = Settings(openai_api_key="test-key")

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, *_args, **_kwargs):
            return _FakeResponse(
                {
                    "choices": [{"message": {"content": "Answer [sample.cob:1-2]"}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16},
                }
            )

    monkeypatch.setattr(
        "legacylens.answer.observe_model_call",
        lambda **kwargs: _ObservedSpan(spans, kwargs),
    )
    monkeypatch.setattr("legacylens.answer.httpx.Client", _Client)

    answer = _openai_answer(settings, "Where is main?", "ctx", timeout=1.0)
    assert "Answer" in answer
    assert len(spans) == 1
    assert spans[0]["run_type"] == "llm"
    assert spans[0]["provider"] == "openai"
    assert spans[0]["outputs"]["usage"]["total_tokens"] == 16


def test_streaming_llm_call_wraps_with_observability(monkeypatch) -> None:
    spans: list[dict] = []
    settings = Settings(openai_api_key="test-key")

    class _StreamCtx:
        def __enter__(self) -> "_StreamCtx":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"Hello "},"finish_reason":null}]}'
            yield 'data: {"choices":[{"delta":{"content":"world"},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}'
            yield "data: [DONE]"

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def stream(self, *_args, **_kwargs):
            return _StreamCtx()

    monkeypatch.setattr(
        "legacylens.answer.observe_model_call",
        lambda **kwargs: _ObservedSpan(spans, kwargs),
    )
    monkeypatch.setattr("legacylens.answer.httpx.Client", _Client)

    events = list(_openai_stream_answer(settings, "Where is main?", "ctx"))
    assert events[0] == {"type": "token", "token": "Hello "}
    assert events[1] == {"type": "token", "token": "world"}
    assert events[2]["type"] == "done"
    assert len(spans) == 1
    assert spans[0]["run_type"] == "llm"
    assert spans[0]["outputs"]["usage"]["total_tokens"] == 12
