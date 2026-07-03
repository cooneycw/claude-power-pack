---
name: Browser Session Wrapper
description: Named concurrent browser sessions over upstream playwright-mcp via a lease-desk pool
trigger: browser session, playwright, named session, concurrent browser, lease desk, storage state
---

# Browser Session Wrapper (Lease-Desk)

Recover **named concurrent** browser sessions on top of upstream
`@playwright/mcp` - the one capability upstream lacks
(microsoft/playwright-mcp#1530) - as a thin CPP wrapper, with no fork and no
custom 1.27 GB image. Surface: `/browser:session` and `/browser:help`
(issue #421). Design rationale: `docs/reviews/2026-07-03-playwright-spike-419.md`.

## Why a pool (the constraint)

Upstream playwright-mcp provides **one browser context per client connection**.
So "several named sessions at once" requires **several server instances**. And
Claude Code reads MCP config **only at startup** - a server added mid-session
(`claude mcp add` + `/mcp reconnect`) is not exposed until a restart. That rules
out spawn-per-session (Design B) and leaves exactly one viable shape: a **static,
pre-registered pool** (Design A).

## The lease-desk model

- **Desk** = one pre-registered upstream instance (`playwright-desk-1`, ...),
  each launched with `--isolated` (blank, in-memory context). Registered as an
  MCP server at startup, so its tools appear as `mcp__playwright-desk-N__browser_*`.
- **Session** = a user-named identity (`gmail`, `staging-checkout`). Its cookies +
  origin localStorage are a **portable storage-state JSON** at
  `.claude/playwright-state/<name>.json`.
- **Lease** = binding a session to a free desk. `create`/`resume` acquire; `close`/
  `cleanup` release. The binding lives in the ledger `.claude/playwright-sessions.json`.
- **Sessions outlive desks.** Because identity is a file, a session can be closed,
  the desk reused by another session, the container restarted - and the session
  resumes on any free desk by re-injecting its state file. N desks multiplex an
  unbounded number of named sessions.

```
sessions (unbounded)          desks (fixed pool = concurrency limit)
  gmail ........ leases ---->  playwright-desk-1  (mcp__playwright-desk-1__*)
  staging ...... leases ---->  playwright-desk-2  (mcp__playwright-desk-2__*)
  reporting .... detached      playwright-desk-3  (free)
     ^ state on file, no desk
```

## Components

| Piece | Role |
|-------|------|
| `scripts/playwright-desk.py` | Deterministic ledger + state-file bookkeeping (lease/release/idle-cleanup). Zero-dependency stdlib. Emits `--json` for the skill, human text for you. Never touches the browser. |
| `.claude/commands/browser/session.md` | The `/browser:session` verbs; drives each desk's `browser_*` tools and reads/writes state files. |
| `.claude/playwright-pool.json` | Pool config: desk names, idle timeout, state dir. Seed from `templates/playwright-pool.example.json`. Gitignored. |
| `.claude/playwright-sessions.json` | Live lease ledger (wrapper-owned; do not edit). Gitignored. |
| `.claude/playwright-state/<name>.json` | Per-session storage state. Gitignored. |

## Division of labour (important)

The helper is **deterministic and browser-blind**. It answers "which desk does this
session hold, and where is its state file?" and enforces the pool limit. Everything
that touches a browser - navigate, `browser_set_storage_state` (restore),
`browser_storage_state` (capture) - is done by the model via the desk's MCP tools.
`save` is therefore two moves: the helper records intent + returns the path; the
model captures the storage state and writes it to that path.

## Lifecycle

```
create gmail ┐
             ├─ lease desk-1 (blank) ─ navigate ─ log in ─ save gmail ─┐
resume gmail ┘   (restore state-file first if it exists)               │
                                                                       ▼
             close gmail ── desk-1 freed, .claude/playwright-state/gmail.json kept
                                                                       │
             resume gmail ── lease any free desk ── restore file ── logged in again
```

- `create <name> [url]` - new session on a free desk (error `no_free_desk` when the
  pool is full; `session_exists` if the name is taken).
- `resume <name> [url]` - re-seat an existing session; when the helper reports
  `restore: true`, read the state file and call `browser_set_storage_state` before
  navigating.
- `save <name>` - capture `browser_storage_state` -> write to the reported file.
- `close <name> [--discard]` - free the desk; keep the state file unless `--discard`.
- `list` / `pool` - inspect sessions and occupancy.
- `cleanup [--idle-seconds N]` - release desks of idle sessions (keeps state). This is
  the idle-timeout replacement for the retired server's `SESSION_TIMEOUT`.

## Setup

1. `/cpp:init` -> Full tier -> **browser pool** step: seeds `.claude/playwright-pool.json`
   and registers `playwright-desk-1..N` as stdio MCP servers:
   ```bash
   claude mcp add playwright-desk-1 --scope user -- npx -y @playwright/mcp@0.0.77 --isolated
   ```
2. **Restart Claude Code** (startup-only MCP config load).
3. `/browser:session pool` - confirm the pool and that `mcp__playwright-desk-1__*` tools exist.

## Trade-offs and boundaries

- **Concurrency = pool size.** Widen it by adding desks to the config and registering the
  matching servers (then restart). Each desk adds its `browser_*` tool surface to every
  session's startup context, so keep the default small (3).
- **Not for single-session work.** `/qa:test` and one-off screenshots use plain upstream
  `playwright-mcp`; the pool is only for genuinely concurrent named sessions.
- **Endgame.** If named multi-session lands upstream (microsoft/playwright-mcp#1530), this
  wrapper thins to naming discipline over native support - see issue #422's closing note.
