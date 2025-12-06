"""Fallback manager for resilient LLM requests.

Provides automatic failover between models with:
- Exponential backoff for retries
- Circuit breaker pattern
- Model health tracking
- Graceful degradation
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from app.services.llm.model_registry import (
    ModelCapability,
    ModelConfig,
    ModelRegistry,
    ModelStatus,
    get_model_registry,
)

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_ms: float = 100.0
    max_delay_ms: float = 10000.0
    exponential_base: float = 2.0
    jitter: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a retry attempt (in seconds)."""
        import random

        delay_ms = min(
            self.base_delay_ms * (self.exponential_base ** attempt),
            self.max_delay_ms,
        )

        if self.jitter:
            # Add ±25% jitter
            jitter_factor = 0.75 + random.random() * 0.5
            delay_ms *= jitter_factor

        return delay_ms / 1000.0  # Convert to seconds


@dataclass
class CircuitState:
    """State for a circuit breaker."""

    failures: int = 0
    last_failure: float = 0.0
    is_open: bool = False
    open_until: float = 0.0

    # Config
    failure_threshold: int = 5
    recovery_timeout: float = 30.0  # Seconds before half-open

    def record_failure(self) -> None:
        """Record a failure."""
        self.failures += 1
        self.last_failure = time.time()

        if self.failures >= self.failure_threshold:
            self.is_open = True
            self.open_until = time.time() + self.recovery_timeout
            logger.warning("Circuit breaker opened")

    def record_success(self) -> None:
        """Record a success (resets failures)."""
        self.failures = 0
        self.is_open = False
        self.open_until = 0.0

    def can_attempt(self) -> bool:
        """Check if an attempt is allowed."""
        if not self.is_open:
            return True

        # Check if we can try again (half-open)
        if time.time() >= self.open_until:
            return True

        return False


@dataclass
class FallbackResult:
    """Result from a fallback-aware request."""

    success: bool
    model_id: str
    result: Any = None
    error: str | None = None
    attempts: int = 0
    total_latency_ms: float = 0.0
    models_tried: list[str] = field(default_factory=list)


