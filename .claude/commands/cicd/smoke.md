---
description: Run smoke tests from cicd.yml configuration
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Bash(curl:*), Bash(ls:*), Bash(test:*), Bash(cat:*), Read
---

# /cicd:smoke - Smoke Tests

Run smoke tests from `.claude/cicd.yml` configuration.

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
  echo "Or add smoke tests manually to .claude/cicd.yml:"
  echo ""
  echo "  health:"
  echo "    smoke_tests:"
  echo "      - name: API responds"
  echo "        command: \"curl -sf http://localhost:8000/health\""
  echo "        expected_exit: 0"
  echo "      - name: CLI version"
  echo "        command: \"python -m myapp --version\""
  echo "        expected_output: \"v\\\\d+\\\\.\\\\d+\""
  exit 1
fi
```

If `.claude/cicd.yml` exists but has no `smoke_tests:` section, the CLI will report "no tests configured" and show configuration guidance.

---

## Step 3: Run Smoke Tests

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd smoke
```

---

## Step 4: Present Results

The CLI outputs a markdown table. Present it to the user as-is.

The report includes:
- **Test table**: Each test's name, status (PASS/FAIL), detail, and execution time
- **Summary**: Overall pass/fail count

### Interpreting Results

| Status | Meaning |
|--------|---------|
| `PASS` | Command exited with expected code and output matched (if configured) |
| `FAIL` | Command failed - wrong exit code, output mismatch, or timeout |

### Test Configuration

Each smoke test in `.claude/cicd.yml` supports:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable test name |
| `command` | Yes | Shell command to execute |
| `expected_exit` | No | Expected exit code (default: 0) |
| `expected_output` | No | Regex pattern to match in stdout |
| `timeout` | No | Timeout in seconds (default: 30) |

### No Tests Configured

If the CLI reports "no tests configured", guide the user:

```
No smoke tests configured.

Add tests to .claude/cicd.yml:

  health:
    smoke_tests:
      - name: API responds
        command: "curl -sf http://localhost:8000/health"
        expected_exit: 0
      - name: CLI version
        command: "python -m myapp --version"
        expected_output: "v\\d+\\.\\d+"
      - name: Database connection
        command: "python -c 'import myapp.db; myapp.db.ping()'"
        expected_exit: 0
        timeout: 10

Then re-run: /cicd:smoke
```

---

## Step 5: Handle Failures

When smoke tests fail, provide remediation guidance:

1. **Exit code mismatch**: Show actual vs expected exit code and stderr output
2. **Output mismatch**: Show the expected pattern and actual output
3. **Timeout**: Suggest increasing timeout or checking if the service is running
4. **Command not found**: Suggest installing the dependency or activating the venv

Example failure guidance:

```
Test "API responds" FAILED:
  Command: curl -sf http://localhost:8000/health
  Expected exit: 0, Got: 7
  Detail: Connection refused

  Fix: Ensure the API server is running:
    make run    (if available)
    uvicorn myapp:app --host 0.0.0.0 --port 8000
```

---

## Notes

- Smoke tests verify that a deployed/running system works end-to-end
- Run after `make deploy` or service startup to validate
- Commands run in the project root directory
- Each test is independent - failures don't stop subsequent tests
- Use `--json` flag for machine-readable output
- Use `--summary` flag for one-line pass/fail (useful in scripts)
- Configure tests in `.claude/cicd.yml` under `health.smoke_tests`
- Pair with `/cicd:health` for comprehensive verification
