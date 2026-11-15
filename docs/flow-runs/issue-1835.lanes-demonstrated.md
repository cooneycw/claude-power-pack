<!-- lanes-demonstrated run=8090ef6e5a5049b0a8f762c08afcec3a plan=4df2a6498b2706e49b14f900c3d2b8e57bad6f4233d26bb8bfa9d0cc87551935 -->

| Lane | Result | Evidence |
|---|---|---|
| Harness | passed | Claude install sources: `tests/test_check_doc_helper_flags.py::test_the_live_repository_is_clean` scans `.claude/commands`, `.claude/skills`, `templates` (the checkout `~/.claude` links). Codex install not run: the generated `codex/skills` mirrors are not scanned, as the plan stated |
| Driver | passed | delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`): `make delegated-core-check` (3 drivers match the core) and `driver-parity-check` in the finish gate; `/flow:auto` (Claude implements) doc scanned, unchanged |
| CI provider | not run | Woodpecker: pending the PR pipeline; GitHub Actions not run |
| Toolchain version | passed | the host or container's installed versions: finish gate on this host (python3, uv). CI's pinned uv and Python image: pending the PR pipeline |
| Run location | passed | invoked from the CPP root: `make doc-helper-flags-check`; from another directory: `tests/test_check_doc_helper_flags.py::test_runs_from_another_directory` |
| Reader: delegated worker sessions | passed | `make delegated-core-check` proves the three rendered docs carry the corrected command; the corrected command sent (FLOW_MAILBOX: sent) by hand at Step 3 |
| Reader: make verify / Woodpecker CI | passed | `python3 scripts/check-negative-controls.py --strict --control controls/doc-helper-flags`: 4 BAD cases BAD, GOOD GOOD, anchor blind |
