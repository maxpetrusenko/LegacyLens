from __future__ import annotations

import logging
from pathlib import Path

from legacylens.chunking import chunk_cobol_file
from legacylens.dependency_graph import build_callers_index, save_callers_index
from legacylens.embeddings import build_embedding_provider
from legacylens.models import CodeChunk
from legacylens.vector_store import QdrantStore

COBOL_EXTENSIONS = {".cob", ".cbl", ".cpy", ".cobol", ".at"}
LOGGER = logging.getLogger(__name__)


def discover_cobol_files(codebase_path: Path) -> list[Path]:
    return [
        path
        for path in codebase_path.rglob("*")
        if path.is_file() and path.suffix.lower() in COBOL_EXTENSIONS
    ]


def chunk_codebase(codebase_path: Path) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    files = discover_cobol_files(codebase_path)
    for file_path in files:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        rel_path = str(file_path.relative_to(codebase_path))
        file_chunks = chunk_cobol_file(rel_path, text)
        chunks.extend(file_chunks)
    return chunks


def summarize_chunks(chunks: list[CodeChunk]) -> dict[str, int | float]:
    total_chunks = len(chunks)
    fallback_chunks = sum(1 for chunk in chunks if chunk.symbol_type == "fallback")
    fallback_ratio = (fallback_chunks / total_chunks) if total_chunks else 0.0
    return {
        "total_chunks": total_chunks,
        "fallback_chunks": fallback_chunks,
        "fallback_ratio": fallback_ratio,
    }


def ingest_codebase(codebase_path: Path, settings, batch_size: int = 64) -> dict[str, int | float]:
    chunks = chunk_codebase(codebase_path)
    files = discover_cobol_files(codebase_path)
    if not chunks:
        return {"files": 0, "chunks": 0, "fallback_chunks": 0, "fallback_ratio": 0.0, "dep_edges": 0}

    chunk_summary = summarize_chunks(chunks)
    fallback_ratio = chunk_summary["fallback_ratio"]
    if fallback_ratio > 0.30:
        LOGGER.warning("Parser misfiring: %.2f%% fallback chunks. Check DIVISION guard.", fallback_ratio * 100)

    provider = build_embedding_provider(settings)
    store = QdrantStore(settings)

    sample_vector = provider.embed_texts([chunks[0].text])[0]
    store.ensure_collection(vector_size=len(sample_vector))
    store.upsert_chunks([chunks[0]], [sample_vector])

    for i in range(1, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vectors = provider.embed_texts([chunk.text for chunk in batch])
        store.upsert_chunks(batch, vectors)

    callers_index = build_callers_index(chunks)
    graph_path = codebase_path / settings.dependency_graph_file
    save_callers_index(graph_path, callers_index)

    return {
        "files": len(files),
        "chunks": chunk_summary["total_chunks"],
        "fallback_chunks": chunk_summary["fallback_chunks"],
        "fallback_ratio": fallback_ratio,
        "dep_edges": sum(len(callers) for callers in callers_index.values()),
    }


__all__ = ["discover_cobol_files", "chunk_codebase", "summarize_chunks", "ingest_codebase"]
