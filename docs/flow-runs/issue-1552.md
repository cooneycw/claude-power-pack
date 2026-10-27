# Flow run record - issue #1552

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=ffe4734d3df14c34aeec0c724dafc8b9 -->
## Run 1

- Run-id:            ffe4734d3df14c34aeec0c724dafc8b9
- Run-start:         ed73d2bd6402ca3ba7e04f034e62f9c99eb7fa77
- Issue:             #1552
- Base SHA:          ed73d2bd6402ca3ba7e04f034e62f9c99eb7fa77
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          cooneycw (owner), interactive "approved" of option (b) and then of this Section C
- Recorded at:       2026-10-27T12:30:00Z

### Section B evidence
Owner ruling 2026-10-25 (issue comment): blocked on upstream; no reaper, custom server build or deployment
change. woodpecker-baseline#2 (3.19.0 measurement, 2026-10-25): orphans not rescheduled, pipeline timeout
does not fire, API cancel leaves workflow running. Upstream: no release after v3.19.0 (2026-10-07);
woodpecker-ci/woodpecker#7168 closed unmerged; #220 open. PRs here: #1553, #1574 (agent id/pins, not
orphans). Read-only API probe 2026-10-27: CPP pipelines 3372/3374 = pipeline killed + workflow/steps
running, finished null; 3390 = success throughout; kyle #3796 running at 4 min; every repo timeout=60;
agent record exposes no restart timestamp. Host: no sibling worktree with unpushed work on these paths.

### Section C - the approved plan
1. `scripts/flow-ci-status.sh` - report `stalled` for a Woodpecker pipeline running past its repo timeout + 10 min (terminal, stops --wait), name stalled steps; flag a terminal pipeline with live children; header contract
2. `tests/test_flow_ci_status.py` - past-timeout stalled, inside-timeout still running, killed-with-live-child, clean success
3. `controls/flow-ci-status-stalled/control.json` - committed negative control: 3374-shape past timeout (bad) vs same shape inside timeout (good), with the pre-change script as anchor
4. `.claude/commands/flow/auto.md` - Step 8 handling of `stalled`
5. `.claude/commands/flow/merge.md` - `stalled` handling where it reads CI status
6. `docs/agents/detector-contracts.md` - entry stating what `stalled` claims and does not

Scope: ~6 source files plus generated mirrors, ~250-350 lines. Refs #1552 (does not close).
Risks: per-pipeline timeout larger than repo timeout could flag early (take the larger when exposed);
new status value is a contract change for callers that only know the old values.
