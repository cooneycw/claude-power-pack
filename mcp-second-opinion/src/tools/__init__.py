"""
Gemini tool implementations for agentic capabilities.

These tools can be invoked by Gemini during multi-turn sessions to
gather additional information needed to answer questions.
"""

from tools.fetch_url import (
    FETCH_URL_DECLARATION,
    approve_domain,
    fetch_url,
    get_approved_domains,
    revoke_domain,
)
from tools.web_search import WEB_SEARCH_DECLARATION, web_search

__all__ = [
    "web_search",
    "fetch_url",
    "WEB_SEARCH_DECLARATION",
    "FETCH_URL_DECLARATION",
    "approve_domain",
    "revoke_domain",
    "get_approved_domains",
]
