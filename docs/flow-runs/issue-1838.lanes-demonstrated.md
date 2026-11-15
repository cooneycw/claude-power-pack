# Lanes demonstrated - issue #1838

<!-- lanes-demonstrated run=068669874b7848aa8245bc9842e2b48c plan=d33f25a85d5a18d0a157c07cf036bafde2f26634ab43592191a6b7f7b8a0383c -->

| Lane | Result | Test or observation |
|---|---|---|
| Checkout | passed | main checkout: `tests/test_codex_skill_sync.py` charter tests on the `tmp_repo` fixture; linked worktree: the whole suite ran from this run's worktree under `flow-finish-gate.sh` (FLOW_FINISH_GATE: ok) |
| Harness | passed | Codex install: `test_install_publishes_the_mirrored_charter`; Claude install: `test_a_planted_charter_is_not_registered_as_a_command` with its `flow-CHARTER` control, and `tests/test_skills_check_charters.py` |
| Project state | passed | adopted: `test_a_charter_is_mirrored_with_its_yaml_block_first`; not adopted: `test_without_a_charter_nothing_is_mirrored` (no `charters/`, no error, nothing mirrored) |
| Reader: Codex sessions reading the mirrored CHARTER.md | passed | `test_a_charter_is_mirrored_with_its_yaml_block_first` reads the real generated copy |
