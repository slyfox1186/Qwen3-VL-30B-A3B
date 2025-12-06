"""Image caching with perceptual hashing.

Provides Redis-backed caching for processed images using:
- Perceptual hashing (average hash) for deduplication
- Content-addressed storage for efficient retrieval
- TTL-based expiration for memory management
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class CachedImage:
    """A cached image with metadata."""

    hash: str
    data_url: str
    original_size: int
    cached_size: int
    format: str
    width: int
    height: int
    from_cache: bool = False


def compute_phash(image: Image.Image, hash_size: int = 8) -> str:
    """
    Compute perceptual hash (average hash) for an image.

    This hash is robust to:
    - Resizing
    - Minor color changes
    - Compression artifacts

    Args:
        image: PIL Image
        hash_size: Hash dimension (8 = 64-bit hash)

    Returns:
        Hexadecimal hash string
    """
    # Convert to grayscale and resize to hash_size
    img = image.convert("L").resize(
        (hash_size, hash_size),
        Image.Resampling.LANCZOS,
    )

    # Get pixel data
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)

    # Generate hash: 1 if pixel > average, 0 otherwise
    bits = "".join("1" if px > avg else "0" for px in pixels)

    # Convert to hex
    return hex(int(bits, 2))[2:].zfill(hash_size * hash_size // 4)


def compute_content_hash(data: bytes) -> str:
    """Compute SHA-256 content hash for exact matching."""
    return hashlib.sha256(data).hexdigest()[:16]


def hamming_distance(hash1: str, hash2: str) -> int:
    """Calculate Hamming distance between two hex hashes."""
    bin1 = bin(int(hash1, 16))[2:].zfill(len(hash1) * 4)
    bin2 = bin(int(hash2, 16))[2:].zfill(len(hash2) * 4)
    return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))


class ImageCache:
    """
    Redis-backed image cache with perceptual deduplication.

    Features:
    - Perceptual hash-based deduplication
    - Content hash for exact matches
    - TTL-based expiration
    - Thumbnail storage
    """

    def __init__(
        self,
        redis_client=None,
        prefix: str = "imgcache",
        ttl_seconds: int = 86400,  # 24 hours
        similarity_threshold: int = 5,  # Hamming distance threshold
    ):
        self._redis = redis_client
        self._prefix = prefix
        self._ttl = ttl_seconds
        self._threshold = similarity_threshold
        self._local_cache: dict[str, CachedImage] = {}  # In-memory fallback
        self._phash_index: dict[str, str] = {}  # phash -> content_hash

    def _key(self, hash_id: str) -> str:
        """Generate Redis key."""
        return f"{self._prefix}:{hash_id}"

    async def get(self, image_bytes: bytes) -> CachedImage | None:
        """
        Check if image exists in cache.

        Args:
            image_bytes: Raw image bytes

        Returns:
            CachedImage if found, None otherwise
        """
        try:
            # Compute content hash for exact match
            content_hash = compute_content_hash(image_bytes)

            # Check local cache first
            if content_hash in self._local_cache:
                cached = self._local_cache[content_hash]
                cached.from_cache = True
                logger.debug(f"Image cache hit (local): {content_hash}")
                return cached

            # Check Redis
            if self._redis:
                key = self._key(content_hash)
                data = await self._redis.hgetall(key)
                if data:
                    cached = CachedImage(
                        hash=content_hash,
                        data_url=data.get(b"data_url", b"").decode(),
                        original_size=int(data.get(b"original_size", 0)),
                        cached_size=int(data.get(b"cached_size", 0)),
                        format=data.get(b"format", b"").decode(),
                        width=int(data.get(b"width", 0)),
                        height=int(data.get(b"height", 0)),
                        from_cache=True,
                    )
                    # Store in local cache for faster access
                    self._local_cache[content_hash] = cached
                    logger.debug(f"Image cache hit (Redis): {content_hash}")
                    return cached

            return None

        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            return None

    async def get_similar(
        self,
        image: Image.Image,
    ) -> CachedImage | None:
        """
        Find a perceptually similar cached image.

        Args:
            image: PIL Image to find similar

        Returns:
            CachedImage if similar found, None otherwise
        """
        try:
            phash = compute_phash(image)

            # Check local index
            for cached_phash, content_hash in self._phash_index.items():
                distance = hamming_distance(phash, cached_phash)
                if distance <= self._threshold:
                    if content_hash in self._local_cache:
                        cached = self._local_cache[content_hash]
                        cached.from_cache = True
                        logger.debug(
                            f"Perceptual cache hit: {content_hash} "
                            f"(distance={distance})"
                        )
                        return cached

            return None

        except Exception as e:
            logger.warning(f"Similar image lookup failed: {e}")
            return None

    async def put(
        self,
        image_bytes: bytes,
        processed_image: Image.Image,
        data_url: str,
        original_size: int,
    ) -> CachedImage:
        """
        Store processed image in cache.

        Args:
            image_bytes: Original raw bytes
            processed_image: Processed PIL Image
            data_url: Final data URL
            original_size: Original file size

        Returns:
            CachedImage object
        """
        content_hash = compute_content_hash(image_bytes)
        phash = compute_phash(processed_image)

        cached = CachedImage(
            hash=content_hash,
            data_url=data_url,
            original_size=original_size,
            cached_size=len(data_url),
            format=processed_image.format or "jpeg",
            width=processed_image.width,
            height=processed_image.height,
            from_cache=False,
        )

        # Store in local cache
        self._local_cache[content_hash] = cached
        self._phash_index[phash] = content_hash

        # Store in Redis
        if self._redis:
            try:
                key = self._key(content_hash)
                await self._redis.hset(
                    key,
                    mapping={
                        "data_url": data_url,
                        "original_size": str(original_size),
                        "cached_size": str(len(data_url)),
                        "format": processed_image.format or "jpeg",
                        "width": str(processed_image.width),
                        "height": str(processed_image.height),
                        "phash": phash,
                    },
                )
                await self._redis.expire(key, self._ttl)
                logger.debug(f"Image cached: {content_hash}")
            except Exception as e:
                logger.warning(f"Redis cache write failed: {e}")

        return cached

    async def clear(self) -> int:
        """Clear all cached images. Returns count cleared."""
        count = len(self._local_cache)
        self._local_cache.clear()
        self._phash_index.clear()

        if self._redis:
            try:
                # Scan and delete all cache keys
                pattern = f"{self._prefix}:*"
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(
                        cursor,
                        match=pattern,
                        count=100,
                    )
                    if keys:
                        await self._redis.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis cache clear failed: {e}")

        logger.info(f"Cleared {count} cached images")
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(c.cached_size for c in self._local_cache.values())
        total_original = sum(c.original_size for c in self._local_cache.values())

        return {
            "entries": len(self._local_cache),
            "phash_entries": len(self._phash_index),
            "total_cached_size": total_size,
            "total_original_size": total_original,
            "compression_ratio": (
                total_original / total_size if total_size > 0 else 0
            ),
        }


# Global cache instance
_image_cache: ImageCache | None = None


def get_image_cache(redis_client=None) -> ImageCache:
    """Get or create the global image cache."""
    global _image_cache
    if _image_cache is None:
        _image_cache = ImageCache(redis_client=redis_client)
    return _image_cache
