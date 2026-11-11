# `cpp-memory` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `cpp-memory`

- cpp-memory - portable, harness-neutral entry point to the CPP common-memory ledger, callable identically from Claude Code, Codex or a plain shell and from ANY cwd. It resolves its own location THROUGH SYMLINKS to find the repo - which is what lets `~/.local/bin/cpp-memory` be a link rather than a copy - then runs `lib.cpp_memory` with the best available Python (`$CPP_MEMORY_PYTHON`, else `uv`, else system python3). Fail-open by design: a missing psycopg driver degrades to a local `.claude/learnings.md` rather than crashing
