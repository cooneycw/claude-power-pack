# The shared stash stack

**A linked worktree isolates the working tree. It does not isolate refs.** A
stash entry lives at `refs/stash`, and `refs/stash` lives in the repository's
*common* git dir - the one every worktree shares. So every worktree of a
repository, plus the main checkout, pushes onto and pops off **one stack**.

```
claude-power-pack-issue-1027/  git-dir .git/worktrees/…-1027   git-common-dir .git  <- shared
claude-power-pack-issue-1032/  git-dir .git/worktrees/…-1032   git-common-dir .git  <- shared
claude-power-pack-issue-1046/  git-dir .git/worktrees/…-1046   git-common-dir .git  <- shared
```

All three report the same `git stash list`.

## What goes wrong

`git stash pop` takes whatever is on **top**, not whatever you put there. With
concurrent sessions, top-of-stack is routinely somebody else's entry. The pop
succeeds, prints nothing unusual, and lands a stranger's half-finished edits in
your checkout while your own entry stays behind under a number you no longer
know.

This has happened three times in this repository:

| when | what |
|---|---|
| 2026-08-05 (#521 / #635) | two `/flow:auto` runs stash-pushed seconds apart; each bare pop restored the other's work. Fixed for `/flow:auto` and `/flow:finish` by switching to commit-first |
| 2026-09-03 (#1056) | a `/cpp:update` auto-stash was pushed and never restored; it sat unclaimed on the shared stack for 16 days |
| 2026-09-19 (#1056) | a `/codex:auto` worker on #1032 stashed in its own worktree, ran a test, popped - and got 67 lines of a *different* session's #1027 work. Its own entry was gone from the reflog |

The third is the one that matters for how this page is written. That worker was
producing a RED case against pre-fix code - a task **no flow command covers** -
so it never passed the place where the rule was written. A rule that lives only
in the documents describing the safe paths cannot reach the unsafe ones.

## Do this instead

**1. A branch-local WIP commit.** The default, and what `/flow:auto` and
`/flow:finish` do. A commit belongs to your branch; no sibling session can take
it, and a squash-merge flattens it, so nothing reaches `main`.

```bash
git add -A && git commit -m "wip: snapshot"
# ... do the other thing ...
git reset --soft HEAD~1     # back to staged-but-uncommitted, if you want that
```

**2. Read pre-fix content without moving anything.** For the common "produce a
RED case against the code before the fix" task, you do not need to *revert*
anything - you need to *read* the old bytes:

```bash
git show <base-sha>:path/to/file.py > /tmp/pre-fix.py
```

**3. A second throwaway worktree at the base commit.** When the RED case needs a
whole tree at the old state, not one file:

```bash
git worktree add /tmp/pre-fix-tree <base-sha>
# ... run the failing case there ...
git worktree remove /tmp/pre-fix-tree
```

**4. If you genuinely must stash - own the entry.** Tag it, capture its SHA at
push time, and restore with `apply <sha>`. A SHA names *your* entry; `stash@{0}`
names *whatever is on top right now*.

```bash
CPP_ALLOW_WORKTREE_STASH=1 git stash push -u -m "my-unique-tag"
SHA=$(git stash list --format='%H %gs' | awk '/my-unique-tag/ {print $1; exit}')
# ... later ...
git stash apply "$SHA"
```

**Dropping it is the part you must do by hand, and deliberately.** `git stash
drop` accepts only a `stash@{n}` index, and an index is not a stable handle
here: between resolving your tag to `stash@{0}` and running the drop, a sibling
push renumbers every entry and the drop deletes *theirs*. There is no SHA form
of `drop` to close that window with. So look at the stack, confirm the entry is
yours, and drop it when nothing else is writing:

```bash
git stash list      # find the entry tagged my-unique-tag
git stash drop stash@{N}
```

## What enforces this

`scripts/stash-worktree-guard.sh` - a git `reference-transaction` hook that
**refuses `git stash push` from a linked worktree**. It binds every caller,
because it lives in git rather than in a document: a human, Claude, a Codex
worker, a Qwen worker, a script.

**It is on by default.** Three places install it, and you do not have to do
anything:

| caller | when | scope |
|---|---|---|
| `/flow:auto` Step 1 (`flow-start-resolve.sh --verify`) | every worktree, every lane | the repo that just gained a linked worktree |
| `/cpp:init` Tier 1 | at setup | the project being initialised |
| `/cpp:update` Step 5b.1 | every update | the CPP checkout |

The flow lane is the one that matters most: creating a linked worktree is the
moment `refs/stash` becomes shared across checkouts, so it arms the guard at
exactly the point the hazard appears. All three are advisory and fail-open - a
guard that could not be installed never fails the step it runs in.

By hand:

```bash
~/.claude/scripts/stash-worktree-guard.sh --install /path/to/repo
~/.claude/scripts/stash-worktree-guard.sh --check   /path/to/repo
```

### Turning it off

```bash
~/.claude/scripts/stash-worktree-guard.sh --uninstall /path/to/repo   # off, and stays off
~/.claude/scripts/stash-worktree-guard.sh --enable    /path/to/repo   # back on
```

`--uninstall` removes the hook **and records `cpp.stashGuard=false`** in the
repository config. That record is the whole point: installation is automatic, so
an opt-out the next install overwrites is not an opt-out - it is a question you
answer again every update, which is the oscillation ADR 0009 predicts arriving
as the remedy rather than the problem. `--install` reports `disabled` and
changes nothing while the record stands, and `/cpp:init` and `/cpp:update` are
told not to re-offer.

`disabled` and `absent` are deliberately different verdicts: `absent` says
nobody installed it, `disabled` says somebody turned it off. A caller repairs
the first and must not touch the second.

One install covers the main checkout and every linked worktree, because hooks
resolve through the same place the stack does. Two configurations are called out
rather than assumed:

- an **absolute** `core.hooksPath` is honoured (the whole family reads it);
- a **relative** `core.hooksPath` is refused as `unsupported` - each worktree
  resolves it against its own top-level, so no single install could cover the
  family, and a success there would claim coverage that does not exist;
- `--check` says `current` only for an **executable** copy, because git silently
  ignores a non-executable hook and identical bytes would otherwise read as
  enforcement.

### It guards `push` only, and that is not a gap that can be closed here

Measured on git 2.43.0 while the guard was built:

| from a linked worktree | refusable? | what actually happens |
|---|---|---|
| `git stash push` | **yes** | the `refs/stash` transaction reaches `prepared` *before* the working tree is touched. Refusing aborts cleanly: exit 128, working tree byte-identical, no entry created |
| `git stash pop` | **no** | git applies the stash and prints `Dropped refs/stash@{0}` **first**; a veto afterwards leaves the tree mutated *and* the entry gone - worse than no guard |
| `git stash drop` | no | same shape: `Dropped` precedes the hook |

So the guard acts only on the **creation** of a stash entry, which at
`prepared` has one unambiguous signature: `old` is the null OID.

**Its silence on a `pop` is not approval.** If you are about to pop in a
worktree, nothing is watching; use `apply <sha>` instead.

A future editor who "completes" the guard by acting on deletions too would not
be widening it - they would be adding a refusal that fires after the damage.
`tests/test_stash_worktree_guard.py` pins the limitation so that edit fails
loudly rather than reading as an improvement.

## Related

- `.claude/commands/flow/auto.md`, `.claude/commands/flow/finish.md` - the
  commit-first pattern (#635), pinned by `tests/test_flow_docs_no_shared_stash.py`
- `.claude/commands/cpp/update.md` - runs in the main checkout, so the guard does
  not refuse it; it tags its entry and restores by SHA instead (#1056)
- `docs/decisions/0008-instrument-negative-control-bound.md` - row 74
