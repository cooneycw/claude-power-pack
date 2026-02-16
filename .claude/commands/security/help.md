# Security Commands

Novice-friendly security scanning for Claude Code projects.

## Commands

| Command | Purpose |
|---------|---------|
| `/security:scan` | Full scan: native checks + available external tools |
| `/security:quick` | Fast scan: native checks only (zero deps) |
| `/security:deep` | Deep scan: includes git history analysis |
| `/security:explain <ID>` | Detailed explanation of a finding type |
| `/security:help` | This help page |

## Scan Modes

| Mode | Speed | What's Checked |
|------|-------|---------------|
| **quick** | ~1 sec | .gitignore, permissions, secrets, .env tracking, debug flags |
| **scan** | ~5 sec | Quick + gitleaks, pip-audit, npm audit (if installed) |
| **deep** | ~30 sec | Scan + git history analysis |

## Severity Levels

| Level | Icon | Behavior in /flow |
|-------|------|-------------------|
| CRITICAL | Red circle | Blocks `/flow:finish` and `/flow:deploy` |
| HIGH | Yellow circle | Warning displayed, prompts to proceed |
| MEDIUM | Orange circle | Warning displayed, proceeds |
| LOW | White circle | Info only |

## External Tools (auto-detected)

| Tool | What it scans | Install |
|------|--------------|---------|
| `gitleaks` | Secrets in code + git history | `brew install gitleaks` |
| `pip-audit` | Python dependency CVEs | `uv pip install pip-audit` |
| `npm audit` | Node dependency CVEs | Built into npm |

## /flow Integration

- `/flow:finish` runs `/security:quick` before creating PR
- `/flow:deploy` runs `/security:quick` before deploying
- Configure gating in `.claude/security.yml`

## Configuration

Create `.claude/security.yml` to customize:

```yaml
gates:
  flow_finish:
    block_on: [critical]
    warn_on: [high]
  flow_deploy:
    block_on: [critical, high]
    warn_on: [medium]
suppressions:
  - id: HARDCODED_SECRET
    path: tests/fixtures/.*
    reason: "Test fixtures with fake credentials"
```
