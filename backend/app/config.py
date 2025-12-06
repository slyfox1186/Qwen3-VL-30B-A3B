"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="../.env",  # Root .env file (one level up from backend/)
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "vlm-chat-api"
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    log_level: str = "INFO"

    # vLLM
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_api_key: str = "EMPTY"
    vllm_model: str = "Qwen3-30B-A3B-Instruct-AWQ-4bit"
    vllm_max_model_len: int = 46000  # Must match vLLM server's --max-model-len
    vllm_timeout: float = 120.0
    vllm_temperature: float = 0.6  # Qwen3 recommended

    # Qwen-Agent (enable for proper parallel tool calling)
    qwen_agent_enabled: bool = True

    @property
    def vllm_max_tokens(self) -> int:
        """Dynamic max tokens - 35% of context length for completion."""
        return int(self.vllm_max_model_len * 0.35)

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_data_dir: str = "./data/redis"
    redis_max_connections: int = 20
    redis_socket_timeout: float = 5.0

    # Rate Limiting
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Session
    session_ttl_seconds: int = 86400  # 24 hours
    max_history_messages: int = 50

    # Queue
    queue_stream_name: str = "llm_requests"
    queue_consumer_group: str = "llm_workers"
    queue_max_retries: int = 3

    # Web Access / SerpApi
    serpapi_api_key: str | None = None

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Observability
    sentry_dsn: str | None = None
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1
    enable_metrics: bool = True
    enable_structured_logging: bool = True

    # Embeddings / Vector Search (session-scoped)
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    embedding_batch_size: int = 32
    vector_search_top_k: int = 10
    enable_vector_search: bool = True

    # PostgreSQL (Long-term Memory)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "slyfox1186"
    postgres_password: str = "1812"
    postgres_database: str = "qwen3"
    postgres_pool_min: int = 5
    postgres_pool_max: int = 20

    # Memory Embedding (cross-conversation)
    memory_embedding_model: str = "google/embeddinggemma-300m-qat-q8_0-unquantized"
    memory_embedding_dimension: int = 768
    memory_search_top_k: int = 5
    memory_search_min_score: float = 0.5

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
