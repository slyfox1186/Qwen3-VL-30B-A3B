"""Built-in function implementations.

Safe, commonly-used functions that the LLM can call:
- Math calculations
- Date/time operations
- Data formatting
- Text analysis
"""

import math
import re
from datetime import UTC, datetime
from typing import Any

from app.services.functions.registry import FunctionDefinition, FunctionParameter


def calculate(expression: str) -> dict[str, Any]:
    """
    Safely evaluate a mathematical expression.

    Uses a restricted eval that only allows math operations.
    """
    # Allowed operations and functions
    allowed_names = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "floor": math.floor,
        "ceil": math.ceil,
        "pi": math.pi,
        "e": math.e,
    }

    # Validate expression - only allow safe characters
    safe_pattern = r'^[\d\s\+\-\*\/\%\(\)\.\,a-zA-Z_]+$'
    if not re.match(safe_pattern, expression):
        return {
            "success": False,
            "error": "Expression contains invalid characters",
        }

    try:
        # Evaluate with restricted namespace
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {
            "success": True,
            "expression": expression,
            "result": result,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def get_current_datetime(
    timezone_str: str = "UTC",
    format_str: str = "%Y-%m-%d %H:%M:%S",
) -> dict[str, Any]:
    """Get the current date and time."""
    try:
        now = datetime.now(UTC)

        return {
            "success": True,
            "datetime": now.strftime(format_str),
            "iso": now.isoformat(),
            "timestamp": now.timestamp(),
            "timezone": timezone_str,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def format_date(
    date_string: str,
    input_format: str = "%Y-%m-%d",
    output_format: str = "%B %d, %Y",
) -> dict[str, Any]:
    """Format a date string from one format to another."""
    try:
        dt = datetime.strptime(date_string, input_format)
        return {
            "success": True,
            "original": date_string,
            "formatted": dt.strftime(output_format),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def word_count(text: str) -> dict[str, Any]:
    """Count words, characters, and sentences in text."""
    words = len(text.split())
    chars = len(text)
    chars_no_space = len(text.replace(" ", ""))
    sentences = len(re.split(r'[.!?]+', text.strip()))

    return {
        "success": True,
        "words": words,
        "characters": chars,
        "characters_no_spaces": chars_no_space,
        "sentences": max(1, sentences - 1),  # Adjust for split behavior
    }


def convert_units(
    value: float,
    from_unit: str,
    to_unit: str,
) -> dict[str, Any]:
    """Convert between common units."""
    # Conversion factors to base units
    conversions = {
        # Length (base: meters)
        "m": 1.0,
        "km": 1000.0,
        "cm": 0.01,
        "mm": 0.001,
        "mi": 1609.344,
        "yd": 0.9144,
        "ft": 0.3048,
        "in": 0.0254,
        # Weight (base: kilograms)
        "kg": 1.0,
        "g": 0.001,
        "mg": 0.000001,
        "lb": 0.453592,
        "oz": 0.0283495,
        # Temperature handled separately
    }

    # Handle temperature conversion
    if from_unit in ("C", "F", "K") and to_unit in ("C", "F", "K"):
        try:
            # Convert to Celsius first
            if from_unit == "F":
                celsius = (value - 32) * 5 / 9
            elif from_unit == "K":
                celsius = value - 273.15
            else:
                celsius = value

            # Convert from Celsius to target
            if to_unit == "F":
                result = celsius * 9 / 5 + 32
            elif to_unit == "K":
                result = celsius + 273.15
            else:
                result = celsius

            return {
                "success": True,
                "original_value": value,
                "original_unit": from_unit,
                "converted_value": round(result, 4),
                "converted_unit": to_unit,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Handle other conversions
    if from_unit not in conversions or to_unit not in conversions:
        return {
            "success": False,
            "error": f"Unknown units: {from_unit} or {to_unit}",
            "supported_units": list(conversions.keys()),
        }

    try:
        # Convert to base unit, then to target
        base_value = value * conversions[from_unit]
        result = base_value / conversions[to_unit]

        return {
            "success": True,
            "original_value": value,
            "original_unit": from_unit,
            "converted_value": round(result, 6),
            "converted_unit": to_unit,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_uuid() -> dict[str, Any]:
    """Generate a new UUID."""
    import uuid

    new_uuid = uuid.uuid4()
    return {
        "success": True,
        "uuid": str(new_uuid),
        "hex": new_uuid.hex,
    }


def json_format(json_string: str, indent: int = 2) -> dict[str, Any]:
    """Format/pretty-print a JSON string."""
    import json as json_lib

    try:
        parsed = json_lib.loads(json_string)
        formatted = json_lib.dumps(parsed, indent=indent, sort_keys=True)
        return {
            "success": True,
            "formatted": formatted,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def get_builtin_functions() -> list[FunctionDefinition]:
    """Get all built-in function definitions."""
    return [
        FunctionDefinition(
            name="calculate",
            description="Evaluate a mathematical expression safely. Supports basic arithmetic, sqrt, sin, cos, tan, log, exp, and more.",
            parameters=[
                FunctionParameter(
                    name="expression",
                    type="string",
                    description="Mathematical expression to evaluate (e.g., '2 * 3 + sqrt(16)')",
                ),
            ],
            handler=calculate,
            category="math",
        ),
        FunctionDefinition(
            name="get_current_datetime",
            description="Get the current date and time.",
            parameters=[
                FunctionParameter(
                    name="timezone_str",
                    type="string",
                    description="Timezone (currently only UTC supported)",
                    required=False,
                    default="UTC",
                ),
                FunctionParameter(
                    name="format_str",
                    type="string",
                    description="Output format (strftime format)",
                    required=False,
                    default="%Y-%m-%d %H:%M:%S",
                ),
            ],
            handler=get_current_datetime,
            category="datetime",
        ),
        FunctionDefinition(
            name="format_date",
            description="Format a date string from one format to another.",
            parameters=[
                FunctionParameter(
                    name="date_string",
                    type="string",
                    description="Date string to format",
                ),
                FunctionParameter(
                    name="input_format",
                    type="string",
                    description="Input format (strftime format)",
                    required=False,
                    default="%Y-%m-%d",
                ),
                FunctionParameter(
                    name="output_format",
                    type="string",
                    description="Output format (strftime format)",
                    required=False,
                    default="%B %d, %Y",
                ),
            ],
            handler=format_date,
            category="datetime",
        ),
        FunctionDefinition(
            name="word_count",
            description="Count words, characters, and sentences in text.",
            parameters=[
                FunctionParameter(
                    name="text",
                    type="string",
                    description="Text to analyze",
                ),
            ],
            handler=word_count,
            category="text",
        ),
        FunctionDefinition(
            name="convert_units",
            description="Convert between units (length: m, km, mi, ft, in; weight: kg, g, lb, oz; temperature: C, F, K)",
            parameters=[
                FunctionParameter(
                    name="value",
                    type="number",
                    description="Value to convert",
                ),
                FunctionParameter(
                    name="from_unit",
                    type="string",
                    description="Source unit",
                ),
                FunctionParameter(
                    name="to_unit",
                    type="string",
                    description="Target unit",
                ),
            ],
            handler=convert_units,
            category="math",
        ),
        FunctionDefinition(
            name="generate_uuid",
            description="Generate a new random UUID.",
            parameters=[],
            handler=generate_uuid,
            category="utility",
            cacheable=False,  # Should generate new UUID each time
        ),
        FunctionDefinition(
            name="json_format",
            description="Format/pretty-print a JSON string.",
            parameters=[
                FunctionParameter(
                    name="json_string",
                    type="string",
                    description="JSON string to format",
                ),
                FunctionParameter(
                    name="indent",
                    type="integer",
                    description="Indentation spaces",
                    required=False,
                    default=2,
                ),
            ],
            handler=json_format,
            category="utility",
        ),
    ]
