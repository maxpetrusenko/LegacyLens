from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "legacylens_chunks"
    embed_provider: str = "auto"
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-code-2"
    openai_api_key: str | None = None
    openai_embed_model: str = "text-embedding-3-small"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    codebase_path: str = "."
    top_k: int = 10
    answer_k: int = 5
    fallback_score_threshold: float = 0.65
    fallback_gap_threshold: float = 0.15
    context_expand_lines: int = 10
    query_cache_size: int = 256
    dependency_graph_file: str = ".legacylens/dependency_graph.json"


__all__ = ["Settings"]
