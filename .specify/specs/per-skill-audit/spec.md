# Feature Specification: Per-skill audit - CPP usage record and consumer trust boundary

> **Issue:** #1368 (this spec). Implements against it: #1366 (usage-record pilot),
> #1369 (consumer), #1370 (change map), #1371 (enrollment policy). Outcome
> contract: #1367. Programme: skillc #245, workstream skillc #249, waves skillc
> #258 / #259.
> **Created:** 2026-10-04. **Re-pinned:** 2026-10-06 (audit, no content change).
> **FROZEN against skillc #268, 2026-10-06.** skillc #268 merged as
> `cooneycw/skillc` PR #299, commit `f0b9e9e3628b4127df3780ac8efb3fd06459c429`
> (`docs/specs/evaluation-facility/records.md` blob `a0ca00d...`, verified
> **byte-identical** to the provisional pin `fd66c74` this spec was checked
> against before merge - every `[#268]` line citation below stands as-is, no
> re-reading needed). Hand-off:
> [CPP #1368 comment](https://github.com/cooneycw/claude-power-pack/issues/1368#issuecomment-6008422603).
> Two gaps found during the provisional review were **not** addressed by the
> merge and remain open (see Open Questions): the `contradicting` reconciliation
> state is documented as witness-gated but not enforced as such, and no golden
> fixture exists for `unmatched`/duplicate-invocation. R15 stays as written
> regardless of either.
> **Status:** Draft - the rest of the skillc side is pinned to
> `cooneycw/skillc@0375fe8` (origin/main on 2026-10-06; was `8c74a88` on
> 2026-10-04). Every explicit line-number citation into `skillc/records.py`
> and `docs/specs/evaluation-facility/records.md` outside the `[#268]` ones
> was checked against `0375fe8` and is unchanged from the `8c74a88` pin.
>
> Two tickets this spec's dependents will need landed since the `8c74a88` pin,
> not yet reflected in R10-R13 or section E below: skillc **#264** (merged as
> PR #291, `docs/specs/evaluation-facility/protocol.md` section 10 - the three
> workflow-contract lanes and the flow-check obligation matrix) and skillc
> **#265** (merged as PR #292, `docs/specs/evaluation-facility/profiles.md` and
> `skillc/profile.py` - the transitive installation profile, with a worked
> `evals/subjects/cpp-codex-flow-check/` profile that records a per-skill
> `description_digest` / `body_digest`). Neither is #268 and neither changes
> this spec's own requirements, but #1369 (R10, current-content matching) and
> #1370 (the change map) now have real artifacts to cite rather than none.

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
| R7 | **A usage record is never a skillc record kind.** skillc v2 now has EIGHT kinds (`#268`, merged `f0b9e9e`, added `skill-evidence`), each with exactly one authorized producer (`skillc/records.py:92-101`, was `82-90` before `skill-evidence`): `controller`, `assembler`, or `subject-adapter` for the receipt, checked by the controller. A CPP usage record still has no `kind` in that table and is still written inside the subject's environment. skillc states "Records never live in the subject's writable environment" (records.md:810-811, was 559-560 before `skill-evidence` was inserted above it). **`[#268]` answered (`f0b9e9e`, FROZEN):** a usage record enters a bundle only as an ordinary `artifact-manifest.artifacts` entry (path/type/size/digest); `skill-evidence.external_evidence.artifact_ref` then cites that entry's `{path, digest}` (records.md:490-499). Never an `observations` stream, never a bare `raw` pointer, never an observation or a verdict in its own right. |
| R8 | **Local consistency is not provenance.** CPP's reader (`scripts/execution-evidence-verify.py`) checks that a record is internally consistent: it re-derives the verdict from per-check facts, never from `outcome`/`qualifications`. It also checks that the record is bound to the reading checkout's HEAD and tree, and is not renamed or duplicated. A consistent forgery still reads `supported`. This mirrors skillc's own limit, now re-pinned to `f0b9e9e` (main, post-merge; not a `[#268]` field, cited only because `skill-evidence`'s insertion moved it): records.md:716 "cannot catch a forger who writes `assembler`" (was :481 pre-merge), and records.md:866 "Digests are checked for agreement between records, never against the bytes they name" (was :610-611 pre-merge). Provenance requires a controller-owned witness: skillc #269, over the #183 request/reply channel. |
| R9 | **Reconciliation states stay distinct.** A consumer must keep these separate: no usage record; usage record present but not matched to any controller-captured attempt; matched; and matched but contradicting controller state. Absence of a usage record is not evidence of non-use. A usage record is not evidence of use the controller did not observe. **`[#268]` answered (`f0b9e9e`, FROZEN):** `skill-evidence.external_evidence.reconciliation` is exactly these four states - `absent`/`unmatched`/`matched`/`contradicting` (records.md:450-451, :564-574). **Gap found 2026-10-06, relayed to skillc before merge - confirmed NOT addressed by the merge** (orchestrator verified records.md is byte-identical pre/post merge): unlike `execution_observed` (records.md:607-634), which is refused without a cited controller witness record, `contradicting` carries no equivalent enforcement - the `skill-evidence` rule (records.md:845) only requires SOME reason string, from no closed vocabulary, not a witness citation. Stays open (Open Questions, below). See R15. |