class FallbackManager:
    """
    Manages fallback logic for LLM requests.

    Features:
    - Automatic retry with exponential backoff
    - Model fallback when primary fails
    - Circuit breaker to prevent cascade failures
    - Performance-based model selection
    """

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        retry_config: RetryConfig | None = None,
    ):
        self._registry = registry or get_model_registry()
        self._retry_config = retry_config or RetryConfig()
        self._circuits: dict[str, CircuitState] = {}

    def _get_circuit(self, model_id: str) -> CircuitState:
        """Get or create circuit state for a model."""
        if model_id not in self._circuits:
            self._circuits[model_id] = CircuitState()
        return self._circuits[model_id]

    async def execute_with_fallback(
        self,
        request_func,
        required_capabilities: set[ModelCapability] | None = None,
        preferred_model: str | None = None,
    ) -> FallbackResult:
        """
        Execute a request with automatic fallback.

        Args:
            request_func: Async function that takes (model_config) and returns result
            required_capabilities: Required model capabilities
            preferred_model: Preferred model ID (tried first)

        Returns:
            FallbackResult with success/failure and details
        """
        start_time = time.time()
        models_tried: list[str] = []
        last_error: str | None = None

        # Get candidate models
        if preferred_model:
            preferred = self._registry.get(preferred_model)
            if preferred and preferred.status != ModelStatus.UNAVAILABLE:
                models = [preferred]
            else:
                models = []
        else:
            models = []

        # Add fallback models
        exclude = {preferred_model} if preferred_model else set()
        fallback_models = self._registry.list_models(
            required_capabilities=required_capabilities,
            status=ModelStatus.AVAILABLE,
        )
        models.extend(m for m in fallback_models if m.id not in exclude)

        if not models:
            return FallbackResult(
                success=False,
                model_id="",
                error="No available models match requirements",
                models_tried=models_tried,
            )

        # Try each model
        for model in models:
            circuit = self._get_circuit(model.id)

            if not circuit.can_attempt():
                logger.debug(f"Circuit open for {model.id}, skipping")
                continue

            models_tried.append(model.id)

            # Retry loop for this model
            for attempt in range(self._retry_config.max_retries + 1):
                try:
                    request_start = time.time()
                    result = await request_func(model)
                    latency_ms = (time.time() - request_start) * 1000

                    # Success!
                    circuit.record_success()
                    self._registry.record_request(
                        model.id,
                        success=True,
                        latency_ms=latency_ms,
                    )

                    return FallbackResult(
                        success=True,
                        model_id=model.id,
                        result=result,
                        attempts=attempt + 1,
                        total_latency_ms=(time.time() - start_time) * 1000,
                        models_tried=models_tried,
                    )

                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        f"Model {model.id} attempt {attempt + 1} failed: {e}"
                    )

                    circuit.record_failure()
                    self._registry.record_request(
                        model.id,
                        success=False,
                        latency_ms=0,
                    )

                    # Check if we should retry or move to next model
                    if attempt < self._retry_config.max_retries:
                        if circuit.can_attempt():
                            delay = self._retry_config.get_delay(attempt)
                            logger.debug(f"Retrying in {delay:.2f}s")
                            await asyncio.sleep(delay)
                        else:
                            break  # Circuit opened, move to next model
                    else:
                        break  # Max retries reached for this model

        # All models failed
        return FallbackResult(
            success=False,
            model_id=models_tried[-1] if models_tried else "",
            error=last_error or "All models failed",
            attempts=len(models_tried),
            total_latency_ms=(time.time() - start_time) * 1000,
            models_tried=models_tried,
        )

    async def stream_with_fallback(
        self,
        stream_func,
        required_capabilities: set[ModelCapability] | None = None,
        preferred_model: str | None = None,
    ) -> tuple[ModelConfig | None, AsyncGenerator | None, str | None]:
        """
        Get a streaming generator with automatic fallback.

        Args:
            stream_func: Async function that takes (model_config) and returns AsyncGenerator
            required_capabilities: Required model capabilities
            preferred_model: Preferred model ID

        Returns:
            Tuple of (model_config, generator, error)
        """
        # Get candidate models
        models = []

        if preferred_model:
            preferred = self._registry.get(preferred_model)
            if preferred and preferred.status != ModelStatus.UNAVAILABLE:
                circuit = self._get_circuit(preferred.id)
                if circuit.can_attempt():
                    models.append(preferred)

        # Add fallback models
        exclude = {preferred_model} if preferred_model else set()
        fallback_models = self._registry.list_models(
            required_capabilities=required_capabilities,
            status=ModelStatus.AVAILABLE,
        )
        for m in fallback_models:
            if m.id not in exclude:
                circuit = self._get_circuit(m.id)
                if circuit.can_attempt():
                    models.append(m)

        if not models:
            return None, None, "No available models match requirements"

        last_error = None

        # Try each model
        for model in models:
            try:
                generator = await stream_func(model)
                return model, generator, None

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Failed to start stream with {model.id}: {e}")

                circuit = self._get_circuit(model.id)
                circuit.record_failure()
                self._registry.record_request(model.id, success=False, latency_ms=0)

        return None, None, last_error or "All models failed"

    def reset_circuit(self, model_id: str) -> None:
        """Reset a model's circuit breaker."""
        if model_id in self._circuits:
            self._circuits[model_id] = CircuitState()
            logger.info(f"Reset circuit breaker for {model_id}")

    def reset_all_circuits(self) -> None:
        """Reset all circuit breakers."""
        self._circuits.clear()
        logger.info("Reset all circuit breakers")

    def get_circuit_states(self) -> dict[str, dict[str, Any]]:
        """Get all circuit breaker states."""
        return {
            model_id: {
                "failures": state.failures,
                "is_open": state.is_open,
                "open_until": state.open_until,
                "can_attempt": state.can_attempt(),
            }
            for model_id, state in self._circuits.items()
        }


# Global instance
_fallback_manager: FallbackManager | None = None


def get_fallback_manager() -> FallbackManager:
    """Get the global fallback manager."""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = FallbackManager()
    return _fallback_manager
