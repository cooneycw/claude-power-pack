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

Create `.claude/security.yml` to customize gate behavior and suppress known findings.

If this file does not exist, sensible defaults are used (see below).

### Annotated Example

```yaml
# .claude/security.yml — Security gate configuration
# All sections are optional. Missing sections use defaults.

# Gates control how /flow:finish and /flow:deploy respond to findings.
# Each gate has two lists:
#   block_on: severities that STOP the flow (must fix before proceeding)
#   warn_on:  severities that DISPLAY a warning but allow the flow to continue
# Severities not in either list pass silently.
gates:
  flow_finish:
    block_on: [critical]         # CRITICAL findings block PR creation
    warn_on: [high]              # HIGH findings shown as warnings
    # MEDIUM and LOW pass silently
  flow_deploy:
    block_on: [critical, high]   # Both CRITICAL and HIGH block deployment
    warn_on: [medium]            # MEDIUM findings shown as warnings
    # LOW passes silently

# Suppressions hide known false positives from scan results.
# Each entry must have an 'id' matching the finding type.
# 'path' is an optional regex — if provided, only findings in matching
# files are suppressed. 'reason' documents why the suppression exists.
suppressions:
  - id: HARDCODED_SECRET         # Finding type (from /security:explain)
    path: tests/fixtures/.*      # Only suppress in test fixtures
    reason: "Test fixtures with fake credentials"

  - id: DEBUG_FLAG_ENABLED
    path: docs/examples/.*
    reason: "Example code intentionally shows debug configuration"
```

### Default Behavior (no security.yml)

| Gate | Blocks on | Warns on |
|------|-----------|----------|
| `flow_finish` | CRITICAL | HIGH |
| `flow_deploy` | CRITICAL, HIGH | MEDIUM |

### Finding Types

Use `/security:explain <ID>` to see details about any finding type (e.g., `HARDCODED_SECRET`, `ENV_FILE_TRACKED`, `DEBUG_FLAG_ENABLED`). The ID is shown in scan output next to each finding.
