# Issue #1282 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1282
- Read at:      2026-09-28T09:57:15Z
- updatedAt:    2026-09-26T16:29:59Z   (context only - moves on comments and labels)
- Body digest:  754ba1c7355878cd49c2c073c9718420249d472879a746387ff46e68ba14f2b7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2176 of 2176 (cap 16384)

## Body as read
## Summary

`/cpp:status` should report when the claude-power-pack checkout is **behind `origin/main`**, and say so as a distinct state when that cannot be determined.

## Why

The checkout is the single source for every CPP helper on the host: `~/.claude/scripts` is a symlink farm into `<checkout>/scripts`, and kyle session containers mount that directory live (kyle#1197). So a checkout behind `origin/main` means every session on the box - host and container - runs superseded helpers, with nothing saying so. It advances only when something pulls: `/flow:auto` and `/flow:merge` do at the end of a run, a merge done on GitHub directly does not. Context: cooneycw/kyle#1395 (containers frozen on per-file mounts), which owns the kyle-side half of "helpers keep pace with CPP".

## Current state

`.claude/commands/cpp/status.md` has no freshness check. `/cpp:update` has one, at `.claude/commands/cpp/update.md:154`:

```bash
BEHIND=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count 2>/dev/null || echo "0")
```

**Do not copy that shape.** `|| echo "0"` turns "could not count" (no remote-tracking ref, a failed fetch, a detached HEAD) into `0`, which the next line reports as up to date - an unknown rendered as clean. That is worth fixing in `update.md` too, in the same change or as a nit.

## Acceptance

- [ ] `/cpp:status` fetches `origin` and prints one of: `current`, `behind N` (with `git log --oneline HEAD..origin/main`, capped), `ahead N / diverged` (local commits on main - a different warning), or `unknown: <reason>` when the fetch or count fails. `unknown` is never rendered as `current`.
- [ ] It also names the checkout's current branch when it is not `main`: a primary checkout left on a feature branch serves that branch's helpers to every session.
- [ ] Committed cases (ADR 0008 - `/cpp:status` is read by other sessions): a fixture repo one commit behind its origin reads `behind 1`; the same repo after pull reads `current`; a repo whose fetch fails (unreachable remote) reads `unknown`, not `current`.
- [ ] `update.md:154` stops mapping a failed count to `0`.

Found while filing kyle#1395, after cooneycw/claude-power-pack#1258 (PR #1279).

