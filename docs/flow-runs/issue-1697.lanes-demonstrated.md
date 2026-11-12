# Lanes demonstrated - issue #1697

RETROACTIVE RECORD, written 2026-11-12 after Part 2 merged as #1749 (merge
commit 0bf7ba72). That pull request merged without this file; its rows are
taken from the pull request's "Lanes and readers for this change" table.
Part 1 (#1738) merged before the file was asked for.

| Lane | What was demonstrated |
|---|---|
| Harness | The generated `flow-eli5` Codex skill, built by `codex-skill-sync.py` into a temporary directory, carries the reader sentence (`tests/test_changed_output_readers.py::test_the_generated_plan_gate_skill_carries_the_reader_sentence`). `/codex:code_review` is not generated as a Codex skill and has no mirror. No Codex-driven run was exercised. |
| Project state | The review hand-over block run in a temporary repository with a lane file and without one: the reader question is asked either way (`tests/test_changed_output_readers.py`). |
| Reader: tests/test_lanes_contract.py, which reads the prompt text between fixed markers | NOT as planned. The plan said it would run unchanged; it did not: the wording it located text by was reworded, so eight of its lines and one line of `tests/test_lane_file.py` moved with it, one assertion added and none removed. Both then ran against the real edited documents. |
