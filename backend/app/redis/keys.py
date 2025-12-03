"""Redis key patterns and builders with namespacing."""


class RedisKeys:
    """Centralized Redis key management."""

    PREFIX = "vlm"

    @classmethod
    def session(cls, session_id: str) -> str:
        """Session metadata key."""
        return f"{cls.PREFIX}:session:{session_id}"

    @classmethod
    def session_history(cls, session_id: str) -> str:
        """Chat history for a session."""
        return f"{cls.PREFIX}:history:{session_id}"

    @classmethod
    def rate_limit(cls, identifier: str) -> str:
        """Rate limiting key for user/session."""
        return f"{cls.PREFIX}:ratelimit:{identifier}"

    @classmethod
    def request_queue(cls) -> str:
        """LLM request queue stream."""
        return f"{cls.PREFIX}:queue:requests"

    @classmethod
    def processing_set(cls) -> str:
        """Set of currently processing request IDs."""
        return f"{cls.PREFIX}:queue:processing"

    @classmethod
    def session_lock(cls, session_id: str) -> str:
        """Distributed lock for session operations."""
        return f"{cls.PREFIX}:lock:session:{session_id}"

    @classmethod
    def request_result(cls, request_id: str) -> str:
        """Temporary storage for request results."""
        return f"{cls.PREFIX}:result:{request_id}"
