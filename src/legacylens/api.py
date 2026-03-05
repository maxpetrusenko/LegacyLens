from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from legacylens.answer import generate_answer, generate_citations_only, stream_answer_tokens
from legacylens.config import Settings
from legacylens.dependency_graph import (
    build_typed_edges_from_payloads,
    find_callers,
    find_symbol_neighborhood,
    load_callers_index,
)
from legacylens.retrieval import canonicalize_file_path, format_citation, retrieve_with_diagnostics
from legacylens.vector_store import QdrantStore

app = FastAPI(title="LegacyLens MVP")
WEB_DIR = Path(__file__).parent / "web"
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

_WORD_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
_CHITCHAT_PHRASES = {
    "hi",
    "hello",
    "hello there",
    "hey",
    "hey there",
    "yo",
    "sup",
    "thanks",
    "thank you",
}
_CHITCHAT_TOKENS = {"hi", "hello", "hey", "yo", "sup", "there", "thanks", "thank", "you"}


def _default_codebase_path(explicit: str | None) -> str:
    if explicit:
        return explicit
    candidates = [
        Path(__file__).resolve().parent / "sample_codebase",
        Path("tests/testsuite.src"),
        Path("/app/tests/testsuite.src"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return "."


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    codebase_path: str | None = None
    debug: bool = False
    relaxed_thresholds: bool = False


class SourceRef(BaseModel):
    citation: str
    score: float
    text: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    division: str | None = None
    section: str | None = None
    symbol_type: str | None = None
    symbol_name: str | None = None
    tags: list[str] | None = None
    language: str | None = None


class QueryMeta(BaseModel):
    llm_model: str
    embed_provider: str
    embed_model: str
    qdrant_collection: str


class FallbackMeta(BaseModel):
    active: bool = False
    mode: str | None = None
    reason: str | None = None
    severity: str | None = None
    degraded_quality: bool = False


class QueryResponse(BaseModel):
    answer_id: str
    answer: str
    sources: list[SourceRef]
    diagnostics: dict[str, int | float | bool | str | None]
    confidence_label: str
    fallback: FallbackMeta
    query_meta: QueryMeta
    debug_hits: list[SourceRef] | None = None


class CallersResponse(BaseModel):
    symbol: str
    callers: list[str]


class GraphNode(BaseModel):
    id: str
    label: str
    role: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str = "unknown"


class GraphSummary(BaseModel):
    node_count: int
    edge_count: int


class GraphResponse(BaseModel):
    symbol: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    summary: GraphSummary


def _query_meta(settings: Settings) -> QueryMeta:
    use_voyage_model = settings.embed_provider == "voyage" or (
        settings.embed_provider == "auto" and bool(settings.voyage_api_key)
    )
    return QueryMeta(
        llm_model=settings.llm_model,
        embed_provider=settings.embed_provider,
        embed_model=settings.voyage_model if use_voyage_model else settings.openai_embed_model,
        qdrant_collection=settings.qdrant_collection,
    )


def _sources_from_hits(hits) -> list[SourceRef]:
    deduped: dict[tuple[str, int, int], SourceRef] = {}
    for hit in hits:
        normalized_path = canonicalize_file_path(hit.file_path)
        key = (normalized_path, int(hit.line_start), int(hit.line_end))
        candidate = SourceRef(
            citation=format_citation(normalized_path, hit.line_start, hit.line_end),
            score=hit.score,
            text=hit.text,
            file_path=normalized_path,
            line_start=hit.line_start,
            line_end=hit.line_end,
            division=hit.metadata.get("division"),
            section=hit.metadata.get("section"),
            symbol_type=hit.metadata.get("symbol_type"),
            symbol_name=hit.metadata.get("symbol_name"),
            tags=hit.metadata.get("tags"),
            language=hit.metadata.get("language"),
        )
        existing = deduped.get(key)
        if existing is None or candidate.score > existing.score:
            deduped[key] = candidate
    return sorted(deduped.values(), key=lambda source: source.score, reverse=True)


def _fallback_from_diagnostics(diagnostics) -> FallbackMeta:
    active = bool(diagnostics.fallback_mode)
    return FallbackMeta(
        active=active,
        mode=diagnostics.fallback_mode if active else None,
        reason=diagnostics.fallback_reason if active else None,
        severity=diagnostics.fallback_severity if active else None,
        degraded_quality=diagnostics.degraded_quality if active else False,
    )


def _llm_failure_reason(exc: Exception) -> str:
    lowered = str(exc).lower()
    if "timeout" in lowered or "timed out" in lowered:
        return "llm_timeout"
    return "llm_error"


def _collection_meta(settings: Settings) -> dict[str, int | str | None]:
    vector_count: int | None = None
    vector_dim: int | None = None
    vector_metric: str | None = None

    try:
        store = QdrantStore(settings)
        info = store.client.get_collection(collection_name=settings.qdrant_collection)
    except Exception:
        return {
            "vector_count": vector_count,
            "vector_dim": vector_dim,
            "vector_metric": vector_metric,
        }

    for attr in ("vectors_count", "points_count"):
        value = getattr(info, attr, None)
        if value is not None:
            try:
                vector_count = int(value)
            except (TypeError, ValueError):
                pass
            if vector_count is not None:
                break

    config = getattr(info, "config", None)
    params = getattr(config, "params", None)
    vectors = getattr(params, "vectors", None)
    candidate = None
    if isinstance(vectors, dict) and vectors:
        candidate = next(iter(vectors.values()))
    elif vectors is not None:
        candidate = vectors

    if candidate is not None:
        size = getattr(candidate, "size", None)
        distance = getattr(candidate, "distance", None)
        if size is not None:
            try:
                vector_dim = int(size)
            except (TypeError, ValueError):
                vector_dim = None
        if distance is not None:
            vector_metric = str(getattr(distance, "value", distance)).lower()

    return {
        "vector_count": vector_count,
        "vector_dim": vector_dim,
        "vector_metric": vector_metric,
    }


def _stream_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


def _new_answer_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"ans_{ts}_{uuid4().hex[:8]}"


def _query_tokens(query: str) -> list[str]:
    return [token.lower() for token in _WORD_PATTERN.findall(query)]


def _is_query_underspecified(query: str) -> tuple[bool, str | None]:
    normalized = query.strip()
    if len(normalized) <= 1:
        return True, "single_character"
    lowered = normalized.lower()
    if lowered in _CHITCHAT_PHRASES:
        return True, "chitchat"
    tokens = _query_tokens(normalized)
    if tokens and len(tokens) <= 2 and all(token in _CHITCHAT_TOKENS for token in tokens):
        return True, "chitchat"
    return False, None


def _query_hint_detail(reason: str | None = None) -> dict[str, object]:
    return {
        "error": "Query too vague",
        "reason": reason or "missing_intent",
        "action": "Ask a COBOL-specific question with a symbol, behavior, or file hint.",
        "suggestions": [
            "Where is FILE STATUS checked before STOP RUN?",
            "Show callers of DUMP and their source lines.",
            "Trace READ-FILE flow from OPEN to CLOSE.",
        ],
        "retry": {"relaxed_thresholds": False, "how": "Rephrase with COBOL terms and rerun."},
    }


def _no_dataset_detail() -> dict[str, object]:
    return {
        "error": "No datasets indexed",
        "action": "Ingest and index a COBOL dataset before querying.",
        "suggestions": [
            "Run ingestion for your codebase to create vectors.",
            "Verify Qdrant collection has points.",
            "Refresh the console after indexing completes.",
        ],
        "retry": {"relaxed_thresholds": False, "how": "Index data first, then rerun the same query."},
    }


def _insufficient_evidence_detail(top1_score: float, score_gap: float) -> dict[str, object]:
    return {
        "error": "Not enough evidence for a reliable answer",
        "action": "Refine query with stronger COBOL anchors so retrieval can isolate relevant code.",
        "scores": {"top1": round(top1_score, 4), "gap": round(score_gap, 4)},
        "suggestions": [
            "Include exact symbols like READ-FILE, MAIN-PARA, or STOP RUN.",
            "Add a file hint like numeric-display.cob.",
            "Ask one concrete behavior question instead of broad text.",
        ],
        "retry": {"relaxed_thresholds": True, "how": "Use Retry with broader search only after adding anchors."},
    }


def _is_low_signal_query(diagnostics) -> bool:
    return diagnostics.query_intent == "general" and diagnostics.query_entities == 0


def _should_abstain_for_low_evidence(
    hits, diagnostics, settings: Settings, *, relaxed_thresholds: bool = False
) -> bool:
    if not hits or not _is_low_signal_query(diagnostics):
        return False
    min_top1 = settings.answer_min_top1_score
    min_gap = settings.answer_min_score_gap
    if relaxed_thresholds:
        min_top1 = max(0.0, min_top1 - 0.08)
        min_gap = max(0.0, min_gap - 0.015)
    top1 = float(getattr(diagnostics, "top1_score", 0.0) or 0.0)
    score_gap = float(getattr(diagnostics, "score_gap", 0.0) or 0.0)
    if top1 < min_top1:
        return True
    if len(hits) > 1 and score_gap < min_gap:
        return True
    return False


def _has_indexed_vectors(settings: Settings) -> bool | None:
    count = _collection_meta(settings).get("vector_count")
    if isinstance(count, int):
        return count > 0
    return None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/meta")
def meta() -> dict[str, str | int | None]:
    default_codebase = _default_codebase_path(None)
    settings = Settings(codebase_path=default_codebase)
    collection_meta = _collection_meta(settings)
    return {
        "service": "LegacyLens API",
        "status": "ok",
        "health": "/health",
        "query": "/query",
        "query_stream": "/query/stream",
        "callers": "/callers/{symbol}",
        "graph": "/graph/{symbol}",
        "default_codebase": default_codebase,
        "default_codebase_exists": str(Path(default_codebase).exists()).lower(),
        "qdrant_collection": settings.qdrant_collection,
        "qdrant_url": settings.qdrant_url,
        "embed_provider": settings.embed_provider,
        "embed_model": _query_meta(settings).embed_model,
        "llm_model": settings.llm_model,
        "docs": "/docs",
        **collection_meta,
    }


@app.post("/query", response_model=QueryResponse)
def query_codebase(request: QueryRequest, debug: bool = False) -> QueryResponse:
    query_is_vague, reason = _is_query_underspecified(request.query)
    if query_is_vague:
        raise HTTPException(status_code=422, detail=_query_hint_detail(reason))

    settings = Settings(codebase_path=_default_codebase_path(request.codebase_path))
    effective_debug = bool(debug or request.debug)
    has_vectors = _has_indexed_vectors(settings)
    if has_vectors is False:
        raise HTTPException(status_code=422, detail=_no_dataset_detail())

    retrieval = retrieve_with_diagnostics(request.query, settings, Path(settings.codebase_path))
    if retrieval.diagnostics.retrieval_error and not retrieval.hits:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Retrieval failed",
                "cause": retrieval.diagnostics.retrieval_error,
                "action": "Check embedding provider credentials, vector store connectivity, and ingestion status.",
            },
        )

    hits = retrieval.hits
    if not hits:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "No relevant context found",
                "confidence": retrieval.diagnostics.confidence_level,
                "action": "Refine query terms, ingest more code, or verify vector index coverage.",
                "suggestions": [
                    "Add an exact symbol name like READ-FILE or MAIN-PARA.",
                    "Include a file hint such as sample.cob.",
                    "Retry with broader phrasing and fewer constraints.",
                ],
                "retry": {"relaxed_thresholds": True, "how": "Click Retry with broader search in the UI."},
            },
        )
    if _should_abstain_for_low_evidence(
        hits,
        retrieval.diagnostics,
        settings,
        relaxed_thresholds=request.relaxed_thresholds,
    ):
        raise HTTPException(
            status_code=422,
            detail=_insufficient_evidence_detail(
                retrieval.diagnostics.top1_score,
                retrieval.diagnostics.score_gap,
            ),
        )

    fallback = _fallback_from_diagnostics(retrieval.diagnostics)
    try:
        answer = generate_answer(
            request.query,
            hits,
            settings,
            confidence_level=retrieval.diagnostics.confidence_level,
        )
    except Exception as exc:
        answer = generate_citations_only(hits)
        fallback = FallbackMeta(
            active=True,
            mode="citations_only",
            reason=_llm_failure_reason(exc),
            severity="error",
            degraded_quality=True,
        )

    sources = _sources_from_hits(hits)
    confidence = retrieval.diagnostics.confidence_level if retrieval.diagnostics else "unknown"
    query_meta = _query_meta(settings)

    debug_hits = sources[: min(5, len(sources))] if effective_debug else None
    return QueryResponse(
        answer_id=_new_answer_id(),
        answer=answer,
        sources=sources,
        diagnostics=asdict(retrieval.diagnostics),
        confidence_label=confidence,
        fallback=fallback,
        query_meta=query_meta,
        debug_hits=debug_hits,
    )


