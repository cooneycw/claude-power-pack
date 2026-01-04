# MCP Playwright Persistent

Persistent browser automation with session management for Claude Code.

## Features

- **Persistent Sessions**: Browser sessions survive across tool calls
- **Multi-Tab Support**: Open, switch, and manage multiple tabs
- **Full Automation**: Click, type, fill, select, hover, screenshot
- **Headless/Headed**: Run with or without visible browser
- **PDF Generation**: Export pages to PDF (headless only)
- **Console Capture**: Access browser console messages
- **Accessibility Snapshots**: Get page accessibility tree

## Quick Start

```bash
cd mcp-playwright-persistent

# 1. Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install Playwright browsers
uv run playwright install chromium

# 3. Start server (uv handles dependencies automatically)
./start-server.sh

# 4. Add to Claude Code
claude mcp add playwright-persistent --transport sse --url http://127.0.0.1:8081/sse
```

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `127.0.0.1` | Server bind address |
| `SERVER_PORT` | `8081` | Server port |
| `SESSION_TIMEOUT` | `3600` | Session timeout in seconds (1 hour) |

## Tools Reference (29 total)

### Session Management (5 tools)

| Tool | Description |
|------|-------------|
| `create_session` | Create a new browser session |
| `close_session` | Close a session and release resources |
| `list_sessions` | List all active sessions |
| `get_session_info` | Get detailed session information |
| `cleanup_idle_sessions` | Clean up idle sessions |

#### create_session

Create a new persistent browser session.

```python
# Basic usage
session = create_session()

# Custom viewport
session = create_session(
    headless=True,
    viewport_width=1920,
    viewport_height=1080
)
```

**Parameters:**
- `headless` (bool, default=True): Run browser in headless mode
- `viewport_width` (int, default=1280): Browser viewport width
- `viewport_height` (int, default=720): Browser viewport height

**Returns:** `{session_id, active_page_id, headless, viewport}`

#### close_session

Close a session and release resources.

```python
close_session(session_id="abc123")
```

**Parameters:**
- `session_id` (str): The session ID to close

**Returns:** `{status: "closed"|"not_found", session_id}`

#### list_sessions

List all active browser sessions.

```python
sessions = list_sessions()
# Returns: {sessions: [...], count: 2}
```

**Returns:** List of sessions with creation time, last activity, and page count.

#### get_session_info

Get detailed information about a session.

```python
info = get_session_info(session_id="abc123")
# Returns: {session_id, created_at, last_activity, headless, pages: [...], active_page_id}
```

#### cleanup_idle_sessions

Clean up sessions idle longer than specified time.

```python
cleanup_idle_sessions(max_idle_minutes=30)
# Returns: {cleaned: 2, remaining: 1}
```

---

### Navigation Tools (6 tools)

| Tool | Description |
|------|-------------|
| `browser_navigate` | Navigate to a URL |
| `browser_click` | Click an element |
| `browser_type` | Type text with keystrokes |
| `browser_fill` | Fill input (faster than type) |
| `browser_select_option` | Select dropdown option |
| `browser_hover` | Hover over element |

#### browser_navigate

Navigate to a URL.

```python
browser_navigate(
    session_id="abc123",
    url="https://example.com",
    wait_until="networkidle"  # or "load", "domcontentloaded"
)
```

**Parameters:**
- `session_id` (str): The session ID
- `url` (str): URL to navigate to
- `wait_until` (str, default="load"): When to consider navigation complete

**Returns:** `{url, title, status}`

#### browser_click

Click an element on the page.

```python
# Single click
browser_click(session_id="abc123", selector="button#submit")

# Double click
browser_click(session_id="abc123", selector="div.item", click_count=2)

# Right click
browser_click(session_id="abc123", selector="tr.row", button="right")
```

**Parameters:**
- `session_id` (str): The session ID
- `selector` (str): CSS selector or text selector
- `button` (str, default="left"): Mouse button (left, right, middle)
- `click_count` (int, default=1): Number of clicks

#### browser_type

Type text with simulated keystrokes.

```python
browser_type(
    session_id="abc123",
    selector="input#search",
    text="search query",
    delay=50  # 50ms between keystrokes
)
```

**Parameters:**
- `session_id` (str): The session ID
- `selector` (str): CSS selector for input element
- `text` (str): Text to type
- `delay` (int, default=0): Delay between keystrokes in ms

#### browser_fill

Fill an input element (faster than type, clears first).

```python
browser_fill(
    session_id="abc123",
    selector="input#username",
    value="john@example.com"
)
```

**Parameters:**
- `session_id` (str): The session ID
- `selector` (str): CSS selector for input element
- `value` (str): Value to fill

#### browser_select_option

Select an option from a dropdown.

