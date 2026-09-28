# Flow run record - issue #1262

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1262
- Base SHA:          47ddc6cad546d07ecd96dd9a242057fcc2de3c21
- Necessity verdict: Partially addressed
- Approval:          granted (PR-A scope: items 1-9, 12 and the dispositions of 10-11)
- Approver:          run45 orchestrator (fleet mailbox message 1761, replying to the ELI5 report in 1760)
- Recorded at:       2026-09-28T11:05:00Z

## Section B evidence

- Merged PRs touching these paths since 2026-09-26T14:12Z: none. `gh pr list --search 1262`
  returns only #624 (unrelated). #1303 (47ddc6c) touches qa only.
- Duplicate/superseding: #1300 is the next lane (gh-pr-merge wait-then-merge), no line
  overlap. Items 10 and 11 (per-merge half) were delivered by #461, #848 and #852.
- Reproduced: gh repo view from /workspace (a kyle clone) answers cooneycw/kyle whatever
  --path says; the sed fallback keeps `.git`; required contexts are
  ["ci/woodpecker/pr/woodpecker"] (CPP) and ["ci/woodpecker/pr/ci"] (kyle); 101 non-main
  remote branches.

## Section C - the approved plan

1. `scripts/flow-ci-status.sh` - derive the preferred event from required contexts (FLOW_CI_EVENT with its source), resolve the repo inside --path and strip `.git` (FLOW_CI_REPO), report FLOW_CI_WAIT none|settled|expired.
2. `scripts/gh-pr-merge.sh` - paginated completeness file list checked against changedFiles; PR-state pre-check that turns an already-merged PR into GH_PR_MERGE_ALREADY_MERGED; BASE_STALE names directory, HEAD and base tip; local worktree holding the head branch at a sha other than headRefOid is a clean stop, exit 9.
3. `scripts/flow-pr-watch.sh` - FLOW_PR_WATCH_ATTRIBUTION single-run|unresolved with a do-not-baseline warning.
4. `scripts/worktree-remove.sh` - the unpushed refusal names the landed-record and its only writer.
5. `.claude/commands/flow/eli5.md` - CPP-owned section outside the vendored markers adding a `git worktree list` sibling check.
6. `.claude/commands/flow/auto.md` - document exit 9, GH_PR_MERGE_ALREADY_MERGED, FLOW_CI_EVENT and FLOW_CI_WAIT.
7. `tests/test_flow_ci_status.py` - regression tests for items 1-3.
8. `tests/test_gh_pr_merge.py` - regression tests for items 4, 5, 6 and 9.
9. `tests/test_flow_pr_watch.py` - regression test for item 7.
10. `tests/test_worktree_remove.py` - regression test for item 12.
11. `docs/scripts.md` - per-script history entries.
12. `docs/flow-runs/issue-1262.md` - this plan record.
13. `docs/flow-runs/issue-1262.as-read.md` - the as-read issue snapshot.

Scope: about 6 source/doc files plus tests and generated codex mirrors.

Risks: the default-event change for repos whose required context is the pr lane (stated as
a contract change in the PR); exit 9 is a new merge-helper contract value.

Rulings (message 1761): two PRs - the sweeper is PR-B, stacked on this one; the event-default
change and exit 9 are stated in the PR body as contract changes.
