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

import asyncio
import base64
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Server configuration
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8081"))
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1 hour default

# Initialize FastMCP
mcp = FastMCP(
    "MCP Playwright Persistent",
    instructions="""
    Persistent browser automation with session management.

    Create a session first with create_session(), then use the session_id
    for all subsequent operations. Sessions persist across tool calls and
    maintain browser state, cookies, and login sessions.

    Key tools:
    - create_session/close_session - Manage browser sessions
    - browser_navigate - Navigate to URLs
    - browser_click/browser_fill/browser_type - Interact with pages
    - browser_screenshot - Capture screenshots
    - browser_new_tab/browser_switch_tab - Multi-tab support
    """
)

# Session storage
sessions: dict = {}
playwright_instance = None
browser_instance: Optional[Browser] = None


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
# Session Management Tools (5)
# ============================================================================

@mcp.tool()
async def create_session(headless: bool = True, viewport_width: int = 1280, viewport_height: int = 720) -> dict:
    """
    Create a new persistent browser session.

    Args:
        headless: Run browser in headless mode (default True)
        viewport_width: Browser viewport width (default 1280)
        viewport_height: Browser viewport height (default 720)

    Returns:
        Session information including session_id
    """
    browser = await get_browser()
    context = await browser.new_context(
        viewport={"width": viewport_width, "height": viewport_height}
    )

    session_id = str(uuid.uuid4())[:12]
    session = BrowserSession(session_id, context, headless)
    sessions[session_id] = session

    # Create initial page
    page_id, _ = await session.create_page()

    logger.info(f"Created session {session_id}")

    return {
        "session_id": session_id,
        "active_page_id": page_id,
        "headless": headless,
        "viewport": {"width": viewport_width, "height": viewport_height}
    }


