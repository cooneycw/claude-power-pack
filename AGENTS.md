# AGENTS.md

**The rules for working in this repository are in [`CLAUDE.md`](CLAUDE.md). Read
it. This file does not restate them, and where the two could be read as
disagreeing, `CLAUDE.md` is the rules.**

This file exists because Codex looks for `AGENTS.md` and would otherwise find no
agent context at all. It carries only what is different for a Codex session -
facts that cannot be inferred from the tree, or that are wrong if inferred from
`CLAUDE.md` alone. Everything else resolves through the pointer above.

## What is different here for Codex

**The Codex skill surface is generated.** `codex/skills/` is build output. Edit
the source under `.claude/commands/**`, then run `make codex-skills`. Never edit
`codex/skills/` directly: the next regeneration overwrites it, and the parity
gate reds on the drift in between. This is the one hazard the repository does not
otherwise announce.

**Skills arrive as named Codex skills, not slash commands.** Command documents
are written as `/flow:auto`, `/project:next` and so on. On this surface they are
Codex skills named `flow-auto`, `project-next`. A `/name:thing` in any document means
the skill `name-thing` here.

**Codex state is separate.** Configuration, credentials and installed skills live
under `~/.codex/`, never `~/.claude/`. The two namespaces stay isolated, and
`make codex-install` writes only under `~/.codex/` - the skills in
`~/.codex/skills` and an install lock beside them.

**Execution is governed by Codex.** Its own sandbox and approval model decide
what runs. Where a document describes Claude's permission behaviour, that
description is about the other surface; the mechanism here is Codex's.

## Two obligations this surface carries

**Route supplemental findings to the Nit Store, [cpp#864](https://github.com/cooneycw/claude-power-pack/issues/864).**
Something true and worth fixing, found while doing something else, goes there as
one comment per finding rather than widening the change in hand.

**Reciprocal review reaches this surface.** A change generated into
`codex/skills/` is reviewable here, not only on the Claude side; a review that
never reads the generated output is not reviewing what ships.
