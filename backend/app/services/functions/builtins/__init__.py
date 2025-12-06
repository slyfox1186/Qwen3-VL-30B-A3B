"""Built-in functions for the LLM to use."""

from app.services.functions.builtins.functions import get_builtin_functions
from app.services.memory.tools import get_memory_tools


def get_all_builtin_functions():
    """Get all built-in functions including memory tools."""
    return get_builtin_functions() + get_memory_tools()


__all__ = ["get_builtin_functions", "get_memory_tools", "get_all_builtin_functions"]
