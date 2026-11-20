<!-- lanes-demonstrated run=ba462601dcef4525a733360a24ef3fd9 plan=b372cdbea777db5bc3381daa430881a0347ddfd878f8b8238b75aaf24d8a1e0e -->

| Lane | Result | Evidence |
|---|---|---|
| CI provider | passed | Woodpecker PR pipeline 3946 (https://woodpecker.essent-ai.com/repos/1/pipeline/3946) green on 09826179, suite and counter-model enrolment; GitHub Actions and none recorded not run. The tests are provider-independent git fixtures, so this shows the suite passes in CI, not provider-specific behaviour |
| Project state | passed | adopted (move after review): `tests/test_counter_model_adapters.py::test_plan_record_only_commits_after_review_bind_the_reviewed_head`; not adopted (no move): `::test_no_move_records_no_plan_record_move` and the existing binding tests |
