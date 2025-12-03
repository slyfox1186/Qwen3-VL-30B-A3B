"""Build vLLM-compatible multimodal message format."""

from typing import Any

from app.models.domain.message import Message


class MessageBuilder:
    """
    Builds vLLM-compatible multimodal message format.

    Converts internal Message objects to the OpenAI-compatible
    format expected by vLLM for vision-language models.
    """

    @staticmethod
    def build_messages(messages: list[Message]) -> list[dict[str, Any]]:
        """
        Convert domain messages to vLLM format.

        Args:
            messages: List of Message domain objects (text only from history)

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
        image_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Build a single message dict.

        Args:
            role: Message role (user, assistant, system)
            content: Text content
            image_urls: Optional list of image data URLs

        Returns:
            Message dict in OpenAI format
        """
        if not image_urls:
            return {
                "role": role,
                "content": content,
            }

        message_content = []

        # Add images first
        for url in image_urls:
            message_content.append({
                "type": "image_url",
                "image_url": {"url": url},
            })

        # Add text
        if content:
            message_content.append({
                "type": "text",
                "text": content,
            })

        return {
            "role": role,
            "content": message_content,
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
