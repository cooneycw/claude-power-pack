# Implementation Plan: Balanced Agentic Development

> **Branch:** `spec/balanced-agentic-development`
> **Spec:** [spec.md](./spec.md)
> **Created:** 2026-08-15
> **Status:** Approved

---

## Summary

Implement the approved workflow in six bounded PRs. First put an executable
issue-economy control around `flow:wave`; then repair skill discovery and extract
the deterministic `project:init` engine in parallel. Add the Wayfinder discovery
gate only after initialization is testable, teach `project:next` the resulting
planning graph, and trim always-loaded context last. This order prevents review
from multiplying work while the remaining improvements are underway and avoids
rewriting prose before executable sources of truth exist.

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Runtime | Python 3.11+ | Matches the constitution and supports portable, testable state machines |
| State | Repository-local JSONL/JSON under the existing wave runtime directory; checkpoint JSON for project init | Auditable and deterministic without a service dependency |
| Tracker | GitHub CLI/API with text/local fallback contracts | Reuses current CPP integration while preserving offline tests |
| Skill packaging | Native directory + `SKILL.md`, generated Codex packages, reference files | Aligns discovery surfaces and progressive disclosure |
| Testing | pytest fixtures, CLI integration tests, mutation/negative tests | Proves behavior rather than prompt wording |
| Delivery | One PR per coarse task, dependency ordered | Keeps review scope small without regenerating micro-issues |

---

## Constitution Check

- [x] **P1 Context Efficiency:** Entrypoints route to deep references; required
      recovery/state detail stays on demand.
- [x] **P2 Issue-Driven:** Six coarse implementation tasks are synchronized to
      GitHub after this plan is approved.
- [x] **P3 Spec-First:** This approved spec and plan precede implementation.
- [x] **P4 Test-Driven:** Behavioral scenarios and seams are defined for every
      task.
- [x] **P5 Cross-Platform:** New executable workflow logic is Python 3.11+;
      shell remains only as a compatibility adapter where necessary.
- [x] **P6 Infrastructure Resilience:** Repeated issue amplification, generation
      errors, skipped contracts, and scaffold bugs become explicit validators.

---

## Architecture

### Component Overview

```text
project:init command adapter
        |
        v
destination + route classifier ---> Wayfinder map adapter ---> spec/tasks
        |                                  |
        v                                  v
deterministic scaffold engine        project:next collector/router
        |                                  |
        +------------- tested contracts ---+

flow:wave reviewer ---> residual candidate ledger ---> close-time promotion
                              |                         |
                              +---- metrics + audit ----+

canonical skill sources ---> surface validator ---> Claude/Codex installs
                                      |
                                      v
                            compact CLAUDE.md routing
```

### Key Design Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|--------------------|--------|-----------|
| Residual handling | Immediate issues; ignore extras; candidate ledger | Candidate ledger plus one close-time promotion pass | Preserves observations without treating every observation as authorized backlog |
| Promotion authority | Reviewer; automated severity threshold; human at close | Human approval at closed-wave final tree | Severity labels alone did not stop generational issue growth |
| Review enforcement | Prompt prose; GitHub hook only; executable local state machine | Executable state machine called by workflow adapters, backed by prompt guidance | Testable offline and hard to bypass accidentally |
| Skill migration | Keep flat files; symlink mirrors; canonical package conversion | Canonical native packages and generated installs with parity validation | One source of truth and predictable discovery |
| Project-init refactor | Rewrite command in place; Python engine under thin adapter | Characterization tests, then deterministic engine extraction | Protects current outputs while fixing known heredoc and branch defects |
| Wayfinder trigger | Every init; every large project; unclear multi-session only | Destination first, then clarity x session-count gate | Matches the upstream narrow trigger and avoids planning tax |
| Wayfinder storage | Full history in one prompt; map index plus linked decision records | Low-resolution map with linked decision records and explicit frontier | Supports multi-session work without loading full history every time |
| Project-next engine | Optional sibling checkout; duplicate prompt logic; vendored contract core | Check in or package the authoritative deterministic core and fixture corpus with a drift/update procedure | CI must exercise the decision contract, not skip it |
| Verbosity control | Universal line cap; preserve everything; layered information budget | Compact routing metadata, explicit modes, deep references for execution | Depth is retained where it changes decisions or prevents known failure |

