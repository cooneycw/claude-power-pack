# Feature Specification: Codex Consolidation

> **Branch:** `issue-1068-codex-consolidation-establish-the-migration-spec-c`
> **Created:** 2026-09-19
> **Status:** Draft
> **Epic:** #1067 | **Established by:** #1068
> **Companion documents:** [inventory.md](inventory.md) (what exists),
> [ledger.md](ledger.md) (what happens to each thing), [plan.md](plan.md)
> (execution order), [review.md](review.md) (independent review record)

---

## Overview

Claude Power Pack (CPP) and codex-power-pack (CxPP) are two maintained copies of
substantially the same development platform - workflow commands, CI/CD gates,
secrets handling, security scanning, spec-driven development - differing in which
agent harness they target. The owner has decided to keep CPP as the maintained
source with explicit Claude and Codex adapters, and to retire CxPP once Codex
consumers work from CPP.

This specification is the authoritative contract for that migration. It exists
because #1067 is a proposal and says so: it is "the owner's requested migration
plan and implementation backlog, not permission to start implementation." A
proposal cannot govern nine child issues across two repositories, because each
child would otherwise re-derive for itself what the migration must protect - and
anything no child happened to remember would be lost without ever being decided.

**What this document governs.** Children #1068-#1076 reference the sections here
that bind them; they do not copy them (`docs/agents/issue-contract.md`, "How much
document"). Where this spec and an issue body disagree, this spec is the later and
authoritative statement - except where the issue records an owner decision this
spec does not yet reflect, which is a defect in this spec to fix here.

**What this document does NOT do.** It records decisions; it does not make the
ones that are not yet made. Consequential compatibility and retirement choices
that lack an owner ruling appear as `OWNER DECISION - PENDING` rows in
[ledger.md](ledger.md), each naming the options, the consequence of each, and the
child it blocks. A specification that quietly resolved them would manufacture an
authority this work does not hold, and every downstream child would inherit the
ruling as settled fact.

---

## Evidence baseline

Both repositories were re-inspected for #1068. These SHAs supersede the ones
recorded in #1067 and are the baseline every claim in
[inventory.md](inventory.md) and [ledger.md](ledger.md) is made against.

| Repository | #1067 recorded | **Rebaselined (#1068)** | Moved? |
|---|---|---|---|
| claude-power-pack | `194f7305b909eb3186fad79314271dc635480651` | **`5ceb966aac96ca4ec1ddafd4cd330b5a174d9a00`** | Yes - two merges later |
| codex-power-pack | `681ea26b68ff30debdc1efcfa7c57f814f01a0da` | **`681ea26b68ff30debdc1efcfa7c57f814f01a0da`** | No |

Baseline date: **2026-09-19**. Counts at this baseline: 40 open CxPP issues, 1
open CxPP PR (cxpp#239), 34 open CPP issues.

**A baseline is a staleness marker, not a freeze.** Both repositories remain
live. A later reader comparing against these SHAs can tell a changed fact from an
omitted one; without them the two are indistinguishable. Each child that acts on
this spec re-derives the integrated SHA after its own merge (see
[plan.md](plan.md), "Serialization").

---

## User Stories

### US1: Know what would be lost before anything is retired [P1]

**As the** repository owner,
**I want** a single inventory of everything CxPP ships today, re-checked against
both repositories as they actually stand,
**So that** retirement is a sequence of decisions rather than a sequence of
discoveries.

**Acceptance Criteria:**
- [ ] Both main SHAs are rebaselined and recorded (see Evidence baseline).
- [ ] The inventory covers native/shared/generated skills, helper and runtime
      modules, plugin families, invocation policy and evaluation assets,
      hooks/bootstrap/update/status flows, security and test protections,
      credential and state namespaces, docs, installed sources, and known
      downstream consumers.
- [ ] No credential VALUE appears anywhere in this spec set. Namespace paths and
      variable names are inventory; their contents are not.
- [ ] A consumer whose existence is suspected but unconfirmed is recorded as
      **unknown**, never omitted. An empty consumer list and an unexamined one
      must not read alike.

**Test Scenarios:**
1. Given CxPP at `681ea26b`, when the inventory is read, then every top-level
   capability family in that tree appears with a source path.
2. Given a consumer nobody has enumerated, when the inventory is read, then it
   appears as `unknown` with the reason it could not be confirmed.

---

### US2: Every open obligation has a recorded destination [P1]

**As a** worker implementing any later child,
**I want** each open issue, PR and capability to carry an explicit disposition,
**So that** "we decided to drop this" is distinguishable from "nobody noticed
this."

**Acceptance Criteria:**
- [ ] Every one of the 40 open CxPP issues and PR cxpp#239 appears in
      [ledger.md](ledger.md) with source, delivery status, owner, destination and
      disposition.
- [ ] Disposition is one of: `already-covered`, `move`, `adapt`,
      `owner-approved-retirement`, `unresolved`.
- [ ] `owner-approved-retirement` is used only where an owner ruling exists and
      is cited. Absent a ruling the row is `unresolved`, not retirement.
- [ ] Unresolved rows state their **blocking effect**: which child cannot
      complete while the row is unresolved.
- [ ] Both Nit Stores (cxpp#227, cpp#864) have recorded dispositions; their
      findings are triaged, not discarded.

**Test Scenarios:**
1. Given an open CxPP issue absent from the ledger, when the completeness control
   runs, then it FAILS and names the missing number.
2. Given a ledger row marked `owner-approved-retirement` with no cited ruling,
   when a reviewer reads it, then the citation gap is visible on the row.

---

### US3: Shipped foundations are distinguishable from unfinished programs [P1]

**As a** worker deciding what may be moved as-is,
**I want** CxPP's delivered capabilities separated from its in-flight programs,
**So that** an unfinished program is not moved as though it were a working
feature, and a working feature is not discarded as though it were unfinished.

**Acceptance Criteria:**
- [ ] The native-wave surface is split into **shipped foundations** (code present
      and exercised) and **unfinished end-to-end support** (declared but not
      demonstrated).
- [ ] Library tests alone are NOT accepted as evidence of a working native wave.
- [ ] Transferred obligations remain OPEN unless fulfilled, or explicitly
      withdrawn with recorded authority.

---

### US4: The migration has one agreed order, and it is enforced [P2]

**As a** wave orchestrator,
**I want** the dependency order, release matrix and serialization rules in one
place,
**So that** two children editing the same shared file do not silently invalidate
each other's evidence.

**Acceptance Criteria:**
- [ ] Dependency order is recorded with each child's prerequisites.
- [ ] Shared-surface edits (Makefile, dependency lock, CI, generator, installer)
      are serialized, and the integrated SHA is revalidated after each merge.
- [ ] The release matrix enumerates the environment x lifecycle combinations that
      must be demonstrated before cutover.

---

### US5: The plan has been reviewed by someone who did not write it [P1]

**As the** repository owner,
**I want** independent review of this plan with reviewer identity recorded,
**So that** "reviewed" is a measurement rather than an assertion.

**Acceptance Criteria:**
- [ ] Review is performed by models that did not author the plan.
- [ ] Reviewer identity, findings, and per-finding disposition are recorded in
      [review.md](review.md).
- [ ] If independent review is unavailable, that is recorded as unavailable and
      an owner-approved alternative is obtained. **Unavailable is never recorded
      as passed.**

---

### US6: Consequential choices reach the owner as choices [P1]

**As the** repository owner,
**I want** compatibility and retirement decisions surfaced as open decisions,
**So that** no constraint is silently reclassified by an implementer.

**Acceptance Criteria:**
- [ ] Every consequential compatibility or retirement choice without a ruling is
      an `OWNER DECISION - PENDING` row naming options and consequences.
- [ ] No such choice is resolved inside this spec on the implementer's authority.

---

## Trust and compatibility boundaries

These are **constraints** in the sense of `docs/agents/issue-contract.md`:
binding, challengeable on evidence, never silently dropped. They are restated
from #1067's "Binding safety boundaries" because this spec is the surface
children reference; where the wording differs, #1067's intent governs and the
difference is a defect to fix here.

### B1. State and credential namespaces stay isolated

CPP and CxPP maintain separate namespaces. They are **not** merged, silently or
otherwise.

| Client | Config / state | Credentials |
|---|---|---|
| Codex (CxPP) | `~/.codex/` (`config`, `history`, `rules/default`, `scripts/`, `skills/`), `CODEX_HOME` | `~/.config/codex-power-pack/secrets/`, `~/.config/codex-power-pack/audit.log` |
| Claude (CPP) | `~/.claude/` (`commands/`, `scripts/`, `plugins/`, `projects/`, `boot-types/`, `daemon/roster`), `~/.claude-power-pack/` | CPP secrets lane (AWS Secrets Manager) |

A co-installed host has both. Consolidating the *source* does not consolidate the
*state*: a Codex user's credentials and history remain where Codex looks for
them. Path names are inventory; **values are never recorded**.

### B2. A plugin install is not hook trust

Installing or updating a plugin does not authorize a changed hook definition.
Changed hooks require explicit review before they run. Active-session hook roots
and recovery safeguards are preserved, and **an already-trusted path is never
repointed at different bytes** - that is a trust escalation wearing an update's
clothing.

### B3. Source pinning, artifact integrity, invocation policy and negative
controls remain protections

These survive the removal of cross-repo synchronization. They exist to answer
"are these the bytes we agreed to", a question that does not disappear when the
two repositories become one. In particular, a check that cannot fail is not
evidence (ADR 0008): instruments moved or adapted during this migration keep
their negative controls, and an instrument whose control does not come with it is
recorded as **unproven**, not as clean.

### B4. Public behaviour and installed compatibility are preserved

Until replacement evidence exists, or the owner explicitly agrees to a revision.
An installed CxPP that still works must keep working until its consumers are
migrated or explicitly retired.

### B5. No migration shortcuts

Specifically prohibited: bulk PIN bumps, wholesale directory copies, security
suppressions taken to make a gate green, silent capability deletion, and broad
unrelated refactors justified as migration.

### B6. User work is preserved

Including PR cxpp#239 and any dirty worktrees. **No repository deletion.**
Historical issues, tags, attribution and source references remain available after
archival; archival is not erasure.

### B7. Evidence standard

Each material promise requires specific behavioural evidence. **Skipped, unknown,
empty, unavailable and deferred are not clean and not complete.** Closure follows
`docs/agents/issue-contract.md`.

---

## The bidirectional vendor dependency

#1067 records that CPP vendors CxPP's `project_next` engine. Re-inspection found
the dependency runs **both ways**, which constrains archival order in a way the
epic does not capture.

| Direction | Mechanism | Pinned at | Status at baseline |
|---|---|---|---|
| CxPP -> CPP | `lib/vendor.py` + `vendor/project_next/**` (16 whole files) | CxPP source | CPP depends on CxPP as a source of record |
| CPP -> CxPP | `vendor/claude-power-pack/PIN` + `adoption-policy.json`, pulls `codex/skills/` -> `.codex/skills/` | CPP `f64a654f76ea8d26a33eb33f785f6e1065a823b6` | **Behind** CPP main `5ceb966a` |

Two consequences:

1. **#1069 (project-next ownership transfer) is a hard prerequisite for
   archival**, not merely for tidiness. Archiving first would leave CPP
   dependent on a retired source.
2. **The CxPP pull is already stale.** The adoption bridge brings over generated
   surfaces at a pin, not a continuously shared runtime, so CxPP's Codex skills
   at baseline reflect CPP as of `f64a654f`. Any claim that the two surfaces
   agree must state the pin it was measured at. See cxpp#257 and cxpp#275 in
   [ledger.md](ledger.md), which are the instrument-side symptoms of this.

---

## Dependency order

| Child | Bounded outcome | Prerequisites |
|---|---|---|
| #1068 | migration spec, capability inventory, disposition ledger | none - first gate |
| #1069 | CPP becomes canonical owner of project-next | #1068 |
| #1070 | one tested runtime, Codex state and security contracts preserved | #1068 |
| #1071 | native skills and reciprocal review in a thin CPP adapter | #1068, #1070 |
| #1072 | native-wave foundations relocated, downstream obligations preserved | #1068 |
| #1073 | pinned Codex plugins shipped from CPP, safe hook update and rollback | #1069, #1070, #1071, #1072, **and Q6 resolved** |
| #1074 | dual-client release behaviour and failure detection proven | #1069-#1073, **and Q7's unknown-consumer disposition agreed** |
| #1075 | approved reversible consumer cutover, backlog reconciled | #1074 |
| #1076 | retirement readiness audited, archive on final owner approval | #1075 |

**Critical path:** #1068 -> #1070 -> #1071 -> #1073 -> #1074 -> #1075 -> #1076.
#1069 and #1072 proceed after #1068 in disjoint files and join before #1073.

**Two edges the epic did not carry, added on independent review.** #1073 packages
plugins and hooks, and what it packages differs entirely depending on Q6 (native
vs generated skills), so starting it before Q6 is resolved means building a
distribution for an undecided surface. #1074 proves release behaviour for
consumers, and its evidence is scoped by which consumers count - a question Q7
answers. Both were implicit in the text and neither was an edge anything enforced.

**Nit-store triage has no child and needs one.** Both nit stores appear in the
archive exit criteria (194 comments between them at baseline) and in no phase of
the work. An exit criterion nobody is scheduled to satisfy is discovered at the
last gate. Triage is assigned to Phase 6 in [plan.md](plan.md); the alternative -
that it belongs earlier, because a finding may change what the adapter must
preserve - is recorded as review finding **R8** and left to the owner.

Preparation may overlap once prerequisites are met; **acceptance may not bypass
them**. Do not wait on all of #1061, nor on completion of every native-wave
feature, where the relevant migration contracts can be met independently.

---

## Bounded release matrix

Before cutover (#1075), each cell is demonstrated from an **isolated install** -
no neighbouring CxPP checkout on the host, and the CPP artifact pinned.

| Environment \ Lifecycle | Fresh install | Update | Interrupted update -> recovery | Rollback |
|---|---|---|---|---|
| **Claude-only** | required | required | required | required |
| **Codex-only** | required | required | required | required |
| **Co-installed** | required | required | required | required |

Each demonstration records: the CPP artifact pin, the CLI versions in play, the
evidence SHA, and the observed outcome. A cell that was not run is recorded as
**not run**; it is never inferred from a neighbouring cell that passed.

Additionally, before cutover: known-bad inputs are **rejected** (a release
process that accepts a corrupted artifact has no integrity check, only a
ceremony).

---

## Cutover and rollback criteria

**Cutover may proceed when** every release-matrix cell is demonstrated; the same
tested core runs from a pinned CPP artifact in all three environments without a
neighbouring CxPP checkout; fresh install, update, interruption recovery and
rollback are each demonstrated; known-bad inputs are rejected; and current CLI
versions and the evidence SHA are recorded.

**Cutover is reversible by construction.** #1075 performs it only with explicit
owner approval and only with the rollback path already demonstrated - not
described.

**Rollback triggers** (any one is sufficient): a required Codex behaviour is
found to be unpreservable by a bounded adapter; distribution isolation fails;
measured regressions cannot be corrected safely. Escalate the observation.
**Do not silently reintroduce a fork, and do not drop the requirement.**

---

## Archive exit criteria

CxPP may be archived (#1076) only when **all** of the following hold:

- [ ] Every shipped capability has a demonstrated replacement, or an explicitly
      approved retirement.
- [ ] Every known active consumer is migrated or explicitly retired.
- [ ] Unfinished programs have durable owners and destinations.
- [ ] Open PRs and user work (incl. cxpp#239) have recorded dispositions.
- [ ] Both Nit Stores are triaged; no unresolved finding is lost.
- [ ] No active build, install or update path requires CxPP.
- [ ] The last supported CxPP release is preserved, and rollback to it has been
      demonstrated.
- [ ] **Unknown consumer classes have an explicit owner-approved disposition** -
      discover, migrate, or accept-break - and a deprecation notice plus
      migration guide is published to every channel CxPP was distributed
      through. (Review finding **R2**: "every *known* active consumer is
      migrated" is satisfiable while breaking consumers nobody enumerated, and
      this inventory records three such populations. All three reviewers reached
      this independently.)
- [ ] **Host-level artifacts CxPP installed are uninstalled, adopted, or
      explicitly left with recorded reason.** Three of its five hook handlers
      execute from `~/.codex/scripts/`, so "no active build/install/update path
      requires CxPP" can be true while a user's machine still runs its bytes on
      every tool call. An abandoned trusted path is also a hijack target: a
      later package writing to it inherits execution context. (Review finding
      **R5**.)
- [ ] **No documentation, install snippet or example still routes an active
      flow through CxPP.** Copy-pasted instructions are a dependency path that
      no build-graph check sees. (Review finding **R6**.)
- [ ] Explicit final owner approval is recorded.

**Do not archive while consumers still need CxPP maintenance.** Historical
provenance links are allowed and expected to remain.

---

## Out of scope

Explicitly NOT part of #1068:

- Any install, runtime move, issue closure, issue transfer, or archival.
- Building a new workflow platform, tracker, or schema. **One bounded ledger.**
- Recreating the CxPP parity backlog before moving.
- Resolving the owner decisions this spec surfaces.

Explicitly NOT part of the migration as a whole:

- Renaming CPP. Not on the critical path.
- Copying both engines into a monorepo and maintaining two platforms.
- Deleting the CxPP repository.

---

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | Record rebaselined main SHAs for both repositories | Must | US1 |
| R2 | Inventory every CxPP capability family with source paths | Must | US1 |
| R3 | Record credential/state namespaces by name only, never by value | Must | US1 |
| R4 | Record unconfirmed consumers as `unknown`, never omit them | Must | US1 |
| R5 | One ledger row per open CxPP issue and PR, with five recorded fields | Must | US2 |
| R6 | Constrain disposition to the five defined values | Must | US2 |
| R7 | State the blocking effect of every `unresolved` row | Must | US2 |
| R8 | Separate shipped native-wave foundations from unfinished support | Must | US3 |
| R9 | Record dependency order, release matrix and serialization rules | Must | US4 |
| R10 | Record independent reviewer identity, findings and dispositions | Must | US5 |
| R11 | Surface unruled consequential choices as `OWNER DECISION - PENDING` | Must | US6 |
| R12 | Children reference governing sections rather than copying them | Should | US4 |
| R13 | Ship a ledger-completeness control with a committed negative control | Must | US2 |

### Non-Functional Requirements

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR1 | The ledger's completeness claim is machine-checked, not asserted | A control fails on a ledger missing any open CxPP issue or PR |
| NFR2 | That control is proven able to fail | A committed negative-control fixture produces a RED verdict (ADR 0008) |
| NFR3 | No credential value is committed | Secret scan passes over the spec set |
| NFR4 | Staleness is detectable | Every count and claim cites its baseline SHA |

---

## Success Criteria

- [ ] `.specify/specs/codex-consolidation/` holds spec, inventory, ledger, plan
      and review.
- [ ] The ledger accounts for 40/40 open CxPP issues and 1/1 open CxPP PR.
- [ ] The completeness control passes on the real ledger and **fails** on the
      committed negative-control fixture.
- [ ] Independent review is recorded with reviewer identity, or its unavailability
      is recorded with an owner-approved alternative.
- [ ] Owner decisions are surfaced as pending, not resolved.
- [ ] Epic and children reference this spec rather than carrying a competing copy.

---

## Open Questions

These are tracked as `OWNER DECISION - PENDING` rows in [ledger.md](ledger.md).
Listed here so the spec's reader sees what it deliberately did not decide.

- [ ] **Q1.** Native-wave (cxpp#189/#192/#193/#194 and stories): relocate to CPP,
      transfer to Kyle, or owner-approved retirement? Blocks #1072.
- [ ] **Q2.** SAST: CPP #962 owns bandit adoption. Does CxPP's existing SAST
      protection move, or lapse pending #962? Lapsing is a reduction in
      protection and needs a ruling. Blocks #1070.
- [ ] **Q3.** PR cxpp#239 (open, docs mirror): merge before freeze, migrate the
      content to CPP, or close with the work preserved elsewhere? Blocks #1076.
- [ ] **Q4.** The balanced-delivery program (cxpp#219/#220 and stories
      #223-#226): CPP already has `.specify/specs/balanced-agentic-development`.
      Is the CxPP program already-covered, or does it carry obligations CPP's
      spec does not? Blocks #1072.
- [ ] **Q5.** CxPP-native instruments with no CPP analogue (`harness_lint`,
      `skill_contract_lint`, `skill_eval`, `release_validate`): adapt into CPP,
      or retire with approval? Blocks #1071.
- [ ] **Q6.** Does the Codex adapter keep CxPP's **native** skills as native, or
      converge on CPP's generated-surface model? This is the central
      compatibility choice of #1071.
- [ ] **Q7.** Unknown consumer populations (installed Codex hosts,
      plugin-marketplace installs, template adopters): **discover** them before
      cutover, **migrate** what can be reached, or **accept-break** with a
      published notice? Blocks #1074 and #1076. Raised by all three independent
      reviewers; the archive criteria as first written permitted an archive that
      breaks them.
- [ ] **Q8.** Git history for relocated code: does `project_next`, and whatever
      Q1 moves, travel with its history (subtree/filter-repo) or arrive as a
      fresh copy? A copy loses `git blame` and the provenance of every decision
      in it, which is obligation context, not just convenience. Blocks #1069.
- [ ] **Q9 (ORDERING, raised against the epic itself).** #1075 performs backlog
      reconciliation **after** #1074 proves the release. If reconciliation then
      surfaces a missed obligation, #1074's evidence is invalidated and must be
      re-run. Reordering is a change to the epic's own sequence and therefore
      not a change this spec may make; it is surfaced here as review finding
      **R9** for the owner.

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
