<!-- flow-run n=1 id=dbafb8edfde54b91b5ef16b99ef0b99e -->
## Run 1 - issue #1677 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1677
- Read at:      2026-11-11T18:52:13Z
- updatedAt:    2026-11-11T18:48:43Z   (context only - moves on comments and labels)
- Body digest:  3a8fed4dd692123a1a243b5e16af31c4be7e605263ac8a55a35ebdd326fe9c02   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2243 of 2243 (cap 16384)

### Body as read
Promoted from the nit store on the owner's ruling (2026-11-11): a medium-severity finding gets its own issue. Original: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6804396488


- **Where:** `scripts/gh-pr-merge.sh` host preflight (exit 13, `GH_PR_MERGE_HOST_PREFLIGHT: stop`, "CI providers unknown") and `scripts/flow-ci-status.sh` (exit 2 without `--fallback-provider-probes`). Both now read `pipeline.providers` from `<checkout toplevel>/.claude/cicd.yml`.
- **What happened (cooneycw/kyle, 2026-11-11):** the host CPP checkout was pulled to dca1ac6b at 11:01 EST while a wave was running. `~/.claude/scripts` links into that checkout, so every live session got the new helpers at once. The next merge (kyle PR #2293) took the merge lock, stopped in 2 seconds with exit 13, and released. Kyle had no `.claude/cicd.yml`, and kyle ignores `.claude/*`, so the fix (`python -m lib.cicd pipeline --path <worktree> --providers woodpecker --record`) had to be repeated in every worker's worktree.
- **Why it matters:** the stop itself is the designed behaviour ("unknown records stop with the writer remedy"), and it failed closed. The cost is the rollout: no migration note reached running sessions, the remedy is per-worktree for any project that ignores `.claude/`, and a helper that changes under a held lock wastes the slot.
- **Suggested, for whoever aggregates this:** (1) `/cpp:update` or the session-start CPP check names "this project has no recorded CI provider; merges will stop" before a merge is attempted; (2) the writer's remedy text says the file must be tracked or re-recorded per worktree; (3) consider resolving the record from the main checkout when a linked worktree lacks it.
- **Found while:** orchestrating kyle wave `kyle-cli` (kyle #2283 / PR #2293). Kyle's side is handled by tracking the file in kyle PR for #2313.

## Acceptance (draft)
- A project with no recorded CI provider is told so BEFORE a merge is attempted (`/cpp:update`, or the session-start CPP check), by name.
- The remedy text says the record must be tracked or re-recorded per worktree; or a linked worktree resolves the record from the main checkout.
- Red case: a worktree with no record and a main checkout that has one.


<!-- end of body -->
