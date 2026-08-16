# Tasks: Balanced Agentic Development

> **Plan:** [plan.md](./plan.md)
> **Created:** 2026-08-15
> **Status:** Ready

---

## Task Format

```text
[ID] [P?] [Story] Description (depends on X, Y)
```

These are intentionally coarse delivery tasks: one issue and one reviewable PR
per task. Acceptance criteria live in the linked spec and in each task's
checkpoint. Implementation discoveries are recorded in the residual ledger and
are not automatically expanded into more tasks.

---

## Wave 1: Establish issue economy

- [ ] T001 [US1] Implement an executable `flow:wave` residual candidate ledger, classification state machine, final-tree human promotion gate, issue-economy metrics, prompt/reference integration, and behavioral tests

**Checkpoint:** A simulated wave records every residual, cannot create a
follow-up while active, routes active-PR defects back to the PR, and can promote
only one eligible, revalidated, deduplicated, human-approved candidate after
closure. The summary reports seeds, recorded, duplicates, promoted,
amplification, and promotion rate.

---

## Wave 2: Repair foundations

- [ ] T002 [P] [US2] Convert supported native skills to canonical directory-based `SKILL.md` packages, remove or report stale mirrors/retired wrappers, add truthful vendored/adapted/inspired/CPP-authored provenance (including Matt Pocock/MIT attribution for `grill-me` without mislabeling CPP's `grill-yourself`), and add non-mutating source/reference/managed-install parity checks through `make skills-check` (depends on T001)
- [ ] T003 [P] [US3] Add Python/Node/Go/Rust characterization fixtures and extract a deterministic `project:init` planning/apply engine with idempotent dry-run, validated resume checkpoints, resolved template values, and explicit `main` initialization (depends on T001)

**Checkpoint:** T002 and T003 each pass independently. A clean skill install has
surface parity and valid provenance without touching user-authored skills;
missing upstream attribution and false vendored claims fail deterministically.
Repeated init plans are
byte-identical, dry-run does not mutate, resume does not repeat completed work,
and existing supported scaffold outputs remain compatible except for the two
specified bug fixes.

---

## Wave 3: Add discovery and planning-aware routing

- [ ] T004 [US4] Add a destination-first clarity/session-count gate to `project:init`, explicitly approved Wayfinder maps of decision questions with fog/frontier/blocking state, and a resumable cleared-map handoff to specification without production implementation (depends on T003)
- [ ] T005 [US5] Extend `project:next` with native blockedBy/blocking/parent/sub-issue/assignee collection, planning-only Wayfinder routes, explicit fallback uncertainty, shared brief/compact/full decisions, and an authoritative in-repo engine/fixture contract that cannot skip in CI (depends on T004)

**Checkpoint:** All four discovery routes are covered. No tracker mutation occurs
without approval, no decision ticket routes to `flow:auto`, and native and
fallback issue graphs produce explainable recommendations from the same tested
decision core.

---

## Wave 4: Minimize persistent context safely

- [ ] T006 [US6] Reduce `CLAUDE.md` to durable invariants, safety rules, verification commands, source-of-truth pointers, and workflow routing; move owned depth to on-demand references and add word-budget, link, and behavior-preservation checks (depends on T002, T003, T004, T005)

**Checkpoint:** `CLAUDE.md` is at most 2,000 words, every pointer resolves, cold
start navigation remains sufficient, detailed state machines remain available
from their owning skills, and the full repository verification suite passes.

---

## Delivery Guardrails

- Land T001 before starting Wave 2.
- Run at most two workers concurrently; T002 and T003 are the only planned
  parallel pair.
- Keep each task to one focused PR and fix regressions introduced by that PR
  before merge.
- Do not file issues from worker or reviewer residuals. Use the candidate ledger
  and one post-wave promotion pass.
- Require evidence and final-tree revalidation for promotion. Generation 2+
  candidates remain ledger-only absent a human-approved security, data-loss, or
  work-blocking emergency.
- Report recorded and promoted counts at every checkpoint.

---

## Issue Sync

> Generated once from this file with `scripts/speckit-tasks-to-issues.sh` after
> validation. The mapping below is updated in the same specification PR.

| Task | Issue | Status |
|------|-------|--------|
| T001 | [#719](https://github.com/cooneycw/claude-power-pack/issues/719) | open |
| T002 | [#720](https://github.com/cooneycw/claude-power-pack/issues/720) | open |
| T003 | [#721](https://github.com/cooneycw/claude-power-pack/issues/721) | open |
| T004 | [#722](https://github.com/cooneycw/claude-power-pack/issues/722) | open |
| T005 | [#723](https://github.com/cooneycw/claude-power-pack/issues/723) | open |
| T006 | [#724](https://github.com/cooneycw/claude-power-pack/issues/724) | open |

---

## Notes

- `[P]` means the task may run alongside the other `[P]` task after all listed
  dependencies have merged.
- Task issues are the approved implementation plan, not residual issues created
  by review.
- Wayfinder is not used for this work because its destination and route are
  already specified; T004 adds it for future foggy, multi-session projects.

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).*
