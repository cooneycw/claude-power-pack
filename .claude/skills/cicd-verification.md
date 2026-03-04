---
name: CI/CD & Verification
description: Build system, health checks, CI/CD pipeline, and container patterns
trigger: CI/CD, pipeline, health check, smoke test, Makefile generation, GitHub Actions, Dockerfile, docker-compose, verification, post-deploy
---

# CI/CD & Verification Skill

When the user asks about CI/CD, build systems, health checks, smoke tests, pipelines, containers, or deployment verification, load the full reference:

```
Read docs/skills/cicd-verification.md
```

## Quick Reference

### Commands

| Command | Purpose |
|---------|---------|
| `/cicd:init` | Detect framework, generate Makefile and cicd.yml |
| `/cicd:check` | Validate Makefile against CPP standards |
| `/cicd:health` | Run health checks (endpoints + processes) |
| `/cicd:smoke` | Run smoke tests from cicd.yml |
| `/cicd:container` | Generate Dockerfile and docker-compose.yml |
| `/cicd:help` | Overview of CI/CD commands |

### The Verification Loop

```
code → lint/test → deploy → health check → smoke test → report
```

### CLI Usage

```bash
PYTHONPATH="$HOME/Projects/claude-power-pack/lib:$PYTHONPATH"
python3 -m lib.cicd <command> [options]
```

Subcommands: `detect`, `check`, `health`, `smoke`, `pipeline`

### Configuration

Health checks and smoke tests are configured in `.claude/cicd.yml`. See `/cicd:help` for full configuration reference.
