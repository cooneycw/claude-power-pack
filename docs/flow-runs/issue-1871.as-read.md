<!-- flow-run n=1 id=bfcb7406630b437c84dcb536eaf0d5b7 -->
## Run 1 - issue #1871 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1871
- Read at:      2026-11-21T17:36:20Z
- updatedAt:    2026-11-21T15:37:34Z   (context only - moves on comments and labels)
- Body digest:  b9287e0706ef8e20afed6b805e8645b301904d01ba3a1e4429916bc3826f881f   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2367 of 2367 (cap 16384)

### Body as read
Tier: 1

## Outcome

A plan record never trips CI's secret scan for recording a commit hash, and a committed control proves it.

PR #1870 (#1864) went red on CI's `secret-scan` step: gitleaks 8.30.1 rule `generic-api-key` matched a plan-record line in Section B reading `- API main: <40-hex sha>`. It is a false positive, but every other CI step depends on `secret-scan`, so the whole pipeline failed. CI scans git history, so the fix also needed a branch-history rewrite.

## What was measured (main `25f5066a`, 2026-11-21)

- No generator writes that line. "API main" has zero hits in `scripts/`, `templates/`, `.claude/commands/` and `docs/agents/`. The implementing session typed it by hand in Section B.
- No committed record on main has the shape: zero hits in `docs/flow-runs/` and `docs/measurements/` for "api main", or for api/key/token within 20 characters of a 40-hex string.
- The generator already records the fact safely. `flow-plan-record.py begin-run` writes `- Run-start: <HEAD sha>`, and `declare-salvage` writes `- Salvage: <sha>`. So the hand-written line restated a fact the record already carries.
- The local gate catches it. `make secret-scan` (gitleaks `--no-git` on the working tree) fails closed when gitleaks is absent. It went through because the PR was pushed before any finish gate had completed.

## Scope

1. A committed red/green control. Run the pinned gitleaks 8.30.1 with the exact `.woodpecker.yml` `secret-scan` command and `.gitleaks.toml` on fixture files:
   - **red:** a plan-record excerpt with `- API main: <40-hex>` must be reported (`generic-api-key`);
   - **green:** the real generated header (`- Run-id:`, `- Run-start: <40-hex>`, `- Salvage: <40-hex>`) must not be reported.
   The control must say UNKNOWN, never green, when gitleaks is not available. A gate that silently skips is the blind-instrument case.
2. One line in the plan-record guidance (`docs/agents/` where Section B is described): the start commit is already in `Run-start`. Don't restate hashes in free text, and never put `api`/`key`/`token` next to one.
3. No allowlist entry and no rule relaxation in `.gitleaks.toml`.

## Not in scope

- Shipping gitleaks in Kyle's session image, so containers can scan before pushing. That is Kyle-side and is being filed separately by the fleet master. It will be linked here when filed.

Refs #1864, #1870


<!-- end of body -->
