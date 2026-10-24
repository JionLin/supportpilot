"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the SupportPilot backend."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    @property
    def resolved_embedding_base_url(self) -> str:
        """Return embedding API base URL, falling back to LLM base URL.

        Returns:
            str: Effective OpenAI-compatible base URL for embeddings.
        """
        return self.embedding_base_url or self.llm_base_url

    @property
    def resolved_embedding_api_key(self) -> str:
        """Return embedding API key, falling back to LLM API key.

        Returns:
            str: Effective API key for embeddings.
        """
        return self.embedding_api_key or self.llm_api_key

    database_url: str = (
        "postgresql+asyncpg://supportpilot:supportpilot@db:5432/supportpilot"
    )

    max_steps: int = 8
    max_tool_errors: int = 3
    request_timeout_s: int = 60

    admin_password: str = "change-me"

    mock_latency_ms: int = 0
    mock_failure_rate: float = 0.0
    mock_base_url: str = "http://127.0.0.1:8000"

    rag_distance_threshold: float = 0.35
    use_fake_embeddings: bool = False

    webhook_url: str = ""

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://frontend:3000",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Returns:
        Settings: Application settings loaded from the environment.
    """
    return Settings()
