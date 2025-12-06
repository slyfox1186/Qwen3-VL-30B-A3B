"""JSON Schema validator with retry logic.

Validates LLM outputs against JSON schemas and provides
schema-aware retry prompts when validation fails.
"""

import json
import logging
import re
from typing import Any

from jsonschema import Draft7Validator

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Exception raised when schema validation fails."""

    def __init__(
        self,
        message: str,
        errors: list[str],
        raw_response: str | None = None,
    ):
        super().__init__(message)
        self.errors = errors
        self.raw_response = raw_response


class SchemaValidator:
    """
    Validates JSON responses against schemas with retry support.

    Features:
    - JSON extraction from mixed content (handles markdown code blocks)
    - Detailed validation error reporting
    - Schema-aware retry prompt generation
    """

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def extract_json(self, text: str) -> str | None:
        """
        Extract JSON from text that may contain markdown or other content.

        Handles:
        - Raw JSON
        - JSON in ```json code blocks
        - JSON in ``` code blocks
        - JSON embedded in prose

        Args:
            text: Raw text potentially containing JSON

        Returns:
            Extracted JSON string or None if not found
        """
        text = text.strip()

        # Try raw JSON first
        if text.startswith("{") or text.startswith("["):
            return text

        # Try markdown code blocks
        # Match ```json ... ``` or ``` ... ```
        code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
        matches = re.findall(code_block_pattern, text)
        for match in matches:
            stripped = match.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                return stripped

        # Try to find JSON object/array embedded in text
        # Look for the outermost { } or [ ]
        brace_start = text.find("{")
        bracket_start = text.find("[")

        if brace_start == -1 and bracket_start == -1:
            return None

        # Use whichever comes first
        if brace_start >= 0 and (bracket_start == -1 or brace_start < bracket_start):
            # Find matching closing brace
            depth = 0
            in_string = False
            escape_next = False
            for i, char in enumerate(text[brace_start:]):
                if escape_next:
                    escape_next = False
                    continue
                if char == "\\":
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return text[brace_start:brace_start + i + 1]
        elif bracket_start >= 0:
            # Find matching closing bracket
            depth = 0
            in_string = False
            escape_next = False
            for i, char in enumerate(text[bracket_start:]):
                if escape_next:
                    escape_next = False
                    continue
                if char == "\\":
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == "[":
                    depth += 1
                elif char == "]":
                    depth -= 1
                    if depth == 0:
                        return text[bracket_start:bracket_start + i + 1]

        return None

    def validate(
        self,
        response: str,
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any] | list[Any], list[str]]:
        """
        Validate a response against a JSON schema.

        Args:
            response: Raw LLM response text
            schema: JSON Schema to validate against

        Returns:
            Tuple of (parsed_data, validation_errors)
            If validation passes, errors list is empty.
        """
        errors: list[str] = []

        # Extract JSON from response
        json_str = self.extract_json(response)
        if json_str is None:
            errors.append("No valid JSON found in response")
            return {}, errors

        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON syntax: {e.msg} at position {e.pos}")
            return {}, errors

        # Validate against schema
        validator = Draft7Validator(schema)
        validation_errors = list(validator.iter_errors(data))

        for error in validation_errors:
            path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
            errors.append(f"Schema error at '{path}': {error.message}")

        return data, errors

    def generate_retry_prompt(
        self,
        original_prompt: str,
        schema: dict[str, Any],
        errors: list[str],
        raw_response: str | None = None,
    ) -> str:
        """
        Generate a retry prompt that includes validation errors.

        Args:
            original_prompt: The original user prompt
            schema: The target JSON schema
            errors: List of validation errors from previous attempt
            raw_response: The invalid response (for context)

        Returns:
            A new prompt instructing the model to fix the errors
        """
        schema_str = json.dumps(schema, indent=2)
        errors_str = "\n".join(f"- {e}" for e in errors)

        retry_prompt = f"""Your previous response did not match the required JSON schema.

VALIDATION ERRORS:
{errors_str}

REQUIRED SCHEMA:
```json
{schema_str}
```

Please provide a response that:
1. Contains ONLY valid JSON (no markdown, no explanations outside the JSON)
2. Strictly follows the schema above
3. Fixes all the validation errors listed

Original request: {original_prompt}

Respond with the corrected JSON only:"""

        return retry_prompt

    def get_schema_instruction(self, schema: dict[str, Any]) -> str:
        """
        Generate a system instruction for structured output.

        Args:
            schema: JSON Schema definition

        Returns:
            Instruction text to add to system prompt
        """
        schema_str = json.dumps(schema, indent=2)

        return f"""You MUST respond with valid JSON that matches this schema:

```json
{schema_str}
```

IMPORTANT:
- Respond ONLY with valid JSON - no markdown code blocks, no explanations
- Your entire response must be parseable as JSON
- Follow the schema exactly - include all required fields
- Use the correct data types as specified in the schema"""


# Convenience function for single-shot validation
def validate_json_response(
    response: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any] | list[Any], list[str]]:
    """
    Validate a JSON response against a schema.

    Args:
        response: Raw text response
        schema: JSON Schema

    Returns:
        Tuple of (parsed_data, errors)
    """
    validator = SchemaValidator()
    return validator.validate(response, schema)
