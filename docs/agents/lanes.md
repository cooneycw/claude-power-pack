# Lanes exercised

A lane is one of the routes the same behaviour can travel: the main checkout or
a linked worktree, a Claude install or a Codex install, dev or prod, a small
fixture or real-size data. This document is the canonical statement of how a
project lists its lanes, and of how a plan and a closing report say which lanes
a claim was exercised in. Other surfaces point here; they do not restate it.

## Why this exists

A test can be real, can fail, can pass honestly, and still cover less than the
claim it closes. A negative control shows that a check can report the other
verdict. It does not show that the check was pointed at everything the issue
promised.

Evidence, with its limits: a Codex-authored review of cooneycw/kyle on
2026-11-11 hand-picked 34 issues, and the largest family (11) was a capability
that exists in one lane and is absent, disabled or incompatible in another. It
is a purposive sample, not a prevalence estimate. In this repository, #1677 is
the same shape: the CI provider record worked in the main checkout and was
absent in linked worktrees.

The session writing a plan knows only the lanes it thought of. So the list
comes from the repository, not from the session.

## The lane file

A project that adopts lanes commits `.claude/lanes.md`:

```markdown
# Lanes

Reviewed: 2026-11-11

| Lane | Values | How it is exercised |
|---|---|---|
| Checkout | main checkout / linked worktree | tests build both layouts in a temporary repository |
```

- `Reviewed:` is the date a person last read the whole list, in `YYYY-MM-DD`.
  It is written in the file because a file's modification time says only that
  something was edited.
- One row per lane. `Values` names the routes. `How it is exercised` says how
  the project can test the lane, or says that it has no way to today. A lane
  with no way to exercise it is a finding to record, not a row to leave out.
- Keep it short enough to answer on every plan. If answering it is a burden,
  the list is wrong, not the rule.

`/lane:create` drafts the file from a survey checklist and shows the draft,
with the evidence for each row, before writing; `/lane:update` reviews it. Both
record the `Reviewed:` date with `scripts/lane-file.py stamp`, so the date is
never typed by hand. `/project:init` runs `/lane:create` for a new project.

**No lane file means nothing is asked.** A project that has not adopted lanes
gets no table, no question and no failure.

A lane file that exists and cannot be used - unreadable, empty, or a failed
lookup - is reported as such. It is never treated as absent.

## At plan approval

When the project has a lane file, the plan presented for approval answers
EVERY listed lane with one of:

| Answer | Meaning |
|---|---|
| will test | Exercised in this change; name how |
| will refuse | The behaviour says clearly that it is unsupported there |
| not applicable | One line of reason |
| not covered | A known gap, stated before the work starts |

The approver reads "not covered" as a decision to make, while it is cheap to
change. In `/flow:auto` the table goes in the plan record under a
`### Lanes for this change` heading, after Section C's `Risks:` line.

**Readers share the table.** A change that alters an output another part reads
adds one row per reader, named `Reader: <who reads it>`, with the answers from
[the readers reference](changed-output-readers.md). Those rows are owed whether
or not the project has a lane file.

**A lane test is judged, not only counted.** `will test` means a test that
reaches the lane with the real thing where the real thing can be used, and that
could fail if the lane were broken. The reviewer reports one that does neither;
the judgement is the one the readers reference states.

## At close

In `/flow:auto`, what happened goes in a file of its own at Step 6,
`docs/flow-runs/issue-<N>.lanes-demonstrated.md`: a table with one row per
lane answered `will test`. It is deliberately not part of the plan record,
which must not change after approval.

The closing report's Evidence carries the same rows with what happened. A row
whose result differs from the approved answer is explained. In
[the issue contract](issue-contract.md)'s terms, a Demonstrated item names the
lanes it was demonstrated in, and a listed lane nobody names is not tested.

## Where it applies

Tier 2 and Tier 3 work that changes behaviour. A typo, a docs-only change or
anything else with no behavioural lanes says so in one line, for example
`Lanes: none - documentation only`, and carries no table.

## When the list was last reviewed

