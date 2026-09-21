# Idioms that delete the evidence

Six habits, collected from five Nit Store comments, one near-miss on a real
branch, and one gate that had to decide this before it could be trusted. They
look nothing alike and they are one defect:

> **The diagnostic and the success line are produced by different parts of the
> pipeline, and the idiom removes the diagnostic while preserving the success.**

What makes the class worth its own page is what happens next. The reader gets a
**true statement** - the helper really did print that line, the tool really did
send that message, the suite really did pass - and draws a **false conclusion**,
with no artifact left behind that contradicts them. There is nothing to notice.
Re-reading the output is not a defence, because the output is intact; what is
missing was removed before it ever reached the output.

None of these belongs to a file, which is why each was individually declined and
why the class kept coming back. They belong here.

## 1. `git reset --soft <moving ref>` writes a sibling's merged work out of your branch

A linked worktree isolates the working tree. It does not isolate refs -
`refs/remotes/origin/main` lives in the common git dir that every worktree
shares (the same mechanism as [the shared stash stack](shared-stash-stack.md)).
So **a sibling session's `git fetch` in ANY worktree advances `origin/main` for
EVERY worktree, with no signal in yours.**

The ordinary squash idiom then becomes a revert:

```bash
git rebase origin/main          # origin/main == A; worktree is A + mine
#   ... a sibling fetches; origin/main silently becomes B ...
git reset --soft origin/main    # HEAD moves to B, worktree still holds A + mine
git commit                      # the commit's diff is (A + mine) vs B
                                # => every change in A..B is a DELETION authored by me
```

Caught on a real branch before pushing: a commit touching 10 files reported
**22 files, 1022 insertions, 861 deletions**. The extra 12 were another worker's
merged PR, rendered as deletions with this branch's author on them.

**Why it is nearly invisible**, which is the part worth writing down:

- `git log --oneline origin/main..HEAD` shows ONE commit, yours, with your
  message.
- Two-dot and three-dot diffs are **identical** here. The merge-base remedy for
  the reviewer hazard - "diff against the merge base, not the tip" - does not
  detect this one, because after the reset `origin/main` **is** the merge base.
  The revert is inside the commit.
- `make verify` passed green on 3500 tests against a tree with the sibling's
  work reverted. **A suite cannot object to work that is simply absent.**

**Do this instead - pin the base you BRANCHED FROM, not the ref's value now.**
Both halves matter, and pinning alone is not enough:

```bash
# NOT THIS. `rev-parse` resolved after the sibling's fetch pins B, and the reset
# is then exactly as destructive as naming the ref would have been. Pinning
# stops the ref moving DURING your sequence; it cannot undo a move that already
# happened.
BASE=$(git rev-parse origin/main)
git reset --soft "$BASE"

# THIS. The merge base is the commit this branch actually diverged from, so it
# is unaffected by anything a sibling has landed since.
BASE=$(git merge-base HEAD origin/main)
git reset --soft "$BASE"          # collapse onto YOUR base
git commit -m "..."
git merge --no-edit origin/main   # bring the moved base in, deliberately, after
```

