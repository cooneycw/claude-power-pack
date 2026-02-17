# QA Test - Automated Web Testing

Perform automated QA testing on a web application using Playwright MCP.

**Arguments:** `$ARGUMENTS`
- Format: `<url-or-shortcut> [area] [--find N]`
- Examples:
  - `/qa:test https://example.com` - Test full site
  - `/qa:test myapp dashboard` - Test named area via shortcut
  - `/qa:test myapp login --find 3` - Find up to 3 bugs in login area

---

## Step 1: Load Configuration

Check for `.claude/qa.yml` in the project root:

```bash
# Look for config file
cat .claude/qa.yml 2>/dev/null
```

**If `.claude/qa.yml` exists**, parse it to extract:
- `project.url` — default project URL
- `project.repository` — GitHub repo for issue creation
- `shortcuts` — map of shortcut names to URLs
- `test_areas` — named areas with paths, descriptions, and test checks

**If `.claude/qa.yml` does NOT exist**, use interactive fallback (see Step 1b).

---

## Step 1b: Interactive Fallback (no config)

If no `.claude/qa.yml` is found and no URL was provided in arguments:

1. **Inform the user:**
   ```
   No .claude/qa.yml found. Running in interactive mode.
   Tip: Copy templates/qa.yml.example to .claude/qa.yml for persistent config.
   ```

2. **Ask for the target URL** using AskUserQuestion.

3. **Ask for the repository** (for GitHub issue creation) or detect from `gh repo view`.

4. **Proceed with generic test areas** — test the entire page without area-specific plans:
   - Click all interactive elements
   - Fill and submit forms
   - Check console for errors
   - Test navigation links

---

## Step 2: Parse Arguments

Extract from `$ARGUMENTS`:
1. **Target**: URL or shortcut name (resolve via `shortcuts` from config)
2. **Area** (optional): Must match a key in `test_areas` from config
3. **Find count** (optional): `--find N` to stop after N bugs (default: 1)

If a shortcut is used but not found in config, report the error and list available shortcuts.

If an area is specified but not found in config, report available areas.

---

## Step 3: Create Browser Session

Use Playwright MCP to create a headless browser session:

```
create_session(headless=true, viewport_width=1280, viewport_height=720)
```

Store the `session_id` for subsequent operations.

---

## Step 4: Navigate to Target

Navigate to the target URL:
- If shortcut used, resolve to full URL from config
- If area specified, append the area's `path` from config

```
browser_navigate(session_id, url, wait_until="networkidle")
```

---

## Step 5: Test Methodology

### If area is specified and config has test plans:

Use the `tests` list from the area's config as the test checklist. For each test item:
1. Identify the relevant elements on the page
2. Perform the interaction (click, fill, navigate)
3. Verify the expected behavior
4. Check console for errors: `browser_console_messages(session_id)`
5. Note any failures

### If no area specified (full site test):

Test all areas defined in config sequentially:
1. For each area in `test_areas`, navigate to its `path`
2. Run through its `tests` checklist
3. Move to the next area

### Generic testing (no config or no test plans):

#### Click Response Testing
1. **Identify interactive elements**:
   ```
   browser_query_selector_all(session_id, "button, [onclick], a[href], input[type=submit], [role=button]")
   ```
2. **Click and verify** each element:
   - Check console for errors
   - Verify expected state change occurred
   - Note any 4xx/5xx errors, JS exceptions

#### Form Testing
1. Find form inputs
2. Fill with test data
3. Submit and verify response

#### Navigation Testing
1. Click navigation links
2. Verify correct page loads
3. Check for broken links

---

## Step 6: Bug Classification

Classify issues by severity:

| Severity | Description | Example |
|----------|-------------|---------|
| **Critical** | Blocks core functionality | 403 on main action |
| **High** | Major feature broken | Form submission fails |
| **Medium** | Feature partially works | Missing validation |
| **Low** | UI/UX issues | Misaligned elements |

---

## Step 7: Log Bugs as GitHub Issues

For each bug found, create a GitHub issue:

1. **Determine repository**: Use `project.repository` from config, or detect via `gh repo view`
2. **Title format**: `[Bug] <Area>: <Brief description>`
3. **Body includes**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Console errors (verbatim)
   - Technical analysis
   - Environment details
4. **Labels**: `bug`, optional severity label

```bash
gh issue create --repo <repo> --title "<title>" --body "<body>" --label "bug"
```

---

## Step 8: Report Summary

After testing (or reaching `--find N` limit), output:

```markdown
## QA Test Results

**Target:** <URL>
**Config:** .claude/qa.yml | interactive mode
**Areas Tested:** <list>
**Bugs Found:** N

### Issues Created
| # | Severity | Area | Description |
|---|----------|------|-------------|
| 1 | Critical | login | Form 500 on submit |

### Test Coverage
(Dynamic checklist from config test_areas, or generic areas tested)

---
Run `/qa:test <shortcut> <area>` to continue testing.
```

---

## Step 9: Cleanup

Close the browser session:
```
close_session(session_id)
```
