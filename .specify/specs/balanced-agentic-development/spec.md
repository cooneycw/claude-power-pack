# Feature Specification: Balanced Agentic Development

> **Branch:** `spec/balanced-agentic-development`
> **Created:** 2026-08-15
> **Status:** Approved

---

## Overview

Claude Power Pack (CPP) should remain thorough where thoroughness changes a
development decision, while becoming compact at discovery and routing seams.
Today those concerns are mixed: some skills expose implementation detail before
it is needed, `project:init` scaffolds before it establishes whether the route is
known, and `flow:wave` can turn review observations into a self-expanding issue
graph. The result is contradictory feedback that the pack is simultaneously too
verbose, too prescriptive, and not explicit enough.

This feature defines one balancing model:

1. **Compact routing, deep execution.** Entrypoints state when to use a workflow,
   its contract, and where deeper guidance lives. Stateful execution skills may
   remain detailed when omission has caused observed failures.
2. **Decisions before implementation.** `project:init` names the destination and
   selects a discovery path before choosing a framework or writing files.
3. **Evidence before backlog growth.** Review records every residual, but only a
   post-wave promotion pass may create a follow-up issue.
4. **Executable contracts over prose enforcement.** Critical workflow rules are
   represented by deterministic state, validators, and behavioral tests.

