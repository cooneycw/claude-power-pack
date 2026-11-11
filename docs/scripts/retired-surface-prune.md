# `retired-surface-prune` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `retired-surface-prune`

- retired-surface-prune - teardown for GENERATED file surfaces CPP retired but left behind in HOME (#575): curated by `.claude/retired-surfaces.yaml` (the list of record, sibling to `deprecated-mcps.yaml`) AND gated on the GENERATED marker, so hand-authored files (`~/.codex/prompts/cpp-memory.md`) and the user's own skills are preserved; `--check`/`--json`/`--plan` are read-only, `--prune NAME` MOVES owned items to a timestamped `<path>-retired-<date>` sibling rather than deleting them; wired into `/cpp:update` Step 7.9, per-surface and user-confirmed
