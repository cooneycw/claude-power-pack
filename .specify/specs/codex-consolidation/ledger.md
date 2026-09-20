# Codex Consolidation: Disposition Ledger

> **Governing spec:** [spec.md](spec.md) - see US2, US3, US6 and boundary **B7**
> (evidence standard). **Inventory:** [inventory.md](inventory.md).
> **Established by:** #1068 | **Epic:** #1067
> **Baseline:** CPP `5ceb966aac96ca4ec1ddafd4cd330b5a174d9a00`,
> CxPP `681ea26b68ff30debdc1efcfa7c57f814f01a0da`, 2026-09-19
> **Completeness is machine-checked:** `controls/ledger-completeness/`,
> `tests/test_codex_consolidation_ledger.py`.

---

## Disposition vocabulary

Exactly six values. Anything else is a defect in this ledger.

| Disposition | Claims | Requires |
|---|---|---|
| `already-covered` | CPP already provides this; nothing needs to move | The CPP surface, named, **and a parity statement** - see below |
| `move` | Relocates to CPP substantially as-is | A destination child |
| `adapt` | Survives, but in a changed shape | A destination child and the shape change |
| `transfer` | Goes to an owner **outside** CPP | A named external destination **and cited acceptance by that owner** |
| `owner-approved-retirement` | Deliberately not carried forward | **A cited owner ruling.** Absent one, the row is `unresolved` |
| `unresolved` | Not yet decided | A stated **blocking effect** |

**`transfer` exists because independent review found the vocabulary had no word
for it** (review finding R4). Q1 offers "transfer native-wave to Kyle" as a live
option, and with only five values that outcome had to be recorded as
`owner-approved-retirement` - which says the capability was dropped when it was
actually rehomed. A vocabulary that misdescribes an outcome produces a ledger
that reads correctly and means something else. It matches
`docs/agents/issue-contract.md`, which already allows transfer to resolve an
issue given recorded authority and a durable destination; the two requirements in
the table are those two, not new ones.

**`already-covered` requires a PARITY statement, not just a pointer.** All three
independent reviewers found the same hole: naming a CPP surface says something
with that name exists, not that it does the same job. A CxPP capability with
richer behaviour, marked `already-covered` against a rudimentary CPP namesake,
is a silent drop that satisfies every check in this document. So the row must say
what was compared - behaviour, security properties, or the operational contract -
and an unexamined dimension is named as unexamined. "Same name" is not parity.

**`unresolved` is the honest default.** It is used wherever no ruling exists, and
it is not a placeholder to be cleared by an implementer's judgement: spec **US6**
and boundary **B7** make an unresolved material entry a block, never permission
to drop the item.

**Rows are accounting, not authority.** A row saying `already-covered` does not
close the CxPP issue - closure follows `docs/agents/issue-contract.md` and
happens in #1075's backlog reconciliation, under the recorded authority that step
carries. #1068 closes nothing.

---

## A. Owner decisions - RESOLVED 2026-09-20

All nine were ruled by the owner on 2026-09-20. The rulings arrived as one
governing principle plus four specific calls, and the principle does most of the
work:

> CxPP should not have any incremental capability not in CPP. Its only
> differences should be the ability of CPP to work more seamlessly when invoked
> by Codex. If there are incremental capabilities, they can be discarded.

Paired with a disposal route that is **not** the one this spec was written
against: **CxPP is not deleted and not archived.** It stops being updated and
installed, its local folders are uninstalled, and the repository goes **private
and dormant**. History, issues, PRs and attribution stay readable at their
source. See "Dormancy exit criteria", which replaces the archive criteria.

