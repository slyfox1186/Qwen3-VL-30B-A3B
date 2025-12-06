"""Health check endpoints."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_llm_client, get_redis_client
from app.models.schemas.common import (
    DetailedHealthResponse,
    HealthResponse,
    ServiceHealth,
)
from app.redis.client import RedisClient
from app.services.llm.client import VLLMClient

router = APIRouter(prefix="/health")


@router.get("", response_model=HealthResponse)
async def health_check():
    """
    Basic health check for load balancers.

    Returns 200 if service is running.
    """
    return HealthResponse(status="ok")


@router.get("/ready", response_model=DetailedHealthResponse)
async def readiness_check(
    request: Request,
    redis: Annotated[RedisClient, Depends(get_redis_client)],
    llm: Annotated[VLLMClient, Depends(get_llm_client)],
):
    """
    Readiness check verifying all dependencies.

    Returns 200 only if Redis and vLLM are accessible.
    Returns 503 if any service is unavailable.
    """
    services = {}
    overall_status = "ok"

    # Check Redis
    start = time.time()
    redis_healthy = await redis.health_check()
    redis_latency = (time.time() - start) * 1000

    if redis_healthy:
        services["redis"] = ServiceHealth(
            status="ok",
            latency_ms=round(redis_latency, 2),
        )
    else:
        services["redis"] = ServiceHealth(
            status="error",
            error="Connection failed",
        )
        overall_status = "degraded"

    # Check vLLM
    start = time.time()
    vllm_healthy = await llm.health_check()
    vllm_latency = (time.time() - start) * 1000

    if vllm_healthy:
        services["vllm"] = ServiceHealth(
            status="ok",
            latency_ms=round(vllm_latency, 2),
        )
    else:
        services["vllm"] = ServiceHealth(
            status="starting",
            error="Model loading - please wait",
        )
        overall_status = "starting"

    response = DetailedHealthResponse(
        status=overall_status,
        services=services,
    )

    return response
