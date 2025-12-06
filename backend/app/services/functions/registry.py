"""Function registry for tool use.

Manages available functions that can be called by the LLM,
including parameter validation and OpenAI-compatible tool definitions.
"""

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FunctionParameter:
    """Definition of a function parameter."""

    name: str
    type: str  # "string", "number", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None


@dataclass
class FunctionDefinition:
    """Complete function definition."""

    name: str
    description: str
    parameters: list[FunctionParameter] = field(default_factory=list)
    handler: Callable[..., Any | Coroutine[Any, Any, Any]] | None = None
    is_async: bool = False
    requires_sandbox: bool = False
    cacheable: bool = True
    category: str = "general"


class FunctionRegistry:
    """
    Registry for functions available to the LLM.

    Features:
    - Register custom functions with parameter schemas
    - Generate OpenAI-compatible tool definitions
    - Built-in functions for common operations
    - Validation of function calls
    """

    def __init__(self):
        self._functions: dict[str, FunctionDefinition] = {}
        self._load_builtins()

    def _load_builtins(self):
        """Load built-in functions including memory tools."""
        from app.services.functions.builtins import get_all_builtin_functions

        for func_def in get_all_builtin_functions():
            self.register(func_def)

    def register(self, func_def: FunctionDefinition) -> None:
        """
        Register a function.

        Args:
            func_def: Function definition with name, params, and handler
        """
        self._functions[func_def.name] = func_def
        logger.debug(f"Registered function: {func_def.name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister a function.

        Args:
            name: Function name

        Returns:
            True if function was removed
        """
        if name in self._functions:
            del self._functions[name]
            return True
        return False

    def get(self, name: str) -> FunctionDefinition | None:
        """Get a function by name."""
        return self._functions.get(name)

    def list_functions(self, category: str | None = None) -> list[str]:
        """
        List registered function names.

        Args:
            category: Optional category filter

        Returns:
            List of function names
        """
        if category:
            return [
                name for name, func in self._functions.items()
                if func.category == category
            ]
        return list(self._functions.keys())

    def get_openai_tools(
        self,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate OpenAI-compatible tool definitions.

        Args:
            include: Only include these functions (if specified)
            exclude: Exclude these functions

        Returns:
            List of tool definitions in OpenAI format
        """
        tools = []
        exclude_set = set(exclude or [])

        for name, func in self._functions.items():
            # Apply filters
            if include and name not in include:
                continue
            if name in exclude_set:
                continue

            # Build parameter schema
            properties = {}
            required = []

            for param in func.parameters:
                prop: dict[str, Any] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.enum:
                    prop["enum"] = param.enum
                properties[param.name] = prop

                if param.required:
                    required.append(param.name)

            tool = {
                "type": "function",
                "function": {
                    "name": func.name,
                    "description": func.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
            tools.append(tool)

        return tools

    def validate_call(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Validate a function call.

        Args:
            name: Function name
            arguments: Call arguments

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        func = self.get(name)
        if not func:
            return False, [f"Unknown function: {name}"]

        # Check required parameters
        for param in func.parameters:
            if param.required and param.name not in arguments:
                errors.append(f"Missing required parameter: {param.name}")

            if param.name in arguments:
                value = arguments[param.name]

                # Type validation
                if param.type == "string" and not isinstance(value, str):
                    errors.append(f"Parameter {param.name} must be a string")
                elif param.type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Parameter {param.name} must be a number")
                elif param.type == "integer" and not isinstance(value, int):
                    errors.append(f"Parameter {param.name} must be an integer")
                elif param.type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Parameter {param.name} must be a boolean")
                elif param.type == "array" and not isinstance(value, list):
                    errors.append(f"Parameter {param.name} must be an array")
                elif param.type == "object" and not isinstance(value, dict):
                    errors.append(f"Parameter {param.name} must be an object")

                # Enum validation
                if param.enum and value not in param.enum:
                    errors.append(
                        f"Parameter {param.name} must be one of: {', '.join(param.enum)}"
                    )

        return len(errors) == 0, errors


# Global registry singleton
_registry: FunctionRegistry | None = None


def get_function_registry() -> FunctionRegistry:
    """Get the global function registry."""
    global _registry
    if _registry is None:
        _registry = FunctionRegistry()
    return _registry
