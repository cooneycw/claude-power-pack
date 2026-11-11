# Codex skills (generated build output)

**Nothing in this directory except this README is tracked in git** (issue #1670,
ADR 0013, `docs/decisions/0013-codex-mirrors-are-build-output.md`). The
skill directories are built on demand with `make codex-skills` and are ignored.
A fresh clone holds only this file until something builds them.

Per-command Codex SKILL.md skills (issue #555, companion to codex-power-pack
epic cooneycw/codex-power-pack#64) emitted from the single source of truth
`.claude/commands/<family>/*.md` (ADR 0001 section 5). This surface superseded
the flat `codex/prompts/` prompts, retired at the #556 cutover. codex-power-pack
vendored this source (pull model, issue #556 / codex-power-pack#75) rather than
receiving a push from CPP, until it went private and dormant on 2026-09-22
(#1076); nothing outside CPP consumes it now.

Layout per skill:

```
<family>-<command>/
    SKILL.md        # frontmatter (name/description) + Codex harness
                    # adaptations + body inline (short commands)
    reference.md    # full command body (long commands, loaded on demand)
    scripts/<name>  # helper scripts the body references, bundled
                    # byte-identical from scripts/
```

- Generator: `scripts/codex-skill-sync.py` (`make codex-skills` builds this
  directory; `make codex-skills-check` builds it and checks the result)
- Install: `make codex-install` (`--install`) builds the skills in a private
  tree, checks that tree against the sources, and publishes it to
  `~/.codex/skills/`. It does not read this directory. A tree that differs from
  what the sources generate is refused before anything is published
  (`controls/codex-skill-install-fidelity`).
- Installed-copy drift is `scripts/install-drift.sh`'s question; it compares the
  host's copies against a fresh generation, not against this directory.
- Never hand-edit dirs whose SKILL.md carries the GENERATED marker; edit the
  source command and re-run `--write`. Hand-curated skill dirs (no marker)
  are never touched.
