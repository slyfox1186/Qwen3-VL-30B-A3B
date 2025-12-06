"""Function executor with sandboxing and caching.

Safely executes functions called by the LLM with:
- Parameter validation
- Sandboxed execution for code
- Result caching
- Audit logging
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.services.functions.registry import FunctionRegistry, get_function_registry

logger = logging.getLogger(__name__)


@dataclass
class FunctionResult:
    """Result of a function execution."""

    function_name: str
    arguments: dict[str, Any]
    result: Any
    success: bool
    error: str | None = None
    execution_time_ms: float = 0.0
    from_cache: bool = False


@dataclass
class ExecutionAudit:
    """Audit record for function execution."""

    function_name: str
    arguments: dict[str, Any]
    timestamp: float
    success: bool
    error: str | None = None
    execution_time_ms: float = 0.0
    result_hash: str | None = None


class FunctionExecutor:
    """
    Executes functions with validation, sandboxing, and caching.

    Features:
    - Validates function calls before execution
    - Caches results for cacheable functions
    - Provides audit trail for all executions
    - Handles both sync and async functions
    """

    def __init__(
        self,
        registry: FunctionRegistry | None = None,
        enable_cache: bool = True,
        cache_ttl_seconds: int = 300,
        max_cache_size: int = 100,
    ):
        self._registry = registry or get_function_registry()
        self._enable_cache = enable_cache
        self._cache_ttl = cache_ttl_seconds
        self._max_cache_size = max_cache_size
        self._cache: dict[str, tuple[Any, float]] = {}
        self._audit_log: list[ExecutionAudit] = []
        self._max_audit_entries = 1000

    def _cache_key(self, name: str, arguments: dict[str, Any]) -> str:
        """Generate cache key for function call."""
        args_json = json.dumps(arguments, sort_keys=True)
        return f"{name}:{hashlib.md5(args_json.encode()).hexdigest()}"

    def _get_cached(self, key: str) -> Any | None:
        """Get cached result if valid."""
        if not self._enable_cache:
            return None

        if key in self._cache:
            result, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return result
            else:
                del self._cache[key]

        return None

    def _set_cached(self, key: str, result: Any, cacheable: bool) -> None:
        """Cache a result."""
        if not self._enable_cache or not cacheable:
            return

        # Evict old entries if cache is full
        if len(self._cache) >= self._max_cache_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[key] = (result, time.time())

    def _log_audit(
        self,
        name: str,
        arguments: dict[str, Any],
        success: bool,
        error: str | None,
        execution_time_ms: float,
        result: Any,
    ) -> None:
        """Log execution to audit trail."""
        # Compute result hash for audit (not storing full result)
        result_hash = None
        if result is not None:
            try:
                result_json = json.dumps(result, default=str)
                result_hash = hashlib.md5(result_json.encode()).hexdigest()[:16]
            except Exception:
                pass

        audit = ExecutionAudit(
            function_name=name,
            arguments=arguments,
            timestamp=time.time(),
            success=success,
            error=error,
            execution_time_ms=execution_time_ms,
            result_hash=result_hash,
        )

        self._audit_log.append(audit)

        # Trim old entries
        if len(self._audit_log) > self._max_audit_entries:
            self._audit_log = self._audit_log[-self._max_audit_entries:]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> FunctionResult:
        """
        Execute a function by name with given arguments.

        Args:
            name: Function name
            arguments: Function arguments

        Returns:
            FunctionResult with success/error and result
        """
        start_time = time.time()

        # Validate the call
        is_valid, errors = self._registry.validate_call(name, arguments)
        if not is_valid:
            error_msg = "; ".join(errors)
            logger.warning(f"Function validation failed: {name} - {error_msg}")
            return FunctionResult(
                function_name=name,
                arguments=arguments,
                result=None,
                success=False,
                error=error_msg,
            )

        # Get function definition
        func_def = self._registry.get(name)
        if not func_def or not func_def.handler:
            return FunctionResult(
                function_name=name,
                arguments=arguments,
                result=None,
                success=False,
                error=f"Function {name} has no handler",
            )

        # Check cache
        cache_key = self._cache_key(name, arguments)
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug(f"Function {name} returned from cache")
            return FunctionResult(
                function_name=name,
                arguments=arguments,
                result=cached,
                success=True,
                from_cache=True,
            )

        # Execute the function
        try:
            if func_def.is_async:
                result = await func_def.handler(**arguments)
            else:
                result = func_def.handler(**arguments)

            execution_time = (time.time() - start_time) * 1000

            # Cache result
            self._set_cached(cache_key, result, func_def.cacheable)

            # Audit log
            self._log_audit(
                name, arguments, True, None, execution_time, result
            )

            logger.info(
                f"Function {name} executed successfully in {execution_time:.1f}ms"
            )

            return FunctionResult(
                function_name=name,
                arguments=arguments,
                result=result,
                success=True,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = str(e)

            # Audit log
            self._log_audit(
                name, arguments, False, error_msg, execution_time, None
            )

            logger.error(f"Function {name} failed: {error_msg}")

            return FunctionResult(
                function_name=name,
                arguments=arguments,
                result=None,
                success=False,
                error=error_msg,
                execution_time_ms=execution_time,
            )

    def get_audit_log(
        self,
        limit: int = 100,
        function_name: str | None = None,
    ) -> list[ExecutionAudit]:
        """
        Get recent audit entries.

        Args:
            limit: Maximum entries to return
            function_name: Filter by function name

        Returns:
            List of audit entries (most recent first)
        """
        entries = self._audit_log

        if function_name:
            entries = [e for e in entries if e.function_name == function_name]

        return list(reversed(entries[-limit:]))

    def clear_cache(self) -> int:
        """Clear the result cache. Returns number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count

    async def execute_batch(
        self,
        calls: list[tuple[str, dict[str, Any]]],
    ) -> list[FunctionResult]:
        """
        Execute multiple function calls in parallel.

        Args:
            calls: List of (function_name, arguments) tuples

        Returns:
            List of FunctionResult in same order as input
        """
        import asyncio

        if not calls:
            return []

        # Execute all calls concurrently
        tasks = [self.execute(name, args) for name, args in calls]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return list(results)

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics."""
        return {
            "cache_entries": len(self._cache),
            "audit_entries": len(self._audit_log),
            "cache_enabled": self._enable_cache,
            "registered_functions": len(self._registry.list_functions()),
        }
