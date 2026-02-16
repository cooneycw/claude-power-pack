---
description: Explain a security finding in detail
allowed-tools: Bash(python3:*), Bash(PYTHONPATH=*)
---

# Security Explain

Get a detailed explanation of a specific security finding type.

## Arguments

- `FINDING_ID` (required) — The finding identifier (e.g., `HARDCODED_PASSWORD`)

## Available Finding IDs

| ID | Description |
|----|-------------|
| `GITIGNORE_MISSING` | No .gitignore file found |
| `GITIGNORE_GAP` | Sensitive pattern missing from .gitignore |
| `FILE_PERMISSIONS` | Sensitive file is world-readable |
| `AWS_ACCESS_KEY` | AWS access key in source code |
| `OPENAI_API_KEY` | OpenAI API key in source code |
| `ANTHROPIC_API_KEY` | Anthropic API key in source code |
| `GITHUB_PAT` | GitHub personal access token in source |
| `HARDCODED_PASSWORD` | Password hardcoded in source |
| `HARDCODED_SECRET` | Secret/token hardcoded in source |
| `ENV_TRACKED` | .env file tracked by git |
| `DEBUG_FLAG` | Debug mode enabled in config |

## Example

```
/security:explain HARDCODED_PASSWORD
```

## Run Command

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security explain "$@"
```
