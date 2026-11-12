# Lanes demonstrated - issue #1691

This file covers the first change for the issue (comments, help headers, documents and two test files; no executable line changes). The second change adds its own rows.

| Lane | What was demonstrated |
|---|---|
| Checkout | `tests/test_flow_wave_reregister_matrix.py` runs every re-registration case from three working directories - the main checkout, a linked worktree, and a directory outside any repository - and every case answers the same from each (29 cases, 88 tests with the two-sidedness check). |
| Harness | Claude install: the corrected `--help` headers are read back by running each helper's own help path, which prints the header of the file it is run from (the header tests for the registry, mailbox, lexicon and exit lines, 125 tests). Codex install: not covered - the generated mirrors are rebuilt and checked by the gate, and no Codex session is run. |
| Coordination | `tests/test_flow_wave_watch_delivery.py` drives the real mailbox helper in an isolated mailbox root: one wake delivers every unread message, a peeking wake acknowledges none, and one orchestrator wake drains two workers' inboxes (5 tests). With the watch made to read only the first box, the two-inbox test fails and the other four pass. Not demonstrated: delivery between two live sessions. |
