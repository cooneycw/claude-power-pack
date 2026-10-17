# Flow run record - issue #1460

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=f0b0b7bfae3a47c6bf06de1269e3bdfa -->
## Run 1

- Run-id:            f0b0b7bfae3a47c6bf06de1269e3bdfa
- Run-start:         8e604a09e7954f79ecdda304145eb3e4a046ecc6
- Issue:             #1460
- Base SHA:          8e604a09e7954f79ecdda304145eb3e4a046ecc6
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6527, replying to plan 6526), with three notes
- Recorded at:       2026-10-17T05:20:00Z

### Section B evidence
No commits or PRs since filing touch these files (#1463-#1468 elsewhere). Duplicates: none; #864 c6227202217 covers the gate's own blind spots. Measured: 40 line-bound backtick citations in 205 in-scope docs, 23 resolving with 0 past EOF, 17 not resolving (7 cross-repo, 4 narrating a retired tool, 3 in dated reviews, 3 bare names), confirmed rot 0; an earlier narrowed backtick scan gave 35 hits, mostly not rot.

### Section C - the approved plan
1. `.woodpecker.yml` - an md-relative-links-check step after git-stage (staged git).
2. `Makefile` - the md-relative-links-check annotation changes from `ci: excluded needs-git` to `ci: runs`.
3. `scripts/check-md-relative-links.py` - docstring: the ruling on backtick and path:line citations, with the measurements and the content-drift reason (a past-EOF check would not have caught R11).
4. `docs/scripts.md` - the entry records the CI consumer and the ruling.
5. `tests/test_check_md_relative_links.py` - pins the CI step.
Plus: the measured backlog posted on #1460; a deliberate dead-link red on THIS PR branch only (cited beside the green); after merge, a reply to #864 c6227202217 that CI on a clean checkout closes the gitignored-target blind spot.
Risks: a backtick citation can rot silently (mitigated only by review, stated); the gate's other blind spots stay in the store.
