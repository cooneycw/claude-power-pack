# `check-ignored-additions` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `check-ignored-additions`

- check-ignored-additions - advisory guard warning when a blanket-ignore rule silently swallowed a file the repo should track; skips a short allow-list of files git-ignored by design (env-only `.claude/` runtime state such as `settings.local.json`/`friction.jsonl`) so it never cries wolf on them (#504)
- check-ignored-additions blocks in a linked worktree (#1258) - a flow worktree is created clean from a tracked tree, so a non-scratch ignored file in it was written by that run: the class that ships a clean clone without a file something reads at run time (#1144's ownership manifest). Exit 3 there; the primary checkout stays advisory; `--advisory` forces exit 0, `--strict` exits 3 anywhere. `.claude/runs/` is by-design runtime state (a failed gate leaves its run JSON there when the runner could not resolve a git directory, or on a pre-#1409 runner), so it never blocks
- check-ignored-additions NAMES `.claude/gate-scratch.txt` in its finding message (#1706). The repo-declared remedy for gate output had existed since #864's follow-up while five sessions reported the same block on kyle's `dashboard-runs/` and skillc's `reports/`: nothing a blocked session read mentioned the file. One stderr line, added after the existing ones in both modes; exit codes and the `CHECK_IGNORED_ADDITIONS_MODE=` marker, which stays the last line, are unchanged. It prints the file the guard actually reads, so an override names the override.