---

## Component Contracts

### Residual candidate ledger

The implementation should expose a small CLI/module (provisional name
`scripts/flow-wave-residuals.py`) with operations equivalent to:

- `record`: validate and append a candidate or canonical-duplicate link.
- `classify`: set the disposition allowed by the policy matrix.
- `list`: return deterministic JSON for summaries and tests.
- `close-wave`: freeze worker/reviewer mutation and enter promotion review.
- `promote`: require closed wave, final-tree evidence, dedup result, eligible
  classification, and explicit human approval before invoking issue creation.
- `summary`: emit seed, recorded, duplicate, promoted, and ratio metrics.

The ledger belongs in the existing wave runtime directory, uses an atomic write
strategy, and records schema version and timestamps. Tests inject a fake issue
creator; they never require network access.

### Skill surface validator

The validator walks canonical Claude and Codex skill packages, parses required
metadata, resolves local references, identifies deprecated flat files and stale
mirrors, and distinguishes managed installed content from user-authored content.
For vendored or adapted content it also validates a provenance record containing
the upstream author, exact source URL, license, pinned revision, and local-change
summary. Provenance class is explicit (`vendored`, `adapted`, `inspired`, or
`cpp-authored`), so shared vocabulary cannot become a false copying claim. The
grill migration must attribute Matt Pocock's MIT-licensed `grill-me` source while
classifying `grill-yourself` as CPP-authored unless history proves otherwise.
`make skills-check` is read-only. Install/repair remains an explicit separate
operation. Migration retains activation summaries under the constitution's
200-character limit and moves long lookup material into `reference.md` only when
the owning workflow can load it on demand.

### Project initialization engine

Extract template rendering and repository mutation behind typed input/output
models. A plan phase returns proposed writes and commands; an apply phase performs
them; checkpoints record completed semantic steps rather than prompt line
numbers. `--dry-run` executes plan only. Resume revalidates the input fingerprint
and current filesystem before continuing. Framework fixtures lock current
supported outputs before refactoring.

### Wayfinder adapter

The adapter first records a human-confirmed destination, then classifies two
axes: route clarity and whether planning exceeds one agent session. It routes:

| Route | Expected sessions | Action |
|-------|-------------------|--------|
| Clear | One | Scaffold |
| Clear | Multiple | Spec and implementation tasks |
| Unclear | One | Focused clarification/grill, then reclassify |
| Unclear | Multiple | Offer Wayfinder map; after approval, chart decisions and stop |

The map is an index with destination, one-line decisions, fog, out of scope, and
links. Questions live in decision records with blocking edges and one of
`grilling`, `prototype`, `research`, or decision-blocking `task`. Production
implementation is prohibited in the map. Tracker mutations are exposed as a
plan first and require confirmation.

### Project-next planning contract

Extend collection to native issue graph and ownership fields, preserving the
existing documented text grammar as fallback. Normalize both sources into one
tested model with provenance and uncertainty. Planning artifacts produce actions
such as `resolve decision`, `clarify destination`, or `collapse cleared map to
spec`; implementation artifacts retain current flow actions. Brief, compact, and
full renderers consume the same decision result.

### Persistent context budget

Reduce `CLAUDE.md` only after canonical code and reference locations exist.
Retain global safety, repository topology, source-of-truth pointers, quality
commands, and the smallest routing table. Move detailed histories, examples, and
state-machine instructions to owned references. Add a word-budget and broken-link
test; do not treat the word target as permission to delete required invariants.

---

## Dependencies

### External Dependencies

No new runtime packages or services are planned. GitHub interaction continues
through the existing `gh` integration. Wayfinder concepts are adapted from the
MIT-licensed `mattpocock/skills` project with attribution; the upstream skill is
not copied or fetched at runtime.