The Wayfinder portion adapts Matt Pocock's situational planning on-ramp: an
effort that is both larger than one agent session and whose route is unclear is
charted as a map of decision questions, then handed to specification and
implementation only after the route is clear. It is not a default planning tax
and does not execute product work. See the upstream
[Wayfinder documentation](https://github.com/mattpocock/skills/blob/main/docs/engineering/wayfinder.md)
(MIT).

---

## User Stories

### US1: Review without backlog amplification [P1]

**As a** wave orchestrator,
**I want** reviewers to record residual findings without immediately filing
issues,
**So that** review remains complete without creating work faster than a wave
closes it.

**Acceptance Criteria:**
- [ ] Every review residual is recorded in a structured candidate ledger.
- [ ] Review and worker sessions cannot create ordinary residual issues during
      an active wave.
- [ ] Acceptance-criteria failures and regressions introduced by the active PR
      are fixed in that PR, not deferred.
- [ ] Follow-up issues are created only by a single post-wave promotion pass
      after final-tree revalidation, deduplication, evidence review, and human
      approval.
- [ ] The wave summary reports seed count, recorded candidates, promoted
      candidates, and amplification ratio.

**Test Scenarios:**
1. Given a reviewer finds a current-PR regression, when it classifies the
   finding, then the ledger marks it `fix-current-pr` and the issue promotion
   path rejects it.
2. Given a serious pre-existing defect with reproducible evidence, when the wave
   closes, then a human may promote one deduplicated candidate after it is
   revalidated against the final tree.
3. Given a speculative improvement or a generation-2 residual, when promotion
   runs, then it remains ledger-only unless the emergency exception and explicit
   human approval both apply.

---

### US2: Trustworthy native skill discovery [P1]

**As a** CPP maintainer or installer,
**I want** every supported agent to discover the same valid skill surface,
**So that** installed behavior does not depend on stale mirrors, legacy flat
files, or broken references.

**Acceptance Criteria:**
- [ ] Claude-native skills use directory-based `SKILL.md` structure with concise
      activation metadata and progressively disclosed reference material.
- [ ] A repository check validates skill metadata, relative references, source
      parity, and installed-surface parity without mutating user-authored skills.
- [ ] Stale `.agents/skills` mirrors and retired wrappers are either removed or
      reported with an actionable owner/source-of-truth message.
- [ ] `make skills-check` fails deterministically for a broken reference,
      duplicate surface, or managed install drift.

---

### US3: Deterministic project initialization [P1]

**As a** developer starting or resuming a project,
**I want** `project:init` to produce predictable, testable output,
**So that** orchestration prose cannot silently generate malformed repositories.

**Acceptance Criteria:**
- [ ] Existing Python, Node, Go, and Rust scaffold behavior is characterized by
      tests before it is refactored.
- [ ] File generation, template rendering, checkpoint state, dry-run, and resume
      behavior live behind a deterministic Python interface.
- [ ] Generated files contain resolved values rather than literal shell variable
      placeholders.
- [ ] New Git repositories consistently use `main` regardless of local Git
      defaults.
- [ ] The command document becomes an orchestration adapter rather than the only
      executable definition of the workflow.

---

### US4: Wayfinder discovery gate [P1]

**As a** developer with a new project idea,
**I want** initialization to distinguish a clear route from multi-session fog,
**So that** simple projects start quickly and ambiguous projects resolve
decisions before committing to a stack.

**Acceptance Criteria:**
- [ ] `project:init` records an agreed destination before framework selection or
      file generation.
- [ ] A clear, single-session effort proceeds directly to scaffolding.
- [ ] A clear, multi-session effort proceeds to the existing spec/task workflow
      without creating a Wayfinder map.
- [ ] An unclear, multi-session effort offers a Wayfinder map and stops before
      production scaffolding; map creation requires explicit user approval.
- [ ] Wayfinder items are decision questions, not implementation slices, and the
      cleared map hands off to a spec rather than code or a pull request.
- [ ] The map preserves destination, decisions so far, not-yet-specified fog,
      out-of-scope items, blocking edges, and the open/unblocked frontier.

**Test Scenarios:**
1. Given a well-scoped CLI, when initialization classifies it as clear and
   single-session, then no map or planning issues are created.
2. Given a large application with settled architecture, when initialization
   classifies it as clear and multi-session, then it creates or links a spec and
   implementation tasks without Wayfinder decision tickets.
3. Given a large idea whose key route decisions are unknown, when the user
   approves Wayfinder, then initialization records the map and exits with a
   resumable `awaiting-decisions` state.

---

### US5: Planning-aware next-action routing [P2]

**As a** developer asking what to do next,
**I want** `project:next` to understand native issue relationships and planning
artifacts,
**So that** it recommends the real frontier and never sends a decision question
to an implementation workflow.

**Acceptance Criteria:**
- [ ] The collector consumes GitHub `blockedBy`, `blocking`, parent, sub-issue,
      and assignee data when available, with explicit uncertainty when not.
- [ ] Wayfinder maps and decision tickets route to planning/resolution actions,
      never `flow:auto`.
- [ ] The authoritative decision engine and contract fixture are available in CI;
      contract tests do not skip because a sibling repository is absent.
- [ ] `project:next` retains brief, compact, and full views. Required evidence is
      preserved in compact output rather than removed to meet an arbitrary line
      target.

---

### US6: Small persistent context, deep on-demand guidance [P2]

**As an** agent working in CPP,
**I want** always-loaded instructions to contain only durable invariants and
routing pointers,
**So that** context is spent on the active problem without weakening necessary
execution guidance.

**Acceptance Criteria:**
- [ ] `CLAUDE.md` contains repository identity, safety constraints, source-of-truth
      pointers, verification commands, and workflow routing—not command histories
      or duplicated manuals.
- [ ] Detailed state machines remain in the skill or reference that owns them.
- [ ] An automated budget and reference check prevents persistent context from
      silently expanding or pointing to missing documentation.
- [ ] No execution skill is shortened solely by line count; reductions require a
      preserved behavioral contract and regression coverage.

---

## Residual Classification and Promotion Policy

| Classification | During the wave | At close |
|----------------|-----------------|----------|
| Current issue acceptance failure | Fix before issue closes | Never promote |
| Defect introduced by active PR | Fix in the same PR | Never promote |
| Serious pre-existing, out-of-scope defect | Record candidate with consequence and evidence | Revalidate, dedupe, then offer for human promotion |
| Security/data-loss/work-blocking emergency | Record and stop unsafe work if needed | Human may explicitly promote despite generation limit |
| Speculative improvement or cleanup | Record as observation | Ledger-only by default |
| Duplicate of existing issue/candidate | Link the canonical record | Never create another issue |

Each candidate MUST contain `candidate_id`, `root_issue`, `source_issue`,
`generation`, `classification`, `consequence`, `evidence`, `disposition`, and
timestamps. Promotion is impossible while the wave is active. Generation 2+
candidates cannot be auto-promoted; in normal operation no candidate is
auto-promoted at any generation.

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A finding changes classification after another PR lands | Revalidate against the final tested tree and update the ledger; do not preserve a stale promotion decision |
| A worker tries to call `gh issue create` for a residual | The wave policy blocks the path and instructs the worker to append a candidate record |
| The same defect is found by several reviewers | Merge evidence into one candidate and retain all source links |
| There are zero seed issues | Do not compute a misleading amplification ratio; report `not-applicable` |
| A candidate has no reproducible evidence | Keep it recorded but ineligible for promotion |
| GitHub native dependency fields are unavailable | Fall back to documented text parsing and mark the inferred edge uncertain |
| Wayfinder's opening check finds no fog | Skip the map and continue to spec or scaffold according to expected session count |
| A Wayfinder item says "build X" | Reject or reclassify it; implementation belongs downstream of the cleared map |
| Initialization is resumed after decisions clear | Collapse linked decisions into the spec, then continue from the saved checkpoint without re-asking settled questions |
| A generated project directory already contains files | Preserve current conflict/resume semantics and make the dry-run disclose every proposed write |
| A detailed skill is long because it encodes recovery states | Move lookup material to references where safe, but retain state transitions and behavioral tests |

---

## Out of Scope

- Replacing CPP's entire issue-driven development model.
- Automatically importing or continuously updating Matt Pocock's full skill set.
- Running Wayfinder for this already-decided CPP improvement effort.
- Allowing Wayfinder to implement production code.
- Filing an issue for every review observation.
- Shortening `project:next` or `flow:wave` by deleting evidence, recovery states,
  or previously proven safeguards.
- Changing model/provider selection or adding a runtime service dependency.
- Retrofitting historical waves or historical issue metrics.

---

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | Persist all wave residuals in a machine-readable candidate ledger | Must | US1 |
| R2 | Enforce the residual classification and promotion state machine in code, not prose alone | Must | US1 |
| R3 | Permit issue creation only in a closed-wave, human-approved promotion transaction | Must | US1 |
| R4 | Report issue-economy metrics in every wave close summary | Must | US1 |
| R5 | Validate canonical skill layout, references, mirrors, and managed install parity | Must | US2 |
| R6 | Convert supported Claude-native skills to directory-based `SKILL.md` packages with progressive disclosure | Must | US2 |
| R7 | Characterize and extract deterministic project generation before changing its user-visible routing | Must | US3 |
| R8 | Support idempotent dry-run and checkpointed resume across Python, Node, Go, and Rust | Must | US3 |
| R9 | Classify discovery by route clarity and expected session count after recording the destination | Must | US4 |
| R10 | Create a Wayfinder map only for unclear multi-session work and only after user approval | Must | US4 |
| R11 | Keep decision tickets distinct from implementation tasks and hand a cleared map to specification | Must | US4 |
| R12 | Consume native issue graph and ownership fields with explicit fallbacks | Should | US5 |
| R13 | Route Wayfinder artifacts to planning actions and make the project-next engine testable in this repository | Must | US5 |
| R14 | Preserve brief, compact, and full `project:next` views under a shared decision contract | Must | US5 |
| R15 | Reduce always-loaded repository guidance while keeping execution detail available on demand | Should | US6 |
| R16 | Run each implementation task through behavioral tests and the standard finish gate | Must | All |

### Non-Functional Requirements

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR1 | Issue economy | Over the first three eligible waves after release, promoted follow-ups / seed issues is <= 0.25; pause and review the policy when a four-seed wave promotes more than one follow-up |
| NFR2 | Review completeness | 100% of declared residuals have a ledger record or a linked canonical duplicate |
| NFR3 | Promotion safety | 0 generation-2+ candidates are promoted without explicit human approval and emergency consequence evidence |
| NFR4 | Determinism | Repeating `project:init --dry-run` with the same inputs produces byte-identical output and no filesystem mutation |
| NFR5 | Context efficiency | `CLAUDE.md` is <= 2,000 words, all references resolve, and detailed command state machines live outside always-loaded context |
| NFR6 | Test reliability | No project-next contract test skips because an optional sibling checkout is missing |
| NFR7 | Compatibility | Existing command names and documented modes remain available unless a task explicitly documents a migration |
| NFR8 | Portability | New executable workflow logic uses Python 3.11+ and passes Linux/macOS-compatible tests without network access |

---

## Success Criteria

- [ ] A behavioral test proves an in-wave reviewer cannot promote a residual issue.
- [ ] A behavioral test proves a current-PR defect is routed back to that PR.
- [ ] Wave summaries distinguish residuals recorded from follow-ups promoted.
- [ ] `make skills-check` detects broken references and managed-surface drift.
- [ ] Characterization fixtures cover all four supported project families plus
      dry-run, resume, placeholder rendering, and default branch behavior.
- [ ] Wayfinder routing tests cover all four clarity/session combinations and
      require approval before tracker mutation.
- [ ] Project-next tests exercise native relationships and planning-only routes
      without a sibling repository.
- [ ] `CLAUDE.md` satisfies its context budget without moving required global
      safety rules out of persistent context.
- [ ] Standard repository verification passes for every implementation PR.
- [ ] Documentation explains when depth is valuable instead of describing all
      verbosity as a defect.

---

## Operating Constraints

- Run at most three seed issues in one implementation wave and at most two
  concurrent workers until issue-economy metrics demonstrate stability.
- Do not create residual issues during worker execution or review.
- Repair active-PR regressions in the active PR.
- Run one promotion pass after the wave reaches a final tested tree.
- Require evidence for promotion; generation 2+ remains ledger-only absent an
  explicit human-approved emergency.
- Report both recorded and promoted counts so apparent review thoroughness is
  not confused with backlog growth.

---

## Open Questions

No blocking product questions remain. Each implementation task may refine file
placement through tests, but it must preserve this routing and issue-economy
contract.

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).*
*Wayfinder concepts adapted from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT License); no upstream skill text is vendored by this specification.*
