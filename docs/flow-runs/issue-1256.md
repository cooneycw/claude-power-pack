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
