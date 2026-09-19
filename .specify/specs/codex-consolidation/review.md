# Codex Consolidation: Independent Review Record

> **Governing spec:** [spec.md](spec.md) - US5 ("the plan has been reviewed by
> someone who did not write it") and boundary **B7**.
> **Established by:** #1068 | **Epic:** #1067
> **Reviewed:** 2026-09-19, against CPP `5ceb966a` / CxPP `681ea26b`

---

## Why this file exists

#1067 states: *"independent model validation is **pending** because the
second-opinion service was unavailable. Do not label this plan independently
validated or ready for implementation on that basis."* #1068's acceptance item 5
inherits that: review happens, identity is recorded, and **unavailable is never
recorded as passed**.

At the time of this run the service was available. `health_check` reported
`status: healthy` with Gemini, OpenAI and Anthropic providers configured, so the
#1067 caveat is discharged by evidence rather than deferred a second time.

---

## Reviewer identity

The rule is a property, not a service: **the reviewing model must not be the
implementing model** (the same rule ADR 0007 applies to code review). The
implementer here is `claude/opus-5`, so all Anthropic models were excluded from
the panel even though they were available - a Claude reviewing a Claude's plan
satisfies the tool and not the requirement.

| Reviewer | Model id | Provider | Outcome |
|---|---|---|---|
| `gemini-3-pro` | `gemini-3.1-pro-preview` | Google | completed, 95% stated confidence |
| `gpt-5.2` | `gpt-5.2` | OpenAI | completed, 82% stated confidence |
| `codex` | `gpt-5.3-codex` | OpenAI | completed, 89% stated confidence |

3 of 3 succeeded. Panel invoked once, in parallel, on the same brief; none saw
another's response, so agreement between them is independent rather than
sequential. Two share a provider, which bounds how independent "3 of 3" is -
`gpt-5.2` and `codex` agreeing is weaker evidence than either agreeing with
`gemini-3-pro`. Where a finding below is marked **3/3** it was also reached by
the non-OpenAI reviewer.

**Brief given:** review a migration plan for defects causing capability or
obligation LOSS; be adversarial and concrete; name risks rather than endorse.
Five specific questions: dependency order, archive-criteria blind spots,
disposition-vocabulary soundness, the one-directional ledger check, inventory
omissions.

**Severity returned:** High (gemini-3-pro), High (codex), Critical-on-two-axes
(gpt-5.2). **No reviewer endorsed the plan as sound as written.**

---

## Findings and dispositions

| # | Finding | Raised by | Disposition |
|---|---|---|---|
| **R1** | `already-covered` requires naming a CPP surface but not PARITY. A CxPP capability with richer behaviour, marked covered against a rudimentary CPP namesake, is a silent drop that satisfies every check in the document. | **3/3** | **ACCEPTED, FIXED.** `ledger.md` vocabulary now requires a parity statement naming what was compared (behaviour, security properties, operational contract) and naming unexamined dimensions as unexamined. |
| **R2** | Archive criteria say "every **known** active consumer migrated or retired". Three consumer populations are recorded as unknown, so the repository can be archived while breaking them, and the criterion still reads satisfied. | **3/3** | **ACCEPTED, FIXED.** New archive exit criterion requiring an owner-approved disposition for unknown consumer classes plus a published deprecation notice and migration guide. Raised as owner decision **Q7**, blocking #1074 and #1076. |
| **R3** | The completeness gate checks row PRESENCE. A row `\| cxpp#239 \| \| \|` passes while recording nothing. | gemini-3-pro, gpt-5.2 | **ACCEPTED, FIXED.** The gate now requires the row to name one of the six dispositions, and `controls/ledger-completeness/cases/bad-row-without-disposition` is a committed case that fails the old rule and passes nothing. |
| **R4** | The vocabulary has no word for handing a capability to an owner OUTSIDE CPP. Q1 offers "transfer native-wave to Kyle", which with five values had to be recorded as `owner-approved-retirement` - describing a rehoming as a deletion. | gemini-3-pro | **ACCEPTED, FIXED.** Sixth disposition `transfer` added, requiring a named external destination and cited acceptance by that owner. Consistent with `docs/agents/issue-contract.md`, which already permits transfer to resolve an issue on those two conditions. |
| **R5** | Three hook handlers execute from `~/.codex/scripts/`. "No active build/install/update path requires CxPP" can be true while a user's machine still runs its bytes every tool call. An abandoned trusted path is also a hijack target for a later package that writes to it. | gemini-3-pro, gpt-5.2, codex (as trust-boundary risk) | **ACCEPTED, FIXED.** New archive exit criterion on host-level artifacts. Inventory §8b records that the byte-provenance mapping for those handlers **does not exist yet**, so **B2** is currently asserted and not verified - stated as a gap rather than left implied. |
| **R6** | Inventory treats capability as code and skills, omitting CI workflows, release/publishing machinery, branch protection, issue forms, docs-as-interface, and git history. These are the things lost silently. | **3/3** | **ACCEPTED, FIXED.** New inventory §8b. Git-history retention raised as owner decision **Q8**, blocking #1069. Publishing channels recorded as **unknown**; branch protection recorded as **unexamined**, not as absent. |
| **R7** | The ledger check has no referential integrity: duplicate `cxpp#N` rows with conflicting dispositions, or a first-cell citation of a number not in the snapshot (typo, renumber), both pass. | gpt-5.2, codex | **ACCEPTED, DEFERRED - and recorded where it will be read.** These are positive-claim integrity, not omission; folding them into this gate would blur what a red from it means, and both reviewers proposing it suggested a separate advisory check. Written into `controls/ledger-completeness`'s `limits` field, which is the text a future reader of this instrument sees. **Still owed; not discharged by being written down.** |
| **R8** | Nit-store triage is an archive exit criterion (194 comments at baseline) with no child scheduled to do it. | gemini-3-pro | **ACCEPTED, PARTIALLY FIXED.** Assigned to Phase 6 in `plan.md` and noted in the spec. Gemini argues it belongs *earlier*, because a finding may change what the adapter must preserve - that is a resequencing of the epic and is **left to the owner**, not decided here. |
| **R9** | Ordering: #1075 reconciles the backlog **after** #1074 proves the release. A missed obligation surfacing at #1075 invalidates #1074's evidence. | gemini-3-pro | **ACCEPTED AS A RISK, NOT FIXED.** The sequence is #1067's own. Changing it is a change to the epic, which this issue may not make (spec **US6**). Raised verbatim as owner decision **Q9**. |
| **R10** | #1073 should depend on Q6, and #1074 on the unknown-consumer decision; the technical edges are recorded but the decision edges are implicit. | codex | **ACCEPTED, FIXED.** Both edges added to the dependency table and to `plan.md`. |
| **R11** | SAST lapse (Q2) is a measurable security downgrade and should block the adapter, not merely be pending. | gemini-3-pro | **ACCEPTED as already-satisfied, and the reason recorded.** Q2 blocks #1070, which is a prerequisite of #1071, so the block already propagates. Noting it because "it is already handled" is the answer most likely to be wrong, and a reader should be able to check the propagation rather than take it. |
| **R12** | Convert the ledger to structured YAML/CSV with schema validation (codex "Approach A", gpt-5.2 "Option B"). | codex, gpt-5.2 | **REJECTED, with reason.** #1068's constraint is explicit: *"Build one bounded ledger, not a new workflow platform."* A schema-plus-renderer is the platform that constraint names. The concrete defect underneath it - rows that record nothing - is closed by R3 without the migration. Revisit if the ledger outgrows review by reading. |
| **R13** | Validate citations live against the GitHub API instead of a committed snapshot (gpt-5.2 "Option C"). | gpt-5.2 | **REJECTED, with reason.** CI has no network and no `gh` credentials, so the check would skip - and a skipped gate printing nothing is indistinguishable from a passing one, which is the failure this whole spec set is written against. gpt-5.2 lists this trade-off itself. `--refresh` covers the freshness need on a host that has both. |
| **R14** | Two-phase retirement: freeze CxPP behind a compatibility shim with a feedback window before archiving (codex "Approach C"); tombstone the repo and publish a final deprecated release (gemini-3-pro). | codex, gemini-3-pro | **PARTIALLY ACCEPTED.** The tombstone half is now an archive exit criterion (R2). The shim-and-window half is a change to the retirement strategy itself, which is the owner's and belongs to #1075/#1076 - recorded here so it reaches them rather than dying in this review. |

**11 accepted (7 fixed in this change, 1 partially, 1 deferred with its home
recorded, 2 accepted as risks for the owner), 2 rejected with reasons, 1 split.**

---

## What the review changed, and one thing it did not

Four defects in this document set were found by reviewers and not by its author:
the parity hole in `already-covered` (**R1**), the missing `transfer` verb
(**R4**), the empty-disposition row (**R3**), and the whole delivery-surface
category (**R6**). Each is a **loss path** - a way for a capability to disappear
while every check in the document reports green.

That is the argument for the stage, and it is worth stating plainly because the
epic's own note said independent validation was pending and might have been
carried as pending again.

**One defect was found neither by review nor by reading.** The completeness
gate's first cut matched `cxpp#N` anywhere in the file, and its own known-bad
fixture passed it, because the fixture's prose contains the token in the
sentence explaining the absence. No reviewer saw that - they were given a
summary, not the source. It was caught by running the committed known-bad input,
which is the whole claim of ADR 0008: re-reading an instrument checks what it
MEANT, and this one meant the right thing both times.

The blind rule is vendored as the control's anchor, so the blindness is a
committed artifact rather than a story in this file.

---

## Standing caveats on this review

- **It reviewed a summary, not the tree.** The panel received the plan's
  structure, counts and constraints - not the two repositories. `gpt-5.2` says
  so itself ("some conclusions depend on repo contents not shown here"). Its
  findings are about the plan's shape; none of them is evidence about a specific
  file.
- **Two of three reviewers share a provider.** See "Reviewer identity".
- **Confidence figures are self-reported** by each model and are not
  measurements.
- **This review does not discharge #1076's own review obligations.** It is
  review of the plan at Phase 0. Each later child's evidence is reviewed on its
  own merits.
