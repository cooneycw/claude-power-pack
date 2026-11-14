# Flow run record - issue #1825

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=7d37e7afc4cf4937b56e7f5c435af7f9 -->
## Run 1

- Run-id:            7d37e7afc4cf4937b56e7f5c435af7f9
- Run-start:         d90712eed2523fc2128674a54ffa7923f8bf2c54
- Issue:             #1825
- Base SHA:          d90712ee
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session reply "approve"
- Recorded at:       2026-11-14T18:05:00Z

### Section B evidence
No commits to tests/test_runner_target_path.py since filing; base d90712ee; no merged PRs since; no duplicates (#1825 filed from the #1824 gate run). Reproduced 8 failed / 20 passed on d90712ee and on the #1824 branch.

### Section C - the approved plan
1. `tests/test_runner_target_path.py` - run_probe(): when uv is not on the fixed target_path, APPEND shutil.which("uv")'s directory; assert uv resolves on target_path and python3 still resolves to the target venv; CI layout unchanged

Scope: tiny, 1 file.
Risks: shadowing (appended last; python3 assert pins it); red visible only on this host layout, CI cannot show red.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | not applicable | no checkout logic |
| Harness | not applicable | test only |
| Driver | not applicable | test only |
| Coordination | not applicable | test only |
| CI provider | not applicable | no CI helper touched |
| Project state | not applicable | no adopted-file logic |
| Toolchain version | will test | ~/.local/bin uv host red then green; CI /usr/local/bin layout unchanged |
| Clone shape | not applicable | no history |
| Run location | not applicable | no cwd logic |
| Gate target | will test | still exercises consumer-PATH boundary with target venv first |
| Wave role state | not applicable | no wave code |

Reader: none - test fixture, no product output.
