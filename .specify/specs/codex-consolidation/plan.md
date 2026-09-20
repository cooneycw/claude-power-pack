# Implementation Plan: Codex Consolidation

> **Governing spec:** [spec.md](spec.md). This plan sequences the work; it does
> not restate the contract or add constraints of its own.
> **Established by:** #1068 | **Epic:** #1067
> **Baseline:** CPP `5ceb966a`, CxPP `681ea26b`, 2026-09-19
> **Amended:** 2026-09-20 - rewritten against the owner's Q1-Q9 rulings. The
> seven-phase migrate-prove-cutover-archive program is superseded by four
> phases. See [ledger.md](ledger.md) §A.

---

## What changed, and why the plan got smaller

The original plan sequenced a capability migration: move the native wave, build
an adapter that preserves 85 native skills, package and ship pinned Codex
plugins with hook-trust transition, prove a dual-client release matrix, cut
over, then archive.

The owner's 2026-09-20 ruling removed the premise. CPP is the platform; CxPP
carries no capability CPP wants; the only difference worth building is CPP
working seamlessly **when invoked by Codex**. Nothing is migrated, so nothing
needs an adapter to preserve it, a distribution to ship it, or a matrix to
prove it.

**Three phases lost their content entirely** - #1070 (shared runtime), #1072
(native-wave relocation) and #1073 (plugin distribution). They are closed
citing the ruling, not left open looking like planned work. A cancelled phase
that stays open is indistinguishable from a late one.

---

## Phases

### Phase 0 - Decision gate (#1068) - COMPLETE

Produced the spec set and surfaced Q1-Q9. **All nine ruled 2026-09-20**, which
discharges acceptance item 6 and closes this issue. The rulings raised **Q10**,
which blocks Phase 3 rather than reopening this one.

### Phase 1 - project-next ownership (#1069) - THE ORDERING CONSTRAINT

Transfers canonical ownership of `project_next` to CPP as a **fresh copy, no
history** (Q8). Carries `templates/` and `project-next.schema.json`, which are
consumer-facing contracts. Reuses cpp#1035 and cxpp#276 - the same defect
family - rather than filing duplicates. **cxpp#276 cannot be discarded with the
rest of CxPP's defects: the defective code is what this phase moves.**

**This phase gates the privacy flip.** `scripts/project-next-vendor.py:90-91`
hardcodes the CxPP `api_root` and `raw_root`; `lib/vendor.py` fetches them
through plain `urllib.request` and carries no auth handling at all. So
`make project-next-drift` and `make project-next-revendor` break the moment
CxPP goes private, and a hardcoded URL constant does not degrade gracefully. Nothing in
`make verify` is affected: `project-next-check` is an offline manifest hash and
`consolidation-ledger-check` reads the committed snapshot.

Exit: CPP owns the engine, `lib/vendor.py` and the vendor bridge are gone, and
no CPP path resolves to `cooneycw/codex-power-pack`.

### Phase 2 - Codex invocation compat (#1071, rescoped)

**This is the only thing being built.** #1071's original scope - "preserve
native skills and reciprocal review in a thin CPP adapter" - is wrong under Q6
and must be rewritten before work starts.

The deliverable is a **thin, Codex-specific `AGENTS.md`**. CPP has none today.
It defers to `CLAUDE.md` by reference rather than restating it, so the two
cannot disagree and no parity instrument is needed - the structural reason CxPP
required `agents-md-lint` and a skill-trigger parity test, and the reason this
shape does not.

What is genuinely Codex-specific, and therefore all that belongs in it:

- the Codex surface is **generated** - edit `.claude/commands/**` and run
  `make codex-skills`; never edit `codex/skills/` directly. This is the one
  hazard a Codex session cannot infer from the repository.
- skills arrive as named Codex skills, not `/flow:*` slash commands.
- state and credentials live under `~/.codex/`, separate from `~/.claude/`
  (spec **B1** - the namespaces stay isolated).
- Codex's own sandbox and approval model governs execution.

Everything else - every Core Directive, the Makefile contract, the security
rules, the gate chain - resolves through one pointer to `CLAUDE.md`.

