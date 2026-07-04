---
description: Run health checks against configured endpoints and processes
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Bash(curl:*), Bash(ss:*), Bash(lsof:*), Bash(ls:*), Bash(test:*), Bash(cat:*), Read
---

# /cicd:health - Health Checks

Run health checks against configured endpoints and processes.

---

## Step 1: Locate CPP Source

```bash
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -z "$CPP_DIR" ]; then
  echo "ERROR: claude-power-pack not found"
  exit 1
fi
```

---

## Step 2: Check for Configuration

```bash
if [ ! -f ".claude/cicd.yml" ]; then
  echo "No .claude/cicd.yml found in $(pwd)"
  echo ""
  echo "Create one with:"
  echo "  /cicd:init    - Auto-detect framework and generate"
  echo ""
  echo "Or add health checks manually to .claude/cicd.yml:"
  echo ""
  echo "  health:"
  echo "    endpoints:"
  echo "      - url: http://localhost:8000/health"
  echo "        name: API Server"
  echo "    processes:"
  echo "      - name: uvicorn"
  echo "        port: 8000"
  exit 1
fi
```

If `.claude/cicd.yml` exists but has no `health:` section, the CLI will report "no checks configured" and show configuration guidance. This is handled gracefully - no error.

---

## Step 3: Run Health Checks

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd health
```

---

## Step 4: Present Results

The CLI outputs a markdown table. Present it to the user as-is.

The report includes:
- **Check table**: Each check's name, type, status (PASS/FAIL), detail, and response time
- **Summary**: Overall pass/fail count

### Interpreting Results

| Status | Meaning |
|--------|---------|
| `PASS` | Check succeeded - endpoint reachable or process running |
| `FAIL` | Check failed - endpoint unreachable, wrong status, or process not found |

### Check Types

| Type | What It Checks |
|------|---------------|
| `endpoint` | HTTP request to URL - checks status code and optional response body |
| `process` | Port listening - uses `ss` or `lsof` to verify process is bound to port |

### No Checks Configured

If the CLI reports "no checks configured", guide the user:

```
No health checks configured.

Add checks to .claude/cicd.yml:

  health:
    endpoints:
      - url: http://localhost:8000/health
        name: API Server
        expected_status: 200
        timeout: 5
    processes:
      - name: uvicorn
        port: 8000

Then re-run: /cicd:health
```

---

## Step 5: Interactive Fallback (No Config)

If no `.claude/cicd.yml` exists, ask the user what to check:

1. Use AskUserQuestion: "What endpoints should I check? (e.g., http://localhost:8000/health)"
2. If the user provides URLs, run `curl -sf -o /dev/null -w "%{http_code}" <URL>` for each
3. Report results in the same table format
4. Offer to save the configuration to `.claude/cicd.yml`

---

## Notes

- Health checks are designed for local development verification
- Endpoint checks use `curl` with configurable timeouts (default 5s)
- Process checks use `ss -tlnp` (preferred) or `lsof -i` as fallback
- All checks run sequentially with timing for each
- Use `--json` flag for machine-readable output
- Use `--summary` flag for one-line pass/fail (useful in scripts)
- Configure checks in `.claude/cicd.yml` under the `health:` section
