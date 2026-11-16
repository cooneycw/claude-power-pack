<!-- flow-run n=1 id=24a6e5c8d5254560a53eeb7bf5977625 -->
## Run 1 - issue #1850 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1850
- Read at:      2026-11-16T01:52:45Z
- updatedAt:    2026-11-15T23:50:24Z   (context only - moves on comments and labels)
- Body digest:  2c0fba27fbe9d64c4854fd87276812cc37f2433039cb7c445034495813e8ef88   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4294 of 4294 (cap 16384)

### Body as read
Tier: 3

## Outcome

`/flow:auto` has a charter: a short statement of what it promises, the situations it supports, and what it does with the rest. Its procedure is then proportional to the work. A one-concern prose change does not carry the same ceremony as a new subsystem.

This needs an owner decision before any edit, because it removes promises instead of relocating them. It is the rule #1846 added to `docs/agents/issue-contract.md` ("Supported scope and proportional prevention") applied to the largest procedure in the repository.

What the #1846 run showed (a six-file prose change):

- The plan answered eleven lanes; nine were "not applicable". **Correction (2026-11-15):** this was the session over-applying the rule. `docs/agents/lanes.md` already lets a docs-only change answer `Lanes: none - documentation only` with no table. What it shows is that the summaries a run reads (`flow/eli5.md`, the `/flow:auto` Step 3 summary) say "every listed lane" and do not mention the exemption.
- It carried a plan record, an as-read snapshot, a second-model review with a receipt, and lane results at close.
- Step 5 (docs) ran a Makefile target that prints two reminders. Step 9 (deploy) is skipped in most repositories.
- `flow/auto.md` cites 168 issue numbers. Most mark a paragraph added after one incident.

Source: observed while running `/flow:auto` on #1846 (2026-11-15), measured on main `f1253b45`. Part of the simplification asked for in [discussion #1830](https://github.com/cooneycw/claude-power-pack/discussions/1830). Related: #1669 (word budgets).

## Questions for the owner (this is the work)

1. **Supported scope.** Which situations does `/flow:auto` promise to handle, and which may preflight simply refuse?
2. **Sorting the incident paragraphs.** Each one is: already enforced by a helper (delete the prose), real judgement (keep), or a one-off with no recurrence **and** no credible severe consequence within supported scope (accept as a limitation and delete; lack of recurrence alone is not enough). Who sorts, and who approves the third group?
3. **A Tier 1 path.** What may a Tier 1 change skip or answer in one line: the lane table, the reader rows, lane results at close?
4. **Step count.** Fold Step 5 into Step 6, and Steps 8 and 9 into one "after merge" step?

## Lane clarity (part of the outcome)

> A lane identifies a supported variation under which the same capability could behave differently. The repository's lane list is an inventory of possibilities. A change's plan identifies the relevant variations and explains what evidence covers them. Listing a variation does not require exercising it on every change.

The selection question is "what about this change could make the result differ between these settings?" Establish whether existing guidance already covers a case before adding an exemption. Add two worked examples to `docs/agents/lanes.md` (a documentation change using the one-line answer; a behavioural change naming the relevant values and evidence) and have the charter point there. (Wording from a Codex review of this issue; see the comments.)

## Constraints

- **The approval gate has no bypass at any tier** (#775). Proportionality shortens what is asked, never whether a human approves the plan.
- **The second-model review stays run-by-default** (ADR 0007) unless the owner rules otherwise in the charter.
- **Nothing is deleted on a word count alone.** Each removal names its group from question 2.
- **No new gate, form or script** to enforce the charter; that would contradict it.

## Acceptance

- [ ] A charter for `/flow:auto` exists where the owner decides charters live, answering questions 1 to 4.
- [ ] Each removed paragraph is listed with its group and, for accepted limitations, the ruling.
- [ ] `flow/auto.md` is shorter and its budget row is lowered.
- [ ] One Tier 1 issue is run on the proportional path and its closing report says what was skipped.

## Proposed approach

Do the sort as a reading-only pass first (discussion #1830, Step 2) and bring the table to the owner. Edit nothing until the third group is ruled on. The helper-side reductions are separate issues and can land first.

## Assumptions

- The charter format from the skill-gauntlet work fits a command, not only a skill. Not checked.



<!-- end of body -->
