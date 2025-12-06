"""Build vLLM-compatible message format."""

from typing import Any

from app.models.domain.message import Message


class MessageBuilder:
    """
    Builds vLLM-compatible message format.

    Converts internal Message objects to the OpenAI-compatible
    format expected by vLLM.
    """

    @staticmethod
    def build_messages(messages: list[Message]) -> list[dict[str, Any]]:
        """
        Convert domain messages to vLLM format.

        Args:
            messages: List of Message domain objects from history

        Returns:
            List of dicts in OpenAI chat format
        """
        result = []

        for msg in messages:
            result.append({
                "role": msg.role,
                "content": msg.content,
            })

        return result

    @staticmethod
    def build_single_message(
        role: str,
        content: str,
    ) -> dict[str, Any]:
        """
        Build a single message dict.

        Args:
            role: Message role (user, assistant, system)
            content: Text content

        Returns:
            Message dict in OpenAI format
        """
        return {
            "role": role,
            "content": content,
        }

    @staticmethod
    def build_system_message(content: str) -> dict[str, Any]:
        """Build a system message."""
        return {
            "role": "system",
            "content": content,
        }

    @staticmethod
    def build_context_from_history(
        history: list[Message],
        system_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build full context from history with optional system prompt.

        Args:
            history: List of Message objects from history
            system_prompt: Optional system prompt to prepend

        Returns:
            List of message dicts ready for LLM
        """
        messages = []

        if system_prompt:
            messages.append(MessageBuilder.build_system_message(system_prompt))

        messages.extend(MessageBuilder.build_messages(history))

        return messages
