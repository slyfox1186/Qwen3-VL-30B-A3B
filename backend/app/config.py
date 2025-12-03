"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
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
    vllm_model: str = "Qwen3-VL-30B-A3B-Instruct-AWQ-4bit"
    vllm_max_tokens: int = 2048
    vllm_timeout: float = 120.0

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

    # Image
    max_image_size_mb: int = 10
    max_images_per_message: int = 1
    allowed_image_formats: list[str] = ["jpeg", "jpg", "png", "gif", "webp"]

    # Web Access / SerpApi
    serpapi_api_key: str | None = None

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def max_image_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.max_image_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
