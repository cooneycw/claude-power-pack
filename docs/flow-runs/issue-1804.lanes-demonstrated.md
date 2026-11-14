# Lanes demonstrated - issue #1804

| Lane | Result | Evidence |
|---|---|---|
| Wave role state | passed | released legacy role returning: `tests/test_flow_wave_reregister_review_regressions.py::test_released_legacy_reuse_starts_empty[omitted,issue-only,full-same,different]` and `::test_released_legacy_restatement_keeps_what_is_supplied` pass on the branch; 4 of them fail on the pre-fix helper (the `different` control passes on both). Fresh/live role: `tests/test_flow_wave_registry.py`, cross-product, matrix, controls and wording suites, 696 passed. Not tested: a role released by current `release` (already empty; existing #1222 tests). |
