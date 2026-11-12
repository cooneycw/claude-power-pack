# Lanes demonstrated - issue #1728

Added retroactively with the #1711 change: PR #1753 merged without this file, and its evidence is in that pull request.

What was actually exercised for each lane the plan answered "will test".

| Lane | What was demonstrated |
|---|---|
| Checkout | `tests/test_flow_finish_gate.py` in a linked worktree: four new tests failing on the script at 68d5fedf and passing on the fix; the existing re-run tests passing on both. The main checkout was not separately exercised |
| Harness | `tests/test_codex_skill_sync.py` passed in the finish gate. A live Codex run was not exercised |
| Project state | The fallback lane through a stubbed `make` (26 failures over the cap are not re-run; a two-id warning counts 2), and the runner lane through a stubbed runner JSON. The parser returned the same ids under gawk, mawk and busybox awk; the CI image's awk is mawk 1.3.4, measured from the pinned image. bash 3.2 and BSD awk were not exercised |