@app.post("/query/stream")
def query_codebase_stream(request: QueryRequest):
    query_is_vague, reason = _is_query_underspecified(request.query)
    if query_is_vague:
        detail = _query_hint_detail(reason)

        def blocked_stream():
            yield _stream_event("error", detail)

        headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
        return StreamingResponse(blocked_stream(), media_type="text/event-stream", headers=headers)

    settings = Settings(codebase_path=_default_codebase_path(request.codebase_path))
    has_vectors = _has_indexed_vectors(settings)
    if has_vectors is False:

        def empty_dataset_stream():
            yield _stream_event("error", _no_dataset_detail())

        headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
        return StreamingResponse(empty_dataset_stream(), media_type="text/event-stream", headers=headers)

    def event_stream():
        retrieval = retrieve_with_diagnostics(request.query, settings, Path(settings.codebase_path))
        hits = retrieval.hits
        if retrieval.diagnostics.retrieval_error and not hits:
            yield _stream_event(
                "error",
                {
                    "error": "Retrieval failed",
                    "cause": retrieval.diagnostics.retrieval_error,
                    "action": "Check embedding provider credentials, vector store connectivity, and ingestion status.",
                },
            )
            return

        if not hits:
            yield _stream_event(
                "error",
                {
                    "error": "No relevant context found",
                    "confidence": retrieval.diagnostics.confidence_level,
                    "suggestions": [
                        "Add an exact symbol name like READ-FILE or MAIN-PARA.",
                        "Include a file hint such as sample.cob.",
                        "Retry with broader phrasing and fewer constraints.",
                    ],
                },
            )
            return

        if _should_abstain_for_low_evidence(
            hits,
            retrieval.diagnostics,
            settings,
            relaxed_thresholds=request.relaxed_thresholds,
        ):
            yield _stream_event(
                "error",
                _insufficient_evidence_detail(
                    retrieval.diagnostics.top1_score,
                    retrieval.diagnostics.score_gap,
                ),
            )
            return

        sources = _sources_from_hits(hits)
        query_meta = _query_meta(settings)
        fallback = _fallback_from_diagnostics(retrieval.diagnostics)
        answer_parts: list[str] = []
        answer_id = _new_answer_id()
        emitted_tokens = False
        finish_reason = "stop"
        token_usage: dict[str, int] | None = None
        yield _stream_event(
            "context",
            {
                "answer_id": answer_id,
                "sources": [source.model_dump() for source in sources],
                "diagnostics": asdict(retrieval.diagnostics),
                "confidence_label": retrieval.diagnostics.confidence_level,
                "fallback": fallback.model_dump(),
                "query_meta": query_meta.model_dump(),
            },
        )

        try:
            for event in stream_answer_tokens(
                request.query,
                hits,
                settings,
                confidence_level=retrieval.diagnostics.confidence_level,
            ):
                if event.get("type") == "token":
                    token = str(event.get("token", ""))
                    if token:
                        emitted_tokens = True
                        answer_parts.append(token)
                        yield _stream_event("token", {"token": token})
                elif event.get("type") == "done":
                    finish_reason = str(event.get("finish_reason", "stop"))
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        token_usage = {
                            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                            "completion_tokens": int(usage.get("completion_tokens", 0)),
                            "total_tokens": int(usage.get("total_tokens", 0)),
                        }
        except Exception as exc:
            if emitted_tokens:
                yield _stream_event(
                    "error",
                    {
                        "error": "Answer stream failed",
                        "cause": str(exc),
                        "reason": _llm_failure_reason(exc),
                    },
                )
                return
            answer = generate_citations_only(hits)
            fallback = FallbackMeta(
                active=True,
                mode="citations_only",
                reason=_llm_failure_reason(exc),
                severity="error",
                degraded_quality=True,
            )
            payload = QueryResponse(
                answer_id=answer_id,
                answer=answer,
                sources=sources,
                diagnostics=asdict(retrieval.diagnostics),
                confidence_label=retrieval.diagnostics.confidence_level,
                fallback=fallback,
                query_meta=query_meta,
                debug_hits=None,
            ).model_dump()
            payload["stream"] = {"finish_reason": "fallback", "usage": None}
            yield _stream_event("done", payload)
            return

        answer = "".join(answer_parts)
        payload = QueryResponse(
            answer_id=answer_id,
            answer=answer,
            sources=sources,
            diagnostics=asdict(retrieval.diagnostics),
            confidence_label=retrieval.diagnostics.confidence_level,
            fallback=fallback,
            query_meta=query_meta,
            debug_hits=None,
        ).model_dump()
        payload["stream"] = {"finish_reason": finish_reason, "usage": token_usage}
        yield _stream_event("done", payload)

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@app.get("/callers/{symbol}", response_model=CallersResponse)
def callers(symbol: str, codebase_path: str | None = None) -> CallersResponse:
    settings = Settings(codebase_path=_default_codebase_path(codebase_path))
    graph_path = Path(settings.codebase_path) / settings.dependency_graph_file
    callers_list = find_callers(symbol, graph_path)
    if callers_list:
        return CallersResponse(symbol=symbol.upper(), callers=callers_list)

    normalized = symbol.upper()
    candidates = {f"PERFORM {normalized}", f"CALL '{normalized}'"}
    try:
        store = QdrantStore(settings)
        payloads = store.iter_payloads()
        callers_from_vector: set[str] = set()
        for payload in payloads:
            raw_used = payload.get("symbols_used", [])
            if not isinstance(raw_used, list):
                continue
            used = {str(item).upper() for item in raw_used}
            if used.intersection(candidates):
                symbol_name = payload.get("symbol_name")
                if isinstance(symbol_name, str) and symbol_name:
                    callers_from_vector.add(symbol_name)
        return CallersResponse(symbol=normalized, callers=sorted(callers_from_vector))
    except Exception:
        return CallersResponse(symbol=normalized, callers=[])


