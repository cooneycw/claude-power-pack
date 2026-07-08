# Codex custom prompts (DEPRECATED)

This flat custom-prompt surface (issue #446) is **deprecated pending cutover**
(issue #555): the per-command Codex skills under [`codex/skills/`](../skills/)
supersede it, and the codex-power-pack cross-repo publish (issue #556) will
retire this directory once the skill surface is consumed there.

Until then both surfaces stay generated and drift-checked:

- Source of truth: `.claude/commands/<family>/*.md` (ADR 0001 section 5)
- Generator: `scripts/codex-prompt-sync.py` (`make codex-prompts` /
  `make codex-prompts-check`)
- Never hand-edit files carrying the GENERATED marker; edit the source and
  re-run `--write`. The hand-curated `cpp-memory.md` (issue #433) is the one
  exception - it is not generated and never overwritten.
