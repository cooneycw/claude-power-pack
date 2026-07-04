---
description: Overview of browser session commands (named concurrent playwright-mcp sessions)
allowed-tools: Bash(python3:*), Read
---

# Browser Commands Help

Named **concurrent** browser sessions over upstream `@playwright/mcp`, using a
static "lease-desk" pool (issue #421). Upstream gives one browser per connection;
this wrapper multiplexes any number of named, independently-authenticated
sessions across a small fixed pool of pre-registered instances - the one feature
upstream lacks (microsoft/playwright-mcp#1530), recovered without a fork.

## Available Commands

| Command | Description |
|---------|-------------|
| `/browser:session create <name> [url]` | Lease a free desk for a new named session |
| `/browser:session resume <name> [url]` | Re-open a session (restores its saved login) |
| `/browser:session save <name>` | Persist the session's cookies/localStorage to a state file |
| `/browser:session close <name> [--discard]` | Free the desk (keep state, or `--discard` to forget) |
| `/browser:session list` | Show sessions, status, and desk occupancy |
| `/browser:session cleanup [--idle-seconds N]` | Release desks of idle sessions (keeps state) |
| `/browser:session pool` | Show pool configuration and occupancy |
| `/browser:help` | This help page |

## The model in one paragraph

A fixed **pool of desks** (`playwright-desk-1..N`, pre-registered at Claude Code startup)
is leased by user-named **sessions**. A session's identity lives in a portable
storage-state file (`.claude/playwright-state/<name>.json`), so **sessions outlive desks**:
`close` frees a desk but keeps the file, `resume` re-leases any free desk and restores the
file into it. N desks multiplex unlimited named sessions.

## Setup (one time)

1. Register the desk pool: `/cpp:init` -> Full tier -> **browser pool** step (writes
   `.claude/playwright-pool.json` from `templates/playwright-pool.example.json` and runs
   `claude mcp add playwright-desk-N ... -- npx -y @playwright/mcp@<ver> --isolated ...`).
2. **Restart Claude Code** so the `playwright-desk-*` MCP servers load at startup
   (mid-session registration does not take effect - see the spike doc).
3. Verify: `/browser:session pool` and confirm `mcp__playwright-desk-1__*` tools exist.

## Configuration: `.claude/playwright-pool.json`

```json
{
  "version": 1,
  "desks": ["playwright-desk-1", "playwright-desk-2", "playwright-desk-3"],
  "idle_timeout_seconds": 1800,
  "state_dir": ".claude/playwright-state"
}
```

| Field | Description |
|-------|-------------|
| `desks` | MCP server names of the pre-registered pool (one browser each). Add more to widen concurrency (then register + restart). |
| `idle_timeout_seconds` | `cleanup` releases sessions idle beyond this (replaces the old server's `SESSION_TIMEOUT`). |
| `state_dir` | Where per-session storage-state files live (gitignored). |

The live ledger `.claude/playwright-sessions.json` is managed by the wrapper - do not edit.

## Requirements

- Node/`npx` on PATH (upstream `@playwright/mcp` runs via `npx`; no custom image).
- Desk pool registered **before** the session started (see Setup).

## When NOT to use this

Single-session automation (`/qa:test`, a one-off screenshot) needs only plain upstream
`playwright-mcp`. Reach for the desk pool only when you need several **named, concurrent**
sessions - e.g. driving two logged-in accounts side by side.

See `docs/skills/browser-session-wrapper.md` for the full guide and
`docs/reviews/2026-07-03-playwright-spike-419.md` for the design rationale.
