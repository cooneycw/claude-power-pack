# Issue #1221 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1221
- Read at:      2026-09-23T21:33:52Z
- updatedAt:    2026-09-23T17:26:55Z   (context only - moves on comments and labels)
- Body digest:  d52387438990bb1eb6e6b9025150dfd38e8da79099620e60eee7a53e262c15c7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2862 of 2862 (cap 16384)

## Body as read
**Record issue**, per the owner's 2026-09-23 ruling that ticketless work gets an issue so the verdict ledger has a subject to key on. Found by worker-B in wave `claude-improvements`; `scripts/flow-start-resolve.sh` is in nobody's lane.

## The defect

`flow-start-resolve.sh` creates the worktree branch **tracking `origin/main`**:

```
$ git -C <flow worktree> rev-parse --abbrev-ref --symbolic-full-name @{u}
origin/main            # on branch issue-1189-...
```

So a bare `git push` from a fresh flow worktree fails with exit 128 — and **git's first suggested remedy pushes the feature branch onto the default branch**:

```
fatal: The upstream branch of your current branch does not match
the name of your current branch.  To push to the upstream branch
on the remote, use

    git push origin HEAD:main        <-- offered FIRST

To push to the branch of the same name on the remote, use

    git push origin HEAD
```

Reproduced with `--dry-run` against a live flow worktree, so nothing was pushed.

## Why it matters beyond the inconvenience

**A worker in a hurry, or any wrapper that takes git's first suggestion, ships unreviewed work straight to `main`.** The finish gate, the approval gate and the counter-model review are all bypassed by a remedy the tool itself recommends.

**And the failure is silent in a chain.** worker-B did not skip its push — it ran it inside a chained command where the failure was swallowed, then assumed the branch was unpushed because it hadn't got to it yet. Four commits of completed security work existed only on one disk for roughly two hours, in a session that had gone deaf. In its words: *"`git push` in a chain is a command whose failure looks exactly like not having run it."*

## Why it looks intermittent

It only fires on a branch whose upstream the resolver set. A worker that happens to use `git push -u origin <branch>` on its **first** push sets the upstream correctly and never sees it again. So the trap is keyed on which form you used first, not on the branch or the worker.

Measured across five live worktrees in one wave: four correct (all first-pushed with `-u`), one defective and unpushed.

## Suggested fix

Either:
- have the resolver set the upstream to the branch's own name after `git worktree add`, or
- set `push.default = current` for the checkout

Either makes a bare `git push` do the obvious thing and **removes the `HEAD:main` suggestion from the failure path entirely**, which is the half that matters.

## Acceptance

1. A flow worktree created by the resolver has its upstream set to its own branch name, or a bare push in one cannot suggest `HEAD:main`.
2. A regression test: a resolver-created worktree, one commit, a bare `git push` reaches the branch's own remote ref — red on today's resolver.
3. The test asserts the failure path never emits `HEAD:main` as a remedy.

