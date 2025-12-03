"""Web access module for SerpApi search and image URL downloading."""

import base64
import json
import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import httpx
import serpapi
from openai import AsyncOpenAI
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)

QUERY_OPTIMIZER_SYSTEM = """Your ONLY job is to return an optimized version of the user's query tuned for use with Google's API search engine.

Example JSON Response: {"query": "optimized search terms"}

Return ONLY a valid JSON object and nothing else."""

QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "The optimized search query"}
    },
    "required": ["query"],
}


class WebAccessError(Exception):
    """Raised when web access operations fail."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class QueryOptimizer:
    """Uses LLM to optimize search queries."""

    def __init__(self):
        settings = get_settings()
        self._client = AsyncOpenAI(
            base_url=settings.vllm_base_url,
            api_key=settings.vllm_api_key,
            timeout=30.0,
        )
        self._model = settings.vllm_model

    async def optimize(self, query: str) -> str:
        """Optimize a user query for Google search."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": QUERY_OPTIMIZER_SYSTEM},
                    {"role": "user", "content": query},
                ],
                max_completion_tokens=100,
                temperature=0.3,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "search_query", "schema": QUERY_SCHEMA},
                },
            )
            result = json.loads(response.choices[0].message.content)
            optimized = result.get("query", query)
            logger.info(f"Query optimized: '{query}' -> '{optimized}'")
            return optimized
        except Exception as e:
            logger.warning(f"Query optimization failed, using original: {e}")
            return query


@dataclass
class ImageDownloadResult:
    """Result of downloading and validating an image from URL."""

    url: str
    format: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    base64_data: str
    data_url: str


@dataclass
class SearchResult:
    """A single search result from SerpApi."""

    title: str
    link: str
    snippet: str | None = None
    thumbnail: str | None = None
    original_image: str | None = None


