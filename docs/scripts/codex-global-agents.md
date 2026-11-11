# `codex-global-agents` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `codex-global-agents` (#1441)

- codex-global-agents - builds Codex's GLOBAL instructions from Claude's (#1441): `--write` makes `~/.codex/AGENTS.md` a generated header + `~/.claude/CLAUDE.md` verbatim + a `## Codex-only additions` section from the owner's host-local `~/.codex/AGENTS.local.md` (never `AGENTS.override.md`, which Codex reads INSTEAD of `AGENTS.md`). A copy, not a pointer: #1071 found Codex stops at a thin `AGENTS.md` unless told to follow it. `--write` refuses to replace a hand-written or hand-edited file without `--adopt`, which backs it up as `AGENTS.md.pre-cpp-<UTC>`; it never creates `~/.codex`. `--check` (default) is report-only, `CODEX_GLOBAL_AGENTS: current|stale|hand-edited|unmanaged|absent|overridden|not-applicable|unknown`, exits 0/3/3/3/3/3/5/4 (`overridden`: a non-empty `~/.codex/AGENTS.override.md`, which Codex reads INSTEAD; an additions file that exists but cannot be read, including a dangling symlink, is `unknown`, never absent), and lists any non-repository `AGENTS.md` in `$HOME` or `~/Projects` without changing the verdict. Wired into `/cpp:status` Tier 5; building is opt-in (`make codex-global-agents`), not part of `/cpp:init` or `/cpp:update`. Negative control `controls/codex-global-agents`
