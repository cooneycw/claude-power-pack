# Flow run record - issue #1860

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=f9f08a92b206474696c5353719e9a90e -->
## Run 1

- Run-id:            f9f08a92b206474696c5353719e9a90e
- Run-start:         2ff42c8db87dfc06dcc43abf5aa7d2f0c368a8b5
- Issue:             #1860
- Base SHA:          2ff42c8db87dfc06dcc43abf5aa7d2f0c368a8b5
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), interactive reply "approved" in this session
- Recorded at:       2026-11-17T01:39:16Z

### Section B evidence
commits: none on origin/main since filing (main at 2ff42c8d). PRs: none merged since filing. dup/super: none (searched; #767, #1626, #1491, #864, #485 unrelated).

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | not applicable - the detector reads no checkout layout (main checkout, linked worktree behave the same); the API-only download path is checked post-merge by a GraphQL round-trip, outside the lanes vocabulary |
| Harness | not applicable - no command document or Codex mirror changes |
| Driver | not applicable - no driver docs touched |
| Coordination | not applicable - no Kyle path |
| CI provider | will test - Woodpecker negative-controls runs controls/check-oscillation via --from-log, no git in the image |
| Project state | not applicable - CPP-internal detector |
| Toolchain version | not applicable - stdlib only; git --format behaviour unchanged |
| Clone shape | not applicable - shallow-history handling unchanged |
| Run location | not applicable - unchanged |
| Gate target | not applicable - CPP itself only |
| Wave role state | not applicable - no wave state |
| Reader: make verify / oscillation target | will test - live run on this repo still examines commits and reports the same verdict shape |
| Reader: check-negative-controls.py | will test - --control controls/check-oscillation: BAD reads BAD, GOOD reads GOOD, anchor blind as before, provenance verified |

### Section C - the approved plan
1. `docs/architecture/c4-l1-context.png` - delete (unreferenced stale screenshot)
2. `docs/architecture/c4-l2-container.png` - delete
3. `docs/architecture/c4-l3-cicd.png` - delete
4. `docs/architecture/c4-l4-config-runner.png` - delete
5. `scripts/check-oscillation.py` - printable commit-header marker shared by GIT_LOG_ARGS and parse_log
6. `controls/check-oscillation/anchors/constructed-single-commit-check-oscillation.py` - same format change, blindness intact
7. `controls/check-oscillation/control.json` - re-pin anchor sha256
8. `controls/check-oscillation/cases/bad-reversed/history.log` - recapture with new GIT_LOG_ARGS
9. `controls/check-oscillation/cases/good-monotonic/history.log` - recapture
10. `tests/test_oscillation_control.py` - regression test: capture and committed cases are NUL-free UTF-8
11. `docs/scripts/check-oscillation.md` - bullet recording why the marker is printable

Scope: 11 files, ~60 lines plus 4 binary deletions and 2 recaptured fixtures.
Risks: marker collision with a diff line (mitigated: line-start anchored, diff body lines are prefixed); control must still discriminate (re-prove via check-negative-controls); external readers of the PNGs (accepted, HTML sources remain).
