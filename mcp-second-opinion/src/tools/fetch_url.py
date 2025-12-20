"""
URL fetching tool for Gemini to read documentation pages.

Fetches and extracts text content from URLs, optimized for documentation sites.
Includes SSRF protections to prevent access to internal networks.
Supports user approval for unknown domains.
"""

import logging
import re
from typing import Any, Dict, List, Set

import httpx
from google.genai import types

from config import Config

logger = logging.getLogger(__name__)

# Session-approved domains (approved by user during this server session)
# This is a global set that persists while the server is running
_session_approved_domains: Set[str] = set()


def get_approved_domains() -> List[str]:
    """Get the list of session-approved domains."""
    return list(_session_approved_domains)


def approve_domain(domain: str) -> bool:
    """
    Approve a domain for fetching in this session.

    Args:
        domain: The domain to approve (e.g., "example.com")

    Returns:
        True if domain was added, False if it was already approved
    """
    domain = domain.lower().strip()
    if domain in _session_approved_domains:
        return False
    _session_approved_domains.add(domain)
    logger.info(f"Domain approved for session: {domain}")
    return True


def revoke_domain(domain: str) -> bool:
    """
    Revoke approval for a domain.

    Args:
        domain: The domain to revoke

    Returns:
        True if domain was removed, False if it wasn't approved
    """
    domain = domain.lower().strip()
    if domain not in _session_approved_domains:
        return False
    _session_approved_domains.discard(domain)
    logger.info(f"Domain approval revoked: {domain}")
    return True


# Gemini function declaration for fetch_url (using new google-genai SDK)
FETCH_URL_DECLARATION = types.FunctionDeclaration(
    name="fetch_url",
    description=(
        "Fetch and read the content of a URL. Best used for documentation pages, "
        "API references, GitHub READMEs, or technical articles. Returns the main "
        "text content extracted from the page (HTML is stripped). "
        "Use this after web_search to read relevant documentation. "
        "Note: Unknown domains require user approval before fetching."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "url": types.Schema(
                type=types.Type.STRING,
                description="The URL to fetch. Must be a valid HTTP/HTTPS URL.",
            ),
            "max_length": types.Schema(
                type=types.Type.INTEGER,
                description="Maximum characters to return (default: 10000, max: 50000)",
            ),
        },
        required=["url"],
    ),
)


