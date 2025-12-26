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

## Shared CDP Pattern

Both can connect to the same Chrome:

```bash
# Start Chrome with debugging
google-chrome --remote-debugging-port=9222

# bdg connects via CDP
bdg --chrome-ws-url ws://localhost:9222/devtools/page/...

# Playwright also connects
# (configure in session creation)
```

## Token Efficiency

| Pattern | Tokens | When |
|---------|--------|------|
| bdg form discovery | ~200 | Initial inspection |
| bdg fill + click | ~100 | Simple form submission |
| Playwright full flow | ~1500 | Complex multi-step |

**Rule of thumb**: Start with bdg, escalate if needed.
