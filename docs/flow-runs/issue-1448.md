# Flow run record - issue #1448

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=7505d78d0f804a0f9a0d1eb49447ce41 -->
## Run 1

- Run-id:            7505d78d0f804a0f9a0d1eb49447ce41
- Run-start:         84b0d9bf284bb176a5595f8dd2dedf9d5c177efc
- Issue:             #1448
- Base SHA:          84b0d9bf
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (owner, in-session "approved")
- Recorded at:       2026-10-14T00:00:00Z

### Section B evidence
Commits since 2026-10-13T21:02:58Z: none on origin/main; none touching scripts/project-next*.py,
.claude/project-next-ownership.json, lib/project_next, controls/project-next-ownership.
Merged PRs since filing: none (latest #1447, #1446, #1445, #1443, #1438 all <= 2026-10-12).
Duplicates/superseding: none (#1262, #417 unrelated). Live repro: exit 2 from a scripts/+lib/-only tree.

### Section C - the approved plan
1. `lib/project_next/ownership.json` - git mv from .claude/project-next-ownership.json; content unchanged except the contract-doc pin
2. `.claude/project-next-ownership.json` - removed (moved)
3. `scripts/project-next.py` - MANIFEST_PATH re-pointed under lib/project_next
4. `scripts/project-next-ownership.py` - MANIFEST_REL re-pointed; LEGACY_MANIFEST_REL fallback for the --repin merge-base baseline
5. `.gitignore` - re-point both negations to the new path
6. `controls/project-next-ownership/cases/bad-drifted-file/lib/project_next/ownership.json` - case manifest moved
7. `controls/project-next-ownership/cases/good-pinned-files/lib/project_next/ownership.json` - case manifest moved
8. `controls/project-next-ownership/cases/bad-drifted-file/.claude/project-next-ownership.json` - removed (moved)
9. `controls/project-next-ownership/cases/good-pinned-files/.claude/project-next-ownership.json` - removed (moved)
10. `controls/project-next-ownership/anchors/constructed-presence-only-project-next-ownership.py` - manifest path only
11. `controls/project-next-ownership/control.json` - anchor sha256
12. `docs/project-next-contract.md` - manifest path sentence (repin its pin)
13. `.claude/commands/project/next.md` - manifest path
14. `tests/test_project_next_contract.py` - re-point + scripts/+lib/-only acceptance test
15. `tests/test_project_next_ownership.py` - re-point + legacy-baseline repin refusal test
16. `CLAUDE.md` - path reference
17. `scripts/check-unicode-dashes.py` - comment path
18. `docs/project-next-provenance.md` - rename-table note for #1448

Scope: ~18 paths, ~100-150 lines plus moves; generated codex/skills mirrors regenerated, not hand-edited.
Risks: unpinned-module scan over lib/project_next (only .py/symlinked dirs - verify with make project-next-check); any out-of-repo consumer of the old path breaks (none found); no runtime fallback by design.