The plan step runs `scripts/lane-file.py age` and relays its `LANE_FILE_AGE:`
line when the list was last reviewed more than 60 days ago (`stale`) or exists
and cannot be dated (`unknown`). It is a notice with a remedy, `/lane:update`.
It never stops a plan, a gate or a merge, and a project with no lane file sees
nothing.

Age is a proxy. A list goes stale when the product changes, not when the
calendar does, and a freshly reviewed list can still be missing a lane. The
stronger signal is the growth rule below. If the notice is routinely dismissed
with no change to the list, drop the notice and keep the rule.

## Growing the list

When a miss turns out to be a lane nobody listed, adding that lane to
`.claude/lanes.md` is part of the fix. This is how the list becomes complete;
no survey finds a lane that leaves no trace in the repository.

## What enforces this, and what does not

Stated plainly, because a rule's existence otherwise implies more coverage than
it has.

**The routing is enforced.** `tests/test_lanes_contract.py` asserts that this
document exists and states the four answers, that the issue contract, the
closing-report contract, `/flow:eli5` and `/codex:code_review` each link here,
that the review prompt still carries the lane question, and that this
repository's own lane file parses and carries a review date.

**The age verdict has a committed control.** `controls/lane-file-age` runs
`lane-file.py age` at a pinned date: a list reviewed 61 days earlier is flagged,
one reviewed exactly 60 days earlier is not, and an undated list is `unknown`.
Its blind anchor - "the project has a lane file" - misses both bad cases.
`tests/test_lane_file.py` pins the rest: absence, every way a file can exist
and be undatable, the stamp, and root resolution.

**The table's presence and completeness are machine-checked; its truth is
not.** In `/flow:auto`, `flow-plan-record.py approve` refuses a plan record
that has no `### Lanes for this change` table, or that leaves a listed lane
without one of the four answers, and names the missing lanes (issue #1731;
committed cases in `controls/flow-plan-record-lanes`). A lane file that exists
and cannot be read refuses too, as unknown. The one-line form above
(`Lanes: none - <reason>`) is accepted with a reason and announced on stderr;
nothing judges the reason. At close, `compliance` puts each lane answered
`will test` that has no row in
`docs/flow-runs/issue-<N>.lanes-demonstrated.md` on its verdict line, directly
after the verdict word, as a state and a count: `PLAN_COMPLIANCE: agreement,
LANES NOT DEMONSTRATED (2) - ...`, or `, LANES NOT CHECKED` when the lane file
or that file exists and cannot be read. The lanes are named on stderr, one per
line, with the reason and what to do (issue #1767; committed cases in
`controls/flow-plan-record-lanes-verdict`). The exit code does not change and
nothing is refused. A project with no lane file, a waived plan, and a plan with
no `will test` answer get the line exactly as it was. Where a lane result
is owed, writing the file is not itself a change to the plan: it is left out of
the touched files, like the plan record beside it. The file is a table - a
header row, a `|---|---|` row, then `| <lane> | <what was demonstrated> |` per
lane - and the stderr note beside the clause says so.

The table itself is not machine-checked for truth. A plan can answer every
lane `will test` and test none of them. Two readers check that:

1. The approver, at plan approval. A plan that should carry the table and does
   not is not approvable.
2. The counter-model review. `/codex:code_review` hands the reviewer the lane
   file and asks it to report a listed lane the plan does not answer, and a
   lane marked `will test` that no test in the diff exercises.

**The second reader is a model, so its red case is an observation, not a
repeatable check.** `tests/fixtures/lanes/` holds an example lane list, a plan that omits a listed
lane and the same plan answering every lane, each with the tests it adds. The
question was put to Codex (`gpt-6.1-sol`) over both, four times, on 2026-11-11.
It reported the omitted lane for the first plan all four times. For the second
plan it reported no lane finding three times; the first time it reported a
loosely worded answer in the example itself, which was then tightened. To
repeat it, hand the reviewer the fixture lane list and each plan with the lane
question from `/codex:code_review`, and read whether the omitted lane is
reported for the first and not for the second. One run does not
establish that the next run answers the same way.

**Not covered.** The delegated-driver review surfaces (`/codex:auto`,
`/qwen:auto`, `/gemma:auto`) carry their own review text and do not ask the
lane question. A lane file whose list is incomplete produces a table that
looks complete.
