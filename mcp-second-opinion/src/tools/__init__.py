"""
Gemini tool implementations for agentic capabilities.

These tools can be invoked by Gemini during multi-turn sessions to
gather additional information needed to answer questions.
"""

from tools.web_search import web_search, WEB_SEARCH_DECLARATION
from tools.fetch_url import (
    fetch_url,
    FETCH_URL_DECLARATION,
    approve_domain,
    revoke_domain,
    get_approved_domains,
)

__all__ = [
    "web_search",
    "fetch_url",
    "WEB_SEARCH_DECLARATION",
    "FETCH_URL_DECLARATION",
    "approve_domain",
    "revoke_domain",
    "get_approved_domains",
]