### Internal Dependencies

| Module or surface | Purpose |
|-------------------|---------|
| `.claude/commands/flow/wave.md` and `register.md` | Wave orchestration and reviewer policy adapters |
| `scripts/flow-wave-lexicon.sh` and wave runtime helpers | Existing state/ledger validation seams |
| `.claude/skills/`, `codex/skills/`, `scripts/codex-skill-sync.py` | Canonical and generated skill surfaces |
| `.claude/commands/project/init.md` | Current scaffold behavior and future thin adapter |
| `.claude/commands/project/next.md`, `docs/project-next-contract.md` | Current planning/implementation routing contract |
| `tests/test_project_next_contract.py` | Existing optional-engine contract test to make authoritative |
| `scripts/eli5-vendor.py` and drift tests | Pattern for checked-in external deterministic core/fixture updates |
| `CLAUDE.md` | Always-loaded repository context to trim last |

---

## Expected File Structure

Exact names may be refined in each issue, but ownership should converge on:

```text
scripts/
├── flow-wave-residuals.py
├── skill-surface-check.py
├── project-init.py
└── project-next.py                 # or packaged equivalent
templates/project-init/
├── python/
├── node/
├── go/
└── rust/
tests/
├── test_flow_wave_residuals.py
├── test_skill_surface_check.py
├── test_project_init.py
├── test_project_wayfinder.py
└── test_project_next_contract.py
.claude/skills/<skill>/
├── SKILL.md
└── reference.md                    # only when depth is required
.claude/commands/project/
├── init.md
└── next.md
```

---

## Implementation Phases

### Phase 1: Control backlog growth

| Task ID | Description | Primary files | Dependencies |
|---------|-------------|---------------|--------------|
| T001 | Implement the residual candidate ledger, close-time promotion gate, metrics, and behavioral wave tests | `scripts/flow-wave-residuals.py`, wave command/reference mirrors, `tests/` | - |

This PR lands first. It is the control plane for all later review work.

### Phase 2: Establish deterministic foundations

| Task ID | Description | Primary files | Dependencies |
|---------|-------------|---------------|--------------|
| T002 | Canonicalize native skill packages and add read-only source/reference/install parity validation | `.claude/skills/`, `codex/skills/`, `scripts/`, `Makefile`, `tests/` | T001 |
| T003 | Characterize and extract deterministic project initialization with dry-run/resume support and known scaffold fixes | `.claude/commands/project/init.md`, `scripts/project-init.py`, templates, `tests/` | T001 |

T002 and T003 may run in parallel with at most two workers.

### Phase 3: Integrate discovery and routing

| Task ID | Description | Primary files | Dependencies |
|---------|-------------|---------------|--------------|
| T004 | Add destination-first Wayfinder classification, approved map creation, decision frontier, and resumable handoff to spec | project init adapter/engine, project command/skill references, `tests/` | T003 |
| T005 | Consume native issue relationships, route planning artifacts safely, and make the authoritative project-next engine/fixtures available in CI | project-next engine/contract/docs/tests | T004 |

These land sequentially because T005 consumes T004's artifact contract.

### Phase 4: Reduce persistent context

| Task ID | Description | Primary files | Dependencies |
|---------|-------------|---------------|--------------|
| T006 | Trim `CLAUDE.md` to durable invariants and routing pointers, with budget/reference/behavior checks | `CLAUDE.md`, owned references, `tests/` | T002, T003, T004, T005 |

Trimming last ensures every removed detail already has a tested owner.

---

## Delivery and Wave Policy

- One GitHub issue and one focused PR per task.
- T001 lands alone.
- T002 and T003 form a two-worker wave after T001.
- T004 and T005 are sequential; T006 is final.
- At most three seed issues and two workers in any wave.
- Worker/reviewer residuals go to the candidate ledger. They do not create
  implementation issues during the wave.
- Active-PR defects are repaired before merge.
- After the final tested tree, run one candidate promotion pass and report the
  recorded/promoted ratio.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| The promotion gate suppresses real defects | Medium | High | Record every finding, preserve evidence, support human close-time promotion, measure both recorded and promoted |
