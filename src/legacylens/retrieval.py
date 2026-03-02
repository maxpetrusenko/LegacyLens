from __future__ import annotations

import subprocess
from pathlib import Path

from legacylens.config import Settings
from legacylens.embeddings import build_embedding_provider
from legacylens.models import RetrievalHit
from legacylens.vector_store import QdrantStore


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
    try:
        result = subprocess.run(
            ["rg", "-n", "--max-count", str(limit), "-e", query, str(codebase_path)],
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


def retrieve(query: str, settings: Settings, codebase_path: Path | None = None) -> list[RetrievalHit]:
    effective_codebase = codebase_path or Path(settings.codebase_path)
    semantic_hits: list[RetrievalHit] = []
    merged: list[RetrievalHit] = []

    try:
        provider = build_embedding_provider(settings)
        store = QdrantStore(settings)
        vector = provider.embed_query(query)
        semantic_hits = store.search(vector, settings.top_k)
    except Exception:
        semantic_hits = []

    if is_low_confidence(semantic_hits, settings.fallback_score_threshold, settings.fallback_gap_threshold):
        merged = dedupe_hits(semantic_hits + keyword_fallback(query, effective_codebase))
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
    return final_hits


__all__ = ["format_citation", "is_low_confidence", "dedupe_hits", "keyword_fallback", "retrieve"]
