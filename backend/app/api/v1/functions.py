"""Function calling API endpoints.

Provides endpoints for:
- Listing available functions
- Executing functions directly
- Getting OpenAI-compatible tool definitions
- Viewing execution audit logs
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.functions import FunctionExecutor, get_function_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/functions")


class FunctionCallRequest(BaseModel):
    """Request to execute a function."""

    name: str = Field(..., description="Function name to execute")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Function arguments",
    )


class FunctionCallResponse(BaseModel):
    """Response from function execution."""

    success: bool
    result: Any | None = None
    error: str | None = None
    execution_time_ms: float = 0.0
    from_cache: bool = False


class FunctionInfo(BaseModel):
    """Information about a registered function."""

    name: str
    description: str
    category: str
    cacheable: bool
    parameters: list[dict[str, Any]]


class FunctionListResponse(BaseModel):
    """Response with list of available functions."""

    functions: list[FunctionInfo]
    total: int


class ToolDefinitionsResponse(BaseModel):
    """OpenAI-compatible tool definitions."""

    tools: list[dict[str, Any]]


class AuditEntry(BaseModel):
    """Function execution audit entry."""

    function_name: str
    arguments: dict[str, Any]
    timestamp: float
    success: bool
    error: str | None = None
    execution_time_ms: float = 0.0
    result_hash: str | None = None


class AuditLogResponse(BaseModel):
    """Response with audit log entries."""

    entries: list[AuditEntry]
    total: int


class ExecutorStatsResponse(BaseModel):
    """Executor statistics."""

    cache_entries: int
    audit_entries: int
    cache_enabled: bool
    registered_functions: int


# Global executor instance
_executor: FunctionExecutor | None = None


def get_executor() -> FunctionExecutor:
    """Get or create the global function executor."""
    global _executor
    if _executor is None:
        _executor = FunctionExecutor()
    return _executor


@router.get("", response_model=FunctionListResponse)
async def list_functions(category: str | None = None) -> FunctionListResponse:
    """
    List all available functions.

    Args:
        category: Optional filter by category (math, datetime, text, utility)
    """
    registry = get_function_registry()
    function_names = registry.list_functions(category=category)

    functions = []
    for name in function_names:
        func_def = registry.get(name)
        if func_def:
            functions.append(FunctionInfo(
                name=func_def.name,
                description=func_def.description,
                category=func_def.category,
                cacheable=func_def.cacheable,
                parameters=[
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                        "default": p.default,
                        "enum": p.enum,
                    }
                    for p in func_def.parameters
                ],
            ))

    return FunctionListResponse(
        functions=functions,
        total=len(functions),
    )


@router.get("/tools", response_model=ToolDefinitionsResponse)
async def get_tool_definitions(
    include: str | None = None,
    exclude: str | None = None,
) -> ToolDefinitionsResponse:
    """
    Get OpenAI-compatible tool definitions for LLM integration.

    Args:
        include: Comma-separated list of function names to include
        exclude: Comma-separated list of function names to exclude
    """
    registry = get_function_registry()

    include_list = include.split(",") if include else None
    exclude_list = exclude.split(",") if exclude else None

    tools = registry.get_openai_tools(include=include_list, exclude=exclude_list)

    return ToolDefinitionsResponse(tools=tools)


@router.post("/execute", response_model=FunctionCallResponse)
async def execute_function(request: FunctionCallRequest) -> FunctionCallResponse:
    """
    Execute a function by name with given arguments.

    This is primarily for testing. In production, functions are
    called automatically by the LLM during chat.
    """
    executor = get_executor()

    try:
        result = await executor.execute(request.name, request.arguments)

        return FunctionCallResponse(
            success=result.success,
            result=result.result,
            error=result.error,
            execution_time_ms=result.execution_time_ms,
            from_cache=result.from_cache,
        )

    except Exception as e:
        logger.error(f"Function execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_log(
    limit: int = 100,
    function_name: str | None = None,
) -> AuditLogResponse:
    """
    Get recent function execution audit log.

    Args:
        limit: Maximum entries to return (default 100)
        function_name: Filter by function name
    """
    executor = get_executor()
    entries = executor.get_audit_log(limit=limit, function_name=function_name)

    return AuditLogResponse(
        entries=[
            AuditEntry(
                function_name=e.function_name,
                arguments=e.arguments,
                timestamp=e.timestamp,
                success=e.success,
                error=e.error,
                execution_time_ms=e.execution_time_ms,
                result_hash=e.result_hash,
            )
            for e in entries
        ],
        total=len(entries),
    )


@router.get("/stats", response_model=ExecutorStatsResponse)
async def get_executor_stats() -> ExecutorStatsResponse:
    """Get executor statistics including cache and audit info."""
    executor = get_executor()
    stats = executor.get_stats()

    return ExecutorStatsResponse(**stats)


@router.post("/cache/clear")
async def clear_cache() -> dict[str, Any]:
    """Clear the function result cache."""
    executor = get_executor()
    count = executor.clear_cache()

    return {
        "success": True,
        "entries_cleared": count,
    }


@router.get("/{name}", response_model=FunctionInfo)
async def get_function(name: str) -> FunctionInfo:
    """Get details of a specific function."""
    registry = get_function_registry()
    func_def = registry.get(name)

    if not func_def:
        raise HTTPException(status_code=404, detail=f"Function not found: {name}")

    return FunctionInfo(
        name=func_def.name,
        description=func_def.description,
        category=func_def.category,
        cacheable=func_def.cacheable,
        parameters=[
            {
                "name": p.name,
                "type": p.type,
                "description": p.description,
                "required": p.required,
                "default": p.default,
                "enum": p.enum,
            }
            for p in func_def.parameters
        ],
    )
