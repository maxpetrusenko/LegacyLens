from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import subprocess
import threading
from collections import OrderedDict
from pathlib import Path
import re
from time import perf_counter

from legacylens.config import Settings
from legacylens.embeddings import build_embedding_provider
from legacylens.models import RetrievalDiagnostics, RetrievalHit, RetrievalResult
from legacylens.vector_store import QdrantStore

_QUERY_CACHE: OrderedDict[str, list[float]] = OrderedDict()
_QUERY_CACHE_LOCK = threading.Lock()
WORD_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
FILE_PATTERN = re.compile(r"\b[\w./-]+\.(?:cob|cbl|cpy|cobol)\b", re.IGNORECASE)
QUOTED_PATTERN = re.compile(r"[\"']([A-Za-z0-9_-]+)[\"']")
DEPENDENCY_PATTERN = re.compile(r"\b(?:perform|call)\s+([A-Za-z0-9-]+)", re.IGNORECASE)


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


def _normalize_entity(token: str) -> str:
    return token.strip().strip("\"'").upper()


def parse_query_intent_entities(query: str) -> tuple[str, list[str], str]:
    normalized_query = query.strip()
    lowered = normalized_query.lower()
    intent = "general"
    if any(word in lowered for word in ("caller", "callers", "call ", "calls", "called", "perform", "dependency", "depends", "invoke")):
        intent = "dependency"
    elif any(word in lowered for word in ("file io", "i/o", "read", "write", "open", "close", "fd")):
        intent = "io"
    elif any(word in lowered for word in ("error", "exception", "invalid key", "at end", "failure")):
        intent = "error_handling"
    elif any(word in lowered for word in ("where", "location", "line", "file")):
        intent = "location"

    entities: list[str] = []
    for match in QUOTED_PATTERN.finditer(normalized_query):
        entity = _normalize_entity(match.group(1))
        if entity and entity not in entities:
            entities.append(entity)
    for match in DEPENDENCY_PATTERN.finditer(normalized_query):
        entity = _normalize_entity(match.group(1))
        if entity and entity not in entities:
            entities.append(entity)
    for match in FILE_PATTERN.finditer(normalized_query):
        entity = match.group(0)
        if entity and entity not in entities:
            entities.append(entity)
    for token in WORD_PATTERN.findall(normalized_query):
        if "-" in token and len(token) > 2:
            entity = _normalize_entity(token)
            if entity not in entities:
                entities.append(entity)

    expanded_query = normalized_query
    if entities:
        expanded_query = f"{normalized_query} {' '.join(entities)}"
    return intent, entities, expanded_query


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


def rerank_hits(hits: list[RetrievalHit], query: str, intent: str, entities: list[str]) -> list[RetrievalHit]:
    if not hits:
        return hits
    query_terms = {term.lower() for term in WORD_PATTERN.findall(query)}
    entity_count = max(1, len(entities))
    reranked: list[tuple[float, RetrievalHit]] = []

    for hit in hits:
        searchable = f"{hit.file_path} {hit.text}".upper()
        hit_terms = {term.lower() for term in WORD_PATTERN.findall(hit.file_path + " " + hit.text)}
        lexical_overlap = (len(query_terms & hit_terms) / len(query_terms)) if query_terms else 0.0
        entity_match = sum(1 for entity in entities if entity in searchable) / entity_count
        tags = hit.metadata.get("tags", []) if isinstance(hit.metadata, dict) else []
        tags_upper = {str(tag).upper() for tag in tags}
        intent_bonus = 0.0
        if intent == "dependency" and ("PERFORM" in searchable or "CALL" in searchable):
            intent_bonus = 0.1
        elif intent == "io" and "IO" in tags_upper:
            intent_bonus = 0.1
        elif intent == "error_handling" and "ERROR_HANDLING" in tags_upper:
            intent_bonus = 0.1
        elif intent == "location" and any(entity.lower().endswith((".cob", ".cbl", ".cpy", ".cobol")) for entity in entities):
            intent_bonus = 0.1

        rerank_score = (hit.score * 0.65) + (lexical_overlap * 0.2) + (entity_match * 0.15) + intent_bonus
        metadata = dict(hit.metadata)
        metadata["rerank_score"] = round(rerank_score, 6)
        reranked.append(
            (
                rerank_score,
                RetrievalHit(
                    file_path=hit.file_path,
                    line_start=hit.line_start,
                    line_end=hit.line_end,
                    text=hit.text,
                    score=hit.score,
                    metadata=metadata,
                ),
            )
        )
    reranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in reranked]


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
    query_intent, query_entities, expanded_query = parse_query_intent_entities(query)

    try:
        def _semantic_retrieve() -> list[RetrievalHit]:
            provider = build_embedding_provider(settings)
            store = QdrantStore(settings)
            vector = _embed_query_cached(expanded_query, settings, provider)
            return store.search(vector, settings.top_k)

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_semantic_retrieve)
        try:
            semantic_hits = future.result(timeout=settings.semantic_timeout_sec)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    except FutureTimeoutError:
        semantic_hits = []
        retrieval_error = "semantic retrieval timed out"
    except Exception as exc:
        semantic_hits = []
        retrieval_error = str(exc)

    if is_low_confidence(semantic_hits, settings.fallback_score_threshold, settings.fallback_gap_threshold):
        hybrid_triggered = True
        fallback_hits = keyword_fallback(expanded_query, effective_codebase)
        merged = dedupe_hits(semantic_hits + fallback_hits)
    else:
        merged = dedupe_hits(semantic_hits)
    merged = rerank_hits(merged, query, query_intent, query_entities)

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
        query_intent=query_intent,
        query_entities=len(query_entities),
        rerank_applied=bool(merged),
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
    "parse_query_intent_entities",
    "rerank_hits",
    "retrieve",
    "retrieve_with_diagnostics",
]