| Prose adapters bypass executable policy | Medium | High | Give all adapters one CLI/module and test forbidden state transitions |
| Skill migration breaks discovery for one agent | Medium | High | Inventory before mutation, parity fixtures, managed-only install repair, rollback mapping |
| Project-init refactor changes generated files | Medium | High | Characterization fixtures first, byte-level plan snapshots, separate refactor from Wayfinder behavior |
| Wayfinder becomes a default bureaucracy | Medium | High | Narrow two-axis trigger, opening no-fog escape, explicit approval before map creation |
| Decision tickets drift into implementation tasks | High | Medium | Enforce question-form/type contract and route them away from `flow:auto` |
| Native GitHub fields vary by API availability | Medium | Medium | Normalize provenance, retain text fallback, expose uncertainty |
| Vendored project-next core drifts | Medium | Medium | Manifest/upstream version, deterministic update command, drift test patterned after ELI5 |
| CLAUDE.md trimming removes a safety invariant | Low | High | Inventory retained invariants, link checks, workflow regression tests, final task only |
| Metrics are gamed by not declaring residuals | Medium | High | Reviewer completion requires ledger record or canonical duplicate; report review completeness separately |

---

## Testing Strategy

### Unit Tests

- Residual schema, classification transitions, generation rules,
  deduplication, approval, ratios, and atomic persistence.
- Skill metadata length, required fields, link resolution, duplicate ownership,
  managed marker behavior, stale mirror detection, missing vendored provenance,
  and false vendored attribution.
- Project input validation, template rendering, plan hashing, checkpoint resume,
  and default branch selection.
- Route classifier truth table and Wayfinder ticket/map invariants.
- Native/text issue normalization, uncertainty, action routing, and renderer
  equivalence.
- Persistent-context budget and reference resolution.

### Integration Tests

- Run a simulated wave from residual declaration through closed-wave promotion
  using a fake issue creator; assert no call occurs earlier.
- Compare current and extracted scaffold fixtures for Python, Node, Go, and Rust;
  verify dry-run leaves an empty target unchanged.
- Simulate a foggy initialization, approval, decision resolution, map clear, spec
  handoff, and resume.
- Exercise `project:next` against fixture graphs containing native blockers,
  parents/sub-issues, assignments, Wayfinder maps, and implementation issues.
- Run `make skills-check`, Codex generated-surface checks, and standard `make
  verify` from a clean checkout.

### Mutation and Negative Tests

- Remove a residual consequence/evidence field and assert promotion fails.
- Attempt promotion while the wave is active and assert the issue creator is not
  called.
- Break one skill reference or add a stale managed install file and assert the
  check fails without deleting user content.
- Restore the quoted-heredoc and implicit-default-branch bugs in fixtures and
  assert tests fail.
- Route a `wayfinder:grilling` item to `flow:auto` and assert the contract fails.
- Remove the bundled project-next core/fixtures and assert CI fails rather than
  skips.

### Manual Verification

- Review the first real wave summary for understandable recorded/promoted
  metrics and conduct the explicit promotion confirmation.
- Exercise one small-clear and one large-foggy `project:init` flow in Claude Code
  and Codex installs.
- Read the compact `project:next` output to confirm it remains decision-complete,
  then compare `--brief` and `--full` views.
- Review the final `CLAUDE.md` as a cold-start agent navigation document.

---

## Rollout and Measurement

1. Land T001 and use it for all subsequent waves.
2. Capture baseline and per-wave counts in close summaries: seeds, residuals
   recorded, duplicates, promoted issues, amplification, and promotion rate.
3. If a four-seed wave promotes more than one issue, pause new waves and inspect
   classification/evidence quality before changing thresholds.
4. After three eligible waves, review whether amplification is <= 0.25 and
   whether any undeclared defects escaped. Tune the policy from evidence rather
   than prompt length.
5. Keep each compatibility migration reversible until its installed-surface and
   behavioral tests pass in a clean environment.

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).*