| ID | Ruling | Consequence |
|---|---|---|
| **Q1** Native-wave | **`owner-approved-retirement`** - incremental capability with no CPP analogue | cxpp#189/#192/#193/#194/#201/#202/#203/#206/#208/#229 close under this ruling as the recorded authority. The 14 `lib/native_wave` modules, the transport proof and the 6 contract documents stay readable in the dormant repository; nothing is deleted |
| **Q2** SAST continuity | **MOOT - not a choice any more.** CPP adopted bandit on 2026-09-20 (`3d4a9a3`, PR #1118, cpp#962 CLOSED 12:03Z) | `bandit-audit` is in `make verify` with a live positive control (`bandit-audit-selftest`) and an adjudication control (`controls/bandit-audit`). The owner's ruling - "if we have security exposures from anything scaffolded to make the CPP functionality work in Codex, we should SAST review as we would any new scaffolded feature" - is discharged by the existing gate. **Inventory §5 recorded SAST as absent and went stale in 19 hours**; corrected there |
| **Q3** PR cxpp#239 | **Keep the Codex review docs in CxPP.** Merge the PR before dormancy | The three research documents live on a branch today. "Keep them in Codex" is true of `main` only once the PR is merged, so merging is the act that makes the ruling true. Dormancy then preserves them |
| **Q4** Balanced-delivery overlap | **`owner-approved-retirement`** under the governing principle | cxpp#219/#220/#223/#224/#225/#226 close under this ruling. **No parity comparison is required**, because nothing is being claimed as `already-covered`: the obligations are withdrawn, not transferred |
| **Q5** CxPP-only instruments | **`owner-approved-retirement`** - `harness_lint`, `skill_contract_lint`, `skill_eval`, `release_validate` | All four are incremental capability with no CPP analogue (inventory §5) |
| **Q6** Native vs generated skills | **CPP's generated surface.** The 85 native and 74 plugin-packaged skills are not carried | Codex reaches CPP's own surface, generated from `.claude/commands/**` by `scripts/codex-skill-sync.py`. This also moots the two derived-repo tells in cxpp#242 and the native-surface framing of cxpp#228/#248 |
| **Q7** Unknown consumer populations | **accept-break.** The privacy flip executes it | **Ordering constraint, not a caveat:** `scripts/project-next-vendor.py:90-91` hardcodes `api_root=https://api.github.com/repos/cooneycw/codex-power-pack` and `raw_root=https://raw.githubusercontent.com/cooneycw/codex-power-pack`, fetched by `lib/vendor.py` - the shared core, which carries **no auth handling at all** (no `authorization`, `bearer`, `GH_TOKEN` or `GITHUB_TOKEN`; the whole request is `Request(url, headers={"User-Agent": ...})`). So `make project-next-drift` and `make project-next-revendor` break the moment the repository is private, and because the CxPP URL is a hardcoded constant rather than configuration, **nothing degrades gracefully**. **#1069 must land first.** `make verify` is unaffected: `project-next-check` hashes the vendored manifest offline, and `consolidation-ledger-check` reads the committed snapshot and touches the network only under `--refresh` |
| **Q8** Git history | **Fresh copy. No history transfer** | The premise the question was posed under does not hold: history is only lost if the source disappears, and a private dormant repository still serves `git blame` and every provenance link this ledger cites. Exactly one commit (`f39bcf3`, a docs change) has touched `lib/project_next` since CPP's vendored pin `1724e7d9`, so the content transfer is close to a no-op |
| **Q9** Backlog-reconciliation ordering | **Dissolved. No archive gate is needed** | The question existed because a missed obligation surfacing at reconciliation would invalidate a release proof produced for an archive gate. With no archive gate there is no proof for it to invalidate, and reconciliation becomes part of going dormant |

### Q10 - RESOLVED 2026-09-20, by reversing the presumption

Q10 was raised by the Q1-Q9 rulings, not left open by them: the governing
principle disposes of *capabilities*, and eleven rows are defect **findings**.
The owner ruled it the same day:

> just because cxpp has vulnerabilities, we don't import those. and we should
> presume cpp doesn't have those vulnerabilities until proven otherwise.

**All eleven are `owner-approved-retirement`**, citing that ruling.

**What it settles, and why the proposed alternative was worse.** The pass
originally proposed here was "does CPP have the same defect? Yes gives
`already-covered` or a filed CPP issue; No gives retirement." That has a gap: a
row nobody has compared is neither Yes nor No, so **unexamined** became a reason
to hold - and eleven rows would have stayed open indefinitely on the strength of
nobody having looked. The ruling closes the gap toward retirement. Absent proof
CPP has the defect, CPP does not have it.

The three reasons these rows actually gave - the family looks shared, CPP has an
analogous component, nobody has checked - are each **insufficient on their own**
under this ruling. A row escalates only on a demonstrated, reproducible defect in
CPP's own code, and at that point it is a CPP issue on its own merits and the
CxPP row is irrelevant to it.

**What it does not say.** It sets a burden of proof; it does not forbid looking.
Checking a CPP component cheaply and filing only when the check produces a
finding is consistent with it. Forbidden is filing on suspicion, and carrying
rows open on the strength of "unexamined".

**Q10 no longer blocks dormancy.**

**cxpp#276 is untouched and is not one of the eleven.** It stays `move`: the
defective code is what #1069 relocates into CPP, so it arrives as *code* rather
than as an imported finding, and it is owned under #1069.

---

## B. Open CxPP issues (40 of 40)

Every open CxPP issue at baseline appears exactly once. `status` is delivery
status at baseline, not a judgement of worth.

### B.1 Native Codex platform delivery (10)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#189 - Native Codex platform delivery (epic) | unfinished; foundations only (inventory §8) | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#192 - Wave 3: ship native flow-register/flow-wave | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#193 - Wave 4: integrate native formations into Kyle | unfinished; Kyle scope unconfirmed | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#194 - Wave 5: spec-to-platform scaffolding | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#201 - Bind wave planning, judged gates, worker lifecycle, exact-head CI | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#202 - Package flow-register/flow-wave with installed deps | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#203 - Validate a complete wave with three Codex workers | **never demonstrated** - the evidence #1067 warns not to assume | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#206 - Native session wake and delivery adapters | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#208 - Local Kylex delivery with reproducible evidence | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |
| cxpp#229 - Harden native wave delivery, listening, worker recovery | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q1 |

### B.2 Balanced delivery program (6)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#219 - Wave 2: preserve context, evidence-based plan revision | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q4 |
| cxpp#220 - Wave 3: verify outcomes, demonstrate implementation freedom | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q4 |
| cxpp#223 - Preserve governing outcomes across handoffs | unfinished | unassigned | CPP `docs/agents/issue-contract.md` covers part | `owner-approved-retirement` - Q4. The named CPP surface is context, NOT a coverage claim: the obligation is withdrawn, not transferred |
| cxpp#224 - Let agents challenge requirements, revise plans | unfinished | unassigned | CPP flow:auto Step 4 (#859) covers part | `owner-approved-retirement` - Q4. The named CPP surface is context, NOT a coverage claim: the obligation is withdrawn, not transferred |
| cxpp#225 - Account for delivered outcomes in PR evidence | unfinished | unassigned | CPP flow:auto Step 6 (#860) covers part | `owner-approved-retirement` - Q4. The named CPP surface is context, NOT a coverage claim: the obligation is withdrawn, not transferred |
| cxpp#226 - Prove handoffs and agent freedom with integration coverage | unfinished | unassigned | retired with CxPP | `owner-approved-retirement` - Q4 |

**Why these are `owner-approved-retirement` and NOT `already-covered`.** The
distinction survives Q4's answer and matters more because of it. `already-covered`
claims CPP does this job, and owes a parity statement proving it; the owner's
ruling makes no such claim. It withdraws the obligations. Three rows still name a
candidate CPP surface because that context is true and useful, but **naming it is
not a coverage claim** - nobody compared #859/#860 or `issue-contract.md` against
these six, and this ledger must not read as though somebody had.

### B.3 Nit stores and findings routing (3)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#227 - **Nit Store** (29 comments @ baseline) | active inbox | owner | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). **Cost recorded, not hidden:** 29 findings retire unread. They stay readable in the dormant repository; nothing routes them to cpp#864 |
| cxpp#228 - claude-code-review is native so no CPP edit reaches it | open finding | unassigned | #1071 (adapter) | `owner-approved-retirement` - Q6 removes the native surface this defect is about. The reciprocal-review requirement itself carries into the Codex compat layer |
| cxpp#248 - No skill routes a finding to the Nit Store (0 of 85) | open defect | unassigned | #1071 | `owner-approved-retirement` - Q6 retires the 85 native skills the count refers to. **The requirement carries:** CPP's generated Codex surface must route findings to cpp#864 |

### B.4 Instruments, gates and verification (13)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#236 - Wayfinder map: CxPP resilience as a derived repo | open | unassigned | superseded in effect by this spec set | `owner-approved-retirement` - the map's question is answered by this spec set and the 2026-09-20 rulings |
| cxpp#241 - Promote claude-code-review to a routine counter-model stage | open | unassigned | CPP flow:auto Step 6 counter-model review (#934, ADR 0007) | `already-covered` - CPP runs it by default with a receipt; CxPP's direction (Claude counters Codex) is the mirror of CPP's and needs the #1071 adapter to reach the Codex surface |
| cxpp#242 - Adopt the Oscillation Control (+ derived-repo tells) | open | unassigned | CPP `make oscillation`, `controls/check-oscillation` | `already-covered` - parity examined: the oscillation control itself, present in CPP as `make oscillation` + `controls/check-oscillation`. The two derived-repo tells are **moot**: Q6 removed the derived surface they were tells for |
| cxpp#247 - Skipped security gate reports ok, not warn | open defect | unassigned | CPP #1027 shipped per-verdict exit codes (PR #1057, merged 2026-09-19) | `already-covered` - **verify against `5ceb966a`**, not against #1067's `194f7305`, which predates the fix |
| cxpp#249 - No shellcheck: 81 `.sh` unlinted | open defect | unassigned | CPP `make shellcheck`, `controls/shellcheck-gate` | `already-covered` by the gate's existence; CPP #972 records its own 175-finding backlog, so the protection transfers with a known debt |
| cxpp#250 - Mutation-prove the negative-control battery | open | unassigned | CPP #970 (same requirement, ADR 0008 bound) | `already-covered` - cpp#970 **merged 2026-09-20** (`aebb33c`, PR #1128), so the mutation requirement is now delivered rather than pending. Parity examined: the ADR 0008 bound and its mutation requirement; CxPP's own battery is not carried |
| cxpp#256 - cicd-verify dispatches to nothing (14 sites) | **live defect** | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). Unexamined is no longer a reason to hold. CPP's `lib/cicd` registers `verify`; no defect has been demonstrated in it |
| cxpp#257 - make verify exits 0 on a broken pin reproduction | **live defect** | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). CPP runs its own pin gates and none has been shown to exit 0 on a broken reproduction |
| cxpp#259 - Four of six verify gates only aimable through an adapter | open defect | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). No comparison was made and none is owed; CPP's gate-aiming is presumed sound absent a demonstration |
| cxpp#274 - Secret scan cannot see its own config, or history | **live defect** | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). Security-relevant, and retired on the same presumption as the rest: CPP's `controls/secret-scan` has not been shown to share the blind spot. A demonstration would make it a CPP issue on its own merits |
| cxpp#275 - Three instruments name a subject they never examined | **live defect** | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). cpp#1029 is the same family and is **CLOSED** (2026-09-19) - a shared family was never sufficient, and this one is not even live |
| cxpp#283 - Complete negative-control coverage without overstating it | open | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). cpp#1036 is **CLOSED** (2026-09-20); `controls/check-negative-controls` is live and undemonstrated against this defect |
| cxpp#284 - Adopt remaining CPP testing/review contracts | open | unassigned | superseded by this migration | `owner-approved-retirement` - adopting CPP contracts into a dormant repository is work with no consumer |

### B.5 Runner, results and baseline reproducibility (5)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#279 - Invalidate carried CI/CD results on source/plan change | open defect | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). "CPP has an analogous hazard recorded" is one of the three reasons the ruling names as insufficient on its own |
| cxpp#280 - finish/check must report executed gates and real test evidence | open defect | unassigned | CPP #1027 (shipped, PR #1057) + #1070 | `already-covered` - cpp#1027's per-verdict exit codes. Parity examined: executed/skip/unknown reporting. The Codex-side path is retired with Q6, not adapted |
| cxpp#281 - Bound runner subprocess trees, retain timeout evidence | open defect | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). No CPP comparison exists and none is owed |
| cxpp#282 - Reproducible test baseline across scanner versions | **partially delivered** - fixture-policy slice landed via PR cxpp#287 | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). The undelivered remainder is a CxPP gap; CPP's own baseline reproducibility is undemonstrated as defective |
| cxpp#285 - Close the CPP testing-protocol gap | open | unassigned | superseded by this migration | `owner-approved-retirement` - same shape as cxpp#284: a gap in a repository that is going dormant |

### B.6 project-next and evergreen (3)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#276 - project-next recommends continue_work on a CLOSED issue | **live defect** | unassigned | **#1069** | `move` - travels with project-next ownership. CPP #1035 records the same family of defect; reuse both scopes and their tests, do not file duplicates |
| cxpp#230 - Evergreen: revalidate Codex harness, messaging, watcher assumptions | recurring | unassigned | CPP #871 is the analogous evergreen | `already-covered` - cpp#871 is the maintained evergreen. Parity examined: the recurring re-check of harness/messaging assumptions. The Codex-specific half narrows to the compat layer |
| cxpp#277 - Three unhomed 2026-09-12 findings (needs re-verification first) | open, unverified | unassigned | retired with CxPP | `owner-approved-retirement` - **Q10, owner ruling 2026-09-20** (presume CPP does not have CxPP's defect until proven otherwise). Unverified at baseline and unverified now. The ruling resolves the symmetry the row named: an unverified finding is not evidence of a CPP defect |

### B.7 Open pull request (1)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| **PR cxpp#239** - docs: mirror the 2026-09-14 research set under `docs/research/` (open, @cooneycw, 2026-09-14) | open, unmerged user work | owner | CxPP `main` | `move` - **Q3: merge before dormancy.** The docs sit on a branch today, so merging is the act that makes "keep them in Codex" true of `main` |

---

## C. Relevant CPP issues

These are **not** migration entries; they are evidence dependencies. Each is an
existing CPP obligation the migration must not silently absorb or discharge.

| CPP issue | Relevance | Treatment |
|---|---|---|
| cpp#864 - **Nit Store** (165 comments @ baseline) | Destination for cxpp#227's findings | Triage both before archive (spec archive criteria). Do not bulk-append |
| cpp#962 - No Python SAST (bandit) | Owns SAST adoption | Q2 depends on it. Migration must not lose CxPP's SAST protection meanwhile |
| cpp#970 - Inspection cannot distinguish load-bearing from decorative control | **CLOSED 2026-09-20** (`aebb33c`, PR #1128) | Received cxpp#250's obligation and DISCHARGED it. The baseline row said "stays open"; that was true for one day |
| cpp#972 - shellcheck: 175 sub-error findings unreviewed | Known debt carried with the shellcheck gate | Disclosed, not hidden, when cxpp#249 is recorded `already-covered` |
| cpp#1028 - Four checkers with no path to a verdict | Includes `codex-skills-check` and the eli5 drift check on the Codex surface | Directly affects #1071/#1073 |
| cpp#1029 - The executed copy cannot say what it holds | **CLOSED 2026-09-19** | Same family as cxpp#275. A closed counterpart weakens the liveness claim; it does not discharge the variant |
| cpp#1030 - flow:auto Step 6 review blind to new files; no nit-store routing | Affects the counter-model stage this very run uses | Same family as cxpp#228/#248 |
| cpp#1034 - Skill surface has no working validation | Bears on Q6 (native vs generated) | #1071 evidence dependency |
| cpp#1035 - project:next ranks an inbox as top startable issue | Same defect family as cxpp#276 | Reuse scope and tests under #1069; do not duplicate |
| cpp#1036 - check-negative-controls: N of M is not a fraction | **CLOSED 2026-09-20** | Bore on cxpp#283; no longer a live dependency |
| cpp#1047 - Receipt hardcodes `--implementer` | Counter-model receipt integrity | Affects the review evidence this migration produces |
| cpp#1048 - Every receipt records the same reviewer | Counter-model receipt integrity | Same |
| cpp#1054 - delegated-run-check: TOOL_ERRORS never non-zero on the codex lane | Codex lane instrument blindness | #1070/#1071 evidence dependency |
| cpp#1061 - Wave: deepen 74 instruments behind one gate interface | Overlaps the instrument work | **Do not wait on all of #1061** where migration contracts can be met independently (#1067) |

### Rebaseline correction to #1067's reuse table

#1067 lists CPP **#1066** and **#1027** as live reuse targets. Both **closed**
after the epic was written and before this ledger's baseline:

| Issue | State @ `5ceb966a` | Closed by |
|---|---|---|
| cpp#1066 | **CLOSED** | PR #1077, merged 2026-09-19T13:55Z |
| cpp#1027 | **CLOSED** | PR #1057, merged 2026-09-19T13:42Z |

This matters beyond bookkeeping: cxpp#247 and cxpp#280 are recorded
`already-covered` **because of** #1027's per-verdict exit codes. A worker
verifying against #1067's `194f7305` would find that fix absent and conclude the
coverage claim was false.

---

## D. Capabilities with no issue attached

Inventory entries that carry an obligation without an open issue to track it.
Without this section they would fall out of the accounting entirely - they are
exactly the items nobody would notice going missing.

| Capability | Source | Destination | Disposition |
|---|---|---|---|
| `lib/project_next` | CxPP `lib/project_next` + CPP `vendor/project_next/**` | CPP canonical | `move` - #1069, **fresh copy, no history (Q8)**. **Hard prerequisite for the privacy flip, not for archival** (Q7): the vendor fetch is unauthenticated |
| `vendor/claude-power-pack/` pull bridge (PIN, adoption-policy, overlays, sha256) | CxPP | retired with CxPP | `owner-approved-retirement` - the overlays exist to adapt CPP content FOR CxPP. With CxPP dormant they have no subject, so there is nothing to re-home |
| `lib/skill_eval` + `make skill-eval-check`/`skill-eval-live` | retired with CxPP | `owner-approved-retirement` - Q5 |
| `scripts/harness_lint.py` + allowlist | retired with CxPP | `owner-approved-retirement` - Q5 |
| `scripts/skill_contract_lint.py`, `skill_contract_baseline.py` | retired with CxPP | `owner-approved-retirement` - Q5 |
| `scripts/release_validate.py` + `make release-validate` | retired with CxPP | `owner-approved-retirement` - Q5. The release proof it served is retired with the plugin-distribution program |
| `scripts/cxpp-hook-transition.py` | retired with CxPP | `owner-approved-retirement` - **CPP ships no hooks into the Codex namespace.** `make codex-install` writes `~/.codex/skills` only, so there is no installed-hook path to transition. **Spec B2 survives as a constraint**: if CPP ever ships a Codex hook, B2 reactivates and this capability has to be rebuilt, not remembered |
| `~/.codex/scripts/` installed helper resolution | retired with CxPP | `owner-approved-retirement` - CPP's generated skills are self-contained under `~/.codex/skills`; nothing resolves from `~/.codex/scripts/` |
| `lib/friction` (library) | CPP `friction-log.sh` + `.claude/friction.jsonl` | `already-covered` - parity examined: friction capture and its ledger. The Codex hook lane that needed a writer is retired with the hooks |
| `.codex/hooks.json` (5 events) | retired with CxPP | `owner-approved-retirement` - CPP ships no Codex hooks |
| `extensions/cxpp-issue-sync` | retired with CxPP | `owner-approved-retirement` - Q1's principle: incremental capability with no CPP analogue |
| `extras/sequential-thinking` | retired with CxPP | `owner-approved-retirement` - Q1's principle: incremental capability with no CPP analogue |
| `templates/project-next.schema.json`, `templates/*` | CPP with #1069 | `move` - consumer-facing contract. Q7 rules the downstream break accepted; the relocation still has to happen before the privacy flip |
| 6 native-wave contract documents | CxPP `docs/` | retired with CxPP | `owner-approved-retirement` - Q1 |
| `docs/release-process.md` | retired with CxPP | `owner-approved-retirement` - CPP owns its own release process |
| Plugin-marketplace e2e records (6 docs) | retired with CxPP | `owner-approved-retirement` - Q6 retires the plugin-distribution program these records are evidence for |
| **Unknown installed Codex hosts** | unenumerable | `owner-approved-retirement` - **Q7: accept-break.** Chosen, not defaulted into. The privacy flip executes it |
| **Unknown plugin-marketplace installs** | unenumerable | `owner-approved-retirement` - **Q7: accept-break** |
| **Unknown template adopters** | unenumerable | `owner-approved-retirement` - **Q7: accept-break** |

---

## E. Accounting summary @ baseline, and after the 2026-09-20 rulings

| | @ baseline | After rulings |
|---|---:|---:|
| Open CxPP issues accounted | **40 / 40** | **40 / 40** |
| Open CxPP PRs accounted | **1 / 1** | **1 / 1** |
| Relevant CPP issues recorded | 14 | 14 |
| Capabilities with no issue | 19 | 19 |
| Owner decisions pending | 9 | **0** - Q1-Q9 and Q10 all ruled 2026-09-20 |
| Rows `unresolved` | 32 | **0** |
| Rows blocking archive | 7 | **n/a - there is no archive gate** |

**21 rows moved from `unresolved` to a disposition on one ruling.** That is what
a governing principle buys, and it is also the reason to be careful with it: a
sentence that disposes of twenty-one rows at once will dispose of a
twenty-second nobody checked.

**Zero rows remain `unresolved`, and the last eleven closed on a PRESUMPTION -
which a later reader must be able to see, or they will re-open the question.**

Those eleven were defect FINDINGS rather than capabilities, so the governing
principle did not reach them. The owner ruled them separately the same day:
**presume CPP does not have CxPP's vulnerabilities until proven otherwise.** All
eleven are therefore `owner-approved-retirement`.

**This is a burden of proof, not a finding of fact.** Nobody established that
CPP lacks these defects. What was established is who carries the burden: absent
a demonstrated, reproducible defect in CPP's own code, the CxPP row retires. The
eleven titles read like live defects because they *are* live defects - **in
CxPP**, verified OPEN there on 2026-09-20. They say nothing about CPP, and that
is exactly the inference the ruling forbids.

So a later reader finding eleven alarming titles marked retired is not looking
at an oversight. Three specific temptations are already answered: a shared
family is not evidence (cxpp#275's counterpart cpp#1029 is CLOSED); an analogous
CPP component is not evidence (cxpp#279); and nobody having checked is not
evidence (cxpp#259, cxpp#281). If you can demonstrate the defect in CPP's code,
file it as a CPP issue on its own merits - the CxPP row is irrelevant to it and
reopening this ledger is not the route.

**What went the other way.** Two rows improved on evidence rather than on ruling:
cxpp#250 is now `already-covered` because cpp#970 merged on 2026-09-20
(`aebb33c`, PR #1128), and Q2 dissolved entirely because cpp#962 closed the same
morning. Both were written as pending 19 hours earlier.

**Then the same check was run across ALL of section C, and the decay is not two
rows - it is ten of fourteen.** Every CPP issue this ledger leans on was
re-queried on 2026-09-20:

| State @ 2026-09-20 | CPP issues |
|---|---|
| **CLOSED** (10) | cpp#962, #970, #1027, #1028, #1029, #1030, #1034, #1036, #1047, #1048, #1054, #1066 - twelve counting the two the baseline already recorded |
| OPEN (4) | cpp#864, #972, #1035, #1061 |

Section C is headed "existing CPP obligations the migration must not silently
absorb or discharge". Most of them had already been discharged by CPP's own
work, one and two days before anyone read the table. **The eleven CxPP rows in
Q10 were verified OPEN in the same sweep**, so the findings themselves are live;
it is the CPP counterparts they were argued against that moved.

**Two of those stale claims were load-bearing and were asserted by this
document.** The Q10 case originally rested partly on "cxpp#275 has an OPEN CPP
counterpart in cpp#1029" and "cxpp#283 bears on cpp#1036, both live". Both were
false. Q10 survives on the remaining rows, but an argument for keeping eleven
findings alive that cites two closed tickets as evidence of liveness is making
the reader's mistake for them.

**The method, since it is the transferable part.** State was read per issue with
a control on the extraction itself - cpp#962 asserted CLOSED and cpp#864
asserted OPEN before trusting any other answer - because a query that returns
nothing and a query that is broken are indistinguishable, and a sweep reporting
everything OPEN would have looked exactly like the unswept original.

A ledger that is not re-derived against the tree it describes decays this fast.
Re-run this sweep before citing section C, not after.
