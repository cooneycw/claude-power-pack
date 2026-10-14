<!-- flow-run n=1 id=7505d78d0f804a0f9a0d1eb49447ce41 -->
## Run 1 - issue #1448 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1448
- Read at:      2026-10-14T09:47:21Z
- updatedAt:    2026-10-13T21:02:58Z   (context only - moves on comments and labels)
- Body digest:  0252e0687d13a107b4bb5b7c7f8d76e30e23c929f06292549ee439c61bec7d5d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1839 of 1839 (cap 16384)

### Body as read
## Summary

`scripts/project-next.py` finds its ownership manifest from its own location:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / ".claude" / "project-next-ownership.json"
```

That assumes a full CPP checkout around the script. In a kyle container, `~/.claude` holds only the `scripts/` and `lib/` mounts, so `/project:next` dies before it renders anything:

```
project-next: [Errno 2] No such file or directory: '/home/claude/.claude/.claude/project-next-ownership.json'
exit 2
```

`lib/` is already live-mounted in containers (kyle #1661). Kyle chose not to mount `.claude/`: a single-file mount detaches on the next `git pull` (kyle's #1177 writer rule), and mounting the whole directory exposes untracked local state (`friction.jsonl`, `deploy.log`, `settings.local.json`).

## Ask

Make `project-next.py` read its pin from a path under `lib/`, for example `lib/project_next/ownership.json`, or otherwise from a location that ships with `lib/`. Keep `make project-next-repin`, `scripts/project-next-ownership.py check`, `tests/test_project_next_*` and `controls/project-next-ownership` pointing at the same single file.

## Acceptance

- `python3 ~/.claude/scripts/project-next.py <repo> --input <fixture> --json` exits 0 from a tree containing only `scripts/` and `lib/`.
- Kyle's container run check (`HELPER_RUN_PROBE`, kyle #1682) turns green on a container that mounts the new revision. Today it is red by name: `project-next.py (repo-data-missing)`.

Other helpers that read CPP repo data (`mcp-drift.py`, `retired-surface-prune.py`, `codex-skill-sync.py`, `counter-model-uniformity-check.py`, `counter-model-reviewer-attribution.py`) are declared container-unsupported on the kyle side. They maintain a CPP checkout and are out of scope here.

Companion to cooneycw/kyle#1682.

