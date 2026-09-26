# Flow run record - issue #1257

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1257
- Base SHA:          5bed7408efbb213a98bc5662e525d0a934d6053d
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          repository owner (cooneycw), in-session reply "approved."
- Recorded at:       2026-09-26T14:35:58Z

## Section B evidence
- Commits since filing touching lib/project_next or scripts/project-next.py: 5bed740 (PR #1270, #1035 items 1-4; explicitly defers item 5 = this issue; no delivery/blob logic).
- Merged PRs since filing: #1270, #1255 (unrelated resync test).
- Duplicate/superseding issues: none (searched; found #1035 parent closed, #864 nit store, #1075/#1211 unrelated).

## Section C - the approved plan
Placement: a CPP adapter extension `cpp_extensions.worktree_delivery`, not an engine/contract change (no contract bump).

1. `scripts/project-next.py` - WorktreeDelivery dataclass, CppExtensions.worktree_delivery, worktree_delivery() with injectable runner (merge-base diff vs origin/<default> diff path intersection; fresh status; one ls-remote), render in brief/compact/full, wire into main().
2. `tests/test_project_next_worktree_delivery.py` - negative controls on real temp git repos (delivered, one-file-differs not-proven, dirty not delivered, untracked not delivered, deleted-path not-proven) plus failing-runner unknown and fixture-input unknown.
3. `.claude/commands/project/next.md` - add worktree_delivery to the CPP extension contract list.
4. `codex/skills/project-next/SKILL.md` - regenerated mirror of #3 (resync helper only).

Scope: ~180 lines code, ~200 lines tests.
Risks: real-git controls skip in the git-less CI image (only failing-runner and fixture cases run there); ls-remote needs network and degrades to unknown; per-worktree status duplicates the collector's call deliberately.
