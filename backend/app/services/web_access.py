"""Web access module for SerpApi web search."""

import json
import logging
from dataclasses import dataclass
from typing import Any

import serpapi
from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

QUERY_OPTIMIZER_SYSTEM = """Optimize queries for Google Search API. Remove filler words, fix spelling, extract key terms.

Example JSON Response:
{"query": "optimized search terms"}

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
class SearchResult:
    """A single search result from SerpApi."""

    title: str
    link: str
    snippet: str | None = None


class WebAccessService:
    """
    Service for web access operations.

    Features:
    - SerpApi web search
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ):
        settings = get_settings()
        self._api_key = api_key or settings.serpapi_api_key
        self._timeout = timeout_seconds
        self._optimizer = QueryOptimizer()

        if not self._api_key:
            logger.warning("SERPAPI_API_KEY not configured, search will be unavailable")
            self._client = None
        else:
            self._client = serpapi.Client(api_key=self._api_key)

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


# Module-level convenience functions
_service: WebAccessService | None = None


def get_web_access_service() -> WebAccessService:
    """Get or create the singleton WebAccessService instance."""
    global _service
    if _service is None:
        _service = WebAccessService()
    return _service


async def search_web(query: str, num_results: int = 10, optimize_query: bool = True) -> list[SearchResult]:
    """Perform web search. Convenience function."""
    service = get_web_access_service()
    return await service.search_web(query, num_results, optimize_query=optimize_query)
