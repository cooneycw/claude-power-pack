# `friction-log` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `friction-log`

- friction-log - the capture half of the grill-me cycle (#426): appends one JSON object per friction event to an append-only buffer, which `/self-improvement:retro` later drains. The buffer resolves to the MAIN repo's `.claude/friction.jsonl` via `git-common-dir`, so signals captured inside a `/flow:auto` worktree survive its removal at cleanup (#471). Fail-open by construction - it NEVER exits non-zero and NEVER blocks a run, even on bad input or an unwritable path, because a flow must not break because its flight recorder could not write. Called on every step of every run, success OR failure, since the richest friction is on the runs that fail partway
