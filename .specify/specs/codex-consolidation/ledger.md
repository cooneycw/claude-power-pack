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

## A. Owner decisions - PENDING

These are the choices #1068 deliberately did **not** make (spec US6, Open
Questions Q1-Q6). Each blocks the child named. An implementer who resolves one of
these on their own authority has violated spec **B4**/**B5**.

| ID | Decision | Options and consequence | Blocks |
|---|---|---|---|
| **Q1** | Native-wave disposition | (a) **move** to CPP - CPP inherits 14 modules and 5 open stories it has no analogue for; (b) **`transfer` to Kyle** - Kyle's scope is unconfirmed (see inventory §9), so this may transfer to a consumer that has not agreed. `transfer` requires cited acceptance by that owner, which does not exist at baseline; (c) **owner-approved-retirement** - loses the transport proof and 4 contract documents. Note: whichever is chosen, cxpp#201/#202/#203/#206/#208 remain OPEN unless fulfilled or withdrawn with recorded authority | #1072 |
| **Q2** | SAST continuity | (a) **move** CxPP's SAST now - duplicates work cpp#962 owns; (b) **lapse pending cpp#962** - a measurable reduction in protection for the interval, which #1067 explicitly warns against ("the migration must not silently lose CxPP's SAST protection"). Lapsing needs a ruling *because* it is a reduction | #1070 |
| **Q3** | PR cxpp#239 | (a) **merge** before freeze; (b) **migrate** the docs content to CPP; (c) **close** with content preserved elsewhere. Option (c) requires the durable destination, not the intention. Spec **B6** forbids losing it | #1076 |
| **Q4** | Balanced-delivery program overlap | CPP has `.specify/specs/balanced-agentic-development` (Approved). Is cxpp#219/#220/#223/#224/#225/#226 (a) **already-covered** by it, or (b) carrying obligations CPP's spec does not? A wrong (a) silently drops six issues | #1072 |
| **Q5** | CxPP-only instruments | `harness_lint`, `skill_contract_lint`, `skill_eval`, `release_validate` have no CPP analogue. (a) **adapt** into CPP; (b) **owner-approved-retirement**. See inventory §5: the asymmetry runs both ways | #1071 |
| **Q6** | Native vs generated skill model | Does the Codex adapter keep CxPP's 85 **native** skills as native, or converge on CPP's generated-surface model (75)? This is the central compatibility choice; it determines whether an installed Codex host sees a changed skill surface | #1071 |

---

## B. Open CxPP issues (40 of 40)

Every open CxPP issue at baseline appears exactly once. `status` is delivery
status at baseline, not a judgement of worth.

### B.1 Native Codex platform delivery (10)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#189 - Native Codex platform delivery (epic) | unfinished; foundations only (inventory §8) | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#192 - Wave 3: ship native flow-register/flow-wave | unfinished | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#193 - Wave 4: integrate native formations into Kyle | unfinished; Kyle scope unconfirmed | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#194 - Wave 5: spec-to-platform scaffolding | unfinished | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#201 - Bind wave planning, judged gates, worker lifecycle, exact-head CI | unfinished | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#202 - Package flow-register/flow-wave with installed deps | unfinished | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#203 - Validate a complete wave with three Codex workers | **never demonstrated** - the evidence #1067 warns not to assume | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#206 - Native session wake and delivery adapters | unfinished | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#208 - Local Kylex delivery with reproducible evidence | unfinished | unassigned | pending Q1 | `unresolved` - blocks #1072 |
| cxpp#229 - Harden native wave delivery, listening, worker recovery | unfinished | unassigned | pending Q1 | `unresolved` - blocks #1072 |

### B.2 Balanced delivery program (6)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#219 - Wave 2: preserve context, evidence-based plan revision | unfinished | unassigned | pending Q4 | `unresolved` - blocks #1072 |
| cxpp#220 - Wave 3: verify outcomes, demonstrate implementation freedom | unfinished | unassigned | pending Q4 | `unresolved` - blocks #1072 |
| cxpp#223 - Preserve governing outcomes across handoffs | unfinished | unassigned | CPP `docs/agents/issue-contract.md` covers part | `unresolved` - pending Q4 |
| cxpp#224 - Let agents challenge requirements, revise plans | unfinished | unassigned | CPP flow:auto Step 4 (#859) covers part | `unresolved` - pending Q4 |
| cxpp#225 - Account for delivered outcomes in PR evidence | unfinished | unassigned | CPP flow:auto Step 6 (#860) covers part | `unresolved` - pending Q4 |
| cxpp#226 - Prove handoffs and agent freedom with integration coverage | unfinished | unassigned | pending Q4 | `unresolved` - blocks #1072 |

**Why these are not `already-covered` despite the named CPP surfaces.** CPP's
#859/#860 work and `issue-contract.md` address the same *concerns*. Whether they
discharge these specific *obligations* is exactly what Q4 asks, and answering it
by inspection is the failure mode `already-covered` is most prone to. Three rows
name the candidate CPP surface so Q4 can be answered from evidence rather than
from scratch.

### B.3 Nit stores and findings routing (3)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#227 - **Nit Store** (29 comments @ baseline) | active inbox | owner | CPP cpp#864, after triage | `unresolved` - **blocks #1076.** Spec archive criterion: "no unresolved finding is lost". 29 comments must be triaged, not bulk-migrated |
| cxpp#228 - claude-code-review is native so no CPP edit reaches it | open finding | unassigned | #1071 (adapter) | `adapt` - it is the reciprocal-review problem #1071 exists to solve |
| cxpp#248 - No skill routes a finding to the Nit Store (0 of 85) | open defect | unassigned | #1071 | `adapt` - CPP routes via global directive; the Codex surface needs the equivalent |

### B.4 Instruments, gates and verification (13)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#236 - Wayfinder map: CxPP resilience as a derived repo | open | unassigned | superseded in effect by this spec set | `unresolved` - the map's *question* is answered here; whether the issue is discharged is #1075's call |
| cxpp#241 - Promote claude-code-review to a routine counter-model stage | open | unassigned | CPP flow:auto Step 6 counter-model review (#934, ADR 0007) | `already-covered` - CPP runs it by default with a receipt; CxPP's direction (Claude counters Codex) is the mirror of CPP's and needs the #1071 adapter to reach the Codex surface |
| cxpp#242 - Adopt the Oscillation Control (+ derived-repo tells) | open | unassigned | CPP `make oscillation`, `controls/check-oscillation` | `already-covered` for the control itself; the two derived-repo tells (native vs generated) are **`unresolved`** and become moot only if Q6 removes the derived surface |
| cxpp#247 - Skipped security gate reports ok, not warn | open defect | unassigned | CPP #1027 shipped per-verdict exit codes (PR #1057, merged 2026-09-19) | `already-covered` - **verify against `5ceb966a`**, not against #1067's `194f7305`, which predates the fix |
| cxpp#249 - No shellcheck: 81 `.sh` unlinted | open defect | unassigned | CPP `make shellcheck`, `controls/shellcheck-gate` | `already-covered` by the gate's existence; CPP #972 records its own 175-finding backlog, so the protection transfers with a known debt |
| cxpp#250 - Mutation-prove the negative-control battery | open | unassigned | CPP #970 (same requirement, ADR 0008 bound) | `already-covered` by CPP #970 remaining open - **the obligation transfers to an open CPP issue, it is not discharged** |
| cxpp#256 - cicd-verify dispatches to nothing (14 sites) | **live defect** | unassigned | #1070 | `adapt` - CPP's `lib/cicd` registers `verify`; the fix arrives with the shared runtime |
| cxpp#257 - make verify exits 0 on a broken pin reproduction | **live defect** | unassigned | #1069/#1073 | `adapt` - a pin-integrity gap; see inventory §3, the pin is stale at baseline |
| cxpp#259 - Four of six verify gates only aimable through an adapter | open defect | unassigned | #1070 | `adapt` |
| cxpp#274 - Secret scan cannot see its own config, or history | **live defect** | unassigned | #1070 | `adapt` - CPP's `controls/secret-scan` is the destination; the two remedies' conflict must be resolved there, not dropped |
| cxpp#275 - Three instruments name a subject they never examined | **live defect** | unassigned | #1070 | `adapt` - directly the stale-pin/wrong-repo family; inventory §3 |
| cxpp#283 - Complete negative-control coverage without overstating it | open | unassigned | CPP `controls/check-negative-controls` + #1036 | `adapt` |
| cxpp#284 - Adopt remaining CPP testing/review contracts | open | unassigned | superseded by this migration | `unresolved` - adopting CPP contracts *into CxPP* is work the consolidation may make unnecessary; #1075 decides |

### B.5 Runner, results and baseline reproducibility (5)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#279 - Invalidate carried CI/CD results on source/plan change | open defect | unassigned | #1070 | `adapt` - CPP has the analogous hazard recorded; the contract must survive the runtime merge |
| cxpp#280 - finish/check must report executed gates and real test evidence | open defect | unassigned | CPP #1027 (shipped, PR #1057) + #1070 | `already-covered` in CPP's gate verdicts; the Codex-side reporting path is `adapt` under #1070 |
| cxpp#281 - Bound runner subprocess trees, retain timeout evidence | open defect | unassigned | #1070 | `adapt` |
| cxpp#282 - Reproducible test baseline across scanner versions | **partially delivered** - fixture-policy slice landed via PR cxpp#287 | unassigned | #1070 | `adapt` - **do not record all of #282 as complete** (#1067 says so explicitly); only the fixture-policy slice landed |
| cxpp#285 - Close the CPP testing-protocol gap | open | unassigned | superseded by this migration | `unresolved` - same shape as cxpp#284; #1075 decides |

### B.6 project-next and evergreen (3)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#276 - project-next recommends continue_work on a CLOSED issue | **live defect** | unassigned | **#1069** | `move` - travels with project-next ownership. CPP #1035 records the same family of defect; reuse both scopes and their tests, do not file duplicates |
| cxpp#230 - Evergreen: revalidate Codex harness, messaging, watcher assumptions | recurring | unassigned | CPP #871 is the analogous evergreen | `adapt` - an evergreen has no completion state; it needs a maintained home or it silently stops running |
| cxpp#277 - Three unhomed 2026-09-12 findings (needs re-verification first) | open, unverified | unassigned | pending re-verification | `unresolved` - **the findings are unverified at baseline.** Migrating an unverified finding as though it were verified is the error this row exists to prevent |

### B.7 Open pull request (1)

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| **PR cxpp#239** - docs: mirror the 2026-09-14 research set under `docs/research/` (open, @cooneycw, 2026-09-14) | open, unmerged user work | owner | pending Q3 | `unresolved` - **blocks #1076.** Spec **B6** requires user work be preserved; an archive with this PR unresolved destroys it |

---

## C. Relevant CPP issues

These are **not** migration entries; they are evidence dependencies. Each is an
existing CPP obligation the migration must not silently absorb or discharge.

| CPP issue | Relevance | Treatment |
|---|---|---|
| cpp#864 - **Nit Store** (165 comments @ baseline) | Destination for cxpp#227's findings | Triage both before archive (spec archive criteria). Do not bulk-append |
| cpp#962 - No Python SAST (bandit) | Owns SAST adoption | Q2 depends on it. Migration must not lose CxPP's SAST protection meanwhile |
| cpp#970 - Inspection cannot distinguish load-bearing from decorative control | Receives cxpp#250's obligation | Stays open; receiving an obligation is not discharging one |
| cpp#972 - shellcheck: 175 sub-error findings unreviewed | Known debt carried with the shellcheck gate | Disclosed, not hidden, when cxpp#249 is recorded `already-covered` |
| cpp#1028 - Four checkers with no path to a verdict | Includes `codex-skills-check` and the eli5 drift check on the Codex surface | Directly affects #1071/#1073 |
| cpp#1029 - The executed copy cannot say what it holds | Stale checkout / wrong-tree drift checks | Same family as cxpp#275 |
| cpp#1030 - flow:auto Step 6 review blind to new files; no nit-store routing | Affects the counter-model stage this very run uses | Same family as cxpp#228/#248 |
| cpp#1034 - Skill surface has no working validation | Bears on Q6 (native vs generated) | #1071 evidence dependency |
| cpp#1035 - project:next ranks an inbox as top startable issue | Same defect family as cxpp#276 | Reuse scope and tests under #1069; do not duplicate |
| cpp#1036 - check-negative-controls: N of M is not a fraction | Bears on cxpp#283 | #1070/#1071 evidence dependency |
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
| `lib/project_next` | CxPP `lib/project_next` + CPP `vendor/project_next/**` | CPP canonical | `move` - #1069. **Hard prerequisite for archival** (inventory §3) |
| `vendor/claude-power-pack/` pull bridge (PIN, adoption-policy, overlays, sha256) | CxPP | retired when CxPP retires | `unresolved` - the *overlays* encode CxPP-local adaptations. Retiring the bridge without re-homing them loses them silently. Blocks #1073 |
| `lib/skill_eval` + `make skill-eval-check`/`skill-eval-live` | CxPP | pending Q5 | `unresolved` - blocks #1071 |
| `scripts/harness_lint.py` + allowlist | CxPP | pending Q5 | `unresolved` - blocks #1071 |
| `scripts/skill_contract_lint.py`, `skill_contract_baseline.py` | CxPP | pending Q5 | `unresolved` - blocks #1071 |
| `scripts/release_validate.py` + `make release-validate` | CxPP | pending Q5 | `unresolved` - blocks #1071; bears directly on #1074's release proof |
| `scripts/cxpp-hook-transition.py` | CxPP | #1073 | `adapt` - spec **B2**: the safe-hook-update capability, not an implementation detail |
| `~/.codex/scripts/` installed helper resolution | CxPP | #1073 | `adapt` - CPP's three-tier fallback is a *different* contract (inventory §4) |
| `lib/friction` (library) | CxPP | CPP `friction-log.sh` + `.claude/friction.jsonl` | `adapt` - different shapes; the Codex hook lane needs a writer |
| `.codex/hooks.json` (5 events) | CxPP | #1073 | `adapt` under spec **B2** |
| `extensions/cxpp-issue-sync` | CxPP | none identified | `unresolved` - no destination named. Blocks #1076 |
| `extras/sequential-thinking` | CxPP | none identified | `unresolved` - no destination named. Blocks #1076 |
| `templates/project-next.schema.json`, `templates/*` | CxPP | CPP with #1069 | `move` - consumer-facing contract; relocating changes what downstreams resolve |
| 6 native-wave contract documents | CxPP `docs/` | pending Q1 | `unresolved` - blocks #1072 |
| `docs/release-process.md` | CxPP | #1074 | `adapt` |
| Plugin-marketplace e2e records (6 docs) | CxPP `docs/` | #1074 evidence | `adapt` - prior evidence of the behaviour #1074 must re-demonstrate |
| **Unknown installed Codex hosts** | inventory §9 | unenumerable | `unresolved` - **blocks #1076.** Cannot satisfy "every known active consumer is migrated or explicitly retired" while the population is unknown |
| **Unknown plugin-marketplace installs** | inventory §9 | unenumerable | `unresolved` - blocks #1076 |
| **Unknown template adopters** | inventory §9 | unenumerable | `unresolved` - blocks #1076 |

---

## E. Accounting summary @ baseline

| | Count |
|---|---|
| Open CxPP issues accounted | **40 / 40** |
| Open CxPP PRs accounted | **1 / 1** |
| Relevant CPP issues recorded | 14 |
| Capabilities with no issue | 19 |
| Owner decisions pending | 6 |
| Rows `unresolved` | 32 |
| Rows blocking #1076 (archive) | 7 |

**32 unresolved rows is the deliverable, not a shortfall.** #1068's job was to
find out what is undecided, and a ledger reporting few unresolved rows this early
would mean an implementer had been deciding things. Each unresolved row names the
child it blocks; none of them may be cleared by an implementer's judgement (spec
**US6**, **B7**).

**Three of the seven archive blockers are `unknown` consumer populations.** They
cannot be closed by analysis of these two repositories - only by enumeration on
hosts. #1076 should plan for that measurement rather than discovering it late.
