---
description: Run full security scan (native + external tools)
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Read(*.py), Read(*.yml)
---

# Security Scan

Run a full security scan using native checks plus any available external tools.

## Arguments

- `--json` - Output as JSON (machine-readable)
- `--verbose` - Show matched patterns and additional details
- `--path <dir>` - Scan a specific directory (default: current project)

## What's Checked

### Native (always available)
- `.gitignore` coverage for sensitive file patterns
- File permissions on secrets/keys
- High-confidence secret patterns (AWS keys, GitHub tokens, API keys)
- `.env` files tracked by git
- Debug flags in production configs

### External (auto-detected)
- **gitleaks** — secret detection in working tree
- **pip-audit** — Python dependency CVEs
- **npm audit** — Node.js dependency CVEs

## Process

1. Run the security scanner on the current project
2. Display novice-friendly results with Why/Fix/Cmd for each finding
3. Exit code 0 if no critical issues, 1 if critical issues found

## Run Command

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security scan
```
