# Flow run record - issue #1824

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=35e6a3ad61d941cc965af390117c8b4e -->
## Run 1

- Run-id:            35e6a3ad61d941cc965af390117c8b4e
- Run-start:         d90712eed2523fc2128674a54ffa7923f8bf2c54
- Issue:             #1824
- Base SHA:          d90712ee
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session reply "approved"
- Recorded at:       2026-11-14T17:40:00Z

### Section B evidence
No commits to scripts/flow-finish-gate.sh or its tests since the issue was filed; base d90712ee. Check introduced by #1793 (e252dd53). No merged PRs since filing; no duplicate issues (#1824 filed this session from the #1822 gate failure).

### Section C - the approved plan
1. `scripts/flow-finish-gate.sh` - cpp_environment_check accepts a bare X.Y cfg value as minor-only evidence; all cfg minors must agree; full values still agree in full; garbage still invalid
2. `controls/flow-cpp-runtime/run-case.py` - modes major-minor-runtime (GOOD), major-minor-disagreeing (BAD), major-minor-contradictory (BAD)
3. `controls/flow-cpp-runtime/cases/good-major-minor-runtime/case.json` - GOOD case
4. `controls/flow-cpp-runtime/cases/bad-major-minor-disagreeing/case.json` - BAD case
5. `controls/flow-cpp-runtime/cases/bad-major-minor-contradictory/case.json` - BAD case
6. `controls/flow-cpp-runtime/control.json` - register the three cases, update limits
7. `tests/test_cpp_environment_preservation.py` - real-uv venv rewritten to version_info = 3.11 is preserved and passes; cfg 3.12 with real 3.11 interpreter refused unverified

Scope: small, 7 files.
Risks: widening a gate (X.Y is weaker evidence; the interpreter probe must still agree and new BAD cases pin disagreement); existing historical anchors may score new BAD cases unexpectedly - run the control and report.

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | not applicable | venv path from CPP_DIR, not checkout layout |
| Harness | not applicable | shell gate, no mirror content |
| Driver | not applicable | same gate for every driver |
| Coordination | not applicable | runs before admission |
| CI provider | not applicable | no CI helper touched |
| Project state | will test | new cases cover an existing venv; existing bootstrap case covers absent |
| Toolchain version | will test | real-uv test uses host uv; control cases cover both cfg spellings |
| Clone shape | not applicable | no history access |
| Run location | not applicable | gate runs from target cwd as today |
| Gate target | not applicable | CPP's own runtime only |
| Wave role state | not applicable | no wave code |

Reader: the FLOW_FINISH_GATE fail (cpp-runtime-environment-unverified ...) line - flow:auto/finish verdict line (format unchanged) and the control's run-case asserts (unchanged).