@mcp.tool()
async def close_session(session_id: str) -> dict:
    """
    Close a browser session and release resources.

    Args:
        session_id: The session ID to close

    Returns:
        Confirmation of session closure
    """
    if session_id in sessions:
        await close_session_internal(session_id)
        return {"status": "closed", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


@mcp.tool()
async def list_sessions() -> dict:
    """
    List all active browser sessions.

    Returns:
        List of active sessions with their details
    """
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


@mcp.tool()
async def get_session_info(session_id: str) -> dict:
    """
    Get detailed information about a session.

    Args:
        session_id: The session ID

    Returns:
        Detailed session information
    """
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


@mcp.tool()
async def cleanup_idle_sessions(max_idle_minutes: int = 30) -> dict:
    """
    Clean up sessions that have been idle for too long.

    Args:
        max_idle_minutes: Maximum idle time in minutes (default 30)

    Returns:
        Number of sessions cleaned up
    """
    cleaned = 0
    threshold = datetime.now() - timedelta(minutes=max_idle_minutes)

    for sid, session in list(sessions.items()):
        if session.last_activity < threshold:
            await close_session_internal(sid)
            cleaned += 1

    return {"cleaned": cleaned, "remaining": len(sessions)}


# ============================================================================
# Navigation Tools (6)
# ============================================================================

@mcp.tool()
async def browser_navigate(session_id: str, url: str, wait_until: str = "load") -> dict:
    """
    Navigate to a URL.

    Args:
        session_id: The session ID
        url: URL to navigate to
        wait_until: When to consider navigation complete (load, domcontentloaded, networkidle)

    Returns:
        Navigation result with page title
    """
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


@mcp.tool()
async def browser_click(session_id: str, selector: str, button: str = "left", click_count: int = 1) -> dict:
    """
    Click an element on the page.

    Args:
        session_id: The session ID
        selector: CSS selector or text selector
        button: Mouse button (left, right, middle)
        click_count: Number of clicks (1 for single, 2 for double)

    Returns:
        Click result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.click(selector, button=button, click_count=click_count)
    return {"status": "clicked", "selector": selector}


@mcp.tool()
async def browser_type(session_id: str, selector: str, text: str, delay: int = 0) -> dict:
    """
    Type text into an element (simulates keystrokes).

    Args:
        session_id: The session ID
        selector: CSS selector for input element
        text: Text to type
        delay: Delay between keystrokes in ms

    Returns:
        Type result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.type(selector, text, delay=delay)
    return {"status": "typed", "selector": selector, "length": len(text)}


@mcp.tool()
async def browser_fill(session_id: str, selector: str, value: str) -> dict:
    """
    Fill an input element with text (faster than type, clears first).

    Args:
        session_id: The session ID
        selector: CSS selector for input element
        value: Value to fill

    Returns:
        Fill result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.fill(selector, value)
    return {"status": "filled", "selector": selector}


@mcp.tool()
async def browser_select_option(session_id: str, selector: str, value: str) -> dict:
    """
    Select an option from a dropdown.

    Args:
        session_id: The session ID
        selector: CSS selector for select element
        value: Option value to select

    Returns:
        Select result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.select_option(selector, value)
    return {"status": "selected", "selector": selector, "value": value}


@mcp.tool()
async def browser_hover(session_id: str, selector: str) -> dict:
    """
    Hover over an element.

    Args:
        session_id: The session ID
        selector: CSS selector for element

    Returns:
        Hover result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.hover(selector)
    return {"status": "hovered", "selector": selector}


# ============================================================================
# Tab Management Tools (6)
# ============================================================================

@mcp.tool()
async def browser_new_tab(session_id: str, url: Optional[str] = None) -> dict:
    """
    Open a new tab in the session.

    Args:
        session_id: The session ID
        url: Optional URL to navigate to

    Returns:
        New tab information
    """
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


@mcp.tool()
async def browser_switch_tab(session_id: str, page_id: str) -> dict:
    """
    Switch to a different tab.

    Args:
        session_id: The session ID
        page_id: The page ID to switch to

    Returns:
        Switch result
    """
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


@mcp.tool()
async def browser_close_tab(session_id: str, page_id: str) -> dict:
    """
    Close a tab.

    Args:
        session_id: The session ID
        page_id: The page ID to close

    Returns:
        Close result
    """
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


@mcp.tool()
async def browser_go_back(session_id: str) -> dict:
    """
    Navigate back in browser history.

    Args:
        session_id: The session ID

    Returns:
        Navigation result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.go_back()
    return {"url": page.url, "title": await page.title()}


@mcp.tool()
async def browser_go_forward(session_id: str) -> dict:
    """
    Navigate forward in browser history.

    Args:
        session_id: The session ID

    Returns:
        Navigation result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.go_forward()
    return {"url": page.url, "title": await page.title()}


@mcp.tool()
async def browser_reload(session_id: str) -> dict:
    """
    Reload the current page.

    Args:
        session_id: The session ID

    Returns:
        Reload result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    await page.reload()
    return {"url": page.url, "title": await page.title()}


# ============================================================================
# Capture Tools (5)
# ============================================================================

@mcp.tool()
async def browser_screenshot(session_id: str, full_page: bool = False, selector: Optional[str] = None) -> dict:
    """
    Take a screenshot of the page.

    Args:
        session_id: The session ID
        full_page: Capture full scrollable page
        selector: Optional selector to screenshot specific element

    Returns:
        Base64 encoded screenshot
    """
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


@mcp.tool()
async def browser_snapshot(session_id: str) -> dict:
    """
    Get an accessibility snapshot of the page.

    Args:
        session_id: The session ID

    Returns:
        Accessibility tree snapshot
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    snapshot = await page.accessibility.snapshot()
    return {"snapshot": snapshot}


@mcp.tool()
async def browser_pdf(session_id: str, format: str = "A4") -> dict:
    """
    Generate PDF of the page (headless only).

    Args:
        session_id: The session ID
        format: Paper format (A4, Letter, etc.)

    Returns:
        Base64 encoded PDF
    """
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


@mcp.tool()
async def browser_get_content(session_id: str) -> dict:
    """
    Get the HTML content of the page.

    Args:
        session_id: The session ID

    Returns:
        Page HTML content
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    content = await page.content()
    return {"html": content, "url": page.url}


@mcp.tool()
async def browser_get_text(session_id: str, selector: Optional[str] = None) -> dict:
    """
    Get text content from the page or an element.

    Args:
        session_id: The session ID
        selector: Optional CSS selector (gets body text if not specified)

    Returns:
        Text content
    """
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
# Evaluation Tools (4)
# ============================================================================

@mcp.tool()
async def browser_evaluate(session_id: str, script: str) -> dict:
    """
    Execute JavaScript in the page context.

    Args:
        session_id: The session ID
        script: JavaScript code to execute

    Returns:
        Script execution result
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    page = await session.get_active_page()
    if not page:
        return {"error": "No active page"}

    result = await page.evaluate(script)
    return {"result": result}


@mcp.tool()
async def browser_wait_for(session_id: str, selector: str, state: str = "visible", timeout: int = 30000) -> dict:
    """
    Wait for an element to reach a specific state.

    Args:
        session_id: The session ID
        selector: CSS selector
        state: State to wait for (attached, detached, visible, hidden)
        timeout: Timeout in milliseconds

    Returns:
        Wait result
    """
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


@mcp.tool()
async def browser_wait_for_navigation(session_id: str, timeout: int = 30000) -> dict:
    """
    Wait for navigation to complete.

    Args:
        session_id: The session ID
        timeout: Timeout in milliseconds

    Returns:
        Navigation result
    """
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


@mcp.tool()
async def browser_console_messages(session_id: str, limit: int = 50) -> dict:
    """
    Get console messages from the page.

    Args:
        session_id: The session ID
        limit: Maximum number of messages to return

    Returns:
        List of console messages
    """
    session = await get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    messages = session.console_messages[-limit:] if limit else session.console_messages
    return {"messages": messages, "count": len(messages)}


# ============================================================================
# Query Tools (2)
# ============================================================================

@mcp.tool()
async def browser_get_attribute(session_id: str, selector: str, attribute: str) -> dict:
    """
    Get an attribute value from an element.

    Args:
        session_id: The session ID
        selector: CSS selector
        attribute: Attribute name to get

    Returns:
        Attribute value
    """
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


@mcp.tool()
async def browser_query_selector_all(session_id: str, selector: str, limit: int = 100) -> dict:
    """
    Query all elements matching a selector.

    Args:
        session_id: The session ID
        selector: CSS selector
        limit: Maximum number of elements to return

    Returns:
        List of matching elements with their text content
    """
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
# Health Check Tool (1)
# ============================================================================

@mcp.tool()
async def health_check() -> dict:
    """
    Check the health of the MCP server.

    Returns:
        Server health status
    """
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
    logger.info(f"Starting MCP Playwright Persistent on {SERVER_HOST}:{SERVER_PORT}")

    # Run the MCP server with SSE transport
    mcp.run(
        transport="sse",
        host=SERVER_HOST,
        port=SERVER_PORT,
    )


if __name__ == "__main__":
    main()
