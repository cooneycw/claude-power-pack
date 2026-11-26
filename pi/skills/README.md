# Generated pi topic packages

Only this README is tracked. Build with `make pi-skills` and compare with
`make pi-skills-check`. Canonical sources are `.claude/skills/` and their linked
Markdown guides. A1 refuses a changed nonempty output root; rebuild into a new
empty `skills` directory rather than pruning user content.

Use `scripts/pi-skill-sync.py --install` for explicit core-backed installation
from a clean bound source revision; `--verify-installed` inspects under existing
shared locks without creating state. Adoption requires named slugs and retains
in-scope backups. See [the CLI reference](../../docs/scripts/pi-skill-sync.md).
A file snapshot never establishes contextual runtime selection; live host
RPC/syscall acceptance remains separate from these files and local tests.
