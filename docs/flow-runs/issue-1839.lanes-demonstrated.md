# Lanes demonstrated - issue #1839

<!-- lanes-demonstrated run=01c876d2223847e588c20aaf5f3a1766 plan=25fe36bd825a3047404b6d2ddc678c99ab753cf93c5fb72de5fc7046f9fb8909 -->

| Lane | Result | Test or observation |
|---|---|---|
| Harness | passed | Claude install: `test_the_live_repository_is_clean` scans the live `.claude/commands`, `.claude/skills` and `templates` (live gate: `ok - 347 flag(s) on 257 invocation(s) in 126 doc(s) checked`); Codex install: `codex/skills` mirrors are ignored build output and are not a scanned surface |
| CI provider | passed | Woodpecker PR pipeline 3915 on `cdfed69c` (https://woodpecker.essent-ai.com/repos/1/pipeline/3915): success, including `doc-helper-flags-check` and the negative-controls step |
| Toolchain version | passed | CI: pinned `ghcr.io/astral-sh/uv:python3.11-bookworm-slim` image (pipeline 3915); host: Python 3.12.3, uv 0.12.5 (`tests/test_check_doc_helper_flags.py` 25 passed, `flow-finish-gate.sh` ok) |
| Run location | passed | from the CPP root: `flow-finish-gate.sh` ran `make verify`; from another directory: `test_runs_from_another_directory` and `test_a_comment_inside_a_fence_cannot_quote_the_next_line` (runs with `cwd` outside the scanned tree) |
| Reader: make verify / Woodpecker doc-helper-flags-check | passed | verdict line and exit codes unchanged in format (`ok - ...` exit 0, `UNKNOWN_FLAG:` exit 1); one new stderr note line `note - N helper path(s) inside a shell comment, not invocations, unchecked`; `make verify` passed in the finish gate and pipeline 3915 passed |
| Reader: check-negative-controls.py (make negative-controls) | passed | `--strict --control controls/doc-helper-flags`: PASS, 9 BAD read BAD, 6 GOOD read GOOD, constructed anchor blind on every BAD case |
