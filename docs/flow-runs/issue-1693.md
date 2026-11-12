# Flow run record - issue #1693

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=51f1b2edbe2f4e689b7f725cb57798c1 -->
## Run 1

- Run-id:            51f1b2edbe2f4e689b7f725cb57798c1
- Run-start:         4c8aa79a3f58baca937692c6c19e2d896b29af40
- Issue:             #1693
- Base SHA:          4c8aa79a3f58baca937692c6c19e2d896b29af40
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox: "GATE: GO-WITH-CONDITIONS #1693", outbox rev 11, 2026-11-11T19:17:47-05:00
- Recorded at:       2026-11-12T00:18:34Z

### Section B evidence
- commits touching the five scripts since filing: none
- PRs: #1721 merged (4 rows joined here), #1722 open (#1692, other files)
- related issues: #1708, #1709 (apart and after), #1705-#1707 (other files)
- survey at 4c8aa79a: 5,202 lines; 2,708 code, 2,239 comment, 255 blank; about 12 dead lines (0.2 percent), 160 to 190 duplicated, about 550 history commentary of which about 285 already recorded in docs/scripts
- reframing accepted by the approver: the trim is in the commentary; no refusal is removed

### Gate conditions (orchestrator)
- Mechanical code-identity check with zero exceptions for four files; worktree-remove.sh carries only the named CDPATH line and --help block; show it failing on a one-code-line mutation.
- --help prints a region bounded by markers in the file, not a line range; a test asserts it contains the Usage section and names exit 9, shown red once.
- Move before remove, in separate commits, so conservation can be checked at each.
- Finding 723 declined here and posted to the Nit Store #1725; record on #1693 where each joined row went.
- Unexercised refusals filed as their own issue (#1726), not fixed here.
- PR states lines before, lines after, and how many of the difference are a move into docs/scripts.
- Independent old-versus-new read before the Codex review; two review passes, ask before a third.
- make lint and make typecheck before the gate; no push until the merge slot.

### Section C - the approved plan
1. `scripts/gh-pr-merge.sh` - history commentary removed after it is recorded in the reference; two mis-attached comment blocks re-attached; usage comment corrected (finding 628); no code line changes
2. `scripts/worktree-remove.sh` - history commentary removed after it is recorded; --help prints the marker-bounded header; CDPATH neutralised in the relative-path cd (finding 557)
3. `scripts/flow-worktree-claim.sh` - history commentary only
4. `scripts/flow-worktree-sweep.sh` - history commentary only
5. `scripts/flow-worktree-guard.sh` - history commentary only
6. `docs/scripts/gh-pr-merge.md` - receives moved history verbatim
7. `docs/scripts/worktree-remove.md` - receives moved history verbatim
8. `docs/scripts/flow-worktree-claim.md` - receives moved history verbatim
9. `docs/scripts/flow-worktree-sweep.md` - receives moved history verbatim
10. `docs/scripts/flow-worktree-guard.md` - receives moved history verbatim
11. `controls/census.md` - the worktree-remove row names exit 9 (finding 556)
12. `tests/test_worktree_remove_help.py` - --help output contains the Usage section and names exit 9

Scope: 12 files. 5,202 lines before in the five scripts; about 4,590 after; about 265 of the difference is a move into docs/scripts.

Risks: a comment can be load-bearing (tests extract script text, two checkers read gh-pr-merge.sh, anchors derive from these scripts); history versus rationale is a judgement and mixed blocks keep their rationale; the change is mostly a move.