```python
browser_select_option(
    session_id="abc123",
    selector="select#country",
    value="us"
)
```

#### browser_hover

Hover over an element.

```python
browser_hover(session_id="abc123", selector="div.menu")
```

---

### Tab Management (6 tools)

| Tool | Description |
|------|-------------|
| `browser_new_tab` | Open a new tab |
| `browser_switch_tab` | Switch to a different tab |
| `browser_close_tab` | Close a tab |
| `browser_go_back` | Navigate back in history |
| `browser_go_forward` | Navigate forward in history |
| `browser_reload` | Reload current page |

#### browser_new_tab

Open a new tab in the session.

```python
# Empty tab
tab = browser_new_tab(session_id="abc123")

# Tab with URL
tab = browser_new_tab(session_id="abc123", url="https://example.com")
# Returns: {page_id, url, is_active}
```

#### browser_switch_tab

Switch to a different tab.

```python
browser_switch_tab(session_id="abc123", page_id="page456")
# Returns: {page_id, url, title}
```

#### browser_close_tab

Close a tab.

```python
browser_close_tab(session_id="abc123", page_id="page456")
```

#### browser_go_back / browser_go_forward / browser_reload

```python
browser_go_back(session_id="abc123")
browser_go_forward(session_id="abc123")
browser_reload(session_id="abc123")
# All return: {url, title}
```

---

### Capture Tools (5 tools)

| Tool | Description |
|------|-------------|
| `browser_screenshot` | Take a screenshot |
| `browser_snapshot` | Get accessibility snapshot |
| `browser_pdf` | Generate PDF (headless only) |
| `browser_get_content` | Get page HTML |
| `browser_get_text` | Get text content |

#### browser_screenshot

Take a screenshot of the page.

```python
# Viewport screenshot
screenshot = browser_screenshot(session_id="abc123")

# Full page screenshot
screenshot = browser_screenshot(session_id="abc123", full_page=True)

# Element screenshot
screenshot = browser_screenshot(session_id="abc123", selector="div#chart")

# Returns: {screenshot: "base64...", format: "png", full_page: bool}
```

**Parameters:**
- `session_id` (str): The session ID
- `full_page` (bool, default=False): Capture full scrollable page
- `selector` (str, optional): Screenshot specific element

#### browser_snapshot

Get an accessibility snapshot of the page (ARIA snapshot in YAML format).

```python
snapshot = browser_snapshot(session_id="abc123")
# Returns: {snapshot: "- document: ...", format: "yaml"}
```

#### browser_pdf

Generate PDF of the page (headless mode only).

```python
pdf = browser_pdf(session_id="abc123", format="A4")
# Returns: {pdf: "base64...", format: "A4"}
```

**Parameters:**
- `session_id` (str): The session ID
- `format` (str, default="A4"): Paper format (A4, Letter, etc.)

#### browser_get_content

Get the HTML content of the page.

```python
content = browser_get_content(session_id="abc123")
# Returns: {html: "<!DOCTYPE html>...", url: "..."}
```

#### browser_get_text

Get text content from the page or an element.

```python
# Full page text
text = browser_get_text(session_id="abc123")

# Element text
text = browser_get_text(session_id="abc123", selector="article.content")
# Returns: {text: "...", selector: "..."}
```

---

### Evaluation Tools (4 tools)

| Tool | Description |
|------|-------------|
| `browser_evaluate` | Execute JavaScript |
| `browser_wait_for` | Wait for element state |
| `browser_wait_for_navigation` | Wait for navigation |
| `browser_console_messages` | Get console messages |

#### browser_evaluate

Execute JavaScript in the page context.

```python
result = browser_evaluate(
    session_id="abc123",
    script="document.title"
)
# Returns: {result: "Page Title"}

# Complex script
result = browser_evaluate(
    session_id="abc123",
    script="Array.from(document.querySelectorAll('a')).map(a => a.href)"
)
```

#### browser_wait_for

Wait for an element to reach a specific state.

```python
browser_wait_for(
    session_id="abc123",
    selector="div.loading",
    state="hidden",  # or "visible", "attached", "detached"
    timeout=10000    # 10 seconds
)
# Returns: {status: "found"|"timeout", selector, state}
```

#### browser_wait_for_navigation

Wait for navigation to complete.

```python
browser_wait_for_navigation(session_id="abc123", timeout=30000)
# Returns: {status: "complete"|"timeout", url}
```

#### browser_console_messages

Get console messages from the page.

```python
messages = browser_console_messages(session_id="abc123", limit=50)
# Returns: {messages: [{type, text, timestamp}, ...], count}
```

---

### Query Tools (2 tools)

| Tool | Description |
|------|-------------|
| `browser_get_attribute` | Get element attribute |
| `browser_query_selector_all` | Query all matching elements |

