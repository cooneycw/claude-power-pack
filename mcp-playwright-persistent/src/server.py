#!/usr/bin/env python3
"""
MCP Playwright Persistent Server

A persistent browser automation server with session management.
Port: 8081
Transport: SSE

Features:
- Persistent browser sessions
- Multi-tab support
- Full automation (click, type, fill, select, hover)
- Screenshot and PDF generation
"""

import argparse
import base64
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from starlette.requests import Request
from starlette.responses import JSONResponse

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Server configuration
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8081"))
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1 hour default

# Initialize FastMCP
mcp = FastMCP(
    "MCP Playwright Persistent",
    instructions="""Persistent browser automation with session management.

    Create a session first with create_session(), then use session_id for all operations.

    Core tools (always loaded):
    - create_session / close_session - Session lifecycle
    - browser_navigate - Go to URL
    - browser_click / browser_fill - Interact with elements
    - browser_screenshot - Capture page or element

    Extended tools (search to discover): tabs, PDF, evaluate JS, wait, query selectors.
    """
)

# Session storage
sessions: dict = {}
playwright_instance = None
browser_instance: Optional[Browser] = None


@mcp.custom_route("/", methods=["GET"])
async def root_health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Claude Code MCP connection verification."""
    return JSONResponse({
        "status": "healthy",
        "server": "MCP Playwright Persistent",
        "port": SERVER_PORT,
        "sessions": len(sessions),
    })


class BrowserSession:
    """Represents a persistent browser session."""

    def __init__(self, session_id: str, context: BrowserContext, headless: bool = True):
        self.session_id = session_id
        self.context = context
        self.pages: dict[str, Page] = {}
        self.active_page_id: Optional[str] = None
        self.headless = headless
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.console_messages: list = []

    def update_activity(self):
        self.last_activity = datetime.now()

    def is_expired(self) -> bool:
        return datetime.now() - self.last_activity > timedelta(seconds=SESSION_TIMEOUT)

    async def get_active_page(self) -> Optional[Page]:
        if self.active_page_id and self.active_page_id in self.pages:
            return self.pages[self.active_page_id]
        return None

    async def create_page(self) -> tuple[str, Page]:
        page = await self.context.new_page()
        page_id = str(uuid.uuid4())[:8]
        self.pages[page_id] = page
        self.active_page_id = page_id

        # Capture console messages
        page.on("console", lambda msg: self.console_messages.append({
            "type": msg.type,
            "text": msg.text,
            "timestamp": datetime.now().isoformat()
        }))

        return page_id, page


async def get_browser() -> Browser:
    """Get or create the browser instance."""
    global playwright_instance, browser_instance

    if browser_instance is None:
        playwright_instance = await async_playwright().start()
        browser_instance = await playwright_instance.chromium.launch(headless=True)
        logger.info("Browser instance created")

    return browser_instance


async def get_session(session_id: str) -> Optional[BrowserSession]:
    """Get a session by ID."""
    session = sessions.get(session_id)
    if session and not session.is_expired():
        session.update_activity()
        return session
    elif session and session.is_expired():
        await close_session_internal(session_id)
    return None


async def close_session_internal(session_id: str):
    """Internal session cleanup."""
    session = sessions.pop(session_id, None)
    if session:
        try:
            await session.context.close()
        except Exception as e:
            logger.error(f"Error closing session: {e}")


# ============================================================================
# Session Management Tools - core: create_session, close_session
# ============================================================================

@mcp.tool(tags={"core"})
async def create_session(
    headless: bool = True,
    viewport_width: int = 1280,
    viewport_height: int = 720,
    cdp_endpoint: Optional[str] = None
) -> dict:
    """Create a persistent browser session. Returns session_id for all subsequent operations."""
    global playwright_instance

    if cdp_endpoint:
        # Connect to existing Chrome via CDP
        if playwright_instance is None:
            playwright_instance = await async_playwright().start()

        try:
            browser = await playwright_instance.chromium.connect_over_cdp(cdp_endpoint)
            logger.info(f"Connected to existing browser at {cdp_endpoint}")
            is_external = True
        except Exception as e:
            return {"error": f"Failed to connect to CDP endpoint: {str(e)}"}
    else:
        # Launch new browser
        browser = await get_browser()
        is_external = False

    context = await browser.new_context(
        viewport={"width": viewport_width, "height": viewport_height}
    )

    session_id = str(uuid.uuid4())[:12]
    session = BrowserSession(session_id, context, headless)
    session.is_external_browser = is_external  # Track if using external browser
    sessions[session_id] = session

    # Create initial page
    page_id, _ = await session.create_page()

    logger.info(f"Created session {session_id}")

    result = {
        "session_id": session_id,
        "active_page_id": page_id,
        "headless": headless,
        "viewport": {"width": viewport_width, "height": viewport_height}
    }

    if cdp_endpoint:
        result["cdp_endpoint"] = cdp_endpoint
        result["external_browser"] = True

    return result


@mcp.tool(tags={"core"})
async def close_session(session_id: str) -> dict:
    """Close a browser session and release all resources."""
    if session_id in sessions:
        await close_session_internal(session_id)
        return {"status": "closed", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


@mcp.tool(tags={"extended"})
async def list_sessions() -> dict:
    """List all active browser sessions with their details."""
    active_sessions = []
    for sid, session in list(sessions.items()):
        if session.is_expired():
            await close_session_internal(sid)
        else:
            active_sessions.append({
                "session_id": sid,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "page_count": len(session.pages),
                "active_page_id": session.active_page_id
            })
    return {"sessions": active_sessions, "count": len(active_sessions)}


@mcp.tool(tags={"extended"})
async def get_session_info(session_id: str) -> dict:
    """Get detailed session info including pages, URLs, and activity timestamps."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found", "session_id": session_id}

    pages_info = []
    for pid, page in session.pages.items():
        try:
            pages_info.append({
                "page_id": pid,
                "url": page.url,
                "title": await page.title()
            })
        except Exception:
            pages_info.append({"page_id": pid, "error": "Page closed"})

    return {
        "session_id": session_id,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat(),
        "headless": session.headless,
        "pages": pages_info,
        "active_page_id": session.active_page_id
    }


