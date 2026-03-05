from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx

from legacylens.config import Settings
from legacylens.observability import observe_model_call


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...


class LocalHashEmbeddingProvider:
    def __init__(self, dimensions: int = 1536, settings: Settings | None = None) -> None:
        self.dimensions = dimensions
        self._token_pattern = re.compile(r"[A-Za-z0-9_-]+")
        self._settings = settings

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = self._token_pattern.findall(text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0.0:
            return [value / norm for value in vector]
        return vector

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        with observe_model_call(
            settings=self._settings,
            name="embedding.local_hash.embed_texts",
            run_type="embedding",
            provider="local_hash",
            model=f"local-hash-{self.dimensions}",
            input_count=len(texts),
            metadata={"input_chars": sum(len(text) for text in texts)},
        ) as span:
            vectors = [self._embed(text) for text in texts]
            span.set_outputs(
                {
                    "vector_count": len(vectors),
                    "dimensions": len(vectors[0]) if vectors else self.dimensions,
                }
            )
            return vectors

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


class VoyageEmbeddingProvider:
    def __init__(self, api_key: str, model: str, settings: Settings | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=60.0)
        self._settings = settings

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        with observe_model_call(
            settings=self._settings,
            name="embedding.voyage.embed_texts",
            run_type="embedding",
            provider="voyage",
            model=self.model,
            input_count=len(texts),
            metadata={"input_chars": sum(len(text) for text in texts)},
        ) as span:
            response = self._client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
            vectors = [row["embedding"] for row in payload["data"]]
            span.set_outputs(
                {
                    "vector_count": len(vectors),
                    "dimensions": len(vectors[0]) if vectors else 0,
                }
            )
            return vectors

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str, settings: Settings | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=60.0)
        self._settings = settings

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        with observe_model_call(
            settings=self._settings,
            name="embedding.openai.embed_texts",
            run_type="embedding",
            provider="openai",
            model=self.model,
            input_count=len(texts),
            metadata={"input_chars": sum(len(text) for text in texts)},
        ) as span:
            response = self._client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
            vectors = [row["embedding"] for row in payload["data"]]
            span.set_outputs(
                {
                    "vector_count": len(vectors),
                    "dimensions": len(vectors[0]) if vectors else 0,
                }
            )
            return vectors

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embed_provider.lower()
    if provider == "voyage":
        if not settings.voyage_api_key:
            raise ValueError("VOYAGE_API_KEY is required when EMBED_PROVIDER=voyage.")
        return VoyageEmbeddingProvider(settings.voyage_api_key, settings.voyage_model, settings)
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBED_PROVIDER=openai.")
        return OpenAIEmbeddingProvider(settings.openai_api_key, settings.openai_embed_model, settings)

    if provider == "auto":
        if settings.voyage_api_key:
            return VoyageEmbeddingProvider(settings.voyage_api_key, settings.voyage_model, settings)
        if settings.openai_api_key:
            return OpenAIEmbeddingProvider(settings.openai_api_key, settings.openai_embed_model, settings)
        raise ValueError(
            "No embedding provider configured. Set VOYAGE_API_KEY or OPENAI_API_KEY, "
            "or explicitly set EMBED_PROVIDER to a configured provider."
        )

    raise ValueError(f"Unsupported EMBED_PROVIDER '{settings.embed_provider}'. Use: auto, voyage, openai.")


__all__ = [
    "EmbeddingProvider",
    "LocalHashEmbeddingProvider",
    "VoyageEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "build_embedding_provider",
]
