<!-- flow-run n=1 id=0825157b7c3c49e7b362993a0a0e3394 -->
## Run 1 - issue #1831 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1831
- Read at:      2026-11-14T20:23:36Z
- updatedAt:    2026-11-14T19:22:07Z   (context only - moves on comments and labels)
- Body digest:  238a8cb689f5e321c4780281724da79491f051b715462c0d2f8a7eec188fe34f   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1767 of 1767 (cap 16384)

### Body as read
## Problem

`scripts/flow-finish-gate.sh` (lease identity, added by #1828) derives `--pr` with `timeout 15 gh pr view "<branch>" --json number --jq .number`. When the branch name is all digits (for example `123`, which is a valid git branch), `gh pr view 123` resolves **PR #123**, not the PR whose head is branch `123`. The lease then carries an unrelated PR number.

A related case is untested: `gh pr view <branch>` with a branch name that also heads a PR from a fork, or a closed older PR on the same branch name. gh's selection there has not been measured.

## Why it matters

The label exists so the owner, reading `kyle-lock status full-suite`, can tell which run holds or waits for the lease. A wrong PR number misleads exactly that reader. The gate's verdict is unaffected: this is metadata, and the lease is still taken and released correctly.

## Fix

- Look the PR up by head branch explicitly: `gh pr list --head "<branch>" --state open --json number,headRefName,headRepositoryOwner`.
- Accept the number only when exactly one PR matches and its head branch, and this repository, are the ones derived. Otherwise omit `--pr`; never guess.
- Keep the 15s bound and the "no `timeout`, no lookup" rule.

## Acceptance

- [ ] On branch `123` with a fake `gh` that answers `pr view 123` with PR #123, the gate passes no `--pr` (red case: the current gate passes `--pr 123`).
- [ ] Zero matches, or two or more, passes no `--pr`.
- [ ] Existing `tests/test_flow_finish_gate.py::test_coordination_lease_says_what_it_is_for` cases still pass.

## Source

Codex counter-model review, pass 4, on the #1828 branch (PR to follow), deferred at the escalated pass cap of 4 recorded at https://github.com/cooneycw/claude-power-pack/issues/1828#issuecomment-6882874663.


<!-- end of body -->
