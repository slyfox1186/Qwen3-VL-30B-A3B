"""Schema registry for structured output types.

Manages JSON schemas for structured LLM outputs, including:
- Built-in common schemas (extraction, classification, form)
- Custom user-defined schemas
- Schema versioning and validation
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Built-in schemas for common use cases
BUILTIN_SCHEMAS: dict[str, dict[str, Any]] = {
    # Entity extraction schema
    "extraction": {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The extracted entity name"},
                        "type": {"type": "string", "description": "Entity type (person, place, org, etc)"},
                        "context": {"type": "string", "description": "Surrounding context"},
                    },
                    "required": ["name", "type"],
                },
            },
        },
        "required": ["entities"],
    },
    # Classification schema
    "classification": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Primary classification category"},
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score 0-1",
            },
            "reasoning": {"type": "string", "description": "Explanation for classification"},
            "subcategories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional subcategories",
            },
        },
        "required": ["category", "confidence"],
    },
    # Sentiment analysis schema
    "sentiment": {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["positive", "negative", "neutral", "mixed"],
                "description": "Overall sentiment",
            },
            "score": {
                "type": "number",
                "minimum": -1,
                "maximum": 1,
                "description": "Sentiment score from -1 (negative) to 1 (positive)",
            },
            "aspects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "aspect": {"type": "string"},
                        "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                    },
                    "required": ["aspect", "sentiment"],
                },
                "description": "Aspect-based sentiment breakdown",
            },
        },
        "required": ["sentiment", "score"],
    },
    # Summary schema
    "summary": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Brief title for the content"},
            "summary": {"type": "string", "description": "Concise summary paragraph"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Bullet points of key information",
            },
            "word_count": {"type": "integer", "description": "Word count of summary"},
        },
        "required": ["summary", "key_points"],
    },
    # Question-answer schema
    "qa": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "Direct answer to the question"},
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in the answer",
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "References or sources for the answer",
            },
            "follow_up_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suggested follow-up questions",
            },
        },
        "required": ["answer"],
    },
    # Data extraction to table format
    "table": {
        "type": "object",
        "properties": {
            "headers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Column headers",
            },
            "rows": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": ["string", "number", "boolean", "null"]},
                },
                "description": "Table rows (each row is an array of values)",
            },
        },
        "required": ["headers", "rows"],
    },
    # Code generation schema
    "code": {
        "type": "object",
        "properties": {
            "language": {"type": "string", "description": "Programming language"},
            "code": {"type": "string", "description": "The generated code"},
            "explanation": {"type": "string", "description": "Code explanation"},
            "dependencies": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Required dependencies/imports",
            },
        },
        "required": ["language", "code"],
    },
}


class SchemaRegistry:
    """
    Registry for JSON schemas used in structured output.

    Provides built-in schemas for common use cases and supports
    custom schemas with versioning.
    """

    def __init__(self):
        self._custom_schemas: dict[str, dict[str, dict[str, Any]]] = {}

    def get_builtin_schema(self, name: str) -> dict[str, Any] | None:
        """Get a built-in schema by name."""
        return BUILTIN_SCHEMAS.get(name)

    def list_builtin_schemas(self) -> list[str]:
        """List all available built-in schema names."""
        return list(BUILTIN_SCHEMAS.keys())

    def register_custom_schema(
        self,
        name: str,
        schema: dict[str, Any],
        version: str = "1.0.0",
    ) -> None:
        """
        Register a custom schema.

        Args:
            name: Unique schema identifier
            schema: JSON Schema definition
            version: Semantic version string
        """
        if name not in self._custom_schemas:
            self._custom_schemas[name] = {}

        self._custom_schemas[name][version] = schema
        logger.info(f"Registered custom schema: {name}@{version}")

    def get_custom_schema(
        self,
        name: str,
        version: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a custom schema by name and optional version.

        Args:
            name: Schema identifier
            version: Specific version, or None for latest

        Returns:
            Schema definition or None if not found
        """
        if name not in self._custom_schemas:
            return None

        versions = self._custom_schemas[name]

        if version:
            return versions.get(version)

        # Get latest version
        if versions:
            latest = sorted(versions.keys(), reverse=True)[0]
            return versions[latest]

        return None

    def get_schema(
        self,
        name: str,
        version: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a schema (built-in or custom) by name.

        Args:
            name: Schema identifier
            version: Specific version for custom schemas

        Returns:
            Schema definition or None if not found
        """
        # Check built-in first
        builtin = self.get_builtin_schema(name)
        if builtin:
            return builtin

        # Check custom schemas
        return self.get_custom_schema(name, version)

    def list_custom_schemas(self) -> dict[str, list[str]]:
        """List all custom schemas with their versions."""
        return {
            name: list(versions.keys())
            for name, versions in self._custom_schemas.items()
        }

    def delete_custom_schema(
        self,
        name: str,
        version: str | None = None,
    ) -> bool:
        """
        Delete a custom schema.

        Args:
            name: Schema identifier
            version: Specific version, or None to delete all versions

        Returns:
            True if deleted, False if not found
        """
        if name not in self._custom_schemas:
            return False

        if version:
            if version in self._custom_schemas[name]:
                del self._custom_schemas[name][version]
                if not self._custom_schemas[name]:
                    del self._custom_schemas[name]
                return True
            return False

        del self._custom_schemas[name]
        return True


# Global singleton instance
_registry: SchemaRegistry | None = None


def get_schema_registry() -> SchemaRegistry:
    """Get the global schema registry instance."""
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
    return _registry
