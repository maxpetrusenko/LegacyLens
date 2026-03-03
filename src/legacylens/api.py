from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from legacylens.answer import generate_answer
from legacylens.config import Settings
from legacylens.dependency_graph import find_callers
from legacylens.retrieval import format_citation, retrieve_with_diagnostics
from legacylens.vector_store import QdrantStore

app = FastAPI(title="LegacyLens MVP")
WEB_DIR = Path(__file__).parent / "web"
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    codebase_path: str | None = None


class SourceRef(BaseModel):
    citation: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    diagnostics: dict[str, int | float | bool | str | None]


class CallersResponse(BaseModel):
    symbol: str
    callers: list[str]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/meta")
def meta() -> dict[str, str]:
    return {
        "service": "LegacyLens API",
        "status": "ok",
        "health": "/health",
        "query": "/query",
        "callers": "/callers/{symbol}",
        "docs": "/docs",
    }


@app.post("/query", response_model=QueryResponse)
def query_codebase(request: QueryRequest) -> QueryResponse:
    settings = Settings(codebase_path=request.codebase_path or ".")
    retrieval = retrieve_with_diagnostics(request.query, settings, Path(settings.codebase_path))
    hits = retrieval.hits
    answer = generate_answer(request.query, hits, settings)
    sources = [
        SourceRef(citation=format_citation(hit.file_path, hit.line_start, hit.line_end), score=hit.score)
        for hit in hits
    ]
    return QueryResponse(answer=answer, sources=sources, diagnostics=asdict(retrieval.diagnostics))


@app.get("/callers/{symbol}", response_model=CallersResponse)
def callers(symbol: str, codebase_path: str | None = None) -> CallersResponse:
    settings = Settings(codebase_path=codebase_path or ".")
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
