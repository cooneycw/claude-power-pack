<!-- lanes-demonstrated run=340655a894e34a9e8efa02ff06c23a38 plan=3ba5aac381586b51d1bf67845d2d855723a2acd9486adbb83d600e372567af02 -->

| Lane | Result | Test or observation |
|---|---|---|
| Driver | passed | Both values. A per-path dump of context and flags over the live tree (274 helper paths, including `.claude/commands/flow/auto.md` and `templates/delegated-driver-core.md`, which render the delegated drivers) is byte-identical before (19e24318) and after (11b713ad). The dump reports the change on the #1842 input (`[quote]` before, `[cmd] --kind` after), so it can tell the two gates apart. |
| CI provider | passed | Woodpecker: PR pipeline 3919 green on fb1249b3 (https://woodpecker.essent-ai.com/repos/1/pipeline/3919), whose `doc-helper-flags-check` step runs the gate. GitHub Actions: not exercised here, and nothing runs this gate there. |
| Run location | passed | Invoked from the CPP root: `make verify` via `flow-finish-gate.sh`, `FLOW_FINISH_GATE: ok`. From another directory: `test_a_backtick_substitution_with_a_backslash_or_hash_is_unchecked` and `test_a_comment_inside_a_fence_cannot_quote_the_next_line` run the gate with cwd outside the scanned tree. |
