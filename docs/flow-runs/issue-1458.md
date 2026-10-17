# Flow run record - issue #1458

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=8ecd4ac6ee3f419fb248e929c1a168d8 -->
## Run 1

- Run-id:            8ecd4ac6ee3f419fb248e929c1a168d8
- Run-start:         145d42d65be5d1eb8950bddcb806cc1d96e343f3
- Issue:             #1458
- Base SHA:          145d42d65be5d1eb8950bddcb806cc1d96e343f3
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6513, replying to plan 6512), with two constraints
- Recorded at:       2026-10-17T01:30:00Z

### Section B evidence
Commits touching code_review.md or its test since filing: none. Merged PRs since filing: #1463 (unrelated files). Duplicates: none (#1450 is the origin). Sibling worktrees: none. Reproduced: `codex sandbox -- true` exits 101 in a Kyle container, and the probe then prints `blocked`.

### Section C - the approved plan
1. `.claude/commands/codex/code_review.md` - start probe first, with the SAME sandbox invocation and flags as the curl probe (only the argv after `--` differs); start failure -> unverified. In-sandbox curl rc 0 -> open; rc 6/7/28 with the outside control succeeding -> blocked; anything else -> unverified. The rc->verdict mapping is written as ONE table. Fold-in (#864 c6227201565): rm $DIFF_FILE on the exit-3 refusal path.
2. `tests/test_code_review_network_fence.py` - table-driven tests against that table; the rc-101 case is the negative control (unverified, never blocked).
3. `codex/skills` mirrors if code_review.md is mirrored.
Scope: 2-3 files, ~60-100 lines. Risks: container reviews report unverified (honest); a fence giving a curl rc outside 6/7/28 reads unverified (the safe direction).
