<!-- lanes-demonstrated run=5a0c6451735d4d52bdf8a2014b16e670 plan=d842a99f8dbf04b683ea2e9898f262537210991b18ae1f3e1a3598818c18761c -->

# Lanes demonstrated - issue #1823 run 1

| Lane | Result | Evidence |
|---|---|---|
| Checkout | passed | linked worktree: every test in `tests/test_flow_plan_record_lanes.py` builds a temporary repository and `test_the_clause_is_the_same_from_a_plain_repository_and_a_linked_worktree` runs the new rows in both; the controls `controls/flow-plan-record-lanes` and `controls/flow-plan-record-lanes-verdict` run in throwaway repositories. Main checkout of CPP itself: not run |
| Harness | passed | Claude install: the helper run directly by the tests and controls, and this run's own re-approval and compliance with it. Codex install: not run (mirrors built by `make codex-skills`, no live Codex session) |
| Driver | passed | `/flow:auto`: `tests/test_flow_auto_plan_gate.py::test_following_the_stderr_note_clears_the_clause` follows the new note; delegated drivers: `controls/delegated-{codex,qwen,gemma}-plan-lanes` with three-column rows and `tests/test_lanes_contract.py::test_the_delegated_exemption_names_every_answer_that_owes_a_result`. A live delegated run: not run |
| Project state | passed | adopted: every lane-file case; not adopted: `good-no-lane-file` in both controls and `test_the_note_is_silent_where_nothing_is_owed[no-lane-file]` stay silent |
