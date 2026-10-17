<!-- flow-run n=1 id=f0b0b7bfae3a47c6bf06de1269e3bdfa -->
## Run 1 - issue #1460 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1460
- Read at:      2026-10-17T02:20:51Z
- updatedAt:    2026-10-17T00:15:06Z   (context only - moves on comments and labels)
- Body digest:  4448ac036a267a3d8a2d844c2f845393ff18862b5f3796990365b4c5871b41a8   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1897 of 1897 (cap 16384)

### Body as read
Found while reviewing PR #1455 (merged as 049483b; Refs #1413).

## Defect

#1413 is closed, but the citation class that opened it has no check and no owner.

- **The new gate skips the original defects.** `scripts/check-md-relative-links.py` checks relative markdown links only. It skips URLs by design (`:164`) and inline code (`:184`). The #918/#919 citations were GitHub URLs, and the R11 dead citation was a backtick path (`` `behavioral-eval-export.md:22-34` `` at `.specify/specs/per-skill-audit/spec.md:120` on 6457407). The gate would have stayed green on all of them.
- **The replacement citation is still unchecked.** It is `` `scripts/check-behavioral-eval.py:12,238` ``, a line-bound backtick citation. It is accurate today, and nothing will notice when it drifts.
- **The planned follow-up was dropped.** The parked-branch resume note on #1413 recorded ruling 3: file a follow-up issue holding the measured backtick-citation backlog (161 raw / 35 narrowed hits). PR #1455 dropped that plan. Its reasoning is in the PR body and the script docstring, not on the issue, and no follow-up exists.

## Why it matters

The four dead links the gate found are real rot, but they are a side benefit. #1413's acceptance item 3 was answered by a check aimed at a different defect class. Backtick path and `file:line` citations are the population where #1413's rot actually lived, and that rot will recur.

## Scope for this issue

- Decide and implement a check for backtick path citations, including `path:line` forms, or record a ruling that they stay unchecked.
- Hold the measured backlog here.
- Note: the new gate is declared `ci: excluded needs-git` (`Makefile:774`), although `validate` already stages a pinned git into `.ci-bin` (`.woodpecker.yml:101-128`). Because it never runs in CI, a PR that adds a dead link merges green. Decide whether it should run in CI as part of this work.

