from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from legacylens.config import Settings
from legacylens.models import CodeChunk, RetrievalHit


class QdrantStore:
    def __init__(self, settings: Settings) -> None:
        self.collection_name = settings.qdrant_collection
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    def ensure_collection(self, vector_size: int) -> None:
        collections = self.client.get_collections().collections
        names = {item.name for item in collections}
        if self.collection_name in names:
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def upsert_chunks(self, chunks: list[CodeChunk], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        points = [
            PointStruct(
                id=chunk.point_id(),
                vector=vector,
                payload=chunk.payload(),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(self, vector: list[float], limit: int) -> list[RetrievalHit]:
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit,
            with_payload=True,
        )
        hits: list[RetrievalHit] = []
        for result in results:
            payload = dict(result.payload or {})
            hits.append(
                RetrievalHit(
                    file_path=payload.get("file_path", ""),
                    line_start=int(payload.get("line_start", 1)),
                    line_end=int(payload.get("line_end", 1)),
                    text=payload.get("text", ""),
                    score=float(result.score),
                    metadata=payload,
                )
            )
        return hits


__all__ = ["QdrantStore"]
