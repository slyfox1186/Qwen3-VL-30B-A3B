"""Web access tools for LLM function calling.

Provides tools for the LLM to search the web using SerpApi.
"""

from typing import Any

from app.services.functions.registry import FunctionDefinition, FunctionParameter
from app.services.web_access import WebAccessError, get_web_access_service


async def search_web(
    query: str,
    num_results: int = 5,
) -> dict[str, Any]:
    """
    Search the web using Google via SerpApi.

    Args:
        query: Search query (will be optimized automatically)
        num_results: Number of results to return (default 5, max 10)

    Returns:
        Search results with titles, links, and snippets
    """
    service = get_web_access_service()

    # Cap results
    num_results = min(num_results, 10)

    try:
        results = await service.search_web(
            query=query,
            num_results=num_results,
            optimize_query=True,
        )

        # Format results with numbered entries for clarity
        # Escape pipe characters to prevent markdown table breakage
        def sanitize(text: str | None) -> str:
            if not text:
                return ""
            return text.replace("|", "-").strip()

        formatted_results = []
        for i, r in enumerate(results, 1):
            formatted_results.append({
                "result_number": i,
                "title": sanitize(r.title) or "(no title)",
                "url": r.link,
                "description": sanitize(r.snippet) or "(no description)",
            })

        return {
            "success": True,
            "query": query,
            "total_results": len(results),
            "results": formatted_results,
        }

    except WebAccessError as e:
        return {"success": False, "error": e.message}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_web_tools() -> list[FunctionDefinition]:
    """Get all web access tool definitions for registration."""
    return [
        FunctionDefinition(
            name="search_web",
            description="""Search the web using Google. Use for current info, images, docs, facts.

IMPORTANT: When displaying results as a table, use ONLY these fields from each result:
- result_number → Result #
- title → Title (text only)
- url → URL (the actual https:// link)
- description → Description (text only)

Example table format:
| # | Title | Link | Description |
|---|-------|------|-------------|
| 1 | Example Page | [Page Title](https://example.com) | A description here |""",
            parameters=[
                FunctionParameter(
                    name="query",
                    type="string",
                    description="Search query. For images, include 'images' or 'photos' in the query.",
                ),
                FunctionParameter(
                    name="num_results",
                    type="integer",
                    description="Number of results (default 5, max 10).",
                    required=False,
                    default=5,
                ),
            ],
            handler=search_web,
            is_async=True,
            category="web",
            cacheable=True,
        ),
    ]
