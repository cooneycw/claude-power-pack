# Codex skills (generated)

Per-command Codex SKILL.md skills (issue #555, companion to codex-power-pack
epic cooneycw/codex-power-pack#64) emitted from the single source of truth
`.claude/commands/<family>/*.md` (ADR 0001 section 5). This surface superseded
the flat `codex/prompts/` prompts, retired at the #556 cutover. codex-power-pack
vendors this source (pull model, issue #556 / codex-power-pack#75) rather than
receiving a push from CPP.

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
- Drift gate: `tests/test_codex_skill_sync.py` runs `--check`, plus an explicit
  `codex-skills-check` step in `.woodpecker.yml` (issue #556)
- Never hand-edit dirs whose SKILL.md carries the GENERATED marker; edit the
  source command and re-run `--write`. Hand-curated skill dirs (no marker)
  are never touched.
