# Flow run record - issue #1547

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=8446aad069b947329dec18ac238defd3 -->
## Run 1

- Run-id:            8446aad069b947329dec18ac238defd3
- Run-start:         f857754d2c49c157ab25dd671a68e5ecd935f85f
- Issue:             #1547
- Base SHA:          f857754d
- Necessity verdict: Still needed (premise widened: same gate, same gap, at auto Step 7, finish, merge, check)
- Approval:          granted (GATE: GO-WITH-CONDITIONS, orchestrator outbox rev 10)
- Approver:          cpp-group orchestrator (cpp-orch), authority-model=orchestrator-only, policy rev 1
- Recorded at:       2026-10-23T13:30:00Z

### Section B evidence
commits: none on origin/main since filing (tip f857754d, from before the issue). PRs: none merged since.
dup/super: none; related #1542 and #1543 (both closed). Premise verified on f857754d: the unset call exits 126 with no
output; `--bogus` exits 2 and prints only `FLOW_FINISH_GATE_EXIT=2`, with no verdict line. 21 generated fallback
sentences for bundled helpers, each dispositioned in the Step 3 gate (orchestrator outbox rev 9).

### Section C - the approved plan
1. `scripts/codex-skill-sync.py` - BUNDLED_SCRIPTS_BULLET: read every exit-127 fallback as 127-or-126, and a gating helper that prints no verdict line (for the finish gate: no `FLOW_FINISH_GATE:` verdict line) did not run: STOP
2. `.claude/commands/flow/auto.md` - Step 6: a no-verdict-line STOP paragraph plus a verdict-list entry; Step 7 re-gate: the STOP beside "On ok (or skipped / warn", skipped kept as proceed
3. `.claude/commands/flow/finish.md` - the gate: STOP paragraph plus a verdict-list entry; Step 2c check-summary: report did-not-run, still non-blocking
4. `.claude/commands/flow/merge.md` - the re-gate: the STOP
5. `.claude/commands/flow/check.md` - both gate runs: no verdict line is a DID-NOT-RUN report, distinct from the gate's own skipped/SKIP
6. `tests/test_codex_skill_sync.py` - one trigger phrase pinned in every generated gate section (STOP, or did-not-run for report-only sites) and in every bundled-helpers bullet; the premise pin (unset: 126 and no verdict line; usage error: only the _EXIT= trailer)
Scope: 6 sources plus regenerated mirrors. Risk: wording drift, held off by the one-phrase test. The tests pin INSTRUCTION TEXT; whether an agent obeys it is skillc's measurement.
Trigger phrase (identical everywhere): no `FLOW_FINISH_GATE:` verdict line