`/flow:auto` Step 6 ships this as its safe-collapse recipe (#657), with one more
step: before committing, `git diff --staged --diff-filter=D --name-only` must be
empty unless you meant to delete files. Note what that check can and cannot do -
`--diff-filter=D` selects deleted FILES and is blind to a deleted LINE, which is
section 5's hazard and the reason section 2 exists beside it.

**And then count what you are about to delete.** That is item 2.

## 2. Accounting for what you delete

The check adopted to catch item 1 was:

```bash
git diff "$MERGE_BASE" | grep -E '^-[^-]' | sort | uniq -c     # RETIRED - blind
```

`^-[^-]` requires a character after the `-`. It therefore cannot match:

| shape | what it is in the file | why it is invisible |
|---|---|---|
| `-` | a deleted **blank line** | nothing follows the `-` |
| `-- item` | a deleted **markdown bullet** | `- item` renders as `-- item` |
| `----` | a deleted `---` - front matter, thematic break | renders as four dashes |

Measured on a merged documentation PR: **88 matched, 24 bare `-` invisible, 7
`--` invisible, 119 actual.** The seven silently dropped were deleted verdict
definitions and a deleted guidance line. In a repository whose documentation is
largely bullet lists, the blind spot lands precisely on the content most likely
to carry a removed rule or caveat.

**The corrected one-liner is better and still not right:**

```bash
git diff "$BASE" | grep -E '^-' | grep -v '^---' | sort | uniq -c   # better; misses `---`
```

A deleted line whose CONTENT begins `---` renders as `----`, matches `^---`, and
is thrown away with the file headers. Measured on a four-deletion diff: the
retired form saw **1**, this one saw **3**, the truth was **4**.

**So use the instrument, which parses rather than matches:**

```bash
BASE=$(git rev-parse origin/main)
scripts/deletion-accounting.sh --base "$BASE"
```

It consumes the line counts the hunk header declares and looks for a file header
only once both are exhausted, so nothing inside a hunk can be mistaken for one
whatever it spells. It prints the file count first (**the tell** for item 1),
the deleted-line count, how many of them the retired form would have missed, the
binary files it could not line-count, and the census. Exit 0 = nothing deleted,
1 = deletions to review, 2 = **it could not look** - which is a different fact
from "nothing is deleted" and does not share an exit code with it. Its verdict
is consumed by whoever is about to push, and nothing downstream re-derives it,
so it carries a committed negative control (ADR 0008 row 75,
`controls/deletion-accounting`).

**A worked instance of this page's own class, from building it.** The first cut
of that parser recognised headers by their TEXT, narrowed to git's `a/` and `b/`
prefixes because that shape looked unfakeable. Inside a hunk, a deleted `-- a/foo`
followed by an added `++ b/bar` renders as `--- a/foo` / `+++ b/bar` - exactly
that shape - so the parser ended the hunk there and reported **0** deletions
where git reports 2. The fix for a text-matching blindness was itself text
matching, and it was found by a second model rather than by its author. Four
siblings came out of the same review, all of them the same confident zero over
an unexamined population: a diff taken under `color.ui=always`, a file of bytes
that is not a diff, a directory handed to `--diff-file`, and a deleted binary
file.

A **second** pass over the fixes found four more of the same shape - including
`find ... | sort`, where the assignment takes *sort's* status and a partly
failed traversal is accounted as a whole population. That is section 4's rule,
in the instrument written for section 2, by someone who had just written both.

Knowing the class is not immunity to it. What caught all ten was a reviewer that
had not written the code.

Cross-checked against `git diff --numstat` - a count git derives by a different
route - on a real 31-file diff of this repository: 276 deletions across 31
files, identical, of which 18 were invisible to the retired form.

### The fan-out rule, which replaces "every deletion appears exactly twice"

A companion heuristic was propagated alongside the retired grep: *a real deletion
appears exactly twice, so anything with a different multiplicity is noise.* It is
wrong. Run against the same PR it would have fired on **63 distinct lines with
zero real findings**; the measured multiplicities were 1x, 2x, 3x, 4x, 6x and 24x.

> **A multiplicity is a finding only against the KNOWN FAN-OUT of the file it
> came from, and that map must be DERIVED, not hand-listed.**

A generated file copied into six skill directories legitimately shows 6x. A line
in a file that exists once shows 1x. `deletion-accounting.sh` therefore prints
multiplicity and says nothing about what it means - reporting a number is not the
same as being entitled to a rule about it.

## 3. Three idioms that keep the success line

Four instances in one session, four different agents, none able to detect it from
the output they were reading:

| idiom | what it deleted | what still said "ok" |
|---|---|---|
| `helper \| tail -N` then `echo $?` | the helper's exit status - `$?` is **tail's** | the helper's own success line |
| `pkill -f 'issue-834/.venv/bin/pytest'` | the shell running it, whose own command line matched | nothing; the masked exit read as an ordinary failure |
| `( ... ) 2>&1 \| tail -1` around a send | the `command not found` on **stderr**, one line above the success line | `sent message NNN [queued]` |
| a backtick inside a double-quoted `--body "..."` | the command name, substituted out **before the tool saw it** | the tool's `sent ... [queued]`, correctly reporting it delivered what it was handed |

The fourth is the worst, and it is the one to remember: **the corruption happens
UPSTREAM of the tool**, so no amount of checking the tool's result can reveal it.
The tool's success line is true. It is about a different message than the one you
wrote.

Corrected forms:

```bash
# 1. Redirect, then read rc, THEN read the file. Never pipe and then ask $?.
helper > /tmp/out.txt 2>&1; rc=$?

# 2. LOOK before you kill. `pkill -f PATTERN` matches the command line of the
#    shell running it, and `$$` alone is not enough: measured here, an ANCESTOR
#    shell whose argv carries the pattern is matched too.
pgrep -af 'pytest'                                  # read this first
pgrep -f 'pytest' | grep -vx "$$" | xargs -r kill   # then, deliberately

# 3. Never interpolate a body into a double-quoted argument - a backtick is
#    substituted out BEFORE the tool ever sees it. Pass a file, or a QUOTED
#    heredoc, which suppresses substitution entirely.
printf '%s' "$body" | tool send --body-file -
tool send --body "$(cat <<'BODY'
literal `backticks` survive a quoted heredoc
BODY
)"
```

The general rule: **when a diagnostic and a success line come from different
places, do not put a filter between you and either of them.** Write both to a
file and read the file.

## 4. `$?` after a pipe, specifically

This one earns its own section because it bit two of three workers in a single
wave, and because the helpers here print 10+ `FLOW_*` lines per call, so trimming
their output is constant.

`pipefail` is not set in this lane:

```
false | tail -1                      -> 0     pipeline exit = LAST command
false; echo x                        -> 0     compound exit = LAST command
bash -c 'exit 5' 2>&1 | tail -40     -> 0     <- the masking form
set -o pipefail; false | tail -1     -> 1
```

`helper ... | tail -3; echo "exit=$?"` prints `exit=0` while the helper refused
with a usage error. This has become more costly, not less: since #1027 every flow
gate verdict has its OWN exit code (`ok` 0, `warn` 3, `skipped` 4, `fail` 1), so
the pipe now destroys information that did not exist before.

`/codex:auto` documents this at length for its own lane (#798) - and that
hardened the DOCUMENTED invocation while leaving the idiom untouched everywhere
else.

**So the helpers do not rely on you remembering.** Every helper in the flow family
prints `<NAMESPACE>_EXIT=<code>` **on stderr**, as the last thing it writes, in
the marker namespace it already uses (`FLOW_FINISH_GATE_EXIT=`,
`GH_PR_MERGE_EXIT=`, `STASH_GUARD_EXIT=`, ...). Run against the real helper:

```
$ bash scripts/gh-pr-merge.sh | tail -1 ; echo "exit=$?"
Usage: gh-pr-merge.sh [--admin] ... <pr-number> <branch-name>
GH_PR_MERGE_EXIT=2
exit=0
```

`$?` is still tail's and still `0` - nothing can change that from inside the
helper. What changed is that the real status is now **in front of you** while
the misleading one is printed beside it.

**Why stderr rather than stdout**, since the difference is the whole design:

- stdout is these helpers' machine-readable contract, and sibling helpers
  capture it with `$(...)` - `flow-start-resolve.sh` reads
  `flow-worktree-claim.sh` and `stash-worktree-guard.sh` that way, and
  `speckit-context.py refresh` writes a whole issue body to stdout. Metadata on
  a data channel corrupts those callers.
- stderr **bypasses the pipe entirely**, so the status survives `| head -5` too,
  where a trailing stdout line would be lost outright.

Two bounds worth knowing. `stash-worktree-guard.sh` emits only on its admin
lane - it is copied into `.git/hooks/` and its hook lane runs on every ref
update, so a line there would print on every `git commit` in every repository
carrying the guard. And a Python helper must **flush stdout first**: stdout is
block-buffered when piped, so without the flush the status lands *before* the
contract under `2>&1 | tail -N` - present when you check it, absent when you
rely on it.

`$?` is still correct on a bare invocation, and a bare invocation is still
preferred; the `_EXIT=` line is a backstop, not a licence to pipe.

For anything else - a helper that does not carry the line, a third-party tool -
redirect to a file and read `$?` before doing anything else with the output.

See also [the detector contracts](detector-contracts.md), which records the same
mechanism from the other end: a reading taken *through* an instrument is not
evidence about the state *without* it, and the cheapest defence is one control run
with the instrument removed.

## 5. Which distinction does this tidying flag delete?

`git diff --name-only` renders **"my unmerged file"** and **"someone else's landed
file"** identically. `--name-status` prints `D` for the first and `A` for the
second; `--name-only` prints the same bare filename for both. In a migration
check those two demand **opposite actions**, and the false reading points at the
more expensive one. Reversing the range does not rescue it (tested).

The generalisable question, which is the actual deliverable of this section:

> **When a flag's job is to tidy output - drop a column, take just the names, just
> the counts - ask which distinction it deletes, and whether your question depends
> on that distinction.**

And where a comparison is being used to answer a question about **state**, prefer
the query that answers it directly:

```bash
git diff --name-only origin/main            # infers "is it on main" from a comparison
git ls-tree origin/main -- path/to/file     # ASKS "is it on main"
```

CPP's own shipped uses of `--name-only` were checked and are sound, so this is a
hazard for **ad-hoc queries**, not a code fix owed anywhere. [The detector
contracts](detector-contracts.md) carries a second instance of the same shape -
`--diff-filter=D --name-only` selects deleted FILES and cannot see a deleted LINE,
so it answered "does this diff remove a file?" for a condition that was "does this
diff remove anything?" - with `--numstat` as the direct query there.

## 6. A shallow clone deletes the evidence that a negative answer needs

`git merge-base --is-ancestor A B` answers a question about history. A shallow
clone does not have the history. The command still answers.

**The rule, in one line: in a shallow repository a NEGATIVE ancestry result
proves nothing, whatever the exit code. A POSITIVE still proves what it says.**

The asymmetry is the whole content. Reachability is established by exhibiting a
path, so finding one is conclusive no matter how much history is missing -
truncation cannot manufacture a path that is not there. Failing to find one is
established by exhausting the search, and a truncated repository cannot exhaust
anything. "I looked everywhere and there is no path" and "I looked at everything
I have and there is no path" are the same output.

**Do not rely on the exit code to tell you which situation you are in**, because
that depends on the clone's shape rather than on the question:

These are REPRODUCTION SCENARIOS, not a lookup table keyed on clone flags. What
decides the exit code is whether both commit objects are AVAILABLE when the
command runs; the flags only make one outcome or the other likely.

| scenario | what happens | what you get |
|---|---|---|
| full clone | the search completes | 0 or 1, both meaningful |
| shallow, and the commit is absent | the argument does not resolve | 128 - loud, and honest |
| shallow, but both commits are present - fetched tips, a partial clone filling objects on demand, an earlier fetch | the arguments RESOLVE, the history between them does not | **1** - a confident wrong answer |

The third row is the one that matters and it is what CI hits, because
`--filter=tree:0` fetches objects on demand so the arguments resolve almost
always. But do not read the second row as a guarantee: a PLAIN `--depth=1` clone
produces the same quiet 1 whenever both tips happen to be present and only the
history between them is missing. The loud 128 is a courtesy of object absence,
not a property of shallowness, so "we only use plain `--depth=1`" is not a
defence. In every one of these the command proceeds to a real search over an
absent history and reports the ordinary "not an ancestor" code. Nothing anywhere
is marked degraded.

This is the page's defect exactly: the diagnostic - *I could not see the history*
- is produced by a different layer than the verdict, and the clone shape removes
the diagnostic while preserving a verdict that looks like every other verdict.
A reader gets a true statement (the command really did exit 1) and draws a false
conclusion (the commit really is not an ancestor).

**What to do instead.** Establish the clone's shape before believing a negative,
with `git rev-parse --is-shallow-repository`, and treat a negative from a shallow
repository as UNKNOWN rather than as NO. Where the answer is load-bearing, deepen
first (`git fetch --unshallow`, or `--deepen`) and ask again. Where deepening is
not available, say the answer could not be established - which is the honest
verdict and the one this whole page exists to protect.

A worked instance is `scripts/flow-finish-gate.sh`, which decides this before it
can be misled: it establishes shallowness first and records the enrolment
decision as undecidable when the history is truncated, rather than reading an
absence of receipts as an absence of review.

Note also what the third row does to a control. A test that proves the guard
fires on a plain `--depth=1` clone proves it against the LOUD shape only. The
dangerous shape is the quiet one, and a control that never constructs it is
green for a case it has not examined.

## Related

- [the detector contracts](detector-contracts.md) - the two questions asked of any
  instrument in a diff, and the index of instances this page's items 4 and 5 join
- [the shared stash stack](shared-stash-stack.md) - the same refs-are-shared
  mechanism as item 1, one ref along
- [ADR 0008](../decisions/0008-instrument-negative-control-bound.md) - when an
  instrument needs a committed negative control; row 75 is item 2's
- `docs/scripts.md` - `deletion-accounting`, the instrument item 2 ships
- `.claude/commands/flow/auto.md` Step 6 - the safe collapse recipe (#657), which
  is item 1 applied
