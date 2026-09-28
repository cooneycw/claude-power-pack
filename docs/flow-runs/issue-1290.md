# Flow run record - issue #1290

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=af8d279630304b5e879aa3dfcb349633 -->
## Run 1

- Run-id:            af8d279630304b5e879aa3dfcb349633
- Run-start:         51dc14dccc561c65875ab83e4c19343603fefd05
- Issue:             #1290
- Base SHA:          51dc14dccc561c65875ab83e4c19343603fefd05
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2272 (GO with amendments A1-A5) in reply to ELI5 message 2269
- Recorded at:       2026-09-28T16:00:00Z

### Section B evidence
- No PR or branch for #1290 existed. Dependencies #1256 (mcp-drift --scope-check, cd3eb00) and #1282
  (cpp-checkout-freshness.sh, 7d1ad79) are merged. status.md:281-288 greps
  `http://127.0.0.1:8080}/mcp` (stray `}`) and curls it, so second-opinion reachability is never verified.
  Measured in this container: second-opinion stdio initialize+tools/list answers unauthenticated (12 tools),
  project-scope http :8080 refused, scope-check reports a conflict; playwright stdio exits 5 before initialize.

### Section C - the approved plan
1. `scripts/capability-readiness.py` - flow / second-opinion / browser-qa rows, one state each (disabled, unexamined, stale-or-unknown, conflicting, unreachable, ready), table and --json from one row list, exit 0/3/4; consumes flow-helpers-install --check, cpp-commands-link --check, cpp-checkout-freshness.sh and mcp-drift's scope definitions; MCP initialize+tools/list handshake only, redacted config
2. `tests/test_capability_readiness.py` - fixtures: missing helper, conflicting scopes, unreachable service, old checkout, failed freshness lookup, healthy, credential redaction, clean-home install+update smoke with sentinel files
3. `controls/capability-readiness/control.json` - registered negative control (closed-port BAD case a blind anchor calls ready)
4. `controls/capability-readiness/run-case.sh` - builds each case's situation
5. `controls/capability-readiness/cases/good-healthy/scenario` - healthy case
6. `controls/capability-readiness/cases/bad-closed-port/scenario` - unreachable case
7. `controls/capability-readiness/cases/bad-missing-helper/scenario` - missing helper case
8. `controls/capability-readiness/anchors/pre-fix-status-curl.sh` - the pre-fix status.md block as the blind anchor
9. `.claude/commands/cpp/status.md` - replace the buggy curl block with the readiness table
10. `codex/skills/` - regenerated mirrors
11. `docs/scripts.md` - inventory entry
12. `docs/decisions/0008-instrument-negative-control-bound.md` - census row
13. `.claude/verify-coverage.json` - coverage entry

Scope: new script ~450 lines, tests ~400. Risks: stdio probe side effects (mitigated: UV_OFFLINE/UV_NO_SYNC/npm offline, hard timeout, process-group kill). Touched controls run with --strict.
