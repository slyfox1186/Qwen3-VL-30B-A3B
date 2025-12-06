"""Conversation summarization service.

Generates concise summaries of long conversations to:
- Reduce context window usage
- Improve response quality by focusing on relevant context
- Enable longer conversation history
"""

import logging
from typing import Any

from app.models.domain.message import Message

logger = logging.getLogger(__name__)


# Prompt template for summarization
SUMMARIZE_PROMPT = """Summarize this conversation concisely, preserving:
1. Key topics discussed
2. Important decisions or conclusions
3. Any unresolved questions
4. User preferences or requirements mentioned

Be concise but complete. Focus on information that would help continue the conversation.

CONVERSATION:
{conversation}

SUMMARY:"""


class ConversationSummarizer:
    """
    Generates summaries of conversations for context optimization.

    Uses the LLM to create high-quality summaries that preserve
    essential context while reducing token count.
    """

    def __init__(
        self,
        summarize_threshold: int = 50,
        summary_max_tokens: int = 500,
    ):
        """
        Initialize the summarizer.

        Args:
            summarize_threshold: Number of messages before summarization
            summary_max_tokens: Max tokens for the summary
        """
        self.summarize_threshold = summarize_threshold
        self.summary_max_tokens = summary_max_tokens

    def should_summarize(self, messages: list[Message]) -> bool:
        """Check if conversation should be summarized."""
        return len(messages) >= self.summarize_threshold

    def format_messages_for_summary(
        self,
        messages: list[Message],
        max_messages: int = 30,
    ) -> str:
        """
        Format messages for the summarization prompt.

        Takes the oldest messages (which will be summarized and removed).

        Args:
            messages: List of messages
            max_messages: Maximum messages to include in summary request

        Returns:
            Formatted conversation text
        """
        # Take oldest messages for summarization
        to_summarize = messages[:max_messages]

        lines = []
        for msg in to_summarize:
            role = "User" if msg.role == "user" else "Assistant"
            # Truncate long messages
            content = msg.content[:500] if len(msg.content) > 500 else msg.content
            lines.append(f"{role}: {content}")

        return "\n\n".join(lines)

    def build_summary_prompt(self, messages: list[Message]) -> list[dict[str, Any]]:
        """
        Build the prompt for summarization.

        Args:
            messages: Messages to summarize

        Returns:
            List of messages for LLM
        """
        conversation_text = self.format_messages_for_summary(messages)

        return [
            {
                "role": "system",
                "content": "You are a helpful assistant that creates concise conversation summaries.",
            },
            {
                "role": "user",
                "content": SUMMARIZE_PROMPT.format(conversation=conversation_text),
            },
        ]

    def create_summary_context(
        self,
        summary: str,
        original_message_count: int,
    ) -> str:
        """
        Format summary for injection into system context.

        Args:
            summary: The generated summary
            original_message_count: Number of messages that were summarized

        Returns:
            Formatted context string
        """
        return f"""[CONVERSATION CONTEXT - Summary of {original_message_count} earlier messages]
{summary}
[END CONVERSATION CONTEXT]

Continue the conversation naturally based on this context."""


class ContextOptimizer:
    """
    Optimizes conversation context for the LLM.

    Strategies:
    1. Summarize old messages when conversation gets long
    2. Select most relevant recent messages by similarity
    3. Score messages by recency and importance
    4. Inject summary into system prompt
    """

    def __init__(
        self,
        max_context_messages: int = 20,
        summarize_threshold: int = 50,
        preserve_recent: int = 10,
    ):
        """
        Initialize the optimizer.

        Args:
            max_context_messages: Maximum messages to include in context
            summarize_threshold: When to start summarizing
            preserve_recent: Always include this many recent messages
        """
        self.max_context_messages = max_context_messages
        self.summarize_threshold = summarize_threshold
        self.preserve_recent = preserve_recent
        self.summarizer = ConversationSummarizer(summarize_threshold=summarize_threshold)

    def select_context_messages(
        self,
        messages: list[Message],
        query_embedding: Any | None = None,
        message_embeddings: dict[str, Any] | None = None,
    ) -> tuple[list[Message], list[Message], bool]:
        """
        Select the most relevant messages for context.

        Args:
            messages: All conversation messages
            query_embedding: Optional embedding of current query for relevance
            message_embeddings: Optional dict of message_id -> embedding

        Returns:
            Tuple of (selected_messages, messages_to_summarize, needs_summarization)
        """
        if not messages:
            return [], [], False

        total = len(messages)

        # If under threshold, use all messages
        if total <= self.max_context_messages:
            return messages, [], False

        # Always preserve recent messages
        recent = messages[-self.preserve_recent:]
        older = messages[:-self.preserve_recent]

        # Check if we need to summarize
        needs_summary = total >= self.summarize_threshold

        if needs_summary:
            # Mark older messages for summarization
            to_summarize = older[:total - self.max_context_messages]
            to_keep = older[len(to_summarize):]
            return to_keep + recent, to_summarize, True

        # Simple truncation for moderate length
        remaining_slots = self.max_context_messages - len(recent)
        selected_older = older[-remaining_slots:] if remaining_slots > 0 else []

        return selected_older + recent, [], False

    def score_message_importance(
        self,
        message: Message,
        recency_rank: int,
        total_messages: int,
        semantic_score: float | None = None,
    ) -> float:
        """
        Score a message's importance for context selection.

        Combines:
        - Recency (more recent = higher score)
        - Semantic relevance (if available)
        - Content length (longer = potentially more important)
        - Role (user messages often define context)

        Args:
            message: Message to score
            recency_rank: Position from end (0 = most recent)
            total_messages: Total messages in conversation
            semantic_score: Optional semantic similarity to current query

        Returns:
            Importance score 0-1
        """
        # Recency score (exponential decay)
        recency = 1.0 / (1 + recency_rank * 0.1)

        # Content length score (log scale, capped)
        content_len = len(message.content)
        length_score = min(content_len / 500, 1.0) * 0.2

        # Role score (user messages set context)
        role_score = 0.1 if message.role == "user" else 0.0

        # Base score
        base_score = recency * 0.5 + length_score + role_score

        # Add semantic relevance if available
        if semantic_score is not None:
            # Semantic score contributes 30%
            return base_score * 0.7 + semantic_score * 0.3

        return base_score

    def build_optimized_context(
        self,
        messages: list[Message],
        summary: str | None = None,
        system_prompt: str = "",
    ) -> list[dict[str, Any]]:
        """
        Build optimized context with summary injection.

        Args:
            messages: Selected messages for context
            summary: Optional summary of earlier messages
            system_prompt: Base system prompt

        Returns:
            List of messages ready for LLM
        """
        # Inject summary into system prompt if available
        if summary:
            summary_context = self.summarizer.create_summary_context(
                summary,
                original_message_count=self.summarize_threshold,
            )
            enhanced_prompt = f"{system_prompt}\n\n{summary_context}"
        else:
            enhanced_prompt = system_prompt

        # Build message list
        result = [{"role": "system", "content": enhanced_prompt}]

        for msg in messages:
            result.append({
                "role": msg.role,
                "content": msg.content,
            })

        return result
