---
description: Overview of CLAUDE.md management commands
---

# CLAUDE.md Commands

Audit and manage your project's CLAUDE.md governance directives.

## Commands

| Command | Description |
|---------|-------------|
| `/claude-md:lint` | Audit CLAUDE.md for CI/CD, Docker, and troubleshooting directives |
| `/claude-md:help` | This help page |

## Why CLAUDE.md Governance Matters

CLAUDE.md is the primary mechanism for directing Claude Code agent behavior. Without explicit CI/CD and troubleshooting directives, agents default to ad-hoc approaches that bypass your project's build pipeline.

`/claude-md:lint` checks that your CLAUDE.md includes:

| Category | What It Checks |
|----------|----------------|
| CI/CD Protocol | Makefile targets referenced for build/test/deploy |
| Troubleshooting Protocol | Directives to fix CI/CD alongside code |
| Quality Gates | `make lint`, `make test`, `make verify` mentioned |
| Docker Conventions | `make docker-*` targets (if Docker files exist) |
| Deployment Protocol | `make deploy` or deployment workflow |
| Available Commands | Makefile targets listed for reference |

## Scoring

| Score | Rating |
|-------|--------|
| 5-6 / 6 | HEALTHY |
| 3-4 / 6 | NEEDS ATTENTION |
| 0-2 / 6 | UNHEALTHY |

## Quick Start

```bash
# Audit your CLAUDE.md
/claude-md:lint

# Fix gaps in your Makefile first
/cicd:check

# Full project health: Makefile + CLAUDE.md
/cicd:check && /claude-md:lint
```

## Related

- `/cicd:check` - Validate Makefile targets
- `/cicd:init` - Generate Makefile from detected framework
- `/project:init` - Full project scaffolding (generates CLAUDE.md with directives)
