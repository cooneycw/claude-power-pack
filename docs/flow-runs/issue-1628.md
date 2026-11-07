# Flow run record - issue #1628

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=1d6ae7189cf54be0b96d202205208780 -->
## Run 1

- Run-id:            1d6ae7189cf54be0b96d202205208780
- Run-start:         6bc585a3fecffbf42d0d1d9d800696caccc58a3b
- Issue:             #1628
- Base SHA:          6bc585a3
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          repository owner, interactive reply "approved" in this session
- Recorded at:       2026-11-07T18:30:52Z

### Section B evidence
Commits since filing (2026-11-07T18:04:05Z): none on origin/main.
Merged PRs since filing: none (#1627 merged earlier the same day; unrelated).
Duplicate/superseding issues: none (#864 has no entry; #1493, #789, #408 unrelated).
Sibling worktrees: no unpushed commits touching scripts/flow-preflight.py or tests/test_flow_preflight.py.

### Section C - the approved plan
1. `scripts/flow-preflight.py` - add a required bash check with a 4.4 floor, reading the bash on the caller's PATH; unreadable output is unknown, never a pass.
2. `scripts/flow-preflight.sh` - add bash to the hard-coded unexamined list; the file must keep working on bash 3.2.
3. `scripts/hook-permission-census.sh` - move the Python out of $(...) into a variable set by a top-level heredoc so the hook parses on bash 3.2, with no behaviour change.
4. `tests/test_flow_preflight.py` - cover 5.x ok, 3.2 unsupported, the 4.3/4.4 boundary, absent bash, unreadable output and the unselected check; update fixture and expected lists.
5. `tests/test_hook_permission_census.py` - fail if a heredoc reappears inside $(...) in the hook, and run the hook under a real bash below 4 when one exists.
6. `tests/test_flow_start_resolve.py` - add bash to the hard-coded check list.
7. `controls/flow-start-preflight/run-case.py` - add bash to the hard-coded check list.
8. `.claude/commands/cpp/update.md` - report the bash check once after the pull and give Step 5b.1 defined handling for exit 2.
9. `.claude/commands/flow/doctor.md` - document the new check.
10. `README.md` - state the minimum bash version under bootstrap prerequisites with the Homebrew remedy.
11. `docs/scripts.md` - update the flow-preflight entry.
12. `CHANGELOG.md` - add an Unreleased note.

Scope: about 12 files plus the regenerated Codex mirror, roughly 120 lines changed, 60 of them tests.
Risks: /flow:auto now refuses on old bash through --require-preflight; the check sees only the caller's PATH, not launchd jobs with a bare PATH; how Claude Code treats exit 2 from a PermissionRequest hook is unverified; Linux CI cannot run bash 3.2, so only the static check protects the hook there.
