# Flow run record - issue #1695

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=75852eaebd984514b23de5663e23f362 -->
## Run 1

- Run-id:            75852eaebd984514b23de5663e23f362
- Run-start:         ca8652a87bc53d34efd8fc7e834ae5dabe3817df
- Issue:             #1695
- Base SHA:          ca8652a87bc53d34efd8fc7e834ae5dabe3817df
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the repository owner, in this session ("approved", after the Step 3 report)
- Recorded at:       2026-11-11T22:23:08Z

### Section B evidence
- commits since 2026-11-11T22:12:24Z: ca8652a8 (touches docs/agents by adding the Nit Store rollover doc; nothing about lanes)
- merged PRs: #1694
- duplicate/superseding issues: none. #1696 is the follow-up and depends on this issue; #1084 uses "lane" in another sense
- this host: the #1689 worktree holds two unpushed commits (55cf4efb, 182a46a5) touching docs/agents; they do not cover this issue, a merge conflict is possible

### Section C - the approved plan
1. `docs/agents/lanes.md` - new canonical reference: what a lane is, the lane file's location and format, the four answers, the plan and closing tables, the growth rule, tier scope, what enforces it and what does not
2. `.claude/lanes.md` - claude-power-pack's own lane file, with a review date inside it
3. `docs/agents/issue-contract.md` - Demonstrated names its lanes; a listed lane not named is not tested
4. `docs/agents/closing-report-contract.md` - Evidence carries the lane rows with results and explains any difference from the plan
5. `.claude/commands/flow/eli5.md` - pointer outside the vendored core telling the plan to answer the lane file; paid for by moving one history paragraph out, budget unchanged
6. `.claude/commands/codex/code_review.md` - hand the lane file to the reviewer and add the lane question to the prompt; paid for by moving rationale out, budget unchanged
7. `docs/commands-reference.md` - receives the paragraphs moved out of items 5 and 6, verbatim
8. `tests/test_lanes_contract.py` - pins the reference, the routing from both contracts and both commands, the prompt question, and the lane file's format
9. `tests/fixtures/lanes/lanes.md` - example lane list for the red case
10. `tests/fixtures/lanes/plan-omits-lane.md` - example plan that leaves a listed lane out
11. `tests/fixtures/lanes/plan-complete.md` - the same plan answering every lane
12. `CLAUDE.md` - one Project Map line
Scope: 12 files, about 450 lines, prose and tests. No new script, no gate.
Risks: (a) the issue's red case is a model's judgement: the example pair is committed and Codex is run on both once, reported as an observation, not a repeatable make verify check; (b) eli5.md and code_review.md are exactly at their word caps, so text is moved verbatim and an independent old-versus-new read is done before review; (c) the delegated-driver review surfaces do not get the lane question.

### Lanes for this change
| Lane | Answer |
|---|---|
| Project with a lane file / without | will test both: the review prompt is built with and without the file |
| Linked worktree / main checkout | worktree: will test (this run's review); main checkout: not covered |
| Claude install / Codex install | Codex mirrors build in the gate; a Codex-driven run presenting the table: not covered |
| Claude review / delegated-driver reviews | not covered: codex/auto, qwen/auto and gemma/auto keep their own review text |
| With Kyle / without | not applicable: nothing here talks to Kyle |
| GitHub Actions / Woodpecker | not applicable: no CI-provider behaviour changes |
