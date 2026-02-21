# Extras

Optional components that extend Claude Power Pack beyond its core workflow.

These are **not required** for the default `/flow` workflow. Install only what you need.

## Available Extras

| Extra | Description | Requires |
|-------|-------------|----------|
| [`sequential-thinking/`](sequential-thinking/) | Structured step-by-step reasoning with revision and branching | Node.js 18+ |
| [`redis-coordination/`](redis-coordination/) | Distributed locking and session tracking via Redis MCP server | Redis |

## Coordination Tiers

CPP supports three coordination modes. Most users need only `local` (the default).

| Tier | Mode | Description |
|------|------|-------------|
| **Local** (default) | `coordination: local` | Context detected from git cwd/branch. No locking. Zero dependencies. |
| **Git** (optional) | `coordination: git` | State tracked in `.claude/state.json`, synced via git push/pull. For cross-machine solo dev. |
| **Redis** (power-user) | `coordination: redis` | MCP coordination server with distributed locks. For teams running multiple Claude Code sessions. |

To set your coordination mode, add to your project's `.claude/config.yml`:

```yaml
coordination: local  # local | git | redis
```
