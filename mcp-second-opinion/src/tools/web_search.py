"""
Web search tool for Gemini to look up documentation and code examples.

Uses DuckDuckGo for free, no-API-key searches focused on technical content.
"""

import logging
from typing import Any, Dict, List

import httpx
from google.generativeai.types import FunctionDeclaration

logger = logging.getLogger(__name__)

# Gemini function declaration for web_search
WEB_SEARCH_DECLARATION = FunctionDeclaration(
    name="web_search",
    description=(
        "Search the web for programming documentation, code examples, API references, "
        "or technical information. Returns top results with titles, URLs, and snippets. "
        "Use this when you need to look up current documentation, verify API details, "
        "or find code examples for specific libraries or frameworks."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query. Be specific and include library/framework names.",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5, max: 10)",
            },
        },
        "required": ["query"],
    },
)


async def web_search(
    query: str,
    num_results: int = 5,
) -> Dict[str, Any]:
    """
    Perform a web search using DuckDuckGo's instant answer API.

    Args:
        query: Search query (should be specific and technical)
        num_results: Number of results to return (max 10)

    Returns:
        Dict with search results including title, url, and snippet
    """
    num_results = min(num_results, 10)

    try:
        # Use DuckDuckGo HTML search (more reliable than API for programming queries)
        async with httpx.AsyncClient(timeout=10.0) as client:
            # DuckDuckGo lite endpoint for simpler parsing
            response = await client.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; MCPSecondOpinion/1.0)",
                },
            )
            response.raise_for_status()

            # Parse the results from HTML
            results = _parse_ddg_lite_results(response.text, num_results)

            if not results:
                # Fallback: try the instant answer API
                results = await _try_instant_answer(client, query)

            return {
                "success": True,
                "query": query,
                "results": results,
                "num_results": len(results),
            }

    except Exception as e:
        logger.error(f"Web search failed for query '{query}': {e}")
        return {
            "success": False,
            "query": query,
            "error": str(e),
            "results": [],
        }


def _parse_ddg_lite_results(html: str, num_results: int) -> List[Dict[str, str]]:
    """
    Parse search results from DuckDuckGo lite HTML.

    This is a simple parser that extracts links and snippets from the lite page.
    """
    results = []

    # Simple regex-free parsing for DDG lite results
    # Look for result links in the format: <a rel="nofollow" href="...">Title</a>
    import re

    # Find all result entries
    link_pattern = r'<a rel="nofollow" class="result-link" href="([^"]+)">([^<]+)</a>'
    snippet_pattern = r'<td class="result-snippet">([^<]+)</td>'

    links = re.findall(link_pattern, html)
    snippets = re.findall(snippet_pattern, html)

    for i, (url, title) in enumerate(links[:num_results]):
        result = {
            "title": title.strip(),
            "url": url,
            "snippet": snippets[i].strip() if i < len(snippets) else "",
        }
        results.append(result)

    return results


async def _try_instant_answer(client: httpx.AsyncClient, query: str) -> List[Dict[str, str]]:
    """
    Try DuckDuckGo instant answer API as fallback.
    """
    try:
        response = await client.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            },
        )
        response.raise_for_status()
        data = response.json()

        results = []

        # Check for instant answer
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", "Instant Answer"),
                "url": data.get("AbstractURL", ""),
                "snippet": data.get("AbstractText", ""),
            })

        # Check for related topics
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:50] + "...",
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                })

        return results

    except Exception as e:
        logger.warning(f"Instant answer fallback failed: {e}")
        return []
