"""Long-term memory service with vector search.

Provides persistent storage for:
- Key-value facts (e.g., user_name = "jeffrey")
- Semantic memories with vector embeddings

Uses asymmetric encoding with google/embeddinggemma-300m:
- encode_query() for search queries
- encode_document() for stored memories
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.config import get_settings
from app.postgres.client import PostgresClient, get_postgres

logger = logging.getLogger(__name__)

# Lazy-loaded embedding model
_model: Any = None
_model_name: str | None = None


def _load_memory_model(model_name: str) -> Any:
    """Load the memory embedding model lazily on GPU only.

    This function REQUIRES a CUDA-capable GPU. It will fail if no GPU is available
    rather than falling back to CPU for performance reasons.
    """
    global _model, _model_name

    if _model is not None and _model_name == model_name:
        return _model

    try:
        import torch
        from sentence_transformers import SentenceTransformer

        # Verify CUDA is available - fail fast if not
        if not torch.cuda.is_available():
            logger.error(
                "CUDA not available. Memory embedding model REQUIRES GPU. "
                "Memory search will be disabled."
            )
            return None

        device = "cuda"
        logger.info(f"Loading memory embedding model on GPU: {model_name}")

        # Load model directly to GPU
        _model = SentenceTransformer(model_name, device=device)
        _model_name = model_name

        # Log GPU info for confirmation
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"Memory embedding model loaded on GPU: {gpu_name}")

        return _model

    except ImportError as e:
        logger.warning(
            f"Required package not installed: {e}. "
            "Memory search will be disabled. "
            "Install with: pip install sentence-transformers torch"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to load memory embedding model on GPU: {e}")
        return None


@dataclass
class MemorySearchResult:
    """Result from semantic memory search."""

    id: str
    content: str
    memory_key: str | None
    score: float
    importance: str
    created_at: str


class MemoryService:
    """
    Service for long-term memory storage and retrieval.

    Features:
    - Save key-value facts with upsert support
    - Save semantic memories with embeddings
    - Asymmetric vector similarity search (query vs document)
    - CRUD operations
    """

    def __init__(self, postgres: PostgresClient | None = None):
        self._postgres = postgres
        self._settings = get_settings()
        self._model_name = self._settings.memory_embedding_model
        self._dimension = self._settings.memory_embedding_dimension

    @property
    def model(self) -> Any:
        """Get the loaded model (lazy loading)."""
        return _load_memory_model(self._model_name)

    @property
    def is_available(self) -> bool:
        """Check if memory service is available."""
        return self.model is not None

    async def _get_postgres(self) -> PostgresClient:
        """Lazy load PostgreSQL client."""
        if self._postgres is None:
            self._postgres = await get_postgres()
        return self._postgres

    def _embed_document(self, text: str) -> np.ndarray | None:
        """Generate embedding for a document/memory (asymmetric)."""
        if not self.is_available:
            return None

        try:
            # Use encode_document for memories (asymmetric encoding)
            embedding = self.model.encode_document(text)
            return embedding.astype(np.float32)
        except AttributeError:
            # Fallback for models without encode_document
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Failed to generate document embedding: {e}")
            return None

    def _embed_query(self, text: str) -> np.ndarray | None:
        """Generate embedding for a search query (asymmetric)."""
        if not self.is_available:
            return None

        try:
            # Use encode_query for search queries (asymmetric encoding)
            embedding = self.model.encode_query(text)
            return embedding.astype(np.float32)
        except AttributeError:
            # Fallback for models without encode_query
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return None

    async def save_memory(
        self,
        content: str,
        memory_key: str | None = None,
        user_id: str = "default",
        importance: str = "medium",
        source: str = "conversation",
    ) -> str | None:
        """
        Save a memory (key-value fact or semantic memory).

        Args:
            content: The memory content
            memory_key: Optional key for key-value facts (enables upsert)
            user_id: User identifier
            importance: Priority level (low, medium, high)
            source: Origin of memory (conversation, explicit, system)

        Returns:
            Memory ID if saved, None if failed
        """
        pg = await self._get_postgres()

        # Generate embedding using asymmetric document encoding
        embedding = self._embed_document(content)
        if embedding is None:
            logger.warning("Failed to generate embedding for memory, saving without vector")

        try:
            async with pg.pool.acquire() as conn:
                if memory_key:
                    # Upsert for key-value facts
                    # Pass numpy array directly - pgvector handles conversion
                    result = await conn.fetchval(
                        """
                        INSERT INTO memories (user_id, memory_key, content, embedding, importance, source)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (user_id, memory_key) WHERE memory_key IS NOT NULL
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            importance = EXCLUDED.importance,
                            source = EXCLUDED.source,
                            updated_at = NOW()
                        RETURNING id::text
                        """,
                        user_id,
                        memory_key,
                        content,
                        embedding,
                        importance,
                        source,
                    )
                else:
                    # Insert for semantic-only memories
                    result = await conn.fetchval(
                        """
                        INSERT INTO memories (user_id, memory_key, content, embedding, importance, source)
                        VALUES ($1, NULL, $2, $3, $4, $5)
                        RETURNING id::text
                        """,
                        user_id,
                        content,
                        embedding,
                        importance,
                        source,
                    )

                logger.info(f"Saved memory: key={memory_key}, id={result}")
                return result

        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            return None

    async def search_memories(
        self,
        query: str,
        user_id: str = "default",
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[MemorySearchResult]:
        """
        Search for memories using semantic similarity.

        Uses asymmetric encoding: query embedding vs document embeddings.
        """
        pg = await self._get_postgres()

        # Use asymmetric query encoding
        query_embedding = self._embed_query(query)
        if query_embedding is None:
            return []

        top_k = top_k or self._settings.memory_search_top_k
        min_score = min_score or self._settings.memory_search_min_score

        try:
            async with pg.pool.acquire() as conn:
                # Pass numpy array directly - pgvector handles conversion
                rows = await conn.fetch(
                    """
                    SELECT
                        id::text,
                        content,
                        memory_key,
                        importance,
                        to_char(created_at AT TIME ZONE 'UTC',
                            'YYYY-MM-DD"T"HH24:MI:SS"Z"') as created_at,
                        1 - (embedding <=> $1) as score
                    FROM memories
                    WHERE user_id = $2
                        AND embedding IS NOT NULL
                        AND 1 - (embedding <=> $1) >= $3
                    ORDER BY embedding <=> $1
                    LIMIT $4
                    """,
                    query_embedding,
                    user_id,
                    min_score,
                    top_k,
                )

                return [
                    MemorySearchResult(
                        id=row["id"],
                        content=row["content"],
                        memory_key=row["memory_key"],
                        score=float(row["score"]),
                        importance=row["importance"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    async def get_fact(self, key: str, user_id: str = "default") -> str | None:
        """Get a specific fact by key (O(1) B-tree lookup)."""
        pg = await self._get_postgres()

        try:
            async with pg.pool.acquire() as conn:
                result = await conn.fetchval(
                    """
                    SELECT content
                    FROM memories
                    WHERE user_id = $1 AND memory_key = $2
                    """,
                    user_id,
                    key,
                )
                return result

        except Exception as e:
            logger.error(f"Failed to get fact: {e}")
            return None

    async def list_facts(self, user_id: str = "default") -> dict[str, str]:
        """Get all key-value facts for a user."""
        pg = await self._get_postgres()

        try:
            async with pg.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT memory_key, content
                    FROM memories
                    WHERE user_id = $1 AND memory_key IS NOT NULL
                    ORDER BY memory_key
                    """,
                    user_id,
                )
                return {row["memory_key"]: row["content"] for row in rows}

        except Exception as e:
            logger.error(f"Failed to list facts: {e}")
            return {}

    async def delete_memory(
        self,
        memory_id: str | None = None,
        memory_key: str | None = None,
        user_id: str = "default",
    ) -> bool:
        """Delete a memory by ID or key."""
        pg = await self._get_postgres()

        try:
            async with pg.pool.acquire() as conn:
                if memory_id:
                    result = await conn.execute(
                        "DELETE FROM memories WHERE id = $1::uuid AND user_id = $2",
                        memory_id,
                        user_id,
                    )
                elif memory_key:
                    result = await conn.execute(
                        "DELETE FROM memories WHERE memory_key = $1 AND user_id = $2",
                        memory_key,
                        user_id,
                    )
                else:
                    return False

                return "DELETE" in result

        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    async def update_memory(
        self,
        memory_id: str,
        content: str,
        user_id: str = "default",
    ) -> bool:
        """
        Update an existing memory's content and regenerate embedding.

        Args:
            memory_id: UUID of the memory to update
            content: New content to replace existing
            user_id: User identifier for ownership verification

        Returns:
            True if updated successfully, False otherwise
        """
        pg = await self._get_postgres()

        # Regenerate embedding for new content
        embedding = self._embed_document(content)

        try:
            async with pg.pool.acquire() as conn:
                result = await conn.fetchval(
                    """
                    UPDATE memories
                    SET content = $1, embedding = $2, updated_at = NOW()
                    WHERE id = $3::uuid AND user_id = $4
                    RETURNING id::text
                    """,
                    content,
                    embedding,
                    memory_id,
                    user_id,
                )
                if result:
                    logger.info(f"Updated memory: id={memory_id}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return False

    async def get_memory_by_id(
        self,
        memory_id: str,
        user_id: str = "default",
    ) -> dict | None:
        """
        Get a specific memory by ID.

        Args:
            memory_id: UUID of the memory
            user_id: User identifier for ownership verification

        Returns:
            Memory dict with all fields, or None if not found
        """
        pg = await self._get_postgres()

        try:
            async with pg.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        id::text,
                        content,
                        memory_key,
                        importance,
                        source,
                        to_char(created_at AT TIME ZONE 'UTC',
                            'YYYY-MM-DD"T"HH24:MI:SS"Z"') as created_at,
                        to_char(updated_at AT TIME ZONE 'UTC',
                            'YYYY-MM-DD"T"HH24:MI:SS"Z"') as updated_at
                    FROM memories
                    WHERE id = $1::uuid AND user_id = $2
                    """,
                    memory_id,
                    user_id,
                )
                if row:
                    return dict(row)
                return None

        except Exception as e:
            logger.error(f"Failed to get memory by ID: {e}")
            return None

    async def list_all_memories(
        self,
        user_id: str = "default",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """
        List all memories (keyed and semantic) for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of memories to return
            offset: Number of memories to skip (for pagination)

        Returns:
            List of memory dicts sorted by most recently updated
        """
        pg = await self._get_postgres()

        # Cap limit to prevent excessive queries
        limit = min(limit, 50)

        try:
            async with pg.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        id::text,
                        content,
                        memory_key,
                        importance,
                        source,
                        to_char(created_at AT TIME ZONE 'UTC',
                            'YYYY-MM-DD"T"HH24:MI:SS"Z"') as created_at,
                        to_char(updated_at AT TIME ZONE 'UTC',
                            'YYYY-MM-DD"T"HH24:MI:SS"Z"') as updated_at
                    FROM memories
                    WHERE user_id = $1
                    ORDER BY updated_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    user_id,
                    limit,
                    offset,
                )
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to list all memories: {e}")
            return []

    async def find_similar(
        self,
        content: str,
        user_id: str = "default",
        threshold: float = 0.7,
        limit: int = 5,
    ) -> list[MemorySearchResult]:
        """
        Find memories similar to given content (for deduplication/prescan).

        Uses document embedding for fair comparison (doc-to-doc similarity).
        Different from search_memories which uses query embedding (asymmetric).

        Args:
            content: Content to compare against existing memories
            user_id: User identifier
            threshold: Minimum similarity score (0.0 to 1.0)
            limit: Maximum results to return

        Returns:
            List of similar memories with similarity scores
        """
        pg = await self._get_postgres()

        # Use document embedding for fair doc-to-doc comparison
        content_embedding = self._embed_document(content)
        if content_embedding is None:
            return []

        try:
            async with pg.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        id::text,
                        content,
                        memory_key,
                        importance,
                        to_char(created_at AT TIME ZONE 'UTC',
                            'YYYY-MM-DD"T"HH24:MI:SS"Z"') as created_at,
                        1 - (embedding <=> $1) as score
                    FROM memories
                    WHERE user_id = $2
                        AND embedding IS NOT NULL
                        AND 1 - (embedding <=> $1) >= $3
                    ORDER BY embedding <=> $1
                    LIMIT $4
                    """,
                    content_embedding,
                    user_id,
                    threshold,
                    limit,
                )

                return [
                    MemorySearchResult(
                        id=row["id"],
                        content=row["content"],
                        memory_key=row["memory_key"],
                        score=float(row["score"]),
                        importance=row["importance"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Find similar memories failed: {e}")
            return []


# Global singleton
_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    """Get the global memory service instance."""
    global _service
    if _service is None:
        _service = MemoryService()
    return _service
