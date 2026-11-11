# `install-memory-harness` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `install-memory-harness`

- install-memory-harness - installs the harness-neutral common-memory surfaces so both Claude Code and Codex can reach the store: `~/.local/bin/cpp-memory` symlinked at the checkout's `scripts/cpp-memory`, and `~/.codex/prompts/cpp-memory.md` copied from `codex/cpp-memory.md` to give Codex its `/cpp-memory`. Claude Code already discovers the in-repo command, so only these two need installing. Idempotent, and re-run by `/cpp:update`
