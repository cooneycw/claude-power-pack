# Issue #1261 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1261
- Read at:      2026-09-27T17:39:09Z
- updatedAt:    2026-09-26T14:12:35Z   (context only - moves on comments and labels)
- Body digest:  917cea93dbfc501c84f0d97a83e16fd0ff419b60fe851a0ed0717c8343a4c0aa   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2686 of 2686 (cap 16384)

## Body as read
**Wave W1D**, from the Nit Store (#864) sweep of 2026-09-26 against `85e9b03`. Highest severity in this lane: **S1**. Each item below was re-checked against main by a cheap read; before you implement an item, reproduce it on current main, since some of these nits are two weeks old.

Grouped by the files a fix would touch, so this lane can run in parallel with the other lanes in its wave.

## Findings

- [ ] **S1** codex:code_review hardcodes --sandbox read-only, making container reviews silently diff-only (live; found during kyle#1210)
  - evidence: .claude/commands/codex/code_review.md:233 still passes `--sandbox read-only` unconditionally; no container-detection branch found to switch to danger-full-access
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5796191303
- [ ] **S1** Delegated auto lanes create worktrees tracking origin/main, silently blinding the overrun guard once fixed (live; found during issue #1221)
  - evidence: .claude/commands/codex/auto.md:139 (and qwen/gemma equivalents) still say "Create fresh from origin/main" with no reference to flow-start-resolve.sh
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5803519802
- [ ] **S2** codex:code_review's mapfile loses ls-files exit status, so a failed enumeration reads as zero untracked files (live; found during issue #1220 / PR #1231)
  - evidence: .claude/commands/codex/code_review.md:182 still `mapfile -d '' -t UNTRACKED_FILES < <(git ... ls-files ... -z)`; the fixed pattern from flow:auto (#1220/PR #1231, temp file + explicit check) is not applied here
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5811439727
- [ ] **S2** codex/auto.md Step 3/8 approval gate prints to the pane with no mailbox route for orchestrated/fleet runs, worker can stall undetectably (live; found during cpp-issues wave (Kyle group 37))
  - evidence: .claude/commands/codex/auto.md:234 still prints 'Awaiting approval (Step 3/8) - reply approve, revise, or abandon.' with no orchestrated-run detection or mailbox routing
  - nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5740537557

## Negative control (ADR 0008)

A review run in a container must be able to read the files it cites, or say it saw only the diff. A delegated worktree must not track `origin/main`; that is the overrun guard's input. A failed `ls-files` must read as failed, not as zero untracked files.

## Done when

Every box is either fixed, with its red case run on the pre-fix code and the result stated in the PR, or explicitly re-dispositioned in a comment here with evidence (delivered, superseded, or not reproducible).
