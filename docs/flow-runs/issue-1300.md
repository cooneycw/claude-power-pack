# Flow run record - issue #1300

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1300
- Base SHA:          830ef9de3d15596cc39769138a86fad9b8cd996c
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45 orchestrator (fleet mailbox message 2089, replying to the ELI5 report in 2087)
- Recorded at:       2026-09-28T15:00:00Z

## Section B evidence

- Re-verified on 830ef9d: no `--wait-ci`; the check budget is 60 x 10s; expiry prints
  "never reported" then exits 1 (the same code as a red check), and does not separate
  a MISSING context from a PENDING one; the post-wait base fetch is followed by several
  network reads before run_squash; the #502 "Base branch was modified" retry never
  re-checks containment of the new base.
- Merged PRs on gh-pr-merge.sh since the issue was filed (2026-09-27): #1309 (#1262),
  a different area. Duplicates: none.

## Section C - the approved plan

1. `scripts/gh-pr-merge.sh` - `--wait-ci [SECS]` deadline; GH_PR_MERGE_CI_WAIT marker; expiry is exit 10 in every declared path, naming still-running apart from never-posted contexts; base re-checked immediately before run_squash (exit 6, GH_PR_MERGE_BASE_AT_SQUASH); the #502 retry gated on containment of the new base.
2. `tests/test_gh_pr_merge.py` - a red case per wait path and per base-recheck path, run on 830ef9d, with other-verdict controls.
3. `.claude/commands/flow/auto.md` - Step 7: the wait-then-merge-immediately recipe and exit 10.
4. `.claude/commands/flow/merge.md` - the same recipe, exit 10, and the missing exit 9.
5. `docs/scripts.md` - gh-pr-merge history line.
6. `docs/flow-runs/issue-1300.md` - this plan record.
7. `docs/flow-runs/issue-1300.as-read.md` - the as-read issue snapshot.

Scope: one script, two command docs, tests, generated mirrors.

Risks: exit 10 is a new contract value (caller audit in the PR body); R1 and R2 are
behaviour changes.

Rulings (message 2089): R1 yes - expiry exits 10 in the default path too, with every
caller audited and updated where it branches on the code; R2 yes - the #502 retry is
gated on containment; deadline tests use a stub clock, not wall-clock sleeps.