@app.get("/graph/{symbol}", response_model=GraphResponse)
def graph(symbol: str, codebase_path: str | None = None) -> GraphResponse:
    normalized = symbol.upper()
    settings = Settings(codebase_path=_default_codebase_path(codebase_path))
    graph_path = Path(settings.codebase_path) / settings.dependency_graph_file
    callers_index = load_callers_index(graph_path)
    index_edges = [(caller.upper(), callee.upper()) for callee, callers in callers_index.items() for caller in callers]

    payload_typed_edges: list[tuple[str, str, str]] = []
    try:
        store = QdrantStore(settings)
        payload_typed_edges = build_typed_edges_from_payloads(store.iter_payloads())
    except Exception:
        payload_typed_edges = []

    all_edges = sorted(set(index_edges + [(e[0], e[1]) for e in payload_typed_edges]))
    nodes, edges = find_symbol_neighborhood(normalized, all_edges)
    if not edges and normalized:
        callers_list = callers_index.get(normalized, [])
        edges = [(caller.upper(), normalized) for caller in callers_list]
        nodes = sorted({normalized, *[caller.upper() for caller in callers_list]})

    # Build relation lookup from typed payload edges
    relation_map: dict[tuple[str, str], str] = {(e[0], e[1]): e[2] for e in payload_typed_edges}

    graph_nodes = [
        GraphNode(id=node, label=node, role="target" if node == normalized else "related") for node in nodes
    ]
    graph_edges = [
        GraphEdge(source=source, target=target, relation=relation_map.get((source, target), "unknown"))
        for source, target in edges
    ]
    summary = GraphSummary(node_count=len(graph_nodes), edge_count=len(graph_edges))
    return GraphResponse(symbol=normalized, nodes=graph_nodes, edges=graph_edges, summary=summary)
