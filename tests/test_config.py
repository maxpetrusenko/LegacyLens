import pytest

from legacylens.config import Settings


def test_settings_reject_invalid_openai_embed_model() -> None:
    with pytest.raises(ValueError):
        Settings(openai_embed_model="ada-002")


def test_settings_exposes_timeout_aliases() -> None:
    settings = Settings(qdrant_timeout=2.2, semantic_timeout=3.3, embedding_timeout=4.4, llm_timeout=5.5)
    assert settings.qdrant_timeout_sec == 2.2
    assert settings.semantic_timeout_sec == 3.3
    assert settings.embedding_timeout_sec == 4.4
    assert settings.llm_timeout_sec == 5.5