#### browser_get_attribute

Get an attribute value from an element.

```python
href = browser_get_attribute(
    session_id="abc123",
    selector="a.link",
    attribute="href"
)
# Returns: {attribute, value, selector}
```

#### browser_query_selector_all

Query all elements matching a selector.

```python
elements = browser_query_selector_all(
    session_id="abc123",
    selector="li.item",
    limit=100
)
# Returns: {elements: [{index, tag, text}, ...], count, selector}
```

---

### Health Check (1 tool)

| Tool | Description |
|------|-------------|
| `health_check` | Check server health |

```python
health_check()
# Returns: {status: "healthy", server, port, sessions, browser_running}
```

---

## Usage Examples

### Basic Web Scraping

```python
# Create session
session = create_session(headless=True)
sid = session["session_id"]

# Navigate and extract data
browser_navigate(sid, "https://example.com")
text = browser_get_text(sid, selector="h1")
print(text["text"])

# Clean up
close_session(sid)
```

### Form Automation

```python
# Create session
session = create_session()
sid = session["session_id"]

# Navigate to form
browser_navigate(sid, "https://example.com/login")

# Fill form
browser_fill(sid, "input#email", "user@example.com")
browser_fill(sid, "input#password", "secret123")
browser_click(sid, "button[type=submit]")

# Wait for navigation
browser_wait_for_navigation(sid)

# Verify success
text = browser_get_text(sid, selector="h1.welcome")
print(text["text"])

close_session(sid)
```

### Multi-Tab Workflow

```python
session = create_session()
sid = session["session_id"]

# Open multiple tabs
browser_navigate(sid, "https://site1.com")
tab2 = browser_new_tab(sid, "https://site2.com")
tab3 = browser_new_tab(sid, "https://site3.com")

# Switch between tabs
browser_switch_tab(sid, tab2["page_id"])
content2 = browser_get_text(sid)

browser_switch_tab(sid, tab3["page_id"])
content3 = browser_get_text(sid)

close_session(sid)
```

### Screenshot Capture

```python
session = create_session(viewport_width=1920, viewport_height=1080)
sid = session["session_id"]

browser_navigate(sid, "https://example.com")

# Full page screenshot
screenshot = browser_screenshot(sid, full_page=True)

# Save to file
import base64
with open("screenshot.png", "wb") as f:
    f.write(base64.b64decode(screenshot["screenshot"]))

close_session(sid)
```

---

## Deployment

### Systemd Service (Recommended)

```bash
# Generate and install service
cd mcp-playwright-persistent
./deploy/install-service.sh --user

# Enable and start
systemctl --user enable mcp-playwright
systemctl --user start mcp-playwright

# Check status
systemctl --user status mcp-playwright
journalctl --user -u mcp-playwright -f
```

### Docker

```bash
cd mcp-playwright-persistent/deploy
docker-compose up -d
```

### Manual

```bash
cd mcp-playwright-persistent
uv run python src/server.py
```

---

## Troubleshooting

### Browser fails to launch

```bash
# Install Playwright browsers
playwright install chromium

# Or install all browsers
playwright install
```

### Session not found errors

Sessions expire after 1 hour of inactivity (configurable via `SESSION_TIMEOUT`).

```python
# Check if session is still valid
info = get_session_info(session_id="abc123")
if "error" in info:
    # Create new session
    session = create_session()
```

### PDF generation fails

PDF generation only works in headless mode:

```python
# This works
session = create_session(headless=True)
pdf = browser_pdf(session["session_id"])

# This fails
session = create_session(headless=False)
pdf = browser_pdf(session["session_id"])  # Error!
```

### Port already in use

```bash
# Check what's using port 8081
lsof -i :8081

# Change port in .env
echo "SERVER_PORT=8082" >> .env
```

---

## Architecture

```
┌─────────────────────────────────────┐
│         Claude Code / MCP           │
└──────────────┬──────────────────────┘
               │ SSE Transport
               ▼
┌─────────────────────────────────────┐
│    MCP Playwright Persistent        │
│         (FastMCP Server)            │
├─────────────────────────────────────┤
│  Session Manager                    │
│  ├── Session 1 (BrowserContext)     │
│  │   ├── Page A                     │
│  │   └── Page B                     │
│  └── Session 2 (BrowserContext)     │
│      └── Page C                     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│         Playwright Browser          │
│         (Chromium)                  │
└─────────────────────────────────────┘
```

---

## Related

- **MCP Second Opinion**: Port 8080 - Code review with Gemini
- **MCP Coordination**: Port 8082 - Redis-backed distributed locking
- **Playwright Documentation**: https://playwright.dev/python/

---

## License

MIT
