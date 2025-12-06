"""Memory tools for LLM function calling.

Provides tools for the LLM to save and retrieve long-term memories
that persist across all conversations.
"""

from typing import Any

from app.services.functions.registry import FunctionDefinition, FunctionParameter
from app.services.memory.service import get_memory_service


async def save_memory(
    content: str,
    key: str | None = None,
    importance: str = "medium",
) -> dict[str, Any]:
    """
    Save a memory or fact for long-term storage.

    Args:
        content: The information to remember
        key: Optional key for facts (e.g., 'user_name', 'user_preference_language')
        importance: Priority level (low, medium, high)

    Returns:
        Success status and memory details
    """
    service = get_memory_service()

    try:
        memory_id = await service.save_memory(
            content=content,
            memory_key=key,
            importance=importance,
            source="explicit" if key else "conversation",
        )

        if memory_id:
            return {
                "success": True,
                "message": f"Remembered: {content[:100]}{'...' if len(content) > 100 else ''}",
                "memory_id": memory_id,
                "key": key,
            }
        return {"success": False, "error": "Failed to save memory"}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def search_memories(
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Search for relevant memories using semantic similarity.

    Args:
        query: Natural language description of what to search for
        limit: Maximum number of memories to return (default 5, max 20)

    Returns:
        List of relevant memories with similarity scores
    """
    service = get_memory_service()

    # Cap limit at 20
    limit = min(limit, 20)

    try:
        results = await service.search_memories(query=query, top_k=limit)

        memories = [
            {
                "content": r.content,
                "key": r.memory_key,
                "relevance": round(r.score, 3),
                "importance": r.importance,
            }
            for r in results
        ]

        return {
            "success": True,
            "query": query,
            "count": len(memories),
            "memories": memories,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_facts() -> dict[str, Any]:
    """
    List all stored key-value facts about the user.

    Returns:
        Dictionary of all facts (key -> value)
    """
    service = get_memory_service()

    try:
        facts = await service.list_facts()

        return {
            "success": True,
            "count": len(facts),
            "facts": facts,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def delete_memory(
    memory_id: str | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    """
    Delete a memory by ID or key.

    Args:
        memory_id: UUID of the memory to delete (use for semantic memories)
        key: Key of the fact to delete (use for keyed facts)

    Returns:
        Success status and confirmation
    """
    service = get_memory_service()

    if not memory_id and not key:
        return {"success": False, "error": "Must provide either memory_id or key"}

    try:
        deleted = await service.delete_memory(memory_id=memory_id, memory_key=key)

        if deleted:
            identifier = key if key else memory_id
            return {
                "success": True,
                "message": f"Deleted memory: {identifier}",
                "deleted_id": memory_id,
                "deleted_key": key,
            }
        return {"success": False, "error": "Memory not found or already deleted"}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def update_memory(
    memory_id: str,
    content: str,
) -> dict[str, Any]:
    """
    Update an existing memory with new content.

    Args:
        memory_id: UUID of the memory to update
        content: New content to replace the existing memory

    Returns:
        Success status and confirmation
    """
    service = get_memory_service()

    try:
        updated = await service.update_memory(memory_id=memory_id, content=content)

        if updated:
            return {
                "success": True,
                "message": f"Updated memory: {content[:100]}{'...' if len(content) > 100 else ''}",
                "memory_id": memory_id,
            }
        return {"success": False, "error": "Memory not found or update failed"}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def prescan_memories(
    content: str,
    key: str | None = None,
    threshold: float = 0.7,
) -> dict[str, Any]:
    """
    Pre-scan existing memories before saving new information.

    Use this BEFORE save_memory to check for duplicates or existing facts.
    Returns similar memories and whether the key already exists.

    Args:
        content: The content you want to save
        key: Optional key to check if a fact already exists
        threshold: Minimum similarity score (0.0 to 1.0, default 0.7)

    Returns:
        Similar memories, key existence status, and recommended action
    """
    service = get_memory_service()

    try:
        result: dict[str, Any] = {
            "similar_memories": [],
            "key_exists": False,
            "existing_key_content": None,
            "recommendation": "create_new",
        }

        # Check if key already exists
        if key:
            existing = await service.get_fact(key)
            if existing:
                result["key_exists"] = True
                result["existing_key_content"] = existing
                result["recommendation"] = "update_existing"

        # Find similar memories using document-to-document comparison
        similar = await service.find_similar(content, threshold=threshold)
        if similar:
            result["similar_memories"] = [
                {
                    "memory_id": m.id,
                    "content": m.content,
                    "key": m.memory_key,
                    "similarity": round(m.score, 3),
                    "importance": m.importance,
                }
                for m in similar
            ]

            # Update recommendation based on similarity scores
            top_score = similar[0].score
            if top_score > 0.9:
                result["recommendation"] = "skip_duplicate"
            elif top_score > 0.75 and not result["key_exists"]:
                result["recommendation"] = "consider_update"

        return {"success": True, **result}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_all_memories(
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List all memories (both keyed facts and semantic memories).

    Unlike list_facts which only shows keyed facts, this shows everything.

    Args:
        limit: Maximum memories to return (default 20, max 50)
        offset: Number of memories to skip for pagination

    Returns:
        List of all memories sorted by most recently updated
    """
    service = get_memory_service()

    # Cap limit
    limit = min(limit, 50)

    try:
        memories = await service.list_all_memories(limit=limit, offset=offset)

        return {
            "success": True,
            "count": len(memories),
            "offset": offset,
            "memories": [
                {
                    "memory_id": m["id"],
                    "content": m["content"],
                    "key": m["memory_key"],
                    "importance": m["importance"],
                    "source": m["source"],
                    "updated_at": m["updated_at"],
                }
                for m in memories
            ],
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_memory_tools() -> list[FunctionDefinition]:
    """Get all memory tool definitions for registration."""
    return [
        FunctionDefinition(
            name="prescan_memories",
            description=(
                "Pre-scan existing memories BEFORE saving new information. "
                "ALWAYS use this before save_memory to: (1) check for duplicate memories, "
                "(2) see if a key already exists, (3) get recommendations on whether to "
                "create new, update existing, or skip. Returns similar memories with "
                "similarity scores and recommended action."
            ),
            parameters=[
                FunctionParameter(
                    name="content",
                    type="string",
                    description="The content you intend to save. Will be compared against existing memories.",
                ),
                FunctionParameter(
                    name="key",
                    type="string",
                    description="Optional key to check if a fact already exists.",
                    required=False,
                ),
                FunctionParameter(
                    name="threshold",
                    type="number",
                    description="Minimum similarity score 0.0-1.0 (default 0.7). Lower = more matches.",
                    required=False,
                    default=0.7,
                ),
            ],
            handler=prescan_memories,
            is_async=True,
            category="memory",
            cacheable=False,
        ),
        FunctionDefinition(
            name="save_memory",
            description=(
                "Save important information about the user to long-term memory. "
                "BEST PRACTICE: Use prescan_memories first to check for duplicates. "
                "Use when: (1) user shares personal information like name, occupation, or preferences, "
                "(2) user explicitly asks to remember something, "
                "(3) user states important facts about themselves. "
                "Always confirm what was saved to the user."
            ),
            parameters=[
                FunctionParameter(
                    name="content",
                    type="string",
                    description="The information to remember. Be specific and include context.",
                ),
                FunctionParameter(
                    name="key",
                    type="string",
                    description=(
                        "Optional key for facts in snake_case. Examples: 'user_name', "
                        "'user_preferred_name', 'user_occupation', 'user_preference_language'. "
                        "Use keys for facts that should be easily retrievable and updatable."
                    ),
                    required=False,
                ),
                FunctionParameter(
                    name="importance",
                    type="string",
                    description=(
                        "Priority level: 'high' for core identity (name), "
                        "'medium' for preferences, 'low' for minor facts. Default: medium"
                    ),
                    required=False,
                    default="medium",
                    enum=["low", "medium", "high"],
                ),
            ],
            handler=save_memory,
            is_async=True,
            category="memory",
            cacheable=False,
        ),
        FunctionDefinition(
            name="update_memory",
            description=(
                "Update an existing memory with new content. Use this instead of "
                "save_memory when you want to modify existing information rather than "
                "create a duplicate. The embedding will be regenerated automatically. "
                "Get the memory_id from prescan_memories or list_all_memories."
            ),
            parameters=[
                FunctionParameter(
                    name="memory_id",
                    type="string",
                    description="UUID of the memory to update (from prescan or list_all_memories).",
                ),
                FunctionParameter(
                    name="content",
                    type="string",
                    description="New content to replace the existing memory.",
                ),
            ],
            handler=update_memory,
            is_async=True,
            category="memory",
            cacheable=False,
        ),
        FunctionDefinition(
            name="delete_memory",
            description=(
                "Delete a memory that is outdated, incorrect, or no longer relevant. "
                "Use when: (1) user explicitly asks to forget something, "
                "(2) information is confirmed to be wrong, "
                "(3) cleaning up duplicate memories found via prescan. "
                "Can delete by memory_id OR by key (for keyed facts)."
            ),
            parameters=[
                FunctionParameter(
                    name="memory_id",
                    type="string",
                    description="UUID of the memory to delete (use for semantic memories).",
                    required=False,
                ),
                FunctionParameter(
                    name="key",
                    type="string",
                    description="Key of the fact to delete (use for keyed facts like 'user_name').",
                    required=False,
                ),
            ],
            handler=delete_memory,
            is_async=True,
            category="memory",
            cacheable=False,
        ),
        FunctionDefinition(
            name="search_memories",
            description=(
                "Search long-term memory for relevant information using semantic similarity. "
                "Use when: (1) you need user context to personalize a response, "
                "(2) user references something from the past, "
                "(3) before making personalized recommendations. "
                "Do NOT search on every message - only when context is genuinely needed."
            ),
            parameters=[
                FunctionParameter(
                    name="query",
                    type="string",
                    description=(
                        "Natural language description of what to search for. "
                        "Example: 'What programming languages does the user prefer?'"
                    ),
                ),
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum results to return (default 5, max 20)",
                    required=False,
                    default=5,
                ),
            ],
            handler=search_memories,
            is_async=True,
            category="memory",
            cacheable=False,
        ),
        FunctionDefinition(
            name="list_facts",
            description=(
                "List all stored key-value facts about the user (only keyed memories). "
                "Use when: (1) user asks 'what do you know about me?', "
                "(2) quickly checking core user facts. "
                "For a complete view including semantic memories, use list_all_memories."
            ),
            parameters=[],
            handler=list_facts,
            is_async=True,
            category="memory",
            cacheable=False,
        ),
        FunctionDefinition(
            name="list_all_memories",
            description=(
                "List ALL memories including both keyed facts AND semantic memories. "
                "Use when: (1) performing a complete memory audit, "
                "(2) user wants to see everything stored about them, "
                "(3) cleaning up or reviewing memory database. "
                "Supports pagination with limit and offset."
            ),
            parameters=[
                FunctionParameter(
                    name="limit",
                    type="integer",
                    description="Maximum memories to return (default 20, max 50).",
                    required=False,
                    default=20,
                ),
                FunctionParameter(
                    name="offset",
                    type="integer",
                    description="Number of memories to skip for pagination.",
                    required=False,
                    default=0,
                ),
            ],
            handler=list_all_memories,
            is_async=True,
            category="memory",
            cacheable=False,
        ),
    ]
