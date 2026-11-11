# AGENTS.md

**The rules for working in this repository are in [`CLAUDE.md`](CLAUDE.md). Read
it. This file does not restate them, and where the two could be read as
disagreeing, `CLAUDE.md` is the rules.**

This file exists because Codex looks for `AGENTS.md` and would otherwise find no
agent context at all. It carries only what is different for a Codex session -
facts that cannot be inferred from the tree, or that are wrong if inferred from
`CLAUDE.md` alone. Everything else resolves through the pointer above.

## What is different here for Codex

**The Codex skill surface is generated and not tracked.** `codex/skills/` is
ignored build output (issue #1670, ADR 0013): only its README is in git. Edit
the source under `.claude/commands/**`; `make codex-skills` builds the tree when
you want to read it, and `make codex-install` builds, checks and installs it.
Never edit `codex/skills/` directly, and never `git add` it: the next build
overwrites the edit, and an install refuses a tree that differs from its sources.

**Skills arrive as named Codex skills, not slash commands.** Command documents
are written as `/flow:auto`, `/project:next` and so on. On this surface they are
Codex skills named `flow-auto`, `project-next`. A `/name:thing` in any document means
the skill `name-thing` here, where one is generated: a few commands are Claude-only
(`/cpp:init`, and every `/spec`, `/codex`, `/qwen` and `/gemma` command), and have
no Codex skill.

**Codex state is separate.** Configuration, credentials and installed skills live
under `~/.codex/`, never `~/.claude/`. The two namespaces stay isolated, and
`make codex-install` writes only under `~/.codex/` - the skills in
`~/.codex/skills` and an install lock beside them.

**Execution is governed by Codex.** Its own sandbox and approval model decide
what runs. Where a document describes Claude's permission behaviour, that
description is about the other surface; the mechanism here is Codex's.

## Two obligations this surface carries

**Route supplemental findings to the Nit Store, the open issue `scripts/nit-store-resolve.sh` prints.**
Its number changes at each monthly rollover, so ask the resolver and never remember one.
Something true and worth fixing, found while doing something else, goes there as
one comment per finding rather than widening the change in hand.

**Reciprocal review reaches this surface.** A change generated into
`codex/skills/` is reviewable here, not only on the Claude side; a review that
never reads the generated output is not reviewing what ships. That output is no
longer in the diff, so build it (`make codex-skills`) and read it there.
