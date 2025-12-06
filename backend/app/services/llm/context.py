"""Context management service.

Provides intelligent context selection and optimization for LLM conversations,
combining:
- Conversation summarization
- Semantic relevance scoring
- Recency-based selection
- Token budget management
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.models.domain.message import Message
from app.services.llm.client import VLLMClient
from app.services.llm.summarizer import ContextOptimizer, ConversationSummarizer

logger = logging.getLogger(__name__)


@dataclass
class ContextConfig:
    """Configuration for context optimization."""

    max_context_messages: int = 20
    summarize_threshold: int = 50
    preserve_recent: int = 10
    summary_max_tokens: int = 500
    enable_semantic_selection: bool = True


@dataclass
class OptimizedContext:
    """Result of context optimization."""

    messages: list[dict[str, Any]]  # Ready for LLM
    summary: str | None  # Generated summary if any
    summarized_count: int  # Number of messages summarized
    selected_count: int  # Number of messages in context
    total_count: int  # Original message count
    was_optimized: bool  # Whether optimization was applied


class ContextService:
    """
    Service for managing conversation context.

    Provides methods to:
    - Optimize context for long conversations
    - Generate and cache summaries
    - Select semantically relevant messages
    """

    def __init__(
        self,
        llm_client: VLLMClient | None = None,
        config: ContextConfig | None = None,
    ):
        self._llm_client = llm_client
        self._config = config or ContextConfig()
        self._optimizer = ContextOptimizer(
            max_context_messages=self._config.max_context_messages,
            summarize_threshold=self._config.summarize_threshold,
            preserve_recent=self._config.preserve_recent,
        )
        self._summarizer = ConversationSummarizer(
            summarize_threshold=self._config.summarize_threshold,
            summary_max_tokens=self._config.summary_max_tokens,
        )

    async def optimize_context(
        self,
        messages: list[Message],
        system_prompt: str,
        current_query: str | None = None,
        cached_summary: str | None = None,
    ) -> OptimizedContext:
        """
        Optimize conversation context for the LLM.

        Args:
            messages: Full conversation history
            system_prompt: Base system prompt
            current_query: Current user query (for semantic relevance)
            cached_summary: Previously generated summary to reuse

        Returns:
            OptimizedContext with ready-to-use messages
        """
        total_count = len(messages)

        # Check if optimization is needed
        if total_count <= self._config.max_context_messages:
            # No optimization needed
            llm_messages = [{"role": "system", "content": system_prompt}]
            for msg in messages:
                llm_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

            return OptimizedContext(
                messages=llm_messages,
                summary=None,
                summarized_count=0,
                selected_count=total_count,
                total_count=total_count,
                was_optimized=False,
            )

        # Select context messages
        selected, to_summarize, needs_summary = self._optimizer.select_context_messages(
            messages,
        )

        summary = cached_summary
        summarized_count = 0

        # Generate summary if needed and LLM client available
        if needs_summary and to_summarize and self._llm_client and not cached_summary:
            try:
                summary = await self._generate_summary(to_summarize)
                summarized_count = len(to_summarize)
                logger.info(f"Generated summary for {summarized_count} messages")
            except Exception as e:
                logger.warning(f"Failed to generate summary: {e}")
                summary = None

        # Build optimized context
        llm_messages = self._optimizer.build_optimized_context(
            messages=selected,
            summary=summary,
            system_prompt=system_prompt,
        )

        return OptimizedContext(
            messages=llm_messages,
            summary=summary,
            summarized_count=summarized_count,
            selected_count=len(selected),
            total_count=total_count,
            was_optimized=True,
        )

    async def _generate_summary(self, messages: list[Message]) -> str | None:
        """Generate a summary of messages using the LLM."""
        if not self._llm_client:
            return None

        try:
            prompt = self._summarizer.build_summary_prompt(messages)

            result = await self._llm_client.chat_completion(
                messages=prompt,
                max_tokens=self._config.summary_max_tokens,
                temperature=0.3,  # Lower temperature for factual summary
            )

            return result.get("content", "").strip()

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return None

    def get_context_stats(self, messages: list[Message]) -> dict[str, Any]:
        """
        Get statistics about the conversation context.

        Args:
            messages: Conversation messages

        Returns:
            Dict with context statistics
        """
        total = len(messages)
        needs_optimization = total > self._config.max_context_messages
        needs_summarization = total >= self._config.summarize_threshold

        # Estimate token count (rough approximation)
        total_chars = sum(len(m.content) for m in messages)
        estimated_tokens = total_chars // 4  # Rough approximation

        return {
            "total_messages": total,
            "needs_optimization": needs_optimization,
            "needs_summarization": needs_summarization,
            "estimated_tokens": estimated_tokens,
            "max_context_messages": self._config.max_context_messages,
            "summarize_threshold": self._config.summarize_threshold,
        }


# Dependency injection helper
_context_service: ContextService | None = None


def get_context_service(llm_client: VLLMClient | None = None) -> ContextService:
    """Get or create the context service."""
    global _context_service

    if _context_service is None:
        settings = get_settings()
        config = ContextConfig(
            max_context_messages=settings.max_history_messages,
            summarize_threshold=50,
            preserve_recent=10,
        )
        _context_service = ContextService(llm_client=llm_client, config=config)

    return _context_service
