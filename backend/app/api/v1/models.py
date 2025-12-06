"""Model management API endpoints.

Provides endpoints for:
- Listing available models
- Getting model details
- Model health status
- Circuit breaker management
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm.fallback_manager import get_fallback_manager
from app.services.llm.model_registry import (
    ModelCapability,
    ModelStatus,
    get_model_registry,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models")


class ModelInfo(BaseModel):
    """Model information for API response."""

    id: str
    name: str
    provider: str
    capabilities: list[str]
    max_tokens: int
    context_window: int
    status: str
    priority: int
    metrics: dict[str, Any]


class ModelListResponse(BaseModel):
    """Response with list of available models."""

    models: list[ModelInfo]
    total: int
    available: int


class ModelStatsResponse(BaseModel):
    """Model registry statistics."""

    total_models: int
    available: int
    degraded: int
    unavailable: int
    models: list[dict[str, Any]]


class CircuitStatesResponse(BaseModel):
    """Circuit breaker states for all models."""

    circuits: dict[str, dict[str, Any]]


class ModelStatusUpdate(BaseModel):
    """Request to update model status."""

    status: str = Field(..., description="New status: available, degraded, unavailable")


@router.get("", response_model=ModelListResponse)
async def list_models(
    capability: str | None = None,
    status: str | None = None,
) -> ModelListResponse:
    """
    List all available models.

    Args:
        capability: Filter by capability (text, vision, tool_use, etc.)
        status: Filter by status (available, degraded, unavailable)
    """
    registry = get_model_registry()

    # Parse capability filter
    required_caps = None
    if capability:
        try:
            required_caps = {ModelCapability(capability)}
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid capability: {capability}",
            ) from None

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = ModelStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}",
            ) from None

    models = registry.list_models(
        required_capabilities=required_caps,
        status=status_filter,
    )

    model_infos = [
        ModelInfo(
            id=m.id,
            name=m.name,
            provider=m.provider,
            capabilities=[c.value for c in m.capabilities],
            max_tokens=m.max_tokens,
            context_window=m.context_window,
            status=m.status.value,
            priority=m.priority,
            metrics={
                "success_rate": m.metrics.success_rate,
                "avg_latency_ms": m.metrics.avg_latency_ms,
                "avg_tokens_per_second": m.metrics.avg_tokens_per_second,
                "total_requests": m.metrics.total_requests,
            },
        )
        for m in models
    ]

    available_count = sum(1 for m in models if m.status == ModelStatus.AVAILABLE)

    return ModelListResponse(
        models=model_infos,
        total=len(model_infos),
        available=available_count,
    )


@router.get("/stats", response_model=ModelStatsResponse)
async def get_model_stats() -> ModelStatsResponse:
    """Get model registry statistics."""
    registry = get_model_registry()
    stats = registry.get_stats()
    return ModelStatsResponse(**stats)


@router.get("/circuits", response_model=CircuitStatesResponse)
async def get_circuit_states() -> CircuitStatesResponse:
    """Get circuit breaker states for all models."""
    manager = get_fallback_manager()
    return CircuitStatesResponse(circuits=manager.get_circuit_states())


@router.post("/circuits/reset")
async def reset_all_circuits() -> dict[str, Any]:
    """Reset all circuit breakers."""
    manager = get_fallback_manager()
    manager.reset_all_circuits()
    return {"success": True, "message": "All circuit breakers reset"}


@router.get("/{model_id}", response_model=ModelInfo)
async def get_model(model_id: str) -> ModelInfo:
    """Get details of a specific model."""
    registry = get_model_registry()
    model = registry.get(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    return ModelInfo(
        id=model.id,
        name=model.name,
        provider=model.provider,
        capabilities=[c.value for c in model.capabilities],
        max_tokens=model.max_tokens,
        context_window=model.context_window,
        status=model.status.value,
        priority=model.priority,
        metrics={
            "success_rate": model.metrics.success_rate,
            "avg_latency_ms": model.metrics.avg_latency_ms,
            "avg_tokens_per_second": model.metrics.avg_tokens_per_second,
            "total_requests": model.metrics.total_requests,
        },
    )


@router.patch("/{model_id}/status")
async def update_model_status(
    model_id: str,
    update: ModelStatusUpdate,
) -> dict[str, Any]:
    """Update a model's status manually."""
    registry = get_model_registry()
    model = registry.get(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    try:
        new_status = ModelStatus(update.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {update.status}",
        ) from None

    registry.update_status(model_id, new_status)

    return {
        "success": True,
        "model_id": model_id,
        "new_status": new_status.value,
    }


@router.post("/{model_id}/circuits/reset")
async def reset_model_circuit(model_id: str) -> dict[str, Any]:
    """Reset circuit breaker for a specific model."""
    registry = get_model_registry()
    model = registry.get(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    manager = get_fallback_manager()
    manager.reset_circuit(model_id)

    return {
        "success": True,
        "model_id": model_id,
        "message": "Circuit breaker reset",
    }