Two obligations carry into this phase from retired rows: the Codex surface
must **route findings to cpp#864** (cxpp#248's requirement survives its row's
retirement), and reciprocal review must reach the Codex surface (cxpp#228).

Constraints: cap the file with a budget check in the shape of
`check-claude-md-budget.py`. **Spec B2 is dormant, not gone** - CPP's
`make codex-install` writes `~/.codex/skills` only, so there is no installed
hook path today; if CPP ever ships a Codex hook, B2 reactivates and the
hook-transition capability has to be rebuilt rather than remembered.

### Phase 3 - Clean-install proof (#1074, rescoped)

Prerequisites: Phases 1 and 2. (Q10 was answered on 2026-09-20 and no longer gates this phase.)

The dual-client release matrix is retired with the distribution program. What
remains is one demonstration: **a Codex host, from a clean install, reaching
CPP's surface and running a workflow end to end.** A cell that was not run is
recorded as **not run**, never inferred from a neighbour. Known-bad inputs must
be REJECTED.

Q10 previously sat here because its answer could file CPP issues that a later
proof would have to be weighed against. The owner's 2026-09-20 ruling retired
all eleven rows on a presumption, so nothing is pending and this phase is
gated only by Phases 1 and 2.

### Phase 4 - Dormancy (#1075 + #1076, merged)

Prerequisite: Phase 3. Requires explicit final owner approval.

#1075 and #1076 were separate because cutover-then-archive was two irreversible
steps with a proof between them. Dormancy is one step, so they merge.

1. ~~Answer Q10~~ - **done 2026-09-20.** All eleven findings are
   `owner-approved-retirement` under the owner's presumption that CPP does not
   carry CxPP's vulnerabilities absent proof. Nothing to do here but note that
   cxpp#227's 29 findings retire unread.
2. Merge **PR cxpp#239** (Q3), so "keep the Codex review docs in Codex" is true
   of `main` and not only of a branch.
3. Close CxPP's 40 open issues, **each citing the 2026-09-20 ruling** as its
   recorded authority per `docs/agents/issue-contract.md`. A bulk close with no
   cited authority is the failure this ledger exists to prevent.
4. Publish a dated deprecation notice **before** the privacy flip. Q7 is
   accept-break; a break announced after the repository stops being readable is
   not announced.
5. Uninstall CxPP's host-level artifacts, including `~/.codex/scripts/` (review
   finding **R5**: going private does not unwrite a user's disk, and an
   abandoned trusted path is a hijack target).
6. Flip the repository private. **Irreversible for anyone outside the org.**

---

## Serialization

Far less contention than the original program, because only Phases 1 and 2
touch CPP code and they touch disjoint trees. Two surfaces still need care:

| Shared surface | Why serialized |
|---|---|
| `Makefile` | Phase 1 removes vendor targets, Phase 2 may add a budget target; concurrent edits conflict silently in the `verify` chain |
| `scripts/codex-skill-sync.py` and the generated `codex/skills/` | Phase 2's compat work and any command-tree change regenerate the same surface |

`uv.lock`/`pyproject.toml`, `.woodpecker.yml` and the installer paths are no
longer contended - nothing in the reduced program edits them.

---

## What this plan deliberately does not do

- **It does not delete or archive CxPP.** The repository persists, private and
  dormant. This is what makes Q8's fresh copy safe.
- **It does not discard findings silently.** The governing principle retires
  capabilities; the eleven defect findings were retired by a SEPARATE owner
  ruling, on a stated presumption, recorded in ledger section A under Q10. The
  distinction matters: one is "CPP does not want this", the other is "CPP is
  presumed not to have this". Both are decisions; neither is an omission.
- **It does not wait on all of cpp#1061.** Only the instrument contracts a
  given phase actually depends on.
- **It does not cancel urgent safety work on CxPP.** A safety fix for an
  installation still running CxPP remains possible with explicit task
  authority, up until dormancy.

---

## Verification

| Claim | Instrument |
|---|---|
| The ledger accounts for every open CxPP obligation | `make consolidation-ledger-check` (`scripts/check-consolidation-ledger.py`), enumerated in the ADR 0008 census |
| That instrument can fail | `controls/ledger-completeness` - known-bad case + blind anchor, driven by `make negative-fixture-check` and `tests/test_codex_consolidation_ledger.py` |
| The spec set exists and is referenced, not copied | `tests/test_codex_consolidation_ledger.py::test_the_spec_set_is_present` |
| Every Q1-Q9 ruling is recorded with its consequence | [ledger.md](ledger.md) §A; each row cites the ruling |
| Independent review happened | [review.md](review.md), reviewer identity recorded per finding |

**The first two rows are the pair.** The first alone is a claim about one run;
together they are a claim about the check. Re-proved against the amended ledger
on 2026-09-20: emptying cxpp#189's disposition produces
`LEDGER_MISSING: cxpp#189 ... no disposition` and exit 1, while the real file
exits 0.

**What no instrument here checks.** Nothing verifies that a disposition is
*right* - the gate says so itself ("presence and non-emptiness only"). Q10 is
the standing evidence that a machine-checked ledger can be complete and still
wrong about eleven rows.