@mcp.tool(tags={"extended"})
async def cleanup_idle_sessions(max_idle_minutes: int = 30) -> dict:
    """Clean up sessions idle longer than max_idle_minutes (default 30)."""
    cleaned = 0
    threshold = datetime.now() - timedelta(minutes=max_idle_minutes)

    for sid, session in list(sessions.items()):
        if session.last_activity < threshold:
            await close_session_internal(sid)
            cleaned += 1

    return {"cleaned": cleaned, "remaining": len(sessions)}


# ============================================================================
# Navigation Tools - core: navigate, click, fill
# ============================================================================

@mcp.tool(tags={"core"})
async def browser_navigate(session_id: str, url: str, wait_until: str = "load") -> dict:
    """Navigate to a URL. wait_until: load, domcontentloaded, or networkidle."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    response = await page.goto(url, wait_until=wait_until)
    return {
        "url": page.url,
        "title": await page.title(),
        "status": response.status if response else None
    }


@mcp.tool(tags={"core"})
async def browser_click(session_id: str, selector: str, button: str = "left", click_count: int = 1) -> dict:
    """Click an element. Supports CSS selectors and text selectors."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.click(selector, button=button, click_count=click_count)
    return {"status": "clicked", "selector": selector}


@mcp.tool(tags={"extended"})
async def browser_type(session_id: str, selector: str, text: str, delay: int = 0) -> dict:
    """Type text with simulated keystrokes. Use browser_fill for faster input."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.type(selector, text, delay=delay)
    return {"status": "typed", "selector": selector, "length": len(text)}


@mcp.tool(tags={"core"})
async def browser_fill(session_id: str, selector: str, value: str) -> dict:
    """Fill an input element with text. Clears existing value first. Faster than browser_type."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.fill(selector, value)
    return {"status": "filled", "selector": selector}


