---
contract: flow-auto
version: 1
subject: .claude/commands/flow/auto.md
intent:
  id: flow-auto.intent
  what: >
    One open issue goes from a worktree to a merged pull request, through a
    plan the owner approved, with ceremony proportional to the change.
  approved: 2026-11-16
purpose: Take one open GitHub issue through worktree, approved plan, implementation, PR and merge.
owner: owner
scope:
  in: [flow-auto.worktree, flow-auto.plan-record, flow-auto.review-receipt, flow-auto.guarded-merge]
  out: []
consumes: []
provides:
  - id: flow-auto.worktree
    what: implementation happens in the issue's own worktree, never on the default branch
    readers: [owner]
    test: tests/test_flow_worktree_native.py
  - id: flow-auto.plan-record
    what: the approved plan is recorded before the first edit and compared with the diff at finish
    readers: [owner]
    test: tests/test_flow_plan_record_runs.py
  - id: flow-auto.review-receipt
    what: a second-model review receipt, or a recorded skip naming one committed reason
    readers: [owner]
    test: tests/test_counter_model_review.py
  - id: flow-auto.guarded-merge
    what: merges only through gh-pr-merge.sh and removes worktrees only through worktree-remove.sh
    readers: [owner]
    test: tests/test_gh_pr_merge.py
requires:
  - id: flow-auto.issue-not-in-flight
    on_false: stop; another live session holds the issue
    test: tests/test_flow_worktree_claim.py
  - id: flow-auto.host-preflight
    on_false: stop before any issue read, fetch, claim or worktree
    test: tests/test_flow_start_resolve.py
invariants:
  always:
    - id: flow-auto.owner-approves-plan
      test: tests/test_eli5_gate_not_bypassable.py
  never: []
authority: []
failure: []
---

# /flow:auto charter

Owner rulings on #1850 (2026-11-15/16). The YAML block above is in skillc's
`CHARTER.md` format ([charters/README.md](../../README.md)). Under ruling N2(b)
it carries only clauses an EXISTING test backs. A `never` or `authority` clause
needs a committed `bad` case, and none exists yet, so those promises are stated
below in prose. They are binding as prose; they are not machine-checked as
charter clauses.

## What it promises

- One open GitHub issue, in a git repository with the CPP helpers installed,
  driven from a **Claude or Codex** session, with implementation in a worktree.
- The owner approves the plan before any edit, at every tier, with no bypass
  (#775).
- The plan's ceremony is proportional to the change. A Tier 1 documentation-only
  change answers lanes in one line (`Lanes: none - documentation only`), each
  `Reader:` row in one line, and may skip the second-model review when the
  approved plan says so, recorded as `tier-1-docs-only`. The tier claim is on
  the honour system, bound to the approved plan.

## What it declines

Refused mechanically, before anything is created:

- work already in flight (a live session's claim on the issue).

Recommended at Step 3, and closed only with the owner's yes:

- **open prerequisites** - a warning, never a silent start;
- **no longer needed** - a duplicate already evident in the code, or an ADR
  that has moved in another direction. An ADR is evidence, never absolute: the
  project evolves;
- **low frequency and low severity** - the proportionality test in
  [the issue contract](../../../docs/agents/issue-contract.md#supported-scope-and-proportional-prevention).
  Warn that doing the work may delay more important work, and offer to close it
  until it is shown to recur or to be severe. A security risk is never closed on
  these grounds.

## What it never does

- Never proceeds past Step 3 without the owner's approval of THIS run's plan.
- Never implements on the default branch.
- Never merges with a raw `gh pr merge` or removes a worktree by hand.
- Never passes an override a helper names (`--admin`, `--allow-*`, `--steal`).

## What it does not carry

Documentation is not a flow step: no diagram regeneration and no README /
CLAUDE.md review run as part of a run. A document a change makes wrong is part
of that change's plan. Outside the supported scope above, `auto.md` carries no
protective prose; that is the accepted limitation, by ruling.
