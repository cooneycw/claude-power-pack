---
description: Deep security scan (includes git history)
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*), Read(*.py), Read(*.yml)
---

# Security Deep Scan

Thorough security scan including git history analysis. Runs all native and external scanners.

## Arguments

- `--json` - Output as JSON
- `--verbose` - Show additional details

## What's Checked

Everything from `/security:scan` plus:
- **Git history scanning** via gitleaks (if installed)
- Secrets that may have been committed and later removed

## Important

If secrets are found in git history:
- The secret is **compromised** regardless of current file state
- **Rotate the credential immediately**
- Consider using `git filter-repo` to clean history (advanced)
- Never auto-fix git history — too dangerous for novices

## Run Command

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security deep
```
