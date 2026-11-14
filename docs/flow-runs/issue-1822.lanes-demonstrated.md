| Lane | What was demonstrated |
|---|---|
| Driver | `tests/test_lanes_contract.py` compares the answers offered by the template and all three rendered delegated drivers (`codex`, `qwen`, `gemma` `auto.md`) with `LANE_ANSWERS` as sets. It failed on all four surfaces on d90712ee and passes now. Red mutations (offering `needs a decision`, dropping `will refuse`) are reported. `/flow:auto` offers no list; `/flow:eli5` is checked the same way. `tests/test_delegated_plan_lanes.py` still passes for all three drivers |
| Project state | `controls/flow-plan-record-lanes` PASS: `good-no-lane-file` (a project with no lane file) still stamps, and the new `bad-answer-runs-past-the-phrase` (adopted lane file) is refused by the fix and stamped by the pre-fix helper |
