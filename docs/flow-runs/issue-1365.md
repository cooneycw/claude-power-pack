# Flow run record - issue #1365

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=6701a224d6ec4cc6be9c2cbe93741303 -->
## Run 1

- Run-id:            6701a224d6ec4cc6be9c2cbe93741303
- Run-start:         b8825bd31608b254dfabac1589100fc675d44061
- Issue:             #1365
- Base SHA:          b8825bd
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run59:cpp-orch (mailbox message 4661, replying to 4660; conditional approval, 2 conditions, both addressed below)
- Recorded at:       2026-10-06T01:08:48Z

### Section B evidence
- commits since filing (2026-10-01T13:11:42Z) touching scripts/delegated-run-check.sh,
  tests/test_delegated_run_check.py, controls/delegated-run-check: none
- merged PRs since filing mentioning delegated-run: none
- duplicate/superseding issues: none supersedes #1365 itself (still OPEN); #836,
  #892, #1054 are related, closed, and fixed different gaps on the same script
- sibling worktrees with unpushed work on these paths: none found

### Section C - the approved plan
1. `scripts/delegated-run-check.sh` - add attempt-counting siblings
   (`attempted_tool_calls`, `attempted_codex_item`, `attempted_tool_results`,
   each with its own id-dedup set where applicable) to the three existing
   per-harness TOOL_ERRORS recognizers. After the per-line loop, when
   `tool_errors > 0` and `tool_attempts > 1` and `tool_errors == tool_attempts`
   (more than one call attempted, every one failed), emit signal
   `all-tools-failed`; it falls into the existing bash catch-all
   `STATUS=failure` arm with no verdict-loop change needed. Extend the header's
   documented Signals list.
2. `tests/test_delegated_run_check.py` - add the committed red case (issue
   #1365's own incident shape: 3 codex command_execution items, all failed
   with the same "Failed to create unified exec process" error, must yield
   `failure`), the required control (3 calls, 1 fails/2 succeed, must stay
   `success` with `TOOL_ERRORS: 1` - #836's case), plus two conditions added
   by orchestrator review: a GOOD control proving a successful non-command
   item (`file_change`) alongside all-failed commands stays `success`
   (condition 1), and an explicit pin of the >1 threshold itself showing the
   four existing #836/#892/#1054 single-attempt fixtures are genuinely 1-of-1
   runs, not "denial among successes" (condition 2).
Scope: 2 files, ~115 lines added (mirrored counting functions + 4 new tests).
Risks: the single-attempt residual - a 1-of-1 failed run still reports
  `success` under this rule by design (protects #836's pinned cases) but is
  ALSO zero work; named explicitly per orchestrator condition 2 and routed to
  the Nit Store (CPP #864) rather than fixed in this PR.
