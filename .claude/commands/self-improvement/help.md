---
description: Overview of self-improvement commands
---

# Self-Improvement Commands

Retrospective analysis commands that examine recent failures and suggest improvements to project tooling.

## Commands

| Command | Purpose |
|---------|---------|
| `/self-improvement:deployment` | Analyze deployment errors and propose Makefile improvements |
| `/self-improvement:help` | This help page |

## Philosophy

The `/flow` workflow is forward-focused: start, implement, finish, merge, deploy. But when things go wrong, there is value in looking backward to improve the tooling itself.

Self-improvement commands:
- Examine errors from the current session and project history
- Identify patterns of recurring failure
- Propose concrete changes to build/deploy infrastructure
- Optionally apply approved changes

## When to Use

Run `/self-improvement:deployment` after:
- A failed `make deploy` or `make test`
- Repeated build failures in a session
- Setting up a new project's Makefile
- Periodically to audit Makefile quality against CPP standards

## Feedback Loop

```
/flow:deploy -> fails -> /self-improvement:deployment -> fix Makefile -> /flow:deploy -> succeeds
```

## Future Commands

The self-improvement category may grow to include:
- **test** — Analyze test failure patterns, suggest test infrastructure improvements
- **review** — Analyze PR review feedback patterns, suggest code quality improvements
- **session** — Analyze session patterns, suggest CLAUDE.md improvements

## Related Commands

| Command | Relationship |
|---------|-------------|
| `/flow:doctor` | Forward-looking health check (complements retrospective) |
| `/flow:deploy` | The deploy command whose failures this analyzes |
| `/flow:finish` | Quality gates that depend on Makefile targets |
| `/security:scan` | Security-focused analysis (complementary) |
