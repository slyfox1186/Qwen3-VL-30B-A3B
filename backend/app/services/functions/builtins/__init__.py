"""Built-in functions for the LLM to use."""

from app.services.functions.builtins.functions import get_builtin_functions
from app.services.functions.builtins.web_tools import get_web_tools
from app.services.memory.tools import get_memory_tools


def get_all_builtin_functions():
    """Get all built-in functions including memory and web tools."""
    return get_builtin_functions() + get_memory_tools() + get_web_tools()


__all__ = ["get_builtin_functions", "get_memory_tools", "get_web_tools", "get_all_builtin_functions"]
