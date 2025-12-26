# Tiered Browser Automation Skill

Use bdg CLI for lightweight operations, escalate to Playwright MCP for complex workflows.

## Quick Decision Matrix

| Task | Tool | Command Example |
|------|------|-----------------|
| Discover forms | bdg | `bdg dom form` |
| Query DOM | bdg | `bdg dom query "h1"` |
| Get cookies | bdg | `bdg network getCookies` |
| Console logs | bdg | `bdg console --list` |
| Simple fill | bdg | `bdg dom fill 0 "value"` |
| Simple click | bdg | `bdg dom click 5` |
| Multi-tab | Playwright | `browser_new_tab`, `browser_switch_tab` |
| Screenshots | Playwright | `browser_screenshot` |
| Complex waits | Playwright | `browser_wait_for` |
| Login flows | Playwright | Persistent session + cookies |
| React/SPA | Playwright | Better JS handling |

## bdg Quick Reference

```bash
# Start session (headless, 60s timeout)
bdg --headless -t 60 example.com

# Form discovery (best feature!)
bdg dom form

# Fill by index
bdg dom fill 0 "John Doe"
bdg dom click 5

# DOM queries
bdg dom query "button.submit"
bdg dom a11y tree

# Network
bdg network getCookies
bdg network har output.har

# Console
bdg console --list
bdg console -f  # follow mode

# Stop and save
bdg stop
```

## When to Use bdg

1. **Form inspection**: `bdg dom form` provides semantic labels with indices
2. **Quick DOM lookups**: Single selector queries
3. **Cookie/network inspection**: No need for full browser session
4. **Telemetry collection**: Network HAR export, console monitoring
5. **Simple interactions**: Basic fill/click on discovered forms

## When to Escalate to Playwright

1. **Multi-tab workflows**: Need to switch between tabs
2. **Complex waiting**: Wait for specific elements/navigation
3. **Screenshots/PDFs**: Better quality, element targeting
4. **Login sequences**: Persistent auth state needed
5. **React/Angular/Vue**: Better framework compatibility
6. **Form validation**: Complex validation feedback handling
7. **Bot detection triggered**: Site shows CAPTCHA or blocks headless

## Handling Bot Detection

Some sites (DuckDuckGo, Cloudflare-protected) detect headless browsers and trigger CAPTCHA.

### Detection Signs

```bash
# Check page content for CAPTCHA indicators
bdg dom eval 'document.body.innerText.includes("robot") || document.body.innerText.includes("CAPTCHA")'

# Look for challenge elements
bdg dom query "[class*='captcha'], [id*='challenge']"
```

### Workarounds

**Option 1: Use headed mode (bdg)**
```bash
# Run with visible browser
bdg --no-headless -t 120 protected-site.com
```

**Option 2: Custom user-agent (bdg)**
```bash
# Use Chrome flags to set user-agent
bdg --chrome-flags="--user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'" example.com
```

**Option 3: Escalate to Playwright (best for persistent sessions)**
```python
# Playwright with headed mode
session = create_session(headless=False)
# Complete CAPTCHA manually if needed, session persists
```

**Option 4: Use existing browser session**
```bash
# Connect to your regular Chrome (already logged in, cookies set)
google-chrome --remote-debugging-port=9222
bdg --chrome-ws-url ws://localhost:9222/devtools/page/...
```

### Sites Known to Trigger Bot Detection

| Site | Behavior | Workaround |
|------|----------|------------|
| DuckDuckGo | CAPTCHA on search | Use headed mode or Google |
| Cloudflare-protected | Challenge page | Use existing browser |
| LinkedIn | Login blocked | Use Playwright + headed |
| Amazon | CAPTCHA on some actions | Use existing browser |

## Shared CDP Pattern

Both tools can connect to the same Chrome instance for state sharing:

```bash
# Step 1: Start Chrome with debugging
google-chrome --remote-debugging-port=9222

# Step 2: Get the WebSocket URL
curl -s http://localhost:9222/json/version | jq -r '.webSocketDebuggerUrl'
# Returns: ws://localhost:9222/devtools/browser/abc123...
```

**bdg connection:**
```bash
bdg --chrome-ws-url ws://localhost:9222/devtools/page/...
```

**Playwright MCP connection:**
```python
# Use cdp_endpoint parameter to connect to existing Chrome
session = create_session(cdp_endpoint="ws://localhost:9222")
sid = session["session_id"]

# Now operates on the same browser as bdg
browser_navigate(sid, "https://example.com")
```

**Use case:** Login manually in headed Chrome, then automate with cookies preserved.

## Token Efficiency

| Pattern | Tokens | When |
|---------|--------|------|
| bdg form discovery | ~200 | Initial inspection |
| bdg fill + click | ~100 | Simple form submission |
| Playwright full flow | ~1500 | Complex multi-step |

**Rule of thumb**: Start with bdg, escalate if needed.

---

## Workflow Examples

### 1. Form Submission (bdg only)

```bash
# Start session
bdg --headless -t 120 httpbin.org/forms/post

# Discover form structure
bdg dom form
# Output shows indexed fields with semantic labels

# Fill fields by index
bdg dom fill 0 "John Doe"        # Customer name
bdg dom fill 1 "555-1234"        # Phone
bdg dom fill 2 "john@example.com" # Email
bdg dom click 4                   # Select "Medium" radio

# Verify state
bdg dom form  # Shows filled values

# Submit
bdg dom click 12  # Submit button

# Save session data
bdg stop
```

