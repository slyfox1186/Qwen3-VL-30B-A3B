"""Redis-based vector store for semantic search.

Stores embeddings with metadata in Redis and provides
efficient similarity search using cosine similarity.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.redis.client import RedisClient
from app.services.embeddings.service import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


# Redis key prefixes
VECTOR_PREFIX = "vec:"
VECTOR_DATA_PREFIX = "vec:data:"
VECTOR_INDEX_PREFIX = "vec:idx:"


@dataclass
class VectorSearchResult:
    """Result from vector similarity search."""

    id: str
    score: float
    metadata: dict[str, Any]


class VectorStore:
    """
    Redis-based vector store for embeddings.

    Stores embeddings as JSON-serialized numpy arrays with associated metadata.
    Provides similarity search using in-memory cosine similarity computation.

    For production with large datasets, consider using:
    - Redis Stack with RediSearch VSS
    - Pinecone, Weaviate, or Qdrant
    """

    def __init__(
        self,
        redis_client: RedisClient,
        embedding_service: EmbeddingService | None = None,
        namespace: str = "messages",
    ):
        self._redis = redis_client
        self._embeddings = embedding_service or get_embedding_service()
        self._namespace = namespace

    def _vector_key(self, id: str) -> str:
        """Get Redis key for a vector."""
        return f"{VECTOR_DATA_PREFIX}{self._namespace}:{id}"

    def _index_key(self) -> str:
        """Get Redis key for the vector index."""
        return f"{VECTOR_INDEX_PREFIX}{self._namespace}"

    async def add(
        self,
        id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """
        Add a text with its embedding to the store.

        Args:
            id: Unique identifier for this vector
            text: Text to embed and store
            metadata: Additional metadata to store with the vector
            ttl_seconds: Optional TTL for the vector

        Returns:
            True if successfully added
        """
        if not self._embeddings.is_available:
            logger.debug("Embedding service not available, skipping vector storage")
            return False

        try:
            # Generate embedding
            embedding = self._embeddings.embed_text(text)
            if embedding is None:
                return False

            # Prepare data
            data = {
                "id": id,
                "text": text[:500],  # Store truncated text for reference
                "embedding": embedding.tolist(),  # Convert to list for JSON
                "metadata": metadata or {},
            }

            # Store in Redis
            key = self._vector_key(id)
            await self._redis.client.set(key, json.dumps(data))

            if ttl_seconds:
                await self._redis.client.expire(key, ttl_seconds)

            # Add to index (sorted set with timestamp for ordering)
            import time
            await self._redis.client.zadd(
                self._index_key(),
                {id: time.time()},
            )

            if ttl_seconds:
                await self._redis.client.expire(self._index_key(), ttl_seconds)

            logger.debug(f"Added vector for id={id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add vector: {e}")
            return False

    async def add_batch(
        self,
        items: list[tuple[str, str, dict[str, Any] | None]],
        ttl_seconds: int | None = None,
    ) -> int:
        """
        Add multiple texts with their embeddings.

        Args:
            items: List of (id, text, metadata) tuples
            ttl_seconds: Optional TTL for the vectors

        Returns:
            Number of successfully added items
        """
        if not self._embeddings.is_available or not items:
            return 0

        try:
            # Extract texts and generate embeddings in batch
            ids = [item[0] for item in items]
            texts = [item[1] for item in items]
            metadatas = [item[2] or {} for item in items]

            embeddings = self._embeddings.embed_batch(texts)
            if embeddings is None:
                return 0

            # Store each vector
            import time
            timestamp = time.time()
            added = 0

            async with self._redis.pipeline() as pipe:
                for i, (id, text, metadata) in enumerate(zip(ids, texts, metadatas)):
                    data = {
                        "id": id,
                        "text": text[:500],
                        "embedding": embeddings[i].tolist(),
                        "metadata": metadata,
                    }
                    key = self._vector_key(id)
                    pipe.set(key, json.dumps(data))
                    if ttl_seconds:
                        pipe.expire(key, ttl_seconds)
                    pipe.zadd(self._index_key(), {id: timestamp + i * 0.001})
                    added += 1

            if ttl_seconds:
                await self._redis.client.expire(self._index_key(), ttl_seconds)

            logger.info(f"Added {added} vectors in batch")
            return added

        except Exception as e:
            logger.error(f"Failed to add batch vectors: {e}")
            return 0

    async def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """
        Search for similar vectors using cosine similarity.

        Args:
            query: Query text to search for
            top_k: Maximum number of results to return
            min_score: Minimum similarity score (0 to 1)
            filter_metadata: Optional metadata filter (exact match)

        Returns:
            List of search results sorted by similarity (highest first)
        """
        if not self._embeddings.is_available:
            return []

        try:
            # Generate query embedding
            query_embedding = self._embeddings.embed_text(query)
            if query_embedding is None:
                return []

            # Get all vector IDs from index
            vector_ids = await self._redis.client.zrange(self._index_key(), 0, -1)
            if not vector_ids:
                return []

            # Fetch all vectors
            vectors = []
            for vid in vector_ids:
                key = self._vector_key(vid)
                data_str = await self._redis.client.get(key)
                if data_str:
                    vectors.append(json.loads(data_str))

            if not vectors:
                return []

            # Apply metadata filter if provided
            if filter_metadata:
                vectors = [
                    v for v in vectors
                    if all(
                        v.get("metadata", {}).get(k) == val
                        for k, val in filter_metadata.items()
                    )
                ]

            if not vectors:
                return []

            # Extract embeddings and compute similarities
            embeddings = [np.array(v["embedding"], dtype=np.float32) for v in vectors]
            similarities = self._embeddings.cosine_similarity(query_embedding, embeddings)

            # Create results with scores
            results = []
            for i, (vector, score) in enumerate(zip(vectors, similarities)):
                if score >= min_score:
                    results.append(VectorSearchResult(
                        id=vector["id"],
                        score=score,
                        metadata={
                            "text": vector.get("text", ""),
                            **vector.get("metadata", {}),
                        },
                    ))

            # Sort by score (descending) and limit
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def delete(self, id: str) -> bool:
        """
        Delete a vector from the store.

        Args:
            id: Vector ID to delete

        Returns:
            True if deleted
        """
        try:
            key = self._vector_key(id)
            await self._redis.client.delete(key)
            await self._redis.client.zrem(self._index_key(), id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete vector: {e}")
            return False

    async def get(self, id: str) -> dict[str, Any] | None:
        """
        Get a vector by ID.

        Args:
            id: Vector ID

        Returns:
            Vector data including metadata, or None if not found
        """
        try:
            key = self._vector_key(id)
            data_str = await self._redis.client.get(key)
            if data_str:
                return json.loads(data_str)
            return None
        except Exception as e:
            logger.error(f"Failed to get vector: {e}")
            return None

    async def count(self) -> int:
        """Get the number of vectors in the store."""
        try:
            return await self._redis.client.zcard(self._index_key())
        except Exception as e:
            logger.error(f"Failed to count vectors: {e}")
            return 0

    async def clear(self) -> bool:
        """Clear all vectors from the store."""
        try:
            # Get all vector IDs
            vector_ids = await self._redis.client.zrange(self._index_key(), 0, -1)

            # Delete all vectors
            if vector_ids:
                keys = [self._vector_key(vid) for vid in vector_ids]
                await self._redis.client.delete(*keys)

            # Delete index
            await self._redis.client.delete(self._index_key())
            return True
        except Exception as e:
            logger.error(f"Failed to clear vectors: {e}")
            return False
