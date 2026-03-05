from __future__ import annotations

from contextlib import AbstractContextManager, ExitStack, nullcontext
from dataclasses import dataclass, field
from functools import lru_cache
import json
import logging
import os
from time import perf_counter
from typing import Any

from legacylens.config import Settings

LOGGER = logging.getLogger(__name__)

try:
    from langsmith import Client
    from langsmith import utils as langsmith_utils
    from langsmith.run_helpers import trace
    from langsmith.run_helpers import tracing_context
except Exception:  # pragma: no cover - optional dependency fallback
    Client = None
    langsmith_utils = None
    trace = None
    tracing_context = None


@lru_cache(maxsize=8)
def _langsmith_client(api_key: str, workspace_id: str | None):
    if Client is None:
        return None
    return Client(
        api_key=api_key,
        workspace_id=workspace_id or None,
        hide_inputs=False,
        hide_outputs=False,
    )


_LANGSMITH_TRACING_BOOTSTRAPPED = False


def _ensure_langsmith_tracing_enabled() -> None:
    global _LANGSMITH_TRACING_BOOTSTRAPPED
    if _LANGSMITH_TRACING_BOOTSTRAPPED:
        return
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_TRACING_V2", "true")
    cache_clear = getattr(getattr(langsmith_utils, "get_env_var", None), "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
    _LANGSMITH_TRACING_BOOTSTRAPPED = True


class _TraceScope(AbstractContextManager):
    def __init__(self, *contexts: AbstractContextManager) -> None:
        self._contexts = contexts
        self._stack: ExitStack | None = None

    def __enter__(self):
        self._stack = ExitStack()
        entered = None
        for context in self._contexts:
            entered = self._stack.enter_context(context)
        return entered

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._stack is None:
            return False
        return self._stack.__exit__(exc_type, exc, tb)


def _build_trace_context(
    settings: Settings | None,
    *,
    name: str,
    run_type: str,
    inputs: dict[str, Any],
    metadata: dict[str, Any],
    tags: list[str],
) -> AbstractContextManager:
    if settings is None or not settings.observability_enabled:
        return nullcontext(None)
    if trace is None or tracing_context is None or not settings.langchain_api_key:
        return nullcontext(None)

    _ensure_langsmith_tracing_enabled()
    client = _langsmith_client(settings.langchain_api_key, settings.langsmith_workspace_id)
    if client is None:
        return nullcontext(None)
    return _TraceScope(
        tracing_context(
            enabled=True,
            client=client,
            project_name=settings.observability_project,
            tags=tags,
            metadata=metadata,
        ),
        trace(
            name=name,
            run_type=run_type,
            inputs=inputs,
            metadata=metadata,
            tags=tags,
            project_name=settings.observability_project,
            client=client,
        ),
    )


def _log_json(level: int, payload: dict[str, Any]) -> None:
    LOGGER.log(level, json.dumps(payload, sort_keys=True))


@dataclass(slots=True)
class ModelCallObservation(AbstractContextManager["ModelCallObservation"]):
    settings: Settings | None
    name: str
    run_type: str
    provider: str
    model: str
    input_count: int
    inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    _outputs: dict[str, Any] = field(default_factory=dict, init=False)
    _start_time: float = field(default=0.0, init=False)
    _trace_cm: AbstractContextManager = field(default_factory=lambda: nullcontext(None), init=False)
    _trace_run: Any = field(default=None, init=False)

    def __enter__(self) -> "ModelCallObservation":
        self._start_time = perf_counter()
        trace_inputs = dict(self.inputs)
        trace_inputs.setdefault("input_count", self.input_count)
        if self.metadata and "metadata" not in trace_inputs:
            trace_inputs["metadata"] = self.metadata
        self._trace_cm = _build_trace_context(
            self.settings,
            name=self.name,
            run_type=self.run_type,
            inputs=trace_inputs,
            metadata={
                "provider": self.provider,
                "model": self.model,
                **self.metadata,
            },
            tags=["legacylens", self.run_type, self.provider],
        )
        self._trace_run = self._trace_cm.__enter__()
        if self.settings is None or self.settings.observability_enabled:
            _log_json(
                logging.INFO,
                {
                    "event": "model_call_start",
                    "name": self.name,
                    "run_type": self.run_type,
                    "provider": self.provider,
                    "model": self.model,
                    "input_count": self.input_count,
                    "metadata": self.metadata,
                },
            )
        return self

    def set_outputs(self, outputs: dict[str, Any]) -> None:
        self._outputs = outputs

    def __exit__(self, exc_type, exc, tb) -> bool:
        duration_ms = int((perf_counter() - self._start_time) * 1000)
        if exc is None:
            if self._trace_run is not None and hasattr(self._trace_run, "end"):
                self._trace_run.end(outputs=self._outputs or {"status": "ok", "duration_ms": duration_ms})
            if self.settings is None or self.settings.observability_enabled:
                _log_json(
                    logging.INFO,
                    {
                        "event": "model_call_end",
                        "name": self.name,
                        "run_type": self.run_type,
                        "provider": self.provider,
                        "model": self.model,
                        "duration_ms": duration_ms,
                        "outputs": self._outputs,
                    },
                )
        else:
            if self._trace_run is not None and hasattr(self._trace_run, "end"):
                self._trace_run.end(error=f"{exc_type.__name__}: {exc}")
            if self.settings is None or self.settings.observability_enabled:
                _log_json(
                    logging.ERROR,
                    {
                        "event": "model_call_error",
                        "name": self.name,
                        "run_type": self.run_type,
                        "provider": self.provider,
                        "model": self.model,
                        "duration_ms": duration_ms,
                        "error_type": exc_type.__name__,
                        "error": str(exc),
                    },
                )
        return self._trace_cm.__exit__(exc_type, exc, tb)


def observe_model_call(
    *,
    settings: Settings | None,
    name: str,
    run_type: str,
    provider: str,
    model: str,
    input_count: int,
    inputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ModelCallObservation:
    return ModelCallObservation(
        settings=settings,
        name=name,
        run_type=run_type,
        provider=provider,
        model=model,
        input_count=input_count,
        inputs=inputs or {},
        metadata=metadata or {},
    )


__all__ = ["observe_model_call", "ModelCallObservation"]
