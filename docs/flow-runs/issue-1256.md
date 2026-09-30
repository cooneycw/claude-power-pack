# Flow run record - issue #1256

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1256
- Base SHA:          3b4d1b2
- Necessity verdict: Needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2218 in reply to ELI5 message 2216
- Recorded at:       2026-09-28T18:05:00Z

## Section B evidence
- /cpp:update Step 6b classifies an expected server OK whenever it is registered; scripts/mcp-drift.py has no scope logic; drift-detect.sh delegates only --list-orphans.
- Callers of mcp-drift.py: cpp/status.md (--list-orphans), cpp/update.md (--check, --json, --plan, --teardown), scripts/drift-detect.sh (--list-orphans, --plan).

## Section C - the approved plan
1. `scripts/mcp-drift.py` - `--scope-check` (with `--claude-json`, `--project-dir`): every server name defined at 2+ of user/local/project scope with differing endpoints reports SCOPE CONFLICT (exit 1); one definition or equal endpoints OK; unreadable config UNKNOWN (exit 3); endpoints redacted on output; never removes anything
2. `tests/test_mcp_drift.py` - conflict (red on pre-fix), single, same-endpoint, unreadable, redaction, and default exit codes unchanged
3. `.claude/commands/cpp/update.md` - Step 6b calls --scope-check, reports on 1 and 3 and continues; SCOPE CONFLICT status row; OK narrowed

Host-owed: the canonical wiring, removal of the loser, and the run against the real ~/.claude.json.

<!-- flow-run n=2 id=ac54966bc79a4478a13605ca6a59f7bb -->
## Run 2

- Run-id:            ac54966bc79a4478a13605ca6a59f7bb
- Run-start:         9e2d3e7fd4e24c895fbb0753cf014a47dd3cb480
- Issue:             #1256
- Base SHA:          9e2d3e7f
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          cooneycw (owner), in-session reply "approved, go ahead with the stdio canonical plan"
- Recorded at:       2026-09-29T10:29:01Z

### Section B evidence
- Delivered earlier: cd3eb00a (PR #1331, --scope-check), c6b02fad (PR #1337, /cpp:status consumes it). Also on these paths, unrelated: 7d1ad79f (#1305), 879df151 (#1287).
- Related closed issues: #633, #1282, #1290. No duplicate or superseding issue.
- Host reproduction this run: SCOPE CONFLICT second-opinion, user stdio vs project http://127.0.0.1:8080/mcp (exit 1); 8080 is nginx redirecting to /accounts/login/, not second-opinion.
- --scope-check does not read projects[<dir>].disabledMcpjsonServers, and its project-scope remedy (`claude mcp remove -s project`) rewrites the tracked .mcp.json.

### Section C - the approved plan
Canonical wiring on this host: user-scope stdio. The shipped project HTTP entry is disabled on this host only.
1. `scripts/mcp-drift.py` - a project-scope server listed in that project's disabledMcpjsonServers is not counted as a definition and is reported as disabled; the remedy for a project-scope loser suggests disabling rather than `remove -s project`
2. `tests/test_mcp_drift.py` - disabled project entry reads OK (red on pre-fix); the same config without the disable still reports SCOPE CONFLICT; project remedy text no longer says `remove -s project`
Scope: 2 files, ~40-70 lines. Risk: Claude Code might not honour the disable list for that key, in which case the check would read OK while the entry still loads - verify with `claude mcp list`.
Host-owed (not a repo file): back up ~/.claude.json, add second-opinion to the CPP project's disabledMcpjsonServers, re-run --scope-check expecting exit 0, then close #1256.

<!-- flow-run n=3 id=53d1d8feb42546f4850acdf4806150a8 -->
## Run 3

- Run-id:            53d1d8feb42546f4850acdf4806150a8
- Run-start:         e845d6d38b5f9db76ff5d9c89aaa783b0394dae5
- Issue:             #1256
- Base SHA:          e845d6d3
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          cooneycw (owner), in-session reply "approved" to the revised install-phase plan
- Recorded at:       2026-09-30T13:58:52Z

### Section B evidence
- Delivered earlier: cd3eb00a (PR #1331), c6b02fad (PR #1337), 72cb00c5 (PR #1355). Unrelated on these paths: 7d1ad79f (#1305), 879df151 (#1287). Related closed: #633, #1282, #1290; no duplicate.
- Host step done this run: second-opinion added to projects[~/Projects/claude-power-pack].disabledMcpjsonServers (backup ~/.claude.json.bak-1256-20260930T094747); --scope-check rc 1 -> 0 in the main checkout. claude mcp list still prints [Conflicting scopes] (it does not consult the disable list); worktrees still conflict (per-path key).
- Owner reframe: the interest is novice installs. Isolated CLAUDE_CONFIG_DIR repro: the documented `claude mcp add second-opinion --transport http --url ...` fails "unknown option '--url'" while init prints success; with valid syntax and SECOND_OPINION_URL unset no conflict; with SECOND_OPINION_URL set to another host, user 127.0.0.1 vs project remote -> SCOPE CONFLICT in both claude mcp list and --scope-check.

### Section C - the approved plan
1. `.claude/commands/cpp/init.md` - valid `claude mcp add --transport http --scope user second-opinion "$SO_URL"` with SO_URL derived from ${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp; success printed only on exit 0; remote hosts told to set SECOND_OPINION_URL; --scope-check after registering; disclosure and error text match
2. `.claude/commands/cpp/update.md` - same corrected, derived registration command
3. `.claude/commands/second-opinion/help.md` - same
4. `README.md` - same (two sites)
5. `tests/test_mcp_json_override.py` - no live doc carries `claude mcp add ... --url`; every second-opinion registration derives from SECOND_OPINION_URL; both red on pre-fix
Scope: 5 files plus codex mirrors, ~60-100 lines. Risks: existing installs with a hand-registered differing URL are reported not repaired; tests pin prompt text, not model execution.
