from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from legacylens.answer import generate_answer
from legacylens.config import Settings
from legacylens.retrieval import format_citation, retrieve

app = FastAPI(title="LegacyLens MVP")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    codebase_path: str | None = None


class SourceRef(BaseModel):
    citation: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceRef]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query_codebase(request: QueryRequest) -> QueryResponse:
    settings = Settings(codebase_path=request.codebase_path or ".")
    hits = retrieve(request.query, settings, Path(settings.codebase_path))
    answer = generate_answer(request.query, hits, settings)
    sources = [
        SourceRef(citation=format_citation(hit.file_path, hit.line_start, hit.line_end), score=hit.score)
        for hit in hits
    ]
    return QueryResponse(answer=answer, sources=sources)
