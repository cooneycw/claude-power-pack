<!-- flow-run n=1 id=75852eaebd984514b23de5663e23f362 -->
## Run 1 - issue #1695 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1695
- Read at:      2026-11-11T22:20:11Z
- updatedAt:    2026-11-11T22:19:30Z   (context only - moves on comments and labels)
- Body digest:  f7d30d78c99532affe84ac67f4a8b9688bc13e8f4b20c9e15cbae6cd35f49109   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5072 of 5072 (cap 16384)

### Body as read
Tier: 2

Source: owner-requested follow-up to the 2026-11-11 methodology review. Owner approved filing. The evidence is the Codex-authored report `kyle-quality-measures-2026-11-11.html` (built 2026-11-11T20:56Z from read-only GitHub queries on cooneycw/kyle; a purposive sample of 34 issues, not a prevalence estimate). Two of its claims were spot-checked against GitHub (kyle#2098 closed 2026-11-02 and reopened 2026-11-03; kyle#2309 open as described); the other 32 were not.

## Outcome
When an issue is planned and when it is closed, the reader can see which lanes the claim was exercised in and which it was not.

A lane is one of the routes the same behaviour can travel: for example main checkout or linked worktree, Claude or Codex install, dev or prod, small fixture or real-size data. The largest family in the report (11 of 34) is completions whose test was real and could fail, but exercised a narrower lane than the claim it closed. A negative control does not catch this: it shows a check can report the other verdict, not that the check was pointed at everything the issue promised.

`docs/agents/issue-contract.md` already requires every material acceptance item to end as Demonstrated, Revised or Deferred. It does not ask where an item was demonstrated. That is the gap.

Two CPP examples from 2026-11-11:
- #1677: the CI provider record worked in the main checkout and was absent in linked worktrees, which stopped merges mid-wave.
- On the #1674 plan the owner asked by hand, before approving, how the change behaves for a repo that does not use Kyle. The lane was supplied from the owner's memory, not from a list.

## Acceptance
- **Lane file.** A documented location and format for a per-project lane list, checked into the consuming repo. A project with no lane file is unaffected: no table is asked for and nothing fails.
- **CPP's own lane file** is committed. Starting rows, to be corrected at planning: Claude or Codex install; main checkout or linked worktree; with Kyle or without; GitHub Actions or Woodpecker.
- **Issue contract.** `docs/agents/issue-contract.md` states that a Demonstrated item names the lanes it was demonstrated in, and that a listed lane not named is not tested, never covered by default.
- **Plan step.** When the project has a lane file, the plan presented for approval answers every listed lane with one of: will test (naming how), will refuse (the behaviour says it is unsupported there), not applicable (one line of reason), not covered (a stated gap). A change with no behavioural lanes may say so in one line.
- **Closing report.** The same rows appear with results, and any row that differs from the approved plan is explained.
- **Independent read.** The counter-model review asks, for each lane the plan marked will test, whether a test in the diff exercises it, and reports a lane the plan omitted.
- **Growing the list.** When a miss turns out to be a lane nobody listed, adding the lane to the file is part of that fix. This is stated where the lane file is documented.
- **Negative control** (ADR 0008: the review question's verdict is read by an approval that does not re-derive it): a committed example plan that omits a listed lane gets the other verdict from the review question, and a plan that answers every lane does not.

## Constraint
- No new gate script. The checks are the owner at approval and the counter-model review. Whether to record the table in the plan record is decided later, from whether sessions skip it.
- The command documents are on a word budget (#1669). `flow/eli5.md` is at its cap (2,651 of 2,651) and `flow/auto.md` has 8 words of room (10,402 of 10,410). The rule lives in the issue contract; a command document carries at most a pointer, paid for by trimming, with no budget raised.
- Applies to Tier 2 and Tier 3 work that changes behaviour. It must not add a table to a typo or docs-only change.

## Owner decision needed before the plan step and closing report change
#1673 freezes new features in `flow` and `cicd` while it is open. The lane file, the issue-contract rule and CPP's own lane file do not touch those areas. The plan-step and closing-report pointers edit `flow` command documents and add a planning requirement. The owner was asked on 2026-11-11 whether those two get an exception or wait for the wave, and has not yet answered. Until answered, deliver the unaffected parts and leave this issue open.

## Assumption
- That people plus the counter-model review are enough enforcement to start. This morning's review argued that prose a session must recall is the weakest enforcement, so this is a deliberate first step, to be re-read after about 20 issues.
- That the lane list can be kept short enough to answer on every Tier 2 plan. If it cannot, the list is wrong, not the rule.

## Not checked
Whether CPP's own history shows the same proportion of lane misses as the kyle sample. The 244 fix-titled PRs from the 60-day scan have not been traced to the completions they repaired.

Related: cooneycw/kyle lane-file issue (linked in a comment below).


<!-- end of body -->
