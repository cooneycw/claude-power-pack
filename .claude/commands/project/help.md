---
description: Overview of project management commands
---

# Project Commands

Commands for creating and managing projects.

## Commands

| Command | Description |
|---------|-------------|
| `/project:init <name>` | Full project scaffolding — zero to GitHub repo |
| `/project-next` | Scan issues and worktrees to recommend next steps |
| `/project-lite` | Quick project reference with minimal context |
| `/claude-md:lint` | Audit CLAUDE.md for CI/CD and troubleshooting directives |

## /project:init

One-command project setup that orchestrates:

1. Creates `~/Projects/<name>` with framework scaffold (Python/Node/Go/Rust)
2. Initializes git and pushes to a new GitHub repo
3. Generates Makefile from detected framework (`lib/cicd`)
4. Installs CPP commands, skills, and hooks (symlinks)
5. Initializes `.specify/` for spec-driven development
6. Optionally creates an initial feature spec

**Example:**
```
/project:init my-api
```

**Features:**
- Idempotent — safe to re-run if interrupted (completed steps are skipped)
- Framework-specific scaffolds with best-practice project structure
- Integrates with `/flow`, `/spec`, `/security`, and all CPP commands

## /project-next

Full GitHub issue analysis with prioritized recommendations. Scans open issues, maps worktrees, detects hierarchy (Waves/Phases), and suggests what to work on next.

**Use when:** Unsure what to work on, need issue triage, or want cleanup suggestions.

## /project-lite

Lightweight project reference for quick orientation. Shows repo info, conventions, worktrees, and available commands with minimal context usage.

**Use when:** Starting a session, context is high, or you already know what to work on.
