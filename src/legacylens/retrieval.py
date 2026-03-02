from __future__ import annotations

import subprocess
import threading
from collections import OrderedDict
from time import perf_counter
from pathlib import Path

from legacylens.config import Settings
from legacylens.embeddings import build_embedding_provider
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult
from legacylens.vector_store import QdrantStore

_QUERY_CACHE: OrderedDict[str, list[float]] = OrderedDict()
_QUERY_CACHE_LOCK = threading.Lock()


def format_citation(file_path: str, line_start: int, line_end: int) -> str:
    return f"[{file_path}:{line_start}-{line_end}]"


def is_low_confidence(hits: list[RetrievalHit], tau: float, delta: float) -> bool:
    if not hits:
        return True
    top1 = hits[0].score
    top5 = hits[min(4, len(hits) - 1)].score
    return top1 < tau or (top1 - top5) < delta


def dedupe_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    deduped: dict[tuple[str, int], RetrievalHit] = {}
    for hit in hits:
        key = (hit.file_path, hit.line_start)
        current = deduped.get(key)
        if current is None or hit.score > current.score:
            deduped[key] = hit
    return sorted(deduped.values(), key=lambda hit: hit.score, reverse=True)


def _expand_context(codebase_path: Path, hit: RetrievalHit, expand_lines: int) -> str:
    target_file = codebase_path / hit.file_path
    try:
        lines = target_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return hit.text
    start = max(1, hit.line_start - expand_lines)
    end = min(len(lines), hit.line_end + expand_lines)
    return "\n".join(lines[start - 1 : end])


def keyword_fallback(query: str, codebase_path: Path, limit: int = 20) -> list[RetrievalHit]:
    globs = ["-g", "*.cob", "-g", "*.cbl", "-g", "*.cpy", "-g", "*.cobol"]
    try:
        result = subprocess.run(
            ["rg", "-n", "--max-count", str(limit), *globs, "-e", query, str(codebase_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []

    hits: list[RetrievalHit] = []
    for line in result.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        raw_path, raw_line, snippet = parts
        try:
            line_no = int(raw_line)
        except ValueError:
            continue
        raw_file_path = Path(raw_path)
        try:
            rel_path = str(raw_file_path.relative_to(codebase_path))
        except ValueError:
            rel_path = str(raw_file_path)
        hits.append(
            RetrievalHit(
                file_path=rel_path,
                line_start=line_no,
                line_end=line_no,
                text=snippet,
                score=0.3,
                metadata={"source": "ripgrep"},
            )
        )
    return hits


def _cache_key(settings: Settings, query: str) -> str:
    return "|".join(
        [
            settings.embed_provider.lower(),
            settings.voyage_model,
            settings.openai_embed_model,
            query.strip().lower(),
        ]
    )


def _embed_query_cached(query: str, settings: Settings, provider) -> list[float]:
    key = _cache_key(settings, query)
    with _QUERY_CACHE_LOCK:
        cached = _QUERY_CACHE.get(key)
        if cached is not None:
            _QUERY_CACHE.move_to_end(key)
            return cached

    vector = provider.embed_query(query)
    with _QUERY_CACHE_LOCK:
        _QUERY_CACHE[key] = vector
        while len(_QUERY_CACHE) > settings.query_cache_size:
            _QUERY_CACHE.popitem(last=False)
    return vector


def retrieve_with_diagnostics(
    query: str, settings: Settings, codebase_path: Path | None = None
) -> RetrievalResult:
    started = perf_counter()
    effective_codebase = codebase_path or Path(settings.codebase_path)
    semantic_hits: list[RetrievalHit] = []
    fallback_hits: list[RetrievalHit] = []
    merged: list[RetrievalHit] = []
    retrieval_error: str | None = None
    hybrid_triggered = False

    try:
        provider = build_embedding_provider(settings)
        store = QdrantStore(settings)
        vector = _embed_query_cached(query, settings, provider)
        semantic_hits = store.search(vector, settings.top_k)
    except Exception as exc:
        semantic_hits = []
        retrieval_error = str(exc)

    if is_low_confidence(semantic_hits, settings.fallback_score_threshold, settings.fallback_gap_threshold):
        hybrid_triggered = True
        fallback_hits = keyword_fallback(query, effective_codebase)
        merged = dedupe_hits(semantic_hits + fallback_hits)
    else:
        merged = dedupe_hits(semantic_hits)

    final_hits: list[RetrievalHit] = []
    for hit in merged[: settings.answer_k]:
        expanded = _expand_context(effective_codebase, hit, settings.context_expand_lines)
        final_hits.append(
            RetrievalHit(
                file_path=hit.file_path,
                line_start=hit.line_start,
                line_end=hit.line_end,
                text=expanded,
                score=hit.score,
                metadata=hit.metadata,
            )
        )
    diagnostics = RetrievalDiagnostics(
        latency_ms=int((perf_counter() - started) * 1000),
        top1_score=semantic_hits[0].score if semantic_hits else 0.0,
        chunks_returned=len(final_hits),
        hybrid_triggered=hybrid_triggered,
        semantic_hits=len(semantic_hits),
        fallback_hits=len(fallback_hits),
        retrieval_error=retrieval_error,
    )
    return RetrievalResult(hits=final_hits, diagnostics=diagnostics)


def retrieve(query: str, settings: Settings, codebase_path: Path | None = None) -> list[RetrievalHit]:
    return retrieve_with_diagnostics(query, settings, codebase_path).hits


__all__ = [
    "format_citation",
    "is_low_confidence",
    "dedupe_hits",
    "keyword_fallback",
    "retrieve",
    "retrieve_with_diagnostics",
]