### 2. Data Extraction (bdg only)

```bash
# Start session
bdg --headless -t 60 news.ycombinator.com

# Query specific elements
bdg dom query ".titleline > a"

# Get accessibility tree for structure
bdg dom a11y tree | head -50

# Extract via JavaScript
bdg dom eval "Array.from(document.querySelectorAll('.titleline > a')).map(a => a.textContent).join('\n')"

# Export network data
bdg network har hn-requests.har

# Stop
bdg stop
```

### 3. Login Flow (Escalate to Playwright)

When login requires persistent cookies or complex validation:

```python
# Playwright MCP - maintains session state
session = create_session(headless=True)
sid = session["session_id"]

# Navigate to login
browser_navigate(sid, "https://example.com/login")

# Fill credentials
browser_fill(sid, "#username", "user@example.com")
browser_fill(sid, "#password", "secret123")

# Click login and wait for navigation
browser_click(sid, "button[type=submit]")
browser_wait_for_navigation(sid)

# Verify logged in
text = browser_get_text(sid, ".user-profile")

# Continue with authenticated session...
# Session persists cookies across calls

# Cleanup when done
close_session(sid)
```

### 4. Debug Console Monitoring (bdg only)

```bash
# Start with longer timeout for debugging
bdg --headless -t 300 localhost:3000

# Stream console in real-time
bdg console -f

# Or filter by level
bdg console --level error --list

# Check for specific errors
bdg console --list | grep -i "undefined"

# Get network failures
bdg network list --status 4xx,5xx
```

### 5. Screenshot Comparison (Playwright)

```python
# Playwright for high-quality screenshots
session = create_session(headless=True)
sid = session["session_id"]

# Navigate
browser_navigate(sid, "https://example.com")

# Full page screenshot
screenshot = browser_screenshot(sid, full_page=True)
# Returns base64 encoded image

# Element-specific screenshot
element_shot = browser_screenshot(sid, selector=".hero-section")

# Generate PDF
pdf = browser_pdf(sid, format="A4")

close_session(sid)
```

### 6. Hybrid: Inspect with bdg, Act with Playwright

```bash
# Step 1: Quick inspection with bdg
bdg --headless -t 60 complex-app.com
bdg dom form           # Understand form structure
bdg dom a11y tree      # Check accessibility
bdg network getCookies # See existing cookies
bdg stop
```

```python
# Step 2: Complex interaction with Playwright
session = create_session(headless=True)
sid = session["session_id"]

browser_navigate(sid, "https://complex-app.com")

# Multi-step flow based on bdg inspection
browser_fill(sid, "#search", "query")
browser_click(sid, ".search-btn")
browser_wait_for(sid, ".results", state="visible")

# Handle dynamic content
browser_evaluate(sid, "window.scrollTo(0, document.body.scrollHeight)")
browser_wait_for(sid, ".load-more", state="visible")

close_session(sid)
```

### 7. API Response Inspection (bdg only)

```bash
# Monitor XHR/fetch calls
bdg --headless -t 120 spa-app.com

# Trigger some action that makes API calls
bdg dom click ".load-data-btn"

# Wait a moment, then inspect
sleep 2
bdg peek --json | jq '.network[] | select(.url | contains("/api/"))'

# Get full response details
bdg details network <request-id>

bdg stop
```

---

## Escalation Checklist

Before escalating from bdg to Playwright, ask:

- [ ] Does this need **persistent session state**? → Playwright
- [ ] Does this need **multi-tab coordination**? → Playwright
- [ ] Does this need **complex waiting strategies**? → Playwright
- [ ] Does this need **high-quality screenshots/PDFs**? → Playwright
- [ ] Is this a **React/Vue/Angular SPA** with complex state? → Playwright
- [ ] Is the site **triggering bot detection/CAPTCHA**? → Playwright (headed) or existing browser
- [ ] Is this **read-only inspection**? → bdg
- [ ] Is this **simple form fill/click**? → bdg
- [ ] Do I need **network/console telemetry**? → bdg

---

## Troubleshooting

### bdg Issues

| Problem | Solution |
|---------|----------|
| "Port in use" | `bdg cleanup --force` or use different port |
| Session not starting | Check if Chrome is installed: `which google-chrome` |
| Timeout too short | Increase with `-t 300` (5 minutes) |
| Selectors not matching | Use `bdg dom a11y tree` to inspect structure |
| JavaScript errors | Check `bdg console --level error` |

### Common Patterns

**Retry on flaky selectors:**
```bash
# Wait for element before querying
bdg dom eval 'new Promise(r => {
  const check = () => document.querySelector(".dynamic") ? r(true) : setTimeout(check, 100);
  check();
})'
```

**Extract after navigation:**
```bash
bdg dom click ".next-page"
sleep 2  # Wait for page load
bdg dom query ".results"
```

**Quiet mode for scripting:**
```bash
# Minimal output, JSON-friendly
bdg --headless -q -t 60 example.com
bdg dom form --json 2>/dev/null | jq '.fields[0].value'
```
