from __future__ import annotations

from pathlib import Path

from legacylens.chunking import chunk_cobol_file
from legacylens.embeddings import build_embedding_provider
from legacylens.models import CodeChunk
from legacylens.vector_store import QdrantStore

COBOL_EXTENSIONS = {".cob", ".cbl", ".cpy", ".cobol"}


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


def ingest_codebase(codebase_path: Path, settings, batch_size: int = 64) -> dict[str, int]:
    chunks = chunk_codebase(codebase_path)
    if not chunks:
        return {"files": 0, "chunks": 0}

    provider = build_embedding_provider(settings)
    store = QdrantStore(settings)

    sample_vector = provider.embed_texts([chunks[0].text])[0]
    store.ensure_collection(vector_size=len(sample_vector))
    store.upsert_chunks([chunks[0]], [sample_vector])

    for i in range(1, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vectors = provider.embed_texts([chunk.text for chunk in batch])
        store.upsert_chunks(batch, vectors)

    return {"files": len(discover_cobol_files(codebase_path)), "chunks": len(chunks)}


__all__ = ["discover_cobol_files", "chunk_codebase", "ingest_codebase"]
