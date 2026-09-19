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

## Second panel: counter-model review of the change itself

The panel above reviewed the PLAN, from a summary. A second, separate review
read the actual diff: `/flow:auto` Step 6's counter-model stage
([ADR 0007](../../decisions/0007-counter-model-review.md)), which runs by
default and whose rule is the same property - the reviewing model must not be
the implementing model.

| | |
|---|---|
| Reviewer | **`codex/gpt-6-astra`** - read from this run's rollout via its thread id, not copied from a document |
| Implementer | `claude/opus-5` |
| Input | the full 2,250-line diff, read-only sandbox, with repository access for context |
| Passes | 1 |
| Result | **6 findings, 6 accepted, 0 rejected, 0 deferred** |

| # | Severity | Finding | Disposition |
|---|---|---|---|
| **F1** | MEDIUM | The gate counted EVERY `cxpp#N` in cell 1, and searched the WHOLE row for a disposition. So a cross-reference in another row's title discharged an entry's obligation, and a backticked vocabulary word in a title satisfied an empty disposition column. | **ACCEPTED, FIXED.** Subject is now the FIRST token of cell 1; the disposition is searched OUTSIDE cell 1. Two committed cases: `bad-cross-reference-in-title`, `bad-disposition-in-title`. |
| **F2** | MEDIUM | The credential inventory recorded CPP's secrets as AWS Secrets Manager only, omitting `${XDG_CONFIG_HOME:-~/.config}/claude-power-pack/secrets/` - a real local store resolved by `lib/creds`' always-available DotEnv provider. | **ACCEPTED, FIXED.** Verified in `lib/creds/__init__.py` before accepting. Added to spec **B1** and inventory §6, with why it mattered: the omission made isolation read as a Codex-side concern when the two stores are siblings one directory apart. |
| **F3** | MEDIUM | Q7-Q9 were added to the spec's Open Questions and propagated to neither the ledger's decision table nor the plan's prerequisites - so a worker following those documents could start #1069 or #1074 before the ruling they depend on. | **ACCEPTED, FIXED.** Q7-Q9 added to ledger §A with blocking effects; Q6/Q7/Q8 propagated into plan Phases 1, 4, 5; pending count corrected 6 -> 9. |
| **F4** | MEDIUM | The spec's US2 and R6 still constrained the vocabulary to FIVE dispositions while the ledger and gate had six. The authoritative document contradicted the thing it governs. | **ACCEPTED, FIXED.** US2 and R6 now name six, and carry `already-covered`'s parity requirement and `transfer`'s cited-acceptance requirement as acceptance criteria rather than only as ledger prose. |
| **F5** | LOW | Fence stripping recognised backticks only, so a `~~~markdown` illustration of a ledger row accounted for the obligation it illustrated. | **ACCEPTED, FIXED.** Both fence characters, with run-length tracking so a nested different-character fence is content. Committed case: `bad-tilde-fenced-example`. |
| **F6** | LOW | `--refresh` copied the old provenance header verbatim - capture date and baseline SHAs - so a new observation wore the original capture's date, and flattened the issue/PR split under both labels. | **ACCEPTED, FIXED.** The header is regenerated: observation date from the run, code baseline carried forward and labelled as a distinct fact, issue and PR sections counted separately. |

**All six were accepted and none was a false positive.** Four of them - F1, F4,
F5 and the plan/ledger drift in F3 - are defects the first panel could not have
caught, because it reviewed a summary and these live in the source and in the
consistency between documents. That is the argument for both stages existing
rather than either standing in for the other.

**F1 and F5 share a shape with the defect the negative control caught, and that
is the finding underneath the findings.** All three are ways for correct-looking
prose to satisfy a check: an explanatory sentence, a cross-reference, a worked
example. This gate reads a document that is *about* the numbers it checks for,
so the document's own vocabulary is adversarial to it by construction. Five of
the control's six cases now pin one such path each.

### Red cases returned by the counter-model stage

The reviewer was asked, per the Negative Control directive, to name the input
that makes each instrument report the OTHER verdict. It returned three, and they
are recorded here because two of them were **not** already covered:

| Red case proposed | Status |
|---|---|
| `bad-missing-issue` exits 1 naming `cxpp#227`; `bad-row-without-disposition` exits 1; empty snapshot exits 2 | **already covered** before the review |
| Title-token, cross-reference and tilde-fence inputs "should fail but currently pass" | **NOT covered - now committed** as three cases (F1, F5) |
| Substituting the blind anchor for the gate must report BLIND; and removing every `cxpp#227` occurrence INCLUDING prose must make even the anchor exit 1 | **already covered** by the control framework's anchor evaluation; the second half is what makes the anchor a blind predecessor rather than a broken script |

Proposed: 3. Already covered by our tests: 1. Newly committed from this review: 2.

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
