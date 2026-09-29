<!-- flow-run n=1 id=7e30461ab82e487bae9ee2f2a171ddf1 -->
## Run 1 - issue #1348 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1348
- Read at:      2026-09-28T22:31:30Z
- updatedAt:    2026-09-28T22:31:02Z   (context only - moves on comments and labels)
- Body digest:  d32fc73b63c1dba25770a86724ff0524d992608efad368ade123a1a3dcf29dff   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1024 of 1024 (cap 16384)

### Body as read
Promoted from Nit Store #864 (https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5879774278) ahead of the v9.0.0 cut (#1278), which this check guards.

**Outcome:** `scripts/check-version-consistency.py` fails when `uv.lock`'s entry for this project records a different version from `pyproject.toml`. Today it compares `pyproject.toml`, CLAUDE.md "Current version:", the README banner and topmost `### vX`, and the CHANGELOG, but not `uv.lock`. A release that forgets `uv lock` ships two version numbers, and the check stays green. v8.0.0 did change `uv.lock`, so this is a real site.

**Constraint:** read the project's own `[[package]]` entry by name from pyproject's `[project].name`, never by line number. A lockfile with no entry for the project is reported as unreadable/unknown, not as consistent.

**Acceptance:** a committed red case, a tmp tree whose `uv.lock` project version differs from `pyproject.toml`, fails, and it passes with them equal. The real repo stays green on main.

Refs #1278.

