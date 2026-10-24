from functools import lru_cache
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=ROOT / "config.yaml",
        env_file=ROOT / ".env",
        extra="ignore",
    )

    # Secrets (from .env)
    api_key: str = "change-me"
    google_api_key: str = ""
    id_hash_salt: str = "dev-salt"

    # LLM
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 400
    llm_thinking_level: str = "low"
    llm_max_retries: int = 4

    # Models
    embed_model: str = "BAAI/bge-m3"
    embed_batch_size: int = 16
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    query_rewrite_enabled: bool = True

    # Chunking and retrieval
    chunk_gap_minutes: int = 30
    window_size: int = 10
    window_overlap: int = 3
    max_chunk_tokens: int = 400
    min_chunk_chars: int = 80
    vector_top_k: int = 20
    bm25_top_k: int = 20
    rrf_k: int = 60
    rerank_top_n: int = 20
    final_top_k: int = 5
    min_relevance: float = -8.0

    # Extraction and general
    action_min_confidence: float = 0.6
    timezone: str = "Asia/Kolkata"
    rate_limit_per_min: int = 10

    # Storage (relative paths resolve against the repo root)
    db_url: str = "sqlite:///data/app.db"
    chroma_dir: str = "data/chroma_data"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
