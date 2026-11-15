<!-- flow-run n=1 id=6f7c28fb940b45b4889b1ead9aacec9e -->
## Run 1 - issue #1846 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1846
- Read at:      2026-11-15T19:50:54Z
- updatedAt:    2026-11-15T19:49:42Z   (context only - moves on comments and labels)
- Body digest:  5e354fc9e6a1d46567a571a9512797db3052868e50c7da686f3cd4a7b466cb1c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6637 of 6637 (cap 16384)

### Body as read
Tier: 1

## Outcome

A valid finding can end as an **accepted limitation**: its consequence is understood, it stays unimplemented, and no future fix is promised. Today a finding can only be fixed, rejected or deferred, so each one becomes more code or another promise. The chain #1835 -> #1839 -> #1842 -> #1844 is the example: four lexer gaps in a row, each found by review, in shapes no live document uses.

`docs/agents/issue-contract.md` is the canonical place for this rule, so the rule goes there once. The two procedures an agent is actually executing when a finding arrives must stop contradicting it:

- `.claude/commands/flow/auto.md:743` (Step 6, 1c) offers three routes only: accepted means "fix it now", rejected, or deferred to the nit store.
- `docs/agents/counter-model-evidence.md:207` ("Asking for a further pass, and what happens on a refusal") gives a declined pass two routes only: back the fix out and file the finding as its own issue, or keep it as an unreviewed commit.

A canonical paragraph does not change behaviour while the step being run says otherwise, so both get a pointer to the contract. This is a pilot: success is one real finding reaching an accepted end state without generating more required work.

Source: the amendment proposed in [discussion #1830](https://github.com/cooneycw/claude-power-pack/discussions/1830#discussioncomment-19638900). First use, as the owner's pilot: [the ruling on #1844](https://github.com/cooneycw/claude-power-pack/issues/1844#issuecomment-6900182306).

## The text to add

Immediately before "How much document":

> **Supported scope and proportional prevention**
>
> Approve the intended outcome and supported scope before choosing safeguards. Name material exclusions and how unsupported cases are reported. Supporting additional inputs or environments is additional scope; discovering them during review does not automatically make them requirements.
>
> A new mandatory gate, hook, or standing directive needs a justification beyond a reproducible defect: observed recurrence or a credible severe consequence within supported use, and an explanation of why permanent prevention is preferable to a local correction. Include the maintenance and false-blocking costs. A red case proves discrimination; a severity label expresses a judgment. Neither alone establishes that permanent prevention is worthwhile.
>
> A valid finding may be **accepted as a limitation**: its consequence is understood, it remains unimplemented, and no future fix is promised. Record the reason and decision authority in the existing plan, review disposition, or PR. Reconsider it when evidence materially changes its frequency, consequence, or supported scope.
>
> Accepting a limitation cannot silently discharge an existing promise. If it changes agreed acceptance or constraints, record the authorized revision or withdrawal. Assess completion against that revised agreement.

The wording may be tightened; the four points (scope first, justification for permanent prevention, the accepted-limitation disposition, no silent discharge) are the outcome.

## Constraints

- **The three delivery dispositions stay three.** Demonstrated, Revised and Deferred describe acceptance items. An accepted limitation is a disposition for a *finding*. When it changes an acceptance item, that item is Revised under the existing rule and needs the same agreement. Rationale: `tests/test_acceptance_disposition.py` and `scripts/counter-model-receipt.py` both count against the existing vocabulary, and a quiet fourth state would make them disagree with the doc.
- **No new gate, form, field or script.** Rationale: the amendment exists to stop reflexive additions; enforcing it with one would contradict it.
- **It grants no new authority.** An agent still cannot waive a requirement, bypass a failing mandatory check, or call an unexamined input a pass. Only the existing decision authority accepts a limitation.
- **The two routing edits point; they do not restate.** A few sentences each, linking the contract. Rationale: a copied policy is a second, drifting description (discussion #1830, Part 5).
- **`flow/auto.md` stays inside its word budget.** It is 10,406 words against a declared 10,410 in `.claude/command-word-budgets.tsv`, and `make command-docs-budget-check` enforces that. The edit must fit without raising the budget.
- **Review and check results stay truthful.** A receipt still names the last reviewed head and its true counts; an accepted limitation is never recorded as a clean review or a rejected finding. A finding of medium severity or higher is accepted only in the approver's own words, as the refusal policy already requires for keeping an unreviewed fix.

## Acceptance

- [ ] The section above is in `docs/agents/issue-contract.md`, before "How much document".
- [ ] The doc says how an accepted limitation relates to Demonstrated / Revised / Deferred, in a sentence or two.
- [ ] `flow/auto.md` Step 6 triage and the refusal policy in `counter-model-evidence.md` each offer accepting a limitation and link the contract for what that means.
- [ ] `make command-docs-budget-check` passes with the budget table unchanged.
- [ ] **Practical evidence, from the #1844 pilot:** #1844 closes on its recorded ruling with no successor issue filed for the unsupported shapes, and its review receipt and gate results are reported as they were. Cite it in the closing report.
- [ ] `tests/test_acceptance_disposition.py` and `tests/test_issue_contract_routing.py` pass, with no assertion loosened to make room.

## Proposed approach

`issue-contract.md` is 2,737 words on `main` at `19e24318`. Keeping it from growing is a maintenance preference, not an acceptance item: where it is easy, offset the added words (about 190) by moving the history out of the "Declare the tier as a line in the issue" paragraph, whose rule is one sentence. Do not let a word count hold up finishing.

## Assumptions

- No test pins the wording of the tier paragraph. Not checked.
- Editing Step 6 of `flow/auto.md` does not trip `controls/driver-parity` or the delegated-driver vendoring check, although the delegated drivers carry parallel triage text. Not checked.
- `counter-model-receipt.py` needs no change for this issue, because the ruling is recorded in prose on the review or PR record.

## Out of scope

The reviewer-prompt edits (`codex/code_review.md`, `templates/delegated-driver-core.md`), the `flow/eli5.md` challenge section, `self-improvement/retro.md`, and any machine-readable disposition. They wait until this pilot has been used and judged. They are not promised by this issue.


<!-- end of body -->