@mcp.tool(tags={"extended"})
async def browser_select_option(session_id: str, selector: str, value: str) -> dict:
    """Select an option from a dropdown element."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.select_option(selector, value)
    return {"status": "selected", "selector": selector, "value": value}


@mcp.tool(tags={"extended"})
async def browser_hover(session_id: str, selector: str) -> dict:
    """Hover over an element by CSS selector."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.hover(selector)
    return {"status": "hovered", "selector": selector}


# ============================================================================
# Tab Management Tools - all extended
# ============================================================================

@mcp.tool(tags={"extended"})
async def browser_new_tab(session_id: str, url: Optional[str] = None) -> dict:
    """Open a new tab, optionally navigating to a URL."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page_id, page = await session.create_page()

    if url:
        await page.goto(url)

    return {
        "page_id": page_id,
        "url": page.url,
        "is_active": session.active_page_id == page_id
    }


@mcp.tool(tags={"extended"})
async def browser_switch_tab(session_id: str, page_id: str) -> dict:
    """Switch active tab by page_id."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    if page_id not in session.pages:
        return {"error": "Page not found", "page_id": page_id}

    session.active_page_id = page_id
    page = session.pages[page_id]

    return {
        "page_id": page_id,
        "url": page.url,
        "title": await page.title()
    }


@mcp.tool(tags={"extended"})
async def browser_close_tab(session_id: str, page_id: str) -> dict:
    """Close a tab by page_id. Switches to another tab if closing the active one."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    if page_id not in session.pages:
        return {"error": "Page not found"}

    page = session.pages.pop(page_id)
    await page.close()

    # Switch to another page if we closed the active one
    if session.active_page_id == page_id:
        if session.pages:
            session.active_page_id = list(session.pages.keys())[0]
        else:
            session.active_page_id = None

    return {"status": "closed", "page_id": page_id}


@mcp.tool(tags={"extended"})
async def browser_go_back(session_id: str) -> dict:
    """Navigate back in browser history."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.go_back()
    return {"url": page.url, "title": await page.title()}


@mcp.tool(tags={"extended"})
async def browser_go_forward(session_id: str) -> dict:
    """Navigate forward in browser history."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.go_forward()
    return {"url": page.url, "title": await page.title()}


@mcp.tool(tags={"extended"})
async def browser_reload(session_id: str) -> dict:
    """Reload the current page."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.reload()
    return {"url": page.url, "title": await page.title()}


# ============================================================================
# Capture Tools - core: screenshot
# ============================================================================

@mcp.tool(tags={"core"})
async def browser_screenshot(session_id: str, full_page: bool = False, selector: Optional[str] = None) -> dict:
    """Capture a PNG screenshot. Set full_page=True for full scroll, or pass selector for element screenshot."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    if selector:
        element = await page.query_selector(selector)
        if not element:
            return {"error": "Element not found", "selector": selector}
        screenshot = await element.screenshot()
    else:
        screenshot = await page.screenshot(full_page=full_page)

    return {
        "screenshot": base64.b64encode(screenshot).decode(),
        "format": "png",
        "full_page": full_page
    }


@mcp.tool(tags={"extended"})
async def browser_snapshot(session_id: str) -> dict:
    """Get accessibility tree snapshot of the page (YAML format)."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    # Use new aria_snapshot API (page.accessibility was removed in Playwright 1.49+)
    snapshot = await page.locator("body").aria_snapshot()
    return {"snapshot": snapshot, "format": "yaml"}


@mcp.tool(tags={"extended"})
async def browser_pdf(session_id: str, format: str = "A4") -> dict:
    """Generate PDF of the page (headless mode only). Format: A4, Letter, etc."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    if not session.headless:
        return {"error": "PDF generation only works in headless mode"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    pdf = await page.pdf(format=format)
    return {
        "pdf": base64.b64encode(pdf).decode(),
        "format": format
    }


@mcp.tool(tags={"extended"})
async def browser_get_content(session_id: str) -> dict:
    """Get the full HTML content of the current page."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    content = await page.content()
    return {"html": content, "url": page.url}


