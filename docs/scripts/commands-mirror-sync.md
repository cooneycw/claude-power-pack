# `commands-mirror-sync` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `commands-mirror-sync`

- commands-mirror-sync - drift guard + refresher for hosts serving the command surface from an out-of-repo byte-copy of `.claude/commands/` (e.g. `~/Projects/.claude/commands`); `--check` reports drift, `--write` refreshes (prune + copy); wired into `/cpp:update` Step 7.8, opt-in and fail-open (#582)
