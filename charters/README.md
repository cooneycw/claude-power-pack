# Charters

A charter is a `CHARTER.md` that says what a command promises: why it exists,
what it must always do, and what it must never do. skillc's skill-gauntlet
checks each command against it. The format is skillc's, defined in its
`docs/specs/contracts.md` ([skillc PR #746](https://github.com/cooneycw/skillc/pull/746));
this file does not restate it.

## Where a charter lives

| Covers | Charter |
|---|---|
| The slash command `.claude/commands/<family>/<command>.md` | `charters/<family>/<command>/CHARTER.md` |
| The skill `.claude/skills/<name>/` | `.claude/skills/<name>/CHARTER.md`, beside `SKILL.md` |

So `charters/flow/auto/CHARTER.md` covers `/flow:auto`.

Not beside the command: Claude Code registers every `.md` under
`.claude/commands/` as a command, so a charter there becomes a bogus
`/flow:CHARTER`. Not in `codex/skills/`: that tree is generated, and a charter
written there is overwritten or orphaned.

## What the generator does with it

Each charter's YAML block carries `subject:`, the path of the command file it
covers, for example `subject: .claude/commands/flow/auto.md`.

`scripts/codex-skill-sync.py` copies each charter into its generated Codex
skill (`codex/skills/<family>-<command>/CHARTER.md`) with a GENERATED marker
after the YAML block. Its `--check` fails on a charter whose path, command file
or `subject:` do not agree, and on any other file in this directory. Edit the
charter here, never the copy.

Changing a charter is the owner's decision.
