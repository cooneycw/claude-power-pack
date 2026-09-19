# Implementation Plan: Codex Consolidation

> **Governing spec:** [spec.md](spec.md). This plan sequences the work; it does
> not restate the contract or add constraints of its own.
> **Established by:** #1068 | **Epic:** #1067
> **Baseline:** CPP `5ceb966a`, CxPP `681ea26b`, 2026-09-19

---

## Phases

### Phase 0 - Decision gate (#1068) - THIS ISSUE

Produce the spec set. Documentation and inventory only: no installs, no runtime
moves, no issue closures or transfers, no archival.

**Exit:** spec, inventory, ledger, plan and review exist; the ledger accounts for
40/40 open CxPP issues and 1/1 open PR under a machine-checked control; owner
decisions Q1-Q6 are surfaced as pending, not resolved.

### Phase 1 - Ownership and runtime (#1069, #1070)

Disjoint file sets; may run in parallel after Phase 0.

- **#1069** transfers canonical ownership of `project_next` to CPP. **Blocked on
  owner decision Q8** (does the code travel with its git history?) - the answer
  changes the mechanism, not just the paperwork, and deciding it after the move
  means having decided it by accident. This is the
  hard prerequisite for archival (spec, "The bidirectional vendor dependency"):
  until it lands, archiving CxPP strands `lib/vendor.py`. Carries `templates/`
  and `project-next.schema.json`, which are consumer-facing contracts.
  Reuses cpp#1035 and cxpp#276 - the same defect family - rather than filing
  duplicates.
- **#1070** establishes one tested runtime while preserving Codex state and
  security contracts. Blocked on owner decision **Q2** (SAST continuity).
  Receives cxpp#256, #259, #274, #279, #281 and the `adapt` half of #280.

### Phase 2 - Adapter (#1071)

Prerequisite: #1070. Blocked on owner decisions **Q5** and **Q6**.

Preserves native skills and reciprocal review in a thin CPP adapter. **Q6 is the
central compatibility choice of the whole migration**: whether an installed Codex
host keeps the 85 native skills or moves to CPP's generated-surface model. It
determines whether cutover is invisible to a Codex user or is a change they must
be told about.

Receives cxpp#228 and cxpp#248 (nit-store routing on the Codex surface).

### Phase 3 - Native-wave disposition (#1072)

Prerequisite: Phase 0. Blocked on owner decisions **Q1** and **Q4**.

Relocates or retires the native-wave foundations. Spec **US3** binds here: the
`lib/native_wave` modules and the transport proof are FOUNDATIONS, not a working
wave, and cxpp#203 - a complete wave with three independent Codex workers - has
never been demonstrated. Whichever way Q1 goes, cxpp#201/#202/#203/#206/#208
stay OPEN unless fulfilled or withdrawn with recorded authority.

### Phase 4 - Distribution (#1073)

Prerequisites: #1069, #1070, #1071, #1072, **and owner decision Q6 resolved**.
What this phase packages differs entirely depending on whether the Codex surface
stays native or becomes generated, so starting before Q6 means building a
distribution for an undecided surface.

Ships pinned Codex plugins from CPP with safe hook update and rollback. Spec
**B2** is the governing constraint: three of CxPP's five hook handlers resolve to
`~/.codex/scripts/`, so an update that repoints an installed path at different
bytes is a hook-trust change even though no hook definition visibly changed.
`scripts/cxpp-hook-transition.py` is the capability that manages this and must
survive, not be reimplemented from memory.

Also resolves the `vendor/claude-power-pack/overlays/` question: those encode
CxPP-local adaptations, and retiring the bridge without re-homing them loses them
silently (ledger §D).

### Phase 5 - Release proof (#1074)

Prerequisites: Phases 1-4, **and owner decision Q7** (unknown consumer
populations: discover, migrate, or accept-break). Q7 scopes whose behaviour this
phase must prove, so it cannot be answered by the phase that depends on it.

**Q7's discover option needs its measurement planned HERE, not at Phase 7.**
Three archive blockers are unknown consumer populations, and none can be closed
by reading the two repositories - only by enumeration on hosts. Discovering that
at the archive gate is discovering it too late.

Demonstrates every cell of the spec's release matrix from isolated installs. A
cell that was not run is recorded as **not run**, never inferred from a
neighbouring pass. Known-bad inputs must be REJECTED.

The 6 existing plugin-marketplace e2e records in CxPP `docs/` are prior evidence
of the behaviour this phase must re-demonstrate - useful as a starting shape,
never as a substitute for running it.

### Phase 6 - Cutover (#1075)

Prerequisite: #1074. Requires explicit owner approval and a **demonstrated**
rollback path.

Also reconciles the backlog: this is where ledger dispositions become issue state
under the authority this step carries. #1068 closed nothing; #1075 is where
`already-covered` rows may be acted on. **Nit-store triage lands here** - both
stores, 194 comments at baseline - because the archive criteria require it and
no other phase owned it. **Q9 questions this placement**: reconciling after
#1074 has already proved the release means a missed obligation invalidates that
proof. Resequencing is the owner's call, not this plan's.

### Phase 7 - Archive (#1076)

Prerequisite: #1075. Requires final explicit owner approval.

Blocked at baseline by **7 ledger rows**, three of which are unknown consumer
populations that cannot be resolved by reading these two repositories - only by
enumeration on hosts. **Plan for that measurement in Phase 5, not in Phase 7**,
or it will be discovered at the last gate. Also blocked on **Q3** (PR cxpp#239)
and **Q7** (the unknown-consumer disposition).

---

## Serialization

Shared surfaces are edited by one child at a time, and the integrated SHA is
revalidated after each merge:

| Shared surface | Why serialized |
|---|---|
| `Makefile` | Every phase adds or moves targets; concurrent edits conflict silently in the `verify` chain |
| `uv.lock` / `pyproject.toml` | A lock resolved against two different trees is not the tree either child tested |
| `.woodpecker.yml` | Step names and `depends_on` graphs |
| `scripts/codex-skill-sync.py` and the generated `codex/skills/` | Regenerating from a partially-migrated command tree produces a surface neither child intended |
| Installer / bootstrap paths | Spec **B2**; a half-applied installer change is a trust change |

Disjoint implementations may overlap once their prerequisites are met.

---

## What this plan deliberately does not do

- **It does not recreate the CxPP parity backlog before moving.** #1067 says so
  explicitly.
- **It does not wait on all of cpp#1061.** Only the instrument contracts a given
  child actually depends on.
- **It does not cancel urgent safety work on CxPP.** The implementation freeze is
  a recommendation; a safety fix for installations still running CxPP remains
  possible with explicit task authority.
- **It does not resolve Q1-Q6.** Those are the owner's.

---

## Verification

| Claim | Instrument |
|---|---|
| The ledger accounts for every open CxPP obligation | `make consolidation-ledger-check` (`scripts/check-consolidation-ledger.py`), ADR 0008 census row 75 |
| That instrument can fail | `controls/ledger-completeness` - known-bad case + blind anchor, driven by `make negative-fixture-check` and `tests/test_codex_consolidation_ledger.py` |
| The spec set exists and is referenced, not copied | `tests/test_codex_consolidation_ledger.py::test_the_spec_set_is_present`; issue bodies link sections |
| Independent review happened | [review.md](review.md), reviewer identity recorded per finding |

**The first two rows are the pair.** The first alone is a claim about one run;
together they are a claim about the check.