async def fetch_url(
    url: str,
    max_length: int = 10000,
) -> Dict[str, Any]:
    """
    Fetch content from a URL and extract text.

    Includes SSRF protections:
    - Domain allowlist with user approval for unknown domains
    - Private IP blocking (always enforced)
    - Timeout limits
    - Size limits
    - Redirect limits

    Args:
        url: URL to fetch
        max_length: Maximum content length to return (default: 10000, max: 50000)

    Returns:
        Dict with success status, content, and metadata.
        If domain needs approval, returns needs_approval=True with domain info.
    """
    max_length = min(max_length, 50000)

    # ==========================================================================
    # SSRF Protection: Validate URL before fetching
    # ==========================================================================
    status, reason, hostname = Config.is_url_allowed(url, list(_session_approved_domains))

    if status == "blocked":
        logger.warning(f"URL blocked by SSRF protection: {url} - {reason}")
        return {
            "success": False,
            "url": url,
            "error": f"URL blocked: {reason}",
            "content": "",
            "blocked_by": "ssrf_protection",
        }

    if status == "needs_approval":
        logger.info(f"URL requires user approval: {url} (domain: {hostname})")
        return {
            "success": False,
            "url": url,
            "needs_approval": True,
            "domain": hostname,
            "message": (
                f"The domain '{hostname}' is not in the auto-approved list. "
                f"Please ask the user if they want to allow fetching from this domain. "
                f"If approved, use the approve_fetch_domain tool with domain='{hostname}', "
                f"then retry fetch_url."
            ),
            "content": "",
        }

    try:
        async with httpx.AsyncClient(
            timeout=float(Config.FETCH_URL_TIMEOUT),
            follow_redirects=True,
            max_redirects=Config.FETCH_URL_MAX_REDIRECTS,
        ) as client:
            # Use streaming to enforce size limits
            async with client.stream(
                "GET",
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; MCPSecondOpinion/1.0; Documentation Reader)",
                    "Accept": "text/html,application/xhtml+xml,text/plain,text/markdown",
                },
            ) as response:
                response.raise_for_status()

                # Check content length header if available
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > Config.FETCH_URL_MAX_SIZE:
                    logger.warning(f"Content too large: {content_length} bytes > {Config.FETCH_URL_MAX_SIZE}")
                    return {
                        "success": False,
                        "url": url,
                        "error": f"Content too large ({content_length} bytes). Max: {Config.FETCH_URL_MAX_SIZE}",
                        "content": "",
                    }

                # Read content with size limit
                chunks = []
                total_size = 0
                async for chunk in response.aiter_bytes():
                    total_size += len(chunk)
                    if total_size > Config.FETCH_URL_MAX_SIZE:
                        logger.warning(f"Content exceeded size limit during download: {total_size}")
                        return {
                            "success": False,
                            "url": url,
                            "error": f"Content exceeded size limit ({Config.FETCH_URL_MAX_SIZE} bytes)",
                            "content": "",
                        }
                    chunks.append(chunk)

                raw_content = b"".join(chunks)

                # Decode content
                try:
                    text_content = raw_content.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = raw_content.decode("latin-1")

                content_type = response.headers.get("content-type", "")

                # Handle different content types
                if "application/json" in content_type:
                    # Return JSON as-is (useful for API endpoints)
                    content = text_content[:max_length]
                elif "text/plain" in content_type or url.endswith((".md", ".txt", ".rst")):
                    # Plain text or markdown - return as-is
                    content = text_content[:max_length]
                else:
                    # HTML - extract text content
                    content = _extract_text_from_html(text_content, max_length)

                return {
                    "success": True,
                    "url": url,
                    "final_url": str(response.url),  # After redirects
                    "content_type": content_type,
                    "content": content,
                    "length": len(content),
                    "raw_size": total_size,
                    "truncated": len(text_content) > max_length,
                }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching {url}: {e.response.status_code}")
        return {
            "success": False,
            "url": url,
            "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
            "content": "",
        }
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching {url}")
        return {
            "success": False,
            "url": url,
            "error": f"Request timed out after {Config.FETCH_URL_TIMEOUT} seconds",
            "content": "",
        }
    except httpx.TooManyRedirects:
        logger.error(f"Too many redirects fetching {url}")
        return {
            "success": False,
            "url": url,
            "error": f"Too many redirects (max: {Config.FETCH_URL_MAX_REDIRECTS})",
            "content": "",
        }
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return {
            "success": False,
            "url": url,
            "error": str(e),
            "content": "",
        }


def _extract_text_from_html(html: str, max_length: int) -> str:
    """
    Extract readable text from HTML content.

    Uses simple regex-based extraction to avoid heavy dependencies.
    Focuses on main content areas common in documentation sites.
    """
    # Remove script and style elements
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<noscript[^>]*>.*?</noscript>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove navigation, header, footer (common in documentation sites)
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<aside[^>]*>.*?</aside>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Try to find main content area
    main_match = re.search(
        r"<main[^>]*>(.*?)</main>|<article[^>]*>(.*?)</article>|<div[^>]*class=\"[^\"]*content[^\"]*\"[^>]*>(.*?)</div>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if main_match:
        # Use the matched main content
        content = main_match.group(1) or main_match.group(2) or main_match.group(3) or html
    else:
        # Fall back to body content
        body_match = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.DOTALL | re.IGNORECASE)
        content = body_match.group(1) if body_match else html

    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", content)

    # Decode common HTML entities
    html_entities = {
        "&nbsp;": " ",
        "&lt;": "<",
        "&gt;": ">",
        "&amp;": "&",
        "&quot;": '"',
        "&#39;": "'",
        "&apos;": "'",
        "&mdash;": "—",
        "&ndash;": "–",
        "&hellip;": "...",
        "&copy;": "(c)",
        "&reg;": "(R)",
    }
    for entity, char in html_entities.items():
        text = text.replace(entity, char)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    # Truncate if needed
    if len(text) > max_length:
        text = text[:max_length] + "... [truncated]"

    return text
