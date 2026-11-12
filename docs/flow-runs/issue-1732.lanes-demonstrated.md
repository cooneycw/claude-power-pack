# Lanes demonstrated - issue #1732

| Lane | What was demonstrated |
|---|---|
| Checkout | Full clone and depth-1 clone: the fixture repository in `tests/test_negative_controls_provenance_run.py` is built both ways; the shallow one reads `UNCOMPARED` and deepening it turns that into `ok`. Linked worktree: the full gate ran in one on `d5ddb9cd` and compared 46 of 46 historical anchors. CI's deepened clone: PR pipeline 3754 lost its first `--unshallow` to a `shallow.lock` race with another step, recovered through the retry loop, and compared 46 of 46. |
| CI provider | Woodpecker: the `negative-controls` step log of PR pipeline 3754 was read. `CI_PIPELINE_EVENT` was `pull_request`, the flag was passed, and the closing line read `compared=46 uncompared=0`. The same log showed the step's own echo line saying "not passed"; that line is corrected in this change. No main-push pipeline has run this step yet, so "the flag is not passed on a main push" is shown by the test that runs the block, not by a real pipeline. GitHub Actions: not covered. |
| Project state | A tree whose controls carry only constructed anchors passes and says no historical anchor is registered (`test_a_control_with_only_constructed_anchors_is_as_green_as_before`). Not demonstrated against a second real repository. |
