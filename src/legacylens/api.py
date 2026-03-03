from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from legacylens.answer import generate_answer
from legacylens.config import Settings
from legacylens.dependency_graph import (
    build_edges_from_payloads,
    find_callers,
    find_symbol_neighborhood,
    load_callers_index,
)
from legacylens.retrieval import format_citation, retrieve_with_diagnostics
from legacylens.vector_store import QdrantStore

app = FastAPI(title="LegacyLens MVP")
WEB_DIR = Path(__file__).parent / "web"
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


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


class SourceRef(BaseModel):
    citation: str
    score: float
    text: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    diagnostics: dict[str, int | float | bool | str | None]
    confidence_label: str
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


class GraphResponse(BaseModel):
    symbol: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/meta")
def meta() -> dict[str, str]:
    default_codebase = _default_codebase_path(None)
    return {
        "service": "LegacyLens API",
        "status": "ok",
        "health": "/health",
        "query": "/query",
        "callers": "/callers/{symbol}",
        "graph": "/graph/{symbol}",
        "default_codebase": default_codebase,
        "default_codebase_exists": str(Path(default_codebase).exists()).lower(),
        "docs": "/docs",
    }


@app.post("/query", response_model=QueryResponse)
def query_codebase(request: QueryRequest, debug: bool = False) -> QueryResponse:
    settings = Settings(codebase_path=_default_codebase_path(request.codebase_path))
    retrieval = retrieve_with_diagnostics(request.query, settings, Path(settings.codebase_path))
    hits = retrieval.hits
    answer = generate_answer(request.query, hits, settings)
    sources = [
        SourceRef(
            citation=format_citation(hit.file_path, hit.line_start, hit.line_end),
            score=hit.score,
            text=hit.text,
        )
        for hit in hits
    ]
    top_score = retrieval.diagnostics.top1_score if retrieval.diagnostics else 0.0
    if top_score >= 0.35:
        confidence = "high"
    elif top_score >= 0.15:
        confidence = "medium"
    else:
        confidence = "low"

    debug_hits = sources[: min(5, len(sources))] if debug else None
    return QueryResponse(
        answer=answer,
        sources=sources,
        diagnostics=asdict(retrieval.diagnostics),
        confidence_label=confidence,
        debug_hits=debug_hits,
    )


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

    payload_edges: list[tuple[str, str]] = []
    try:
        store = QdrantStore(settings)
        payload_edges = build_edges_from_payloads(store.iter_payloads())
    except Exception:
        payload_edges = []

    all_edges = sorted(set(index_edges + payload_edges))
    nodes, edges = find_symbol_neighborhood(normalized, all_edges)
    if not edges and normalized:
        callers_list = callers_index.get(normalized, [])
        edges = [(caller.upper(), normalized) for caller in callers_list]
        nodes = sorted({normalized, *[caller.upper() for caller in callers_list]})

    graph_nodes = [
        GraphNode(id=node, label=node, role="target" if node == normalized else "related") for node in nodes
    ]
    graph_edges = [GraphEdge(source=source, target=target) for source, target in edges]
    return GraphResponse(symbol=normalized, nodes=graph_nodes, edges=graph_edges)
