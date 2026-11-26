# Antigravity topic build output

Canonical topic packages live in `.claude/skills/`. Run `make antigravity-skills`
from a clean committed checkout, then `make antigravity-skills-check` to verify
the full output. Generated packages and the core management records here are
ignored. Edit the canonical sources; the generated tree is never a source.

This delivery builds topic packages only. Production host installation and the
shared updater are #1889-B; command-derived AGY skills and a real `cpp-update`
invocation remain follow-ups under #1876/#1888/#1889.