class WebAccessService:
    """
    Service for web access operations.

    Features:
    - SerpApi search (web, images, reverse image)
    - Download images from URL
    - Validate and convert images to base64
    """

    MIME_TYPES = {
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
    }

    ALLOWED_FORMATS = {"jpeg", "jpg", "png", "gif", "webp", "bmp"}

    def __init__(
        self,
        api_key: str | None = None,
        max_image_size_bytes: int | None = None,
        timeout_seconds: float = 30.0,
    ):
        settings = get_settings()
        self._api_key = api_key or settings.serpapi_api_key
        self._max_image_size = max_image_size_bytes or settings.max_image_size_bytes
        self._timeout = timeout_seconds
        self._optimizer = QueryOptimizer()

        if not self._api_key:
            logger.warning("SERPAPI_API_KEY not configured, search will be unavailable")
            self._client = None
        else:
            self._client = serpapi.Client(api_key=self._api_key)

    async def download_image_from_url(self, url: str) -> ImageDownloadResult:
        """
        Download an image from URL and return it as base64.

        Args:
            url: The image URL to download

        Returns:
            ImageDownloadResult with validated image data

        Raises:
            WebAccessError: If download or validation fails
        """
        logger.info(f"Downloading image from URL: {url}")

        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.TimeoutException:
            raise WebAccessError(f"Timeout downloading image from {url}", status_code=408)
        except httpx.HTTPStatusError as e:
            raise WebAccessError(
                f"HTTP error downloading image: {e.response.status_code}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            raise WebAccessError(f"Network error downloading image: {e}")

        image_bytes = response.content
        size_bytes = len(image_bytes)

        if size_bytes > self._max_image_size:
            max_mb = self._max_image_size / (1024 * 1024)
            actual_mb = size_bytes / (1024 * 1024)
            raise WebAccessError(
                f"Image size {actual_mb:.1f}MB exceeds maximum {max_mb:.0f}MB"
            )

        # Validate and get image info using PIL
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                img.verify()

            # Re-open to get format and dimensions
            with Image.open(BytesIO(image_bytes)) as img:
                detected_format = img.format.lower() if img.format else None
                width, height = img.size

        except Exception as e:
            raise WebAccessError(f"Invalid or corrupted image: {e}")

        if not detected_format or detected_format not in self.ALLOWED_FORMATS:
            raise WebAccessError(
                f"Unsupported image format: {detected_format}. "
                f"Allowed: {', '.join(self.ALLOWED_FORMATS)}"
            )

        mime_type = self.MIME_TYPES.get(detected_format, f"image/{detected_format}")
        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{base64_data}"

        result = ImageDownloadResult(
            url=url,
            format=detected_format,
            mime_type=mime_type,
            width=width,
            height=height,
            size_bytes=size_bytes,
            base64_data=base64_data,
            data_url=data_url,
        )

        logger.info(
            f"Downloaded image: {detected_format} {width}x{height} "
            f"({size_bytes / 1024:.1f}KB)"
        )

        return result

    async def search_web(
        self,
        query: str,
        num_results: int = 10,
        location: str | None = None,
        optimize_query: bool = True,
    ) -> list[SearchResult]:
        """
        Perform a web search using SerpApi.

        Args:
            query: Search query
            num_results: Maximum number of results to return
            location: Optional location for localized results
            optimize_query: Whether to optimize query using LLM

        Returns:
            List of SearchResult objects

        Raises:
            WebAccessError: If search fails or API key not configured
        """
        if not self._client:
            raise WebAccessError("SERPAPI_API_KEY not configured")

        if optimize_query:
            query = await self._optimizer.optimize(query)

        logger.info(f"Performing web search: {query}")

        params: dict[str, Any] = {
            "engine": "google",
            "q": query,
            "num": num_results,
        }
        if location:
            params["location"] = location

        try:
            results = self._client.search(params)
        except Exception as e:
            raise WebAccessError(f"Search failed: {e}")

        search_results = []
        organic_results = results.get("organic_results", [])

        for item in organic_results[:num_results]:
            search_results.append(
                SearchResult(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    snippet=item.get("snippet"),
                )
            )

        logger.info(f"Found {len(search_results)} web results")
        return search_results

    async def search_images(
        self,
        query: str,
        num_results: int = 10,
        optimize_query: bool = True,
    ) -> list[SearchResult]:
        """
        Perform an image search using SerpApi.

        Args:
            query: Search query
            num_results: Maximum number of results to return
            optimize_query: Whether to optimize query using LLM

        Returns:
            List of SearchResult objects with image URLs

        Raises:
            WebAccessError: If search fails or API key not configured
        """
        if not self._client:
            raise WebAccessError("SERPAPI_API_KEY not configured")

        if optimize_query:
            query = await self._optimizer.optimize(query)

        logger.info(f"Performing image search: {query}")

        try:
            results = self._client.search({
                "engine": "google_images",
                "q": query,
                "num": num_results,
            })
        except Exception as e:
            raise WebAccessError(f"Image search failed: {e}")

        search_results = []
        images_results = results.get("images_results", [])

        for item in images_results[:num_results]:
            search_results.append(
                SearchResult(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    thumbnail=item.get("thumbnail"),
                    original_image=item.get("original"),
                )
            )

        logger.info(f"Found {len(search_results)} image results")
        return search_results

    def reverse_image_search(
        self,
        image_url: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """
        Perform a reverse image search using SerpApi.

        Args:
            image_url: URL of the image to search for
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            WebAccessError: If search fails or API key not configured
        """
        if not self._client:
            raise WebAccessError("SERPAPI_API_KEY not configured")

        logger.info(f"Performing reverse image search: {image_url}")

        try:
            results = self._client.search({
                "engine": "google_reverse_image",
                "image_url": image_url,
                "max_results": str(max_results),
            })
        except Exception as e:
            raise WebAccessError(f"Reverse image search failed: {e}")

        search_results = []

        # Check for inline images (visually similar)
        inline_images = results.get("inline_images", [])
        for item in inline_images[:max_results]:
            search_results.append(
                SearchResult(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    thumbnail=item.get("thumbnail"),
                    original_image=item.get("original"),
                )
            )

        # Also check organic results
        organic_results = results.get("organic_results", [])
        remaining = max_results - len(search_results)
        for item in organic_results[:remaining]:
            search_results.append(
                SearchResult(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    snippet=item.get("snippet"),
                )
            )

        logger.info(f"Found {len(search_results)} reverse image search results")
        return search_results


# Module-level convenience functions
_service: WebAccessService | None = None


def get_web_access_service() -> WebAccessService:
    """Get or create the singleton WebAccessService instance."""
    global _service
    if _service is None:
        _service = WebAccessService()
    return _service


async def download_image(url: str) -> ImageDownloadResult:
    """Download an image from URL. Convenience function."""
    service = get_web_access_service()
    return await service.download_image_from_url(url)


async def search_web(query: str, num_results: int = 10, optimize_query: bool = True) -> list[SearchResult]:
    """Perform web search. Convenience function."""
    service = get_web_access_service()
    return await service.search_web(query, num_results, optimize_query=optimize_query)


async def search_images(query: str, num_results: int = 10, optimize_query: bool = True) -> list[SearchResult]:
    """Perform image search. Convenience function."""
    service = get_web_access_service()
    return await service.search_images(query, num_results, optimize_query=optimize_query)


def reverse_image_search(image_url: str, max_results: int = 10) -> list[SearchResult]:
    """Perform reverse image search. Convenience function."""
    service = get_web_access_service()
    return service.reverse_image_search(image_url, max_results)
