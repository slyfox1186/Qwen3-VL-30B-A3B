"""Embedding service for generating text embeddings.

Uses sentence-transformers for high-quality text embeddings.
Supports lazy loading and caching for efficiency.
"""

import logging
from typing import Any

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model: Any = None
_model_name: str | None = None


def _load_model(model_name: str) -> Any:
    """Load sentence-transformers model on CPU with all available cores.

    Forces CPU to avoid GPU memory contention with vLLM.
    """
    global _model, _model_name

    if _model is not None and _model_name == model_name:
        return _model

    try:
        import os

        import torch
        from sentence_transformers import SentenceTransformer

        # Force CPU and use all available logical cores
        num_threads = os.cpu_count() or 8
        torch.set_num_threads(num_threads)

        logger.info(f"Loading embedding model on CPU ({num_threads} threads): {model_name}")
        _model = SentenceTransformer(model_name, device="cpu")
        _model_name = model_name
        logger.info(f"Embedding model loaded on CPU with {num_threads} threads")
        return _model
    except ImportError:
        logger.warning(
            "sentence-transformers not installed. "
            "Vector search will be disabled. "
            "Install with: pip install sentence-transformers"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        return None


class EmbeddingService:
    """
    Service for generating text embeddings.

    Uses sentence-transformers models for high-quality semantic embeddings.
    Supports batch processing for efficiency.
    """

    def __init__(
        self,
        model_name: str | None = None,
        dimension: int | None = None,
        batch_size: int | None = None,
    ):
        settings = get_settings()
        self._model_name = model_name or settings.embedding_model
        self._dimension = dimension or settings.embedding_dimension
        self._batch_size = batch_size or settings.embedding_batch_size
        self._model: Any = None

    @property
    def model(self) -> Any:
        """Get the loaded model (lazy loading)."""
        if self._model is None:
            self._model = _load_model(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension

    @property
    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self.model is not None

    def embed_text(self, text: str) -> np.ndarray | None:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            Numpy array of shape (dimension,) or None if unavailable
        """
        if not self.is_available:
            return None

        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def embed_batch(self, texts: list[str]) -> list[np.ndarray] | None:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of numpy arrays or None if unavailable
        """
        if not self.is_available or not texts:
            return None

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=self._batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return [e.astype(np.float32) for e in embeddings]
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            return None

    def cosine_similarity(
        self,
        query_embedding: np.ndarray,
        embeddings: list[np.ndarray],
    ) -> list[float]:
        """
        Compute cosine similarity between query and multiple embeddings.

        Since embeddings are normalized, cosine similarity = dot product.

        Args:
            query_embedding: Query embedding (normalized)
            embeddings: List of embeddings to compare against

        Returns:
            List of similarity scores (0 to 1)
        """
        if not embeddings:
            return []

        # Stack embeddings into matrix
        matrix = np.stack(embeddings)

        # Compute dot products (cosine similarity for normalized vectors)
        similarities = np.dot(matrix, query_embedding)

        return similarities.tolist()


# Global singleton
_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service
