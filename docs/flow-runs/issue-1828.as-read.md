<!-- flow-run n=1 id=27a4106219a0480c81ba6e6d810246f7 -->
## Run 1 - issue #1828 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1828
- Read at:      2026-11-14T18:29:24Z
- updatedAt:    2026-11-14T18:25:40Z   (context only - moves on comments and labels)
- Body digest:  c984365cbdda650deb823aab979215250ba4141276388d59783c9dc2570a56b7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6220 of 6220 (cap 16384)

### Body as read
## Problem

The finish gate's Kyle coordination branch (`scripts/flow-finish-gate.sh`, around lines 350-400) and the admission flag it reads (`scripts/coordination-admission.sh`) have five related gaps. Two are about what the gate tells people. Three are about tests and controls that pick up the host's admission state instead of a fixture-owned one. They all sit in the same seam, and one change can close them together.

### A. What the gate tells the queue and the operator

1. **The lease carries no identity.** `flow-finish-gate.sh:385` runs `kyle-lock run full-suite --wait "$_coordination_wait" -- ...` with none of the `--issue`, `--pr` and `--purpose` flags the client supports (`kyle-lock run --help`). In `kyle-lock status full-suite` a CPP gate therefore shows as `issue: null, pr: null, purpose: ""` under the shared principal `service:operator-host-<date>`. On 2026-11-14 the owner read the queue to decide whether to wait behind kyle #2474 or skip it, and could not tell which CPP run held request #142, or which repository or branch it was for. Every host-side CPP gate looks the same, so a stuck one cannot be told from a live one.
   Source: [Nit Store 6882166780](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6882166780), found running #1822.
2. **A queue timeout gets the generic message.** The `no grant within ${wait}s, no gate work started` message is printed only for `kyle-lock` exit 75. Measured on Kyle prod on 2026-11-13: a `--wait 60` that stayed queued for the whole window exits **10**, its last state. Kyle's `run` returns the last answer's code on expiry, and 75 means only that the authority was unavailable. A real queue timeout therefore falls through to `coordination supervisor exited 10 and the gate recorded no status`. A frozen expiry (exit 11) presumably does the same; that was not measured. The verdict is still FAIL, so the gate fails closed, but the #1678 message never reaches the operator.
   Source: [Nit Store 6853399053](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6853399053), evidence in kyle #2130 comment 6853394709.

### B. Host admission leaking into tests and controls

`scripts/coordination-admission.sh:18` reads the admission flag from `CPP_COORDINATION_ADMISSION_FILE`, and otherwise from a file under `$HOME` or `$XDG_CONFIG_HOME`. Several fixtures inherit the host's environment, so on a host with admission ON their result depends on that host:

3. **`tests/test_flow_finish_gate.py`:** fixture sites that do not set `CPP_COORDINATION_ADMISSION_FILE` (`_run_with_uv_stub`, `_gate`, `_enrolment_only` and others) inherit `HOME`. There is also a hand-written list of gate knobs that nothing reds when the gate grows a variable the list lacks.
   Source: [Nit Store 6819640932](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6819640932).
4. **`tests/test_negative_controls.py:44` (`run_harness`):** the three expected-PASS variants of `test_the_real_resume_control_judges_its_good_case_by_the_resume_signal` fail as UNSIGNALLED when admission is on and `kyle-lock` is unavailable. The no-source variant passes because it expects failure, which hides the contamination.
   Source: [Nit Store 6868589796](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6868589796).
5. **`controls/flow-finish-gate/run-case.sh:120`** forwards the host environment. Seven finish-gate controls then go UNSIGNALLED under `make negative-controls` with admission on and no `kyle-lock` on PATH. Also, `tests/conftest.py:731` (`uv_child_env`) allowlists child environment keys and drops `CPP_COORDINATION_ADMISSION_FILE`. Its callers `tests/test_cpp_environment_preservation.py` (the `--plan` cases) and `tests/test_cpp_runner_runtime.py` therefore regain host admission even when the outer run isolated it.
   Source: [Nit Store 6868626536](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6868626536).

Why B matters: a test or control that reports UNSIGNALLED, or fails, because of the host's admission flag says nothing about the code under test. Fixing it by supplying the real `kyle-lock` would be worse, because small fixtures would then take real fleet `full-suite` leases.

## Fix

- **A1.** Pass `--purpose "cpp finish gate: <repo> <branch> <short-sha>"`, and pass `--issue`/`--pr` when they can be derived (the branch's `issue-<N>` and `gh pr view`). When a value cannot be derived, omit it; never guess.
- **A2.** Treat `kyle-lock` exits 10 and 11 with no recorded gate status like 75 for the message: no grant within `${wait}s`, naming the last state (queued or frozen). Leave the verdict unchanged.
- **B.** Give every fixture and control here a fixture-owned admission state:
  - an explicit `CPP_COORDINATION_ADMISSION_FILE` pointing at an owned absent or `off` file, plus an owned `HOME`;
  - carry `CPP_COORDINATION_ADMISSION_FILE` through `uv_child_env`.
  The dedicated coordination controls (`controls/flow-finish-coordination`) keep covering admission itself. Operational admission stays ON.

## Acceptance

- [ ] A known-good gate run shows a non-empty `purpose` naming repo, branch and sha in `kyle-lock status full-suite` (a fake `kyle-lock` that records its argv is enough). A test fails if the flags are dropped.
- [ ] A fake `kyle-lock` that exits 10 (and one that exits 11) without starting the command produces the `no grant within` message. On the pre-fix gate that case prints the generic `supervisor exited 10` line, which is the red case.
- [ ] With the host admission file ON and no `kyle-lock` on PATH, the following pass:
  - `tests/test_flow_finish_gate.py`
  - the resume-control test in `tests/test_negative_controls.py`
  - `make negative-controls`
  - `tests/test_cpp_environment_preservation.py`
  - `tests/test_cpp_runner_runtime.py`

  Run each once with admission ON before the fix to show the red.
- [ ] `controls/flow-finish-coordination` still discriminates: a refused supervisor starts no gate work.

## Source

Aggregated from five Nit Store #1725 comments (links inline). The lease-metadata item was raised by the owner on 2026-11-14, who asked for it to be elevated together with compatible nit-store items.

<!-- end of body -->
