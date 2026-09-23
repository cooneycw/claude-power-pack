# Flow run record - issue #1221

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1221
- Base SHA:          99670b5
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (interactive session, "approved")
- Recorded at:       2026-09-23T21:50:00Z

## Section B evidence
- commits: none touching scripts/flow-start-resolve.sh since filing (last: 0c11b45, #1087)
- PRs: #1199-#1225 merged since 2026-09-22; none touch the resolver
- dup/super: none (#1031 unrelated, #864 nit store)
- Comment instance 2 (reused branch with merged PR): already covered by the
  local-pickup / remote-pickup PR_HEAD probe; pinned by a test, no code change.
- Comment instance 4 (gh pr merge --delete-branch): handled by gh-pr-merge.sh (#461).

## Section C - the approved plan
1. `scripts/flow-start-resolve.sh` - create_worktree: `--no-track` on the -b path; after either path set branch.<b>.remote=origin and branch.<b>.merge=refs/heads/<b> when origin exists (repairs a reused branch tracking origin/main); document in the header contract.
2. `tests/test_flow_start_resolve.py` - regression tests: upstream is origin/<branch>; bare push reaches origin (ls-remote); rejected push never emits HEAD:main; reused leftover branch re-pointed; local-pickup with merged PR reports PR_HEAD=<n>:MERGED + CONFIRM_REQUIRED=1. Red-run (a)-(c) on the pre-fix resolver.

Scope: 2 source files, ~30 lines script, ~120 lines tests, plus generated codex/skills mirrors if bundled.
Risks: `[gone]` upstream before first push (no in-repo tool acts on it; a personal prune-gone alias would). Codex/qwen/gemma auto lanes hand-create worktrees tracking origin/main and their overrun check depends on it - nit store, not this change.
