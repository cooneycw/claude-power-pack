# Feature Specification: Per-skill audit - CPP usage record and consumer trust boundary

> **Issue:** #1368 (this spec). Implements against it: #1366 (usage-record pilot),
> #1369 (consumer), #1370 (change map), #1371 (enrollment policy). Outcome
> contract: #1367. Programme: skillc #245, workstream skillc #249, waves skillc
> #258 / #259.
> **Created:** 2026-10-04
> **Status:** Draft - the skillc side is pinned to `cooneycw/skillc@8c74a88`
> (origin/main on 2026-10-04). skillc #268, which defines the per-skill
> attribution and export records, was in progress when this was written and has
> NOTHING on skillc main yet. Every skillc-side field below that #268 will own is
> marked **[#268]** and must be re-pinned when #268 lands.

---

## Overview

Two different things will be said about a CPP skill, and they must never be confused:

1. **A CPP usage record** - "the CPP runner, on this machine, at this commit and
   tree, executed these checks with these results". CPP writes it. It is local,
   writable and inspectable. It is NOT a verdict and NOT attestation.
   Delivered for `/flow:check` by #1366 (`lib/cicd/evidence.py`,
   `docs/agents/execution-evidence.md`).
2. **A skillc evaluation verdict** - "in this planned trial, an independently
   assembled result established that these obligations were satisfied, violated
   or unknown". skillc's controller and assembler produce it
   (`docs/specs/evaluation-facility/records.md`, version 2). CPP only consumes it
   (#1369, extending `scripts/check-behavioral-eval.py`).

This spec defines the first precisely. It names the boundary between the two,
and maps every #1366 and #1367 acceptance item to the ticket that owns it. It
does not define skillc's records. Those belong to skillc, and this spec cites
them.

---

## User Stories

### US1: An auditor inspects what /flow:check actually ran [P1]

**As** an auditor or a CI job, **I want** a record of what the helper executed,
bound to the code it ran on, **so that** I can check coverage without replaying
the agent and without trusting the agent's report.

**Acceptance Criteria:**
- [ ] The record's fields, states and identity binding are as in R1-R6. Delivered: #1366.
- [ ] A reader states the exact claim a record supports, or why it supports none. Delivered: #1366.

### US2: skillc observes CPP usage without granting it authority [P1]

**As** skillc's report assembler, **I want** to read a CPP usage record as one
labelled input, **so that** per-skill reports can show it, reconciled against
controller-captured state, without a subject-writable file becoming a trusted
observation.

**Acceptance Criteria:**
- [ ] R7-R9 hold. Mapping into skillc records is owned by skillc #268 / #269.

### US3: CPP CI enrolls only on current, valid producer evidence [P2]

**As** a CPP maintainer, **I want** CI to consume skillc's per-skill export and
treat stale, mismatched or incomplete evidence as unknown, **so that** an old
pack-wide PASS cannot stand in for current per-skill assurance.

**Acceptance Criteria:**
- [ ] R10-R13 hold. Owned by #1369 / #1370 / #1371.

---

## Requirements

### A. The CPP usage record (pilot: `/flow:check`) - #1366

| ID | Requirement |
|----|-------------|
| R1 | **Identity.** Schema `cpp.execution-evidence/v1`, `record_kind: cpp-usage-record`. Each record binds: a fresh `invocation_id` (uuid4 hex); the runner `run_id` (shared by a run and its resumes); the optional `/flow` plan-record run id; `observed.repository` (origin URL with userinfo, query and fragment stripped, git common dir, worktree, branch); `observed.helper` (CPP commit, `cpp_runner_modified`, SHA-256 of the runner modules). |
| R2 | **Dirty-tree binding.** `tree_at_start` and `tree_at_end` each carry HEAD, a `dirty` flag and the #804 content signature (a scratch-index `git write-tree` over tracked plus untracked-not-ignored files, excluding `.claude/runs/`). `dirty` alone is insufficient: one edit and two edits to the same file give the same `git status`. A changed signature between start and end is a qualification. |
| R3 | **Per-check facts.** For each runner step: observed `status` (`success`, `failed`, `skipped`, `subsumed`, `not-run`, `pending`, `running`); `exit_code`, null unless the command ran; `attempted_at` / `completed_at`; `executed_in_this_invocation`, true only for success, failed or subsumed; `carried_from_previous_run`; `population` with `measured` false and count null when the tool stated no number, and a measured 0 kept as 0; `reason` for skip, not-run or subsumed; `evidence` holding output/error SHA-256 and byte counts only. |
| R4 | **States.** Exactly one non-terminal begin record, then at most one terminal record: `completed`, `failed` or `interrupted` (an exception such as SIGINT). A terminal record is never rewritten. A killed process leaves `terminal: false`, which reads as a missing terminal event, never as success. `outcome` is `completed`, `completed-with-qualifications`, `failed`, `stopped` (a failed aggregate left gates `not-run`), `interrupted` or `running`. |
| R5 | **Storage, retention, compatibility.** Written atomically (temp, fsync, rename) to `<git-common-dir>/cpp-evidence/<skill>/<invocation_id>.json`. That is outside the working tree, never committed, and survives worktree removal. The newest 50 per skill are kept. `CPP_EXECUTION_EVIDENCE_EXPORT=<dir>` is the only export path. The opt-in is an environment variable (`CPP_EXECUTION_EVIDENCE=<skill>`), so an older runner ignores it. The runner's stdout JSON is unchanged. A reader refuses an unknown schema as unknown. |
| R6 | **Privacy.** Never stored: raw output or error text, the process environment, or credentials. Origin userinfo is stripped. `declared` (skill, `CPP_SKILL_SOURCE`, `CPP_PARENT_INVOCATION_ID`) is recorded from the environment, never verified, and kept apart from `observed`. |

### B. Provenance versus local consistency - the boundary

| ID | Requirement |
|----|-------------|
| R7 | **A usage record is never a skillc record kind.** skillc v2 has seven kinds, each with exactly one authorized producer (`skillc/records.py:82-90`): `controller`, `assembler`, or `subject-adapter` for the receipt, checked by the controller. A CPP usage record has no `kind` in that table and is written inside the subject's environment. skillc states "Records never live in the subject's writable environment" (records.md:559-560). So a usage record may enter a skillc bundle only as **evidence a controller-produced record refers to** (for example an artifact with a digest in an `artifact-manifest`), never as an observation or a verdict. Which field carries it is **[#268]**. |
| R8 | **Local consistency is not provenance.** CPP's reader (`scripts/execution-evidence-verify.py`) checks that a record is internally consistent: it re-derives the verdict from per-check facts, never from `outcome`/`qualifications`. It also checks that the record is bound to the reading checkout's HEAD and tree, and is not renamed or duplicated. A consistent forgery still reads `supported`. This mirrors skillc's own limit: records.md:481 "cannot catch a forger who writes `assembler`", and records.md:610-611 "Digests are checked for agreement between records, never against the bytes they name". Provenance requires a controller-owned witness: skillc #269, over the #183 request/reply channel. |
| R9 | **Reconciliation states stay distinct.** A consumer must keep these separate: no usage record; usage record present but not matched to any controller-captured attempt; matched; and matched but contradicting controller state. Absence of a usage record is not evidence of non-use. A usage record is not evidence of use the controller did not observe. The deterministic rules for duplicate, stale, missing and unmatched evidence are **[#268]**. |

### C. The consumer's responsibilities - #1369, #1370, #1371

| ID | Requirement |
|----|-------------|
| R10 | **Current content.** Evidence applies to a CPP revision only when the evaluated skill, references and helper digests match the revision under review, or a DECLARED equivalence rule covers the difference. Anything else is stale or unknown, never inherited (#1367 item 2; #1370 owns the change map from skill sources, mirrors and helpers to task families). |
| R11 | **Complete bundle accounting.** A per-skill verdict counts only when the whole producer bundle accounts for it. skillc's BUNDLE rules (`ledger-binding`, `unique-ids`, `attempt-accounting`, `lineage`) need the ledger and manifest beside the result. `check-behavioral-eval.py` today reads results "alone - NOT against any ledger" and must keep saying so until #1369 reads the bundle (`behavioral-eval-export.md:22-34`). |
| R12 | **Populations stay visibly different.** Fixture-only consumer tests, locally generated CPP usage records and live independently graded trials are three populations. A report may show them side by side, never summed into one rate (#1367 item 3). |
| R13 | **No new blocking policy here.** Enrollment is #1371's decision under #1084's existing constraint (section D). |

### Non-functional

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR1 | Usage-record cost | Bounded file I/O. No model call, no network, no new approval gate for ordinary skill use. |
| NFR2 | Live trials | None authorized by this spec or its tickets: skillc ADR 0005 rule 5 (`docs/decisions/0005-runtime-scope-and-cost-rulings.md:95-102`). |

---

## D. The unresolved #1084 enrollment interpretation

**Today.** `make behavioral-eval-check` runs `scripts/check-behavioral-eval.py
--advisory` (Makefile:792-794). The flip to blocking is pre-committed (Makefile
:780-788, ADR 0009): "it becomes blocking when `docs/measurements/behavioral-eval/`
holds at least one artifact recorded by a real behavioural case". #1084's own
constraint is "do not gate on a suite that has not been shown to discriminate".

**What is unresolved.** Both readings of "an artifact recorded by a real behavioural
case" are defensible, and they disagree on the first plausible artifact:

1. **Any real record flips it.** A valid `verified-result` from a real case,
   even a NULL comparison (both arms PASS, as in skillc #26's selection report),
   enrolls the gate.
2. **Only a discriminating record flips it.** The case must also have been shown
   to discriminate: it is paired with a degraded arm or mutation it reports
   failure on (#1084 "Negative control" and skillc #150).

Under reading 1, a null result would make the gate blocking with nothing proven
to discriminate. That collides with #1084's constraint. Under reading 2, the
same null result is still VALID evidence and must be retained and reported. A
valid null comparison must never be rendered as an invalid bundle just because
it does not justify enrollment.

**Evidence that settles it** (#1371 owns the decision). It needs a committed
`verified-result` bundle from a CPP-dependent case with a degraded arm. The bundle
must show the case reporting FAIL on the degraded arm and PASS on the intact arm,
and pass skillc's bundle rules. It also needs a recorded policy line naming which
reading applies, its expiry, and its unknown handling. Until then, reading 2 is
the conservative default. The gate stays advisory and no blocking policy changes
in this spec.

---

## E. Acceptance map - every #1366 and #1367 item to its owner

| Item | Owner | State on 2026-10-04 |
|------|-------|---------------------|
| #1366-1 inventory paths; success/failure/skipped/unavailable/interrupted; storage, retention, atomic, survives cleanup | #1366 | Delivered (PR #1372): R4, R5; execution-evidence.md coverage table |
| #1366-2 bind repo, worktree, HEAD plus dirty/content, run/invocation, parent, skill source/version, helper version; standalone needs no issue | #1366 | Delivered: R1, R2, R6 |
| #1366-3 per-check status, exit, timestamps, population, reasons, digests; no zero-for-unmeasured; no skipped-as-passed | #1366 | Delivered: R3 |
| #1366-4 helper-observed vs agent-declared; local receipt is not attestation | #1366, with the boundary here | Delivered: R6, R8 |
| #1366-5 controls: stale+dirty, replay, missing terminal, stopped aggregate, zero population, unreadable, clean; privacy | #1366 | Delivered: `tests/test_execution_evidence.py`, `controls/execution-evidence-verify` |
| #1366-6 real pilot artifact plus reader example; bounded cost; compatibility | #1366 | Delivered: `docs/measurements/execution-evidence/cbf99313...json` |
| #1366-7 canonical `check.md` plus regenerated mirror | #1366 | Delivered |
| #1366 (added 2026-10-04) link this spec | #1366 | This PR |
| #1367-1 consume the producer-owned export; keep record vs bundle validation distinct | #1369 | Open; needs skillc #268 export |
| #1367-2 match evidence to revision and dependency digests; declared equivalence; state trusted provenance | #1369 (matching), #1370 (change map) | Open: R10, R8 |
| #1367-3 per-skill eligible cases and obligations; populations visibly different | #1369 | Open: R12; skillc #272 assembles the report |
| #1367-4 map skill sources, mirrors, helpers to task families; unmapped means not evaluated | #1370 | Open |
| #1367-5 cheap controls in CI; paid evals behind declared budgets; enrollment record before blocking | #1371 | Open: section D; ADR 0005 |
| #1367-6 certify fresh/stale/mismatched/duplicate/missing/empty/forged/unknown-schema/incomplete/null-result controls | #1369 | Open; skillc's golden fixtures (`controls/<rule>/{bad,good}/`) are the producer half |

---

## F. Example records and their interpretation

These are excerpts of real or constructed `cpp.execution-evidence/v1` records,
checked against `lib/cicd/evidence.py` and `scripts/execution-evidence-verify.py`
at the PR #1372 head.

**Good: real, from this branch.** `docs/measurements/execution-evidence/cbf9931314ed45d2927fa5e150daa9d2.json`:

```json
{"outcome": "completed", "terminal": true,
 "observed": {"tree_at_end": {"head": "bce7c881...", "dirty": false, "tree_signature": "b7ef3f27..."},
   "checks": [
     {"id": "lint", "status": "success", "exit_code": 0, "population": {"measured": false, "count": null}},
     {"id": "test", "status": "success", "exit_code": 0, "population": {"kind": "tests", "measured": true, "count": 7156}},
     {"id": "typecheck", "status": "success", "exit_code": 0, "population": {"measured": true, "count": 355}}]}}
```

Reader: `supported` (with `--no-current`, since HEAD has moved). The claim names
the commit, the tree, each check and its population. It disclaims who invoked the
run, whether the file has been edited since, and any step outside the plan.

**Failed: real, from an earlier run on the same branch.** The test gate failed
and typecheck was never reached:

```json
{"outcome": "failed", "terminal": true,
 "observed": {"checks": [
   {"id": "lint", "status": "success", "exit_code": 0},
   {"id": "test", "status": "failed", "exit_code": 2, "population": {"measured": true, "count": 7155}},
   {"id": "typecheck", "status": "pending", "exit_code": null, "executed_in_this_invocation": false}]}}
```

Reader: `not-supported`, with reasons "outcome is failed", "gate test is failed",
and "gate typecheck is pending". The unreached step carries no exit code and is
not marked executed.

**Unknown: constructed.** A record whose `observed` is not an object, or whose
`tree_at_end` lacks a HEAD and signature:

```json
{"schema": "cpp.execution-evidence/v1", "invocation_id": "...", "terminal": true,
 "outcome": "completed", "declared": {}, "observed": {"tree_at_end": null}}
```

Reader: `unknown`, exit 4, "malformed record". Identity that was never captured
cannot be waived by `--no-current`, and a summary saying `completed` does not
help.

**Interrupted invocation.** An exception reaching the runner (SIGINT) writes a
terminal record with `outcome: interrupted` and `terminal_event.detail` naming the
exception. A SIGKILL or power loss writes nothing more, so the begin record stays
`terminal: false`. Both read `not-supported`; the second is reported as "no
terminal event". Neither is ever evidence that the checks passed or failed.

**Standalone invocation.** `/flow:check` outside a `/flow` run has no issue and no
approved plan. `plan_record_run_id` is null and nothing else changes. The record
is as valid as one made inside a flow, and it claims nothing about any issue.
Inside `/flow:auto`, the plan-record run id links the two, but that is a
declared association, not a proof that the flow's other steps ran.

---

## Out of Scope

- Runtime implementation beyond #1366's pilot; any telemetry service; a live
  study; a new approval gate for ordinary skill use.
- Defining skillc record kinds or fields (skillc #268), the controller witness
  (skillc #269, #183), or report assembly (skillc #272).
- Any change to #1084's advisory/blocking state.

---

## Open Questions

- [ ] **[#268]** Which field of which controller-produced record references a CPP
  usage record (artifact-manifest entry, observation stream, or a new kind), and
  the reconciliation rules for duplicate, stale, missing and unmatched records.
  Re-pin this spec's skillc SHA when #268 lands.
- [ ] **[#1371]** Which enrollment reading (section D) applies, decided on the
  evidence named there.
- [ ] Whether usage records for skills other than `flow-check` are worth emitting.
  Decide from the pilot's use, not in advance (#1366 "then decide further
  emitters from the pilot").

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
