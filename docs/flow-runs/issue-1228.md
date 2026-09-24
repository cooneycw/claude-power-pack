# Flow run record - issue #1228

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1228
- Base SHA:          c5b1c5edb180db748738878e577809b47d112611
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the session's user (owner), replying "approved" to the Step 3 report
- Recorded at:       2026-09-24T09:18:10Z

## Section B evidence
- commits: none touching scripts/flow-wave-mailbox.sh, .claude/commands/flow/register.md, .claude/commands/flow/wave.md since 2026-09-23T21:43Z
- PRs merged since filing: #1199 #1209 #1210 #1212 #1213 #1214 #1215 #1216 #1217 #1218 #1219 #1223 #1224 #1225 #1229 #1230 - none touch the mailbox or listener docs
- related: #1107 (open, asks to sequence after this), #871 (open evergreen, evidence source), #868 (closed not-planned; lineage-gated delivery 5/5 vs orphan 0/4), #814 (closed; supervise's motivation)

## Section C - the approved plan
1. `scripts/flow-wave-mailbox.sh` - lineage classification of watchers (ancestor owns a cc-socks session socket; FLOW_WAVE_SESSION_PIDS test hook); new `no-wake` watch state in watch --status / list / list --json (+ session watcher count); duplicate guard refuses only on a session-parented holder and names every holder's pid/start/parentage; supervise records its arming session and the daemon exits `owner-gone` when it is gone
2. `.claude/commands/flow/register.md` - step 4 prescribes a session-parented background watch (run_in_background, re-arm after every wake); supervise demoted to opt-in with its no-wake property stated; no-wake roster state explained
3. `.claude/commands/flow/wave.md` - same for the orchestrator listener and roster reading
4. `tests/test_flow_wave_mailbox.py` - negative control (detached poller no-wake vs session-parented armed), duplicate pass/refuse with holder named, supervise owner-gone exit, unknown-not-no-wake when the scan is unavailable
5. `codex/skills/flow-register/scripts/flow-wave-mailbox.sh` - regenerated mirror
6. `codex/skills/flow-wave/scripts/flow-wave-mailbox.sh` - regenerated mirror

Scope: ~4 source files, ~250-350 lines
Risks: sessions with no messaging socket would read no-wake (mitigated: no readable socket dir -> unknown); a watcher parented to the wrong live session still reads armed; a live session watch makes a later supervise inner watch back off; the #814 forgotten-re-arm and /compact-survival questions stay open and are named, not solved
