# Flow run record - issue #1685

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=39bf3661a9214e9593740e59f505080a -->
## Run 1

- Run-id:            39bf3661a9214e9593740e59f505080a
- Run-start:         d79d0042a2daff328eb8c7f5607fdd7fe00d1b60
- Issue:             #1685
- Base SHA:          d79d0042a2daff328eb8c7f5607fdd7fe00d1b60
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the repository owner, in the interactive session ("approved")
- Recorded at:       2026-11-11T20:45:32Z

### Section B evidence
- Commits since 2026-11-11T20:43:17Z touching tests/test_flow_wave_mailbox.py: none.
- Merged PRs since filing: none. Open PRs mentioning the file: none.
- Duplicate/superseding issues: none (Nit Store comment 5818464125 is a different defect in the same class; #1506/#1573 synchronised other fixtures).
- Sibling worktrees: no unpushed commits on the file; one stale entry (t008/cpp-pin) UNREADABLE, unexamined.

### Section C - the approved plan
1. `tests/test_flow_wave_mailbox.py` - add `_pid_from(path, timeout)`, which waits until the file holds digits and returns the number; use it at the failing test (line 3079), `_daemon_pid` (line 1988) and the supervise cwd test (line 3543); add two tests for the helper (an existing-but-empty file is not accepted until a pid is written; a file that never gets a pid fails at the timeout).

Scope: 1 file, about 45 lines.
Risks: the original flake's rate is unmeasured, so the proof is on the mechanism; the production pid write at flow-wave-mailbox.sh:3057 has the same non-atomic shape and is left out, to be recorded in the Nit Store.
