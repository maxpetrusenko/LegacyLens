from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx

from legacylens.config import Settings


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...


class LocalHashEmbeddingProvider:
    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions
        self._token_pattern = re.compile(r"[A-Za-z0-9_-]+")

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
        return [self._embed(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed(query)


class VoyageEmbeddingProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=60.0)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
        return [row["embedding"] for row in payload["data"]]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(timeout=60.0)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
        return [row["embedding"] for row in payload["data"]]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embed_provider.lower()
    if provider in {"voyage", "auto"} and settings.voyage_api_key:
        return VoyageEmbeddingProvider(settings.voyage_api_key, settings.voyage_model)
    if provider in {"openai", "auto"} and settings.openai_api_key:
        return OpenAIEmbeddingProvider(settings.openai_api_key, settings.openai_embed_model)
    return LocalHashEmbeddingProvider()


__all__ = [
    "EmbeddingProvider",
    "LocalHashEmbeddingProvider",
    "VoyageEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "build_embedding_provider",
]
