# QA Test - Automated Web Testing

Perform automated QA testing on a web application using Playwright MCP.

**Arguments:** `$ARGUMENTS`
- Format: `<url-or-project> [area] [--find N]`
- Examples:
  - `/qa:test https://example.com` - Test full site
  - `/qa:test chess dashboard` - Test chess-agent dashboard
  - `/qa:test chess play --find 3` - Find up to 3 bugs in play area

## Project Shortcuts

| Shortcut | URL | Repository |
|----------|-----|------------|
| `chess` | https://agentic-chess.ca | cooneycw/chess-agent |

---

## Step 1: Parse Arguments

Extract from `$ARGUMENTS`:
1. **Target**: URL or project shortcut
2. **Area** (optional): dashboard, play, training, analysis, viewer, explainer
3. **Find count** (optional): `--find N` to stop after N bugs (default: 1)

If no arguments, prompt user for target.

---

## Step 2: Create Browser Session

Use Playwright MCP to create a headless browser session:

```
create_session(headless=true, viewport_width=1280, viewport_height=720)
```

Store the `session_id` for subsequent operations.

---

## Step 3: Navigate to Target

Navigate to the target URL:
- If shortcut used, resolve to full URL
- If area specified, append appropriate path (e.g., `/game/` for play)

```
browser_navigate(session_id, url, wait_until="networkidle")
```

---

## Step 4: Test Methodology

For each area, perform these tests:

### Click Response Testing

1. **Identify interactive elements**:
   ```
   browser_query_selector_all(session_id, "[hx-post], [hx-get], button, [onclick], a[href]")
   ```

2. **Click and verify** each element:
   - Check console for errors: `browser_console_messages(session_id)`
   - Verify expected state change occurred
   - Note any 4xx/5xx errors, JS exceptions

### Form Testing

1. Find form inputs
2. Fill with test data
3. Submit and verify response

### Navigation Testing

1. Click navigation links
2. Verify correct page loads
3. Check for broken links

---

## Step 5: Bug Classification

Classify issues by severity:

| Severity | Description | Example |
|----------|-------------|---------|
| **Critical** | Blocks core functionality | 403 on main action |
| **High** | Major feature broken | Form submission fails |
| **Medium** | Feature partially works | Missing validation |
| **Low** | UI/UX issues | Misaligned elements |

---

## Step 6: Log Bugs as GitHub Issues

For each bug found:

1. **Title format**: `[Bug] <Area>: <Brief description>`
2. **Body includes**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Console errors (verbatim)
   - Technical analysis
   - Environment details

3. **Labels**: `bug`, optional severity label

```bash
gh issue create --repo <repo> --title "<title>" --body "<body>" --label "bug"
```

---

## Step 7: Report Summary

After testing (or reaching `--find N` limit), output:

```markdown
## QA Test Results

**Target:** <URL>
**Areas Tested:** <list>
**Bugs Found:** N

### Issues Created
| # | Severity | Area | Description |
|---|----------|------|-------------|
| 1 | Critical | Play | CSRF 403 on square click |

### Test Coverage
- [ ] Dashboard widgets
- [x] Play - board interaction
- [ ] Training controls
- [ ] Analysis tools
- [ ] Viewer functionality
- [ ] Explainer content

---
Run `/qa:test <project> <area>` to continue testing.
```

---

## Step 8: Cleanup

Close the browser session:
```
close_session(session_id)
```

---

## Area-Specific Test Plans

### Dashboard
- Stat card data loads
- Quick action buttons work
- Recent games list populates
- System health indicators accurate

### Play
- Board renders correctly
- Square clicks register
- Moves execute
- AI responds
- Game state updates
- Resign/Reset work

### Training
- Status indicators work
- Start/Stop controls function
- Progress updates live
- Loss charts render

### Analysis
- FEN input works
- Position loads
- MCTS visualization renders
- Move suggestions appear

### Viewer
- Game list loads
- Game selection works
- Move navigation functions
- Board syncs with moves

### Explainer
- Content loads
- Interactive elements work
- Examples render
