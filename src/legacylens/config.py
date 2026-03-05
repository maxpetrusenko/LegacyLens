from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "legacylens_chunks"
    qdrant_timeout: float = 1.2
    embed_provider: str = "openai"
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-code-2"
    openai_api_key: str | None = None
    openai_embed_model: str = "text-embedding-3-small"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    codebase_path: str = "."
    top_k: int = 10
    answer_k: int = 5
    fallback_score_threshold: float = 0.65
    fallback_gap_threshold: float = 0.15
    confidence_low_threshold: float = 0.15
    confidence_medium_threshold: float = 0.35
    answer_min_top1_score: float = 0.30
    answer_min_score_gap: float = 0.02
    semantic_timeout: float = 1.5
    embedding_timeout: float = 20.0
    llm_timeout: float = 30.0
    context_expand_lines: int = 10
    query_cache_size: int = 256
    dependency_graph_file: str = ".legacylens/dependency_graph.json"
    target_min_files: int = 50
    target_min_loc: int = 10000
    langchain_api_key: str | None = None
    langchain_org_id: str | None = None
    langsmith_workspace_id: str | None = None
    observability_enabled: bool = True
    observability_project: str = "LegacyLens"

    @property
    def qdrant_timeout_sec(self) -> float:
        return self.qdrant_timeout

    @property
    def semantic_timeout_sec(self) -> float:
        return self.semantic_timeout

    @property
    def embedding_timeout_sec(self) -> float:
        return self.embedding_timeout

    @property
    def llm_timeout_sec(self) -> float:
        return self.llm_timeout

    @model_validator(mode="after")
    def _validate_models(self) -> "Settings":
        allowed_embed_models = {"text-embedding-3-small", "text-embedding-3-large"}
        if self.openai_embed_model not in allowed_embed_models:
            allowed = ", ".join(sorted(allowed_embed_models))
            raise ValueError(f"OPENAI_EMBED_MODEL must be one of: {allowed}.")
        return self


__all__ = ["Settings"]
