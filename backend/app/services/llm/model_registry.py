"""Model registry for multi-model support.

Manages available models with their capabilities, endpoints, and metadata.
Enables dynamic model selection based on requirements and availability.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ModelCapability(Enum):
    """Capabilities a model may support."""

    TEXT = "text"
    VISION = "vision"
    TOOL_USE = "tool_use"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    THINKING = "thinking"  # Extended reasoning
    LONG_CONTEXT = "long_context"  # > 32K tokens


class ModelStatus(Enum):
    """Current status of a model."""

    AVAILABLE = "available"
    DEGRADED = "degraded"  # Working but with issues
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class ModelMetrics:
    """Performance metrics for a model."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    avg_tokens_per_second: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def record_request(
        self,
        success: bool,
        latency_ms: float,
        tokens: int = 0,
    ) -> None:
        """Record a request result."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
            self.total_latency_ms += latency_ms
            self.total_tokens += tokens
            if latency_ms > 0:
                tps = (tokens / latency_ms) * 1000
                # Exponential moving average
                if self.avg_tokens_per_second == 0:
                    self.avg_tokens_per_second = tps
                else:
                    self.avg_tokens_per_second = 0.9 * self.avg_tokens_per_second + 0.1 * tps
        else:
            self.failed_requests += 1


@dataclass
class ModelConfig:
    """Configuration for a model."""

    id: str  # Unique identifier
    name: str  # Display name
    provider: str  # e.g., "vllm", "openai", "anthropic"
    endpoint: str  # Base URL
    api_key: str | None = None
    model_name: str | None = None  # Model name for API calls (if different from id)
    capabilities: set[ModelCapability] = field(default_factory=set)
    max_tokens: int = 4096
    context_window: int = 32768
    cost_per_1k_input: float = 0.0  # Cost tracking
    cost_per_1k_output: float = 0.0
    priority: int = 0  # Higher = preferred
    status: ModelStatus = ModelStatus.UNKNOWN
    metrics: ModelMetrics = field(default_factory=ModelMetrics)
    extra: dict[str, Any] = field(default_factory=dict)

    def has_capability(self, cap: ModelCapability) -> bool:
        """Check if model has a capability."""
        return cap in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "capabilities": [c.value for c in self.capabilities],
            "max_tokens": self.max_tokens,
            "context_window": self.context_window,
            "status": self.status.value,
            "priority": self.priority,
            "metrics": {
                "success_rate": self.metrics.success_rate,
                "avg_latency_ms": self.metrics.avg_latency_ms,
                "avg_tokens_per_second": self.metrics.avg_tokens_per_second,
                "total_requests": self.metrics.total_requests,
            },
        }


class ModelRegistry:
    """
    Registry of available models.

    Features:
    - Register models with capabilities and endpoints
    - Query models by capability requirements
    - Track model performance metrics
    - Select best model based on requirements
    """

    def __init__(self):
        self._models: dict[str, ModelConfig] = {}
        self._load_default_models()

    def _load_default_models(self) -> None:
        """Load default model configurations."""
        from app.config import get_settings

        settings = get_settings()

        # Primary vLLM model (Qwen3-VL)
        self.register(ModelConfig(
            id="qwen3-vl-30b",
            name="Qwen3-VL 30B",
            provider="vllm",
            endpoint=settings.vllm_base_url,
            model_name=settings.vllm_model,
            capabilities={
                ModelCapability.TEXT,
                ModelCapability.VISION,
                ModelCapability.TOOL_USE,
                ModelCapability.STREAMING,
                ModelCapability.THINKING,
                ModelCapability.LONG_CONTEXT,
            },
            max_tokens=8192,
            context_window=131072,
            priority=100,  # Highest priority
            status=ModelStatus.AVAILABLE,
        ))

        logger.info(f"Loaded {len(self._models)} default models")

    def register(self, config: ModelConfig) -> None:
        """Register a model."""
        self._models[config.id] = config
        logger.debug(f"Registered model: {config.id} ({config.name})")

    def unregister(self, model_id: str) -> bool:
        """Unregister a model."""
        if model_id in self._models:
            del self._models[model_id]
            return True
        return False

    def get(self, model_id: str) -> ModelConfig | None:
        """Get a model by ID."""
        return self._models.get(model_id)

    def list_models(
        self,
        required_capabilities: set[ModelCapability] | None = None,
        status: ModelStatus | None = None,
    ) -> list[ModelConfig]:
        """
        List models, optionally filtered by capabilities and status.

        Args:
            required_capabilities: Only include models with all these capabilities
            status: Only include models with this status

        Returns:
            List of matching models, sorted by priority
        """
        models = list(self._models.values())

        if required_capabilities:
            models = [
                m for m in models
                if required_capabilities.issubset(m.capabilities)
            ]

        if status:
            models = [m for m in models if m.status == status]

        # Sort by priority (descending), then by success rate
        return sorted(
            models,
            key=lambda m: (m.priority, m.metrics.success_rate),
            reverse=True,
        )

    def get_best_model(
        self,
        required_capabilities: set[ModelCapability] | None = None,
        exclude: set[str] | None = None,
    ) -> ModelConfig | None:
        """
        Get the best available model for given requirements.

        Args:
            required_capabilities: Required model capabilities
            exclude: Model IDs to exclude (e.g., already tried)

        Returns:
            Best matching model or None
        """
        exclude = exclude or set()

        models = self.list_models(
            required_capabilities=required_capabilities,
            status=ModelStatus.AVAILABLE,
        )

        for model in models:
            if model.id not in exclude:
                return model

        # Also consider degraded models
        degraded = self.list_models(
            required_capabilities=required_capabilities,
            status=ModelStatus.DEGRADED,
        )

        for model in degraded:
            if model.id not in exclude:
                return model

        return None

    def update_status(self, model_id: str, status: ModelStatus) -> None:
        """Update a model's status."""
        if model := self.get(model_id):
            model.status = status
            logger.info(f"Model {model_id} status updated to {status.value}")

    def record_request(
        self,
        model_id: str,
        success: bool,
        latency_ms: float,
        tokens: int = 0,
    ) -> None:
        """Record a request result for metrics."""
        if model := self.get(model_id):
            model.metrics.record_request(success, latency_ms, tokens)

            # Auto-update status based on recent performance
            if model.metrics.total_requests >= 10:
                if model.metrics.success_rate < 0.5:
                    self.update_status(model_id, ModelStatus.UNAVAILABLE)
                elif model.metrics.success_rate < 0.9:
                    self.update_status(model_id, ModelStatus.DEGRADED)
                else:
                    self.update_status(model_id, ModelStatus.AVAILABLE)

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        models = list(self._models.values())
        return {
            "total_models": len(models),
            "available": sum(1 for m in models if m.status == ModelStatus.AVAILABLE),
            "degraded": sum(1 for m in models if m.status == ModelStatus.DEGRADED),
            "unavailable": sum(1 for m in models if m.status == ModelStatus.UNAVAILABLE),
            "models": [m.to_dict() for m in models],
        }


# Global registry singleton
_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    """Get the global model registry."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