@mcp.tool(tags={"extended"})
async def browser_get_text(session_id: str, selector: Optional[str] = None) -> dict:
    """Get text content from page body or a specific element by selector."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    if selector:
        element = await page.query_selector(selector)
        if not element:
            return {"error": "Element not found", "selector": selector}
        text = await element.text_content()
    else:
        text = await page.text_content("body")

    return {"text": text, "selector": selector or "body"}


# ============================================================================
# Evaluation Tools - all extended
# ============================================================================

@mcp.tool(tags={"extended"})
async def browser_evaluate(session_id: str, script: str) -> dict:
    """Execute JavaScript in the page context and return the result."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    result = await page.evaluate(script)
    return {"result": result}


@mcp.tool(tags={"extended"})
async def browser_wait_for(session_id: str, selector: str, state: str = "visible", timeout: int = 30000) -> dict:
    """Wait for element to reach state: attached, detached, visible, or hidden."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    try:
        await page.wait_for_selector(selector, state=state, timeout=timeout)
        return {"status": "found", "selector": selector, "state": state}
    except Exception as e:
        return {"status": "timeout", "selector": selector, "error": str(e)}


@mcp.tool(tags={"extended"})
async def browser_wait_for_navigation(session_id: str, timeout: int = 30000) -> dict:
    """Wait for page navigation to reach networkidle state."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
        return {"status": "complete", "url": page.url}
    except Exception as e:
        return {"status": "timeout", "error": str(e)}


@mcp.tool(tags={"extended"})
async def browser_console_messages(session_id: str, limit: int = 50) -> dict:
    """Get captured console.log messages from the page."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    messages = session.console_messages[-limit:] if limit else session.console_messages
    return {"messages": messages, "count": len(messages)}


# ============================================================================
# Query Tools - all extended
# ============================================================================

@mcp.tool(tags={"extended"})
async def browser_get_attribute(session_id: str, selector: str, attribute: str) -> dict:
    """Get an HTML attribute value from an element."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    element = await page.query_selector(selector)
    if not element:
        return {"error": "Element not found", "selector": selector}

    value = await element.get_attribute(attribute)
    return {"attribute": attribute, "value": value, "selector": selector}


@mcp.tool(tags={"extended"})
async def browser_query_selector_all(session_id: str, selector: str, limit: int = 100) -> dict:
    """Query all elements matching a CSS selector. Returns tag, text for each."""
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    elements = await page.query_selector_all(selector)
    results = []

    for i, element in enumerate(elements[:limit]):
        try:
            text = await element.text_content()
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            results.append({
                "index": i,
                "tag": tag,
                "text": text[:200] if text else None
            })
        except Exception:
            continue

    return {"elements": results, "count": len(results), "selector": selector}


# ============================================================================
# Health Check Tool - core
# ============================================================================

@mcp.tool(tags={"core"})
async def health_check() -> dict:
    """Check MCP server health and browser status."""
    return {
        "status": "healthy",
        "server": "MCP Playwright Persistent",
        "port": SERVER_PORT,
        "sessions": len(sessions),
        "browser_running": browser_instance is not None
    }


# ============================================================================
# Server Entry Point
# ============================================================================

def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="MCP Playwright Persistent")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run with stdio transport (for Claude Code auto-start)",
    )
    args = parser.parse_args()

    if args.stdio:
        logger.info("Starting MCP Playwright Persistent via stdio transport")
        mcp.run(transport="stdio")
    else:
        logger.info(f"Starting MCP Playwright Persistent on {SERVER_HOST}:{SERVER_PORT}")
        mcp.run(
            transport="sse",
            host=SERVER_HOST,
            port=SERVER_PORT,
        )


if __name__ == "__main__":
    main()
