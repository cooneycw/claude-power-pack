# Flow run record - issue #1289

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1289 (PR A of two: detection and enumeration)
- Base SHA:          bdbe0fb
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 1798 in reply to ELI5 message 1796
- Recorded at:       2026-09-28T11:40:00Z

## Section B evidence
- Reproduced on bdbe0fb with detect_framework on temp trees: root Node + backend
  python/uv -> node/npm, backend absent; frontend/+backend/ -> multi, runner_commands
  {}; pyproject+manage.py -> django/unknown, runner_commands {}.
- MULTI end to end: generate_manifest -> check plan -> all gates SKIPPED, runner
  "completed WITH WARNINGS - SKIPPED GATES ... (no Makefile target and no configured
  tool)" - a warn, but a FALSE cause when a nested pyproject configures the tools.
- Commits since 2026-09-27 touching detector.py/models.py: none. Merged PRs since:
  1296, 1302, 1304, 1306. Duplicate/superseding: none.

## Section C - the approved plan
Split approved: PR A now (this record); PR B (no-Makefile runner path) after #1307.
Conditions: (1) the skipped-gate line names uncovered components instead of only
the false cause; (2) enumeration skips non-components, list stated in code, docs/
fixture pinned; (3) runner_resolution is reporting-only - single-root consumers'
generated output unchanged, pinned by control fixtures.

1. `lib/cicd/models.py` - Component record; FrameworkInfo.components and runner_resolution (state, reason, uncovered), additive in to_dict
2. `lib/cicd/detector.py` - always enumerate root + immediate non-excluded subdirs with per-component PM evidence; Python-family PM fallback covers Django; resolution derived
3. `lib/cicd/cli.py` - detect prints components and resolution
4. `lib/cicd/runner.py` - skipped-gate qualifier names uncovered components (condition 1)
5. `scripts/flow-finish-gate.sh` - skipped-gate cause says "at the repository root" (condition 1)
6. `tests/test_cicd_consumer_layouts.py` - fixture matrix with preconditions; reproduced cases red on bdbe0fb; consumer-output controls for single-root layouts

Scope: ~6 files, ~400 lines. Risks: always-enumerating adds components for stray
subdirs (bounded by the exclusion list, reported only); detection runs in the
runner only when gates were skipped; nothing is executed during detection.

## Part B - the approved plan (appended; base d24a408, after #1310 merged)
Approver: run45:orch, message 1798 ("B's plan is fine") and 1841/1976 (cut B from main after #1310).
Prototyped on bdbe0fb before approval: the shipped path already honours a declared
mypy scope, fails the run on a failing declared check, and skips-and-reports an
undeclared tool - so B is expected to be tests only; any code change it exposes goes
back to the orchestrator first.

7. `tests/test_cicd_consumer_runner_path.py` - a Makefile-less Python repo through BUILTIN_PLANS["check"] with a stub uv (argv recorded, nothing fetched): declared mypy scope reaches the argv, a failing declared check fails the run, an undeclared tool is skipped and reported