### C. The consumer's responsibilities - #1369, #1370, #1371

| ID | Requirement |
|----|-------------|
| R10 | **Current content.** Evidence applies to a CPP revision only when the evaluated skill, references and helper digests match the revision under review, or a DECLARED equivalence rule covers the difference. Anything else is stale or unknown, never inherited (#1367 item 2; #1370 owns the change map from skill sources, mirrors and helpers to task families). |
| R11 | **Complete bundle accounting.** A per-skill verdict counts only when the whole producer bundle accounts for it. skillc's BUNDLE rules (`ledger-binding`, `unique-ids`, `attempt-accounting`, `lineage`) need the ledger and manifest beside the result. `check-behavioral-eval.py` today reads results "alone - NOT against any ledger" and must keep saying so until #1369 reads the bundle (`behavioral-eval-export.md:22-34`). |
| R12 | **Populations stay visibly different.** Fixture-only consumer tests, locally generated CPP usage records and live independently graded trials are three populations. A report may show them side by side, never summed into one rate (#1367 item 3). |
| R13 | **No new blocking policy here.** Enrollment is #1371's decision under #1084's existing constraint (section D). |
| R14 | **The referenced payload is CPP's own to validate - skillc never decodes it.** Added 2026-10-06, naming a duty skillc #268 states as its own boundary rather than ours. Re-pinned (`f0b9e9e`, FROZEN): "a genuinely malformed payload behind a correctly labelled, correctly digested, correctly declared reference is invisible to skillc and must stay the consumer's problem" (records.md:558-563; was the shorter, single-layer version at `2f67f076` line ~508-518, now strengthened to a two-layer check - FORMAT plus a new controller-declared `external_evidence_sources` allowlist, records.md:531-563). skillc's `check-records` validates only the manifest entry's envelope and the `skill-evidence` record's own shape; it never parses the referenced bytes as `cpp.execution-evidence/v1`. So whatever `external_evidence.reconciliation` skillc reports (R9's four states), #1369 must independently run `scripts/execution-evidence-verify.py` (or equivalent, now fixed - cooneycw/claude-power-pack#1373, merged 762945f) against the referenced artifact itself before trusting it - a `matched` reconciliation says the usage record correlates to a controller-captured attempt, never that the usage record's own bytes are well-formed CPP evidence. This duty exists whether or not #1373 was live; it is a boundary R10/R11 did not previously name, not a workaround for that bug. |
| R15 | **An un-witnessed `contradicting` renders as `unknown`, not as a verdict.** Added 2026-10-06, pending skillc's answer to the R9 gap above. Until skillc's `check-records` enforces a witness-record citation on `external_evidence.reconciliation: contradicting` the way it already enforces one on `execution_observed` (records.md:607-634), #1369 must not render an un-witnessed `contradicting` as evidence either way. It renders as `unknown`, carrying the reconciliation's own `reason` string verbatim, rather than trusting an assembler's unenforced claim that something disagreed. This keeps #1369 safe under either outcome of the relayed gap: if skillc adds the enforcement, every `contradicting` #1369 ever sees is witnessed by construction and this rule is a no-op; if skillc does not, #1369 was never trusting an unenforced field. |

### Non-functional

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR1 | Usage-record cost | Bounded file I/O. No model call, no network, no new approval gate for ordinary skill use. |
| NFR2 | Live trials | None authorized by this spec or its tickets: skillc ADR 0005 rule 5 (`docs/decisions/0005-runtime-scope-and-cost-rulings.md:95-102`). |

---

## D. The #1084 enrollment interpretation - now recorded, still not enrolled

**Today.** `make behavioral-eval-check` runs `scripts/check-behavioral-eval.py
--advisory` (Makefile:792-794). The flip to blocking is pre-committed (Makefile
:780-788, ADR 0009): "it becomes blocking when `docs/measurements/behavioral-eval/`
holds at least one artifact recorded by a real behavioural case". #1084's own
constraint is "do not gate on a suite that has not been shown to discriminate".

**The reading question (as of 2026-10-04) is resolved; no artifact exists yet.**
Two readings of "an artifact recorded by a real behavioural case" were both
defensible and disagreed on the first plausible artifact: (1) any real
`verified-result`, even a null comparison (both arms PASS), flips the gate; or
(2) only a result shown to discriminate (a paired degraded/mutated arm failing)
flips it. #1084's own text already decided this without needing inference -
its constraint ("do not gate on a suite that has not been shown to
discriminate") and its 2026-09-28 next-step comment ("Show the normal arm
grading PASS and the degraded arm grading FAIL ... Flip
`behavioral-eval-check` to blocking in the same PR") both read as reading 2.
Reviewed and recorded 2026-10-06
([CPP #1084 comment](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6006863349)):
the flip precondition starts from case discrimination, not a CPP-vs-baseline
effect delta - a **non-discriminating** result (degraded arm also passes, as
skillc #201's live run came back) never flips it, however valid the run.

**Superseded the same day by an owner ruling** ([CPP #1084, 2026-10-06](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6007022667) -
"Require improvement too"): the flip now needs **both** case discrimination
**and** a predeclared CPP-vs-baseline improvement on that same discriminating
case. The reconciliation comment's line that a no-effect result "does not
block the flip" is explicitly overridden - a no-effect result on a
discriminating case is still valid evidence, retained and reported, but it
**never** flips the gate by itself. The improvement criterion itself is not
yet ruled (no threshold, test or minimum sample - #1367 still forbids a
universal pass-rate threshold); it will be a per-study, predeclared criterion
put to the owner before any candidate artifact exists. Until it is ruled, no
artifact can satisfy this half either, independent of #273 below. A valid
null comparison must never be rendered as an invalid bundle just because it
does not justify enrollment.

**What settles "discriminating" is #273, not inference, and it does not exist
yet.** A null-PASS and a discriminating-PASS are indistinguishable from any
v2 record today: the trial-ledger `case` identity is exactly `{id, revision}`
plus `observes_selection` (`skillc/trial.py:76-94`, `records.md:135`), and no
record or bundle rule declares that a case has a degraded or mutation
counterpart
([CPP #1084 comment](https://github.com/cooneycw/claude-power-pack/issues/1084#issuecomment-6006877171);
[skillc #273 comment](https://github.com/cooneycw/skillc/issues/273#issuecomment-6006863590)).
skillc has made this a binding scope note on skillc #273: it must either
represent the arm pairing in a validated, controller-produced record that
refuses an unpaired or mismatched claim, or state that pairing is not
computable and refuse to label any result "discriminating" at all. Neither
disposition exists yet. **Decision (CPP side, recorded so it is not left
implicit): the Makefile's pre-commitment waits for skillc #273 or an
equivalent controller-produced pairing record.** It is not reinterpreted to
mean "any real record". An exported artifact flips the gate only when a
validated producer record certifies the pairing **and** the paired arm graded
FAIL while the normal arm graded PASS - never from file/case naming, two
results sitting in one bundle, or a self-declared field in a subject-writable
record.

**Evidence that would settle discrimination, once #273 exists** (#1371 still
owns the enrollment decision itself). A committed bundle containing: the
controller-produced pairing record from #273 naming a CPP-dependent case and
its degraded/mutated counterpart; that counterpart's `verified-result` grading
FAIL; and the normal arm's `verified-result` grading PASS - all passing
skillc's bundle rules. **That alone is no longer sufficient** - the owner
ruling above adds a second, independent requirement: a predeclared
CPP-vs-baseline improvement criterion on that same discriminating case, not
yet ruled. Until both exist, every artifact, including a fully valid
discriminating one, cannot flip the gate, the gate stays advisory, and no
blocking policy changes in this spec. `docs/measurements/behavioral-eval/`
is a 404 on CPP main as of this writing, so the question is current, not
historical.

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

**Good: real, from this branch.** `docs/measurements/execution-evidence/e5fd38dc103949e2b3f84d7b060862b6.json`
(regenerated by issue #1410 to carry the per-check `carried_from_previous_run`
field below; `cbf9931314ed45d2927fa5e150daa9d2.json` is the pre-#1410
historical sample, retained byte-identical because skillc pins it by name and
sha256):

```json
{"outcome": "completed", "terminal": true,
 "observed": {"tree_at_end": {"head": "b8f783bc...", "dirty": false, "tree_signature": "09bdb65e..."},
   "checks": [
     {"id": "lint", "status": "success", "exit_code": 0, "carried_from_previous_run": false, "population": {"measured": false, "count": null}},
     {"id": "test", "status": "success", "exit_code": 0, "carried_from_previous_run": false, "population": {"kind": "tests", "measured": true, "count": 7515}},
     {"id": "typecheck", "status": "success", "exit_code": 0, "carried_from_previous_run": false, "population": {"measured": true, "count": 364}}]}}
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

- [x] **[#268]** Which field references a CPP usage record, and the
  reconciliation vocabulary: **CLOSED, merged.** Answered by `cooneycw/skillc#299`,
  merged as commit `f0b9e9e3628b4127df3780ac8efb3fd06459c429`
  ([hand-off comment](https://github.com/cooneycw/claude-power-pack/issues/1368#issuecomment-6008422603)).
  `records.md`'s blob is byte-identical between the pre-merge pin (`fd66c74`)
  and the merge commit, so every cited line above stands as frozen. Two
  sub-items from that answer were relayed to skillc as time-sensitive while
  #299 was still open and are **confirmed not addressed by the merge**:
  - [ ] `external_evidence.reconciliation: contradicting` is documented as
    gated on a controller witness (the same way `execution_observed` is,
    records.md:607-634) but no rule enforces it, and the
    `reason` vocabulary (`outcome-disagreement`/`stale-identity`) is not
    closed either. Mitigated on our side by R15 regardless of skillc's
    answer.
  - [ ] No golden fixture exists for `reconciliation: unmatched` with reason
    `duplicate-invocation` or `no-correlating-attempt` (checked directly
    against the six named cases, records.md:582-591). `controls/unique-ids/bad/skill-evidence-duplicate`
    is a different thing (a second `skill-evidence` record for one attempt,
    not a reconciliation state) and does not cover this. Raised originally
    by cpp-w3, still unaddressed.
  - Minor, not blocking: `external_evidence.artifact_ref` is checked for
    existence in the attempt's manifest, not for resolving to exactly one
    entry if two captured artifacts shared a digest.
- [x] **[#1371]** Which enrollment reading (section D) applies: resolved
  2026-10-06, reading 2 (discrimination required). Still open under #1371:
  whether a committed bundle meeting section D's evidence requirement exists
  before enrollment proceeds.
- [ ] **[skillc #273]** Added as a dependency 2026-10-06. Neither disposition
  section D names (a validated pairing record, or an explicit
  "not computable" refusal) exists on skillc yet. #1369 and #1371 cannot
  consume a pairing record, and #1371 cannot enroll a discriminating result,
  until #273 lands one of the two. Re-pin section D's skillc SHA when it does.
- [ ] Whether usage records for skills other than `flow-check` are worth emitting.
  Decide from the pilot's use, not in advance (#1366 "then decide further
  emitters from the pilot").
- [ ] Section F's "Failed" example is labelled **real, from an earlier run on
  the same branch**, unlike the Good example, which names a committed path
  (`docs/measurements/execution-evidence/cbf9931...json`) independently
  verifiable against `scripts/execution-evidence-verify.py`, and unlike the
  Unknown example, which is explicitly labelled **constructed**. No path backs
  the Failed example's "real" claim here. Either link the actual record (if one
  survives in `<git-common-dir>/cpp-evidence/`, outside the tree per R5, or was
  captured before #1372 trimmed retention) or relabel it constructed like
  Unknown - "real" should mean the same thing in both places it is claimed.

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
