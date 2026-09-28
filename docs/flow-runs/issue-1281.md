# Flow run record - issue #1281

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1281
- Base SHA:          164fdd4d23f2eaf66ef4ba30408824f7c589c417
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 1721 in reply to ELI5 message 1719
- Recorded at:       2026-09-28T00:00:00Z

## Section B evidence
- Commits since 2026-09-26T16:17:29Z touching scripts/flow-worktree-sweep.sh or
  scripts/lane-serveability-check.sh: none. (fc23e10, 7e68b47 touch controls/ and
  ADR paths only.)
- Merged PRs since filing: 1255, 1270, 1274, 1275, 1279, 1280, 1283, 1284, 1286,
  1287, 1293, 1295, 1296, 1302 - none adds either control.
- Duplicate/superseding issues: none (#1268, #1272 adjacent only).
- Moved premise: since #1171 git is staged into the negative-controls CI step, so
  the sweep control runs in CI; unavailable_signal is still declared for git-absent.

## Section C - the approved plan
Sweep half approved as written. Lane half approved under option (d): a stub curl on
PATH inside run-case.sh, no CI staging of a real curl; transport not exercised.

1. `scripts/flow-worktree-sweep.sh` - add the NEGATIVE-CONTROL directive (comment only)
2. `controls/flow-worktree-sweep/control.json` - registration, detect + unavailable signals, limits (dry-run only)
3. `controls/flow-worktree-sweep/run-case.sh` - throwaway repo + linked worktree, stub gh, fake /proc; refuses inside a checkout
4. `controls/flow-worktree-sweep/cases/` - one bad (removable, sibling-prefix occupant) and good cases (dirty, unpushed, occupied-inside, pr-none, pr-open)
5. `controls/flow-worktree-sweep/anchors/constructed-bare-prefix-occupancy.sh` - constructed blind anchor
6. `docs/decisions/0008-instrument-negative-control-bound.md` - rows 8 and 14 only
7. `scripts/lane-serveability-check.sh` - add the NEGATIVE-CONTROL directive (comment only)
8. `controls/lane-serveability-check/control.json` - registration, detect + unavailable signals, limits (transport not exercised)
9. `controls/lane-serveability-check/run-case.sh` - puts the stub curl on PATH, refuses if curl resolves elsewhere
10. `controls/lane-serveability-check/stub-curl.py` - URL -> per-case fixture response, honours only the gate's flags
11. `controls/lane-serveability-check/cases/` - good-serving, bad-500-loader-killed, bad-200-with-error-field, bad-drops-connection
12. `controls/lane-serveability-check/anchors/constructed-registration-only.sh` - pre-#895 version+tags gate

Scope: ~16 paths, mostly fixtures and prose. Risks: run-case must not measure the
enclosing checkout; fake pids above pid_max; no deletion path exercised (dry-run);
stub curl proves classification, not transport. Harness/census edits (if needed)
stop the run and go back to the orchestrator.
