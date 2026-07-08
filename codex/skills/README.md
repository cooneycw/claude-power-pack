# Codex skills (generated)

Per-command Codex SKILL.md skills (issue #555, companion to codex-power-pack
epic cooneycw/codex-power-pack#64) emitted from the single source of truth
`.claude/commands/<family>/*.md` (ADR 0001 section 5). This surface supersedes
the deprecated flat prompts in [`codex/prompts/`](../prompts/) and is what the
cross-repo publish (issue #556) syncs into codex-power-pack.

Layout per skill:

```
<family>-<command>/
    SKILL.md        # frontmatter (name/description) + Codex harness
                    # adaptations + body inline (short commands)
    reference.md    # full command body (long commands, loaded on demand)
    scripts/<name>  # helper scripts the body references, bundled
                    # byte-identical from scripts/
```

- Generator: `scripts/codex-skill-sync.py` (`make codex-skills` /
  `make codex-skills-check`; `--install` copies to `~/.codex/skills/`)
- Drift gate: `tests/test_codex_skill_sync.py` runs `--check` in CI
- Never hand-edit dirs whose SKILL.md carries the GENERATED marker; edit the
  source command and re-run `--write`. Hand-curated skill dirs (no marker)
  are never touched.
