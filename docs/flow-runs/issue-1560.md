# Flow run record - issue #1560

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=5e2f1600bd854bb4994f2077c0f9f8f1 -->
## Run 1

- Run-id:            5e2f1600bd854bb4994f2077c0f9f8f1
- Run-start:         dd988219e056ddf23fb7ef5ba55e93979c07b61a

- Issue: #1560
- Base SHA: dd988219e056ddf23fb7ef5ba55e93979c07b61a
- Necessity verdict: Still needed
- Approval: granted
- Approver: skillc-proof root orchestrator, GO-WITH-CONDITIONS, durable outbox revision 2
- Recorded at: 2026-10-25T07:45:57.002669+00:00

### Section B evidence

Current origin/main and remote main both resolve to dd988219. No commits since
issue creation 2026-10-25T07:32:18Z, globally or in the two command sources.
Inspected merged PRs #1559/dd988219, #1558/eac62c9c, #1556/2cacaf7a all
predate filing and do not fix the guidance. Related/duplicate candidates
#871, #1072, #868, #867, #1253 and #864 do not supersede #1560.
The sources still infer universal wakeability from Claude watcher ancestry.
Four readable sibling worktrees have no relevant unpushed commits; six missing
registered scratch paths remain unexamined. Native capabilities, local CLI
0.164.0 and a bounded matching exchange were measured; native server version
and general idle wake remain unmeasured. Actual tool/message evidence is
retained privately; public walkthrough uses neutral identifiers.

### Section C - the approved plan

1. `.claude/commands/flow/register.md` - Scope watcher rules to Claude and document durable assignment, native notification, intended-worker matching acknowledgement and bounded unavailable escalation.
2. `.claude/commands/flow/wave.md` - Apply transport distinctions at active setup, assignment and hazard decisions; preserve Claude guards and reject aggregate/send-acceptance delivery claims.
3. `docs/measurements/flow-wave/issue-1560-transport-walkthrough.md` - Retain pinned source scenario, measured versus manual/simulated distinguishing inputs and honest capability/evidence limits, without machine identity or runtime-enforcement claims.
4. `changelog.d/1560.md` - Document the guidance correction and bounded observation without timeout/task-success improvement claims.

Scope: Seven expected changed files including the normal workflow record and
two generated reference.md outputs. The two source command entries above cover
those mirrors under normal compliance mapping; regenerate with make codex-skills.
The complete generator-owned lane is 34 paths, including all 29 derived outputs.
Maximum 650 changed lines excluding required workflow provenance. Only the two
reference outputs are expected to change substantively; new dependencies or
scope/verdict changes return to root before edits.
Risks: a single transport preface could leave contradictory active decisions;
aggregate acknowledgements do not authenticate intended-worker receipt;
capability versions can expire; a local exchange does not prove idle wake.
No runtime helper/guard/test/config changes, live study, host install, deployment
or retired native-wave engine. Request full-test slot; required independent
counter-model review is authorized. Merge clearance remains separate.
