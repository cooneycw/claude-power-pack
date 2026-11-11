# `speckit-tasks-to-issues` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `speckit-tasks-to-issues`

- speckit-tasks-to-issues
- speckit-tasks-to-issues is a stable-path helper (#1618) - command documents print `~/.claude/scripts/speckit-tasks-to-issues.sh`, because a relative `./scripts/` path exists only inside the CPP checkout. It is in the `flow-helpers-install` `HELPERS` set beside `speckit-context.py`, which it resolves from its own directory, so the unattended install reaches it too. It is deliberately absent from the permissions template: it creates GitHub issues, so a prompt is correct
- speckit-tasks-to-issues one separator, empty fields survive (#700) - the `gh issue list` dedup records are joined and split on ASCII unit separator `\037`, never tab, and the jq escape is DERIVED from the shell byte so producer and reader cannot drift. Same defect class as #698 (tab is IFS *whitespace*, so a run collapses and an empty field vanishes, shifting every later field up one slot) but latent rather than live: field 1 is `.number`, which GitHub never leaves empty, so the safety rested on an invariant of an external tool's output recorded nowhere - and it would have decayed into shifted fields, not an error. `tests/test_speckit_tasks_to_issues.py` pins it with an EMPTY-first-field fixture (an all-populated fixture passes against the broken code and proves nothing - #698's lesson) plus a class guard asserting no whitespace-IFS `read` returns to `scripts/`
