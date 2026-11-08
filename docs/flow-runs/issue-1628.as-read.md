<!-- flow-run n=1 id=1d6ae7189cf54be0b96d202205208780 -->
## Run 1 - issue #1628 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1628
- Read at:      2026-11-07T18:21:49Z
- updatedAt:    2026-11-07T18:04:05Z   (context only - moves on comments and labels)
- Body digest:  de1184089539636ace3c8b12ceb4c81d0e306553c8dfc6b1a9eccf6cade92cf0   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2883 of 2883 (cap 16384)

### Body as read
## Problem

CPP helpers now require bash 4 or newer, but nothing states that requirement or checks for it. `#!/usr/bin/env bash` resolves to `/bin/bash` 3.2.57 on a stock macOS host, and helpers fail with raw shell errors partway through a command.

Observed during a `/cpp:update` from v7.4.0 to v10.1.0 on macOS (Darwin 25.5.0, arm64), before bash 5.3 was installed through Homebrew:

| Script | Failure under bash 3.2 |
|--------|------------------------|
| `scripts/stash-worktree-guard.sh` | Parse error at line 309 on `;&` (case fallthrough). Exit 2 from `--install`, so the guard was not installed |
| `scripts/hook-permission-census.sh` | Fails `bash -n`. This is a registered `PermissionRequest` hook, so it would fail on every permission prompt |
| `scripts/delegated-run-check.sh` | Fails `bash -n` |
| `scripts/flow-wave-mailbox.sh` | Fails `bash -n` |
| `scripts/drift-detect.sh` | Line 57: `declare: -A: invalid option`. Exit 2 |
| `scripts/install-drift.sh` | Line 899: `FAMILIES[@]: unbound variable` (empty array under `set -u`). Exit 1, so the Step 5b orphan scan did not run |

All six worked or parsed once bash 5.3 came first on PATH. The first four came from a `bash -n` sweep of `scripts/*.sh`, so scripts that parse under 3.2 but fail at runtime may be missing from this table: 11 scripts in `scripts/*.sh` match a grep for bash 4 constructs.

`/cpp:update` Step 5b.1 only documents a fallback for exit 127, so exit 2 from the stash guard has no defined handling.

## Outcome

On a host whose `bash` is too old, CPP says so once, plainly, and names the remedy, instead of surfacing raw parse errors from individual helpers. The supported bash version is written down.

## Acceptance

- With bash 3.2 first on PATH, `/cpp:update` and `/cpp:init` report the unmet bash requirement by name and give the remedy.
- `/flow:doctor` or the shared host preflight reports the same finding.
- With bash 4 or newer, nothing new is printed.
- The minimum bash version is documented where host prerequisites are listed.

## Constraints

- A registered hook must stay fail-open: an old bash must not block or alter a permission decision.
- A check must be able to report that it could not determine the version, not read that as a pass (see `docs/agents/detector-contracts.md`).

## Proposed approach

Add the check to `scripts/flow-preflight.sh`, or whichever shared preflight owns host prerequisites, and call it from `/cpp:update` and `/cpp:init`. The alternative is making the helpers bash 3.2 compatible, which is more work across more files but removes the dependency on macOS users installing bash.

## Assumption

A host can still resolve the old bash after a modern one is installed. Observed here: with `PATH=/usr/bin:/bin`, `env bash` still gets 3.2, so launchd jobs without a PATH would keep failing. Whether any CPP surface runs that way has not been checked.


<!-- end of body -->
