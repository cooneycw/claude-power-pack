---
description: Quick security scan (native only, fast)
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Read(*.py), Read(*.yml)
---

# Security Quick Scan

Fast security scan using only built-in native scanners. No external tools required.

## Arguments

- `--json` - Output as JSON
- `--verbose` - Show additional details

## What's Checked

- `.gitignore` coverage for sensitive file patterns
- File permissions on secrets/keys
- High-confidence secret patterns in source code
- `.env` files tracked by git
- Debug flags in production configs

## When to Use

- Before creating a PR (run automatically by `/flow:finish`)
- Quick check during development
- CI environments without external tools

## Run Command

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security quick
```
