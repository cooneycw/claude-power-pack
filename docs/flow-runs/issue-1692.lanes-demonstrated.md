# Lanes demonstrated - issue #1692

Added retroactively with the #1711 change: the three pull requests under #1692 merged without this file, and their evidence is in the pull requests named below.

What was actually exercised for each lane the plans answered "will test". Run 1 (PR #1722) was approved before plans carried a lanes table, so it has no row here; its evidence is in that pull request.

| Lane | What was demonstrated |
|---|---|
| Checkout | All three runs were linked worktrees. Run 3 (PR #1750, the `.PHONY` reader): `tests/test_cicd_makefile.py`, three new tests failing on 68d5fedf and passing on the fix, one passing on both. The main checkout was not separately exercised |
| Harness | Run 2 (PR #1733): Codex mirrors rebuilt and `tests/test_codex_skill_sync.py` passed; a live Codex run was not exercised. Run 3 answered not applicable |
| Project state | Run 2: the finish gate's runner lane for real, and its fallback lane through stubbed controls; bash 3.2 and macOS sed were not exercised for the `--help` change. Run 3 answered not applicable |
