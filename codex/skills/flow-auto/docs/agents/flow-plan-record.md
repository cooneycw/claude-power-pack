# The /flow:auto plan record - background

On-demand reference for `scripts/flow-plan-record.py` (issue #1211). **Reading
this is not required to run `/flow:auto`.** The procedure calls the helper and
says what each verdict means at the step that reads it. This page keeps the
reasoning and incident history behind those rules, which used to be pasted into
the procedure as roughly 5,700 words of programs and prose. Open it when a
verdict surprises you, or before you change the helper.

The helper is the only implementation. `tests/test_flow_plan_record.py`,
`tests/test_flow_issue_snapshot.py` and `tests/test_flow_plan_compliance.py` run
it against fixture repositories, including the known-bad and cannot-answer cases
described below. `tests/test_flow_plan_record.py` also fails if the procedure
stops calling the helper or starts carrying a pasted copy again.

| Subcommand | Step | Question it answers | Exits |
|---|---|---|---|
| `reconcile N` | 1 | Is the record on disk the last APPROVED one, or absent? | 0 |
| `read-issue N` | 1 | What did this run read, and when? | 0 recorded, 4 unresolved |
| `approve N` | 4 | Snapshot written and baseline stamped? | 0, 4 snapshot unresolved, 1 no record |
| `drift N` | 6 | Has the issue body moved since Step 1? | 0 clean, 3 drift, 4 unresolved |
| `compliance N` | 6 | Does the diff's FILE SET match Section C? | 0 agreement, 3 finding, 4 unknown |
| `head-check N` | 6 | Does the record exist at the PR head? | 0 present, 1 absent, 4 unverified |

Every "cannot answer" state has its own verdict and exit code. None of them is
ever rendered as clean, agreement or present (#1014, #800).

## Reconcile (`reconcile`, Step 1, issue #1080)

A previous run in this worktree may have left a plan record at
`docs/flow-runs/issue-<N>.md`. `reconcile` returns it to its last COMMITTED state
before Step 2, on EVERY lane including `current-branch` and `resume`.

**The invariant:** after this, the record on disk is exactly the last APPROVED
record for this issue, or absent because none was ever approved on this branch.
That is what makes a later absence mean something - "Step 3 was not reached in
this run" rather than "nobody got around to writing one".

**Why not simply delete it.** Deleting unconditionally was the first design and
it fails worse than the staleness it prevents. Run A completes, writes its record
and commits it. Run B reuses the worktree, deletes the record here, then stops
before Step 3 or is killed. The branch now carries run A's code with NO approval
record, and if anything stages that deletion the PR shows the record being
removed. A stale record is a WRONG answer; no record over committed code is NO
answer, on a branch that previously had one.

**Why not simply leave it.** An UNTRACKED record is a dead run's scratch: some
earlier run wrote it at Step 3 and died before committing. Left in place, Step
6's staging sweeps it into THIS run's commit, and a plan nobody approved in this
run ships as though it were this run's approval.

So tracked is EVIDENCE and is restored; untracked is SCRATCH and is removed. A
tracked record carrying uncommitted edits is restored to the committed version
rather than kept, because the committed version is the one a reviewer actually
signed - which also means this file is not a place to hand-edit between runs.

## Read the issue body, and record WHEN (`read-issue`, Step 1, issue #1081)

A run's stage-1 facts all live in a GitHub issue body: mutable, carrying no SHA,
with an edit history git cannot see. Capture what this run READ, so a later check
can report that the source moved instead of nobody noticing.

**Nothing is written into the worktree at Step 1.** `read-issue` stores the body
and its digest in the git directory. The `gh` fetch is not controlled - stubbing
it would test the stub - so `--body-file` replaces only that call, and the
decision over local files is what the tests drive.

**The state lives in the GIT DIRECTORY, not in shell variables and not in the
worktree.** An agent runs Step 1 and Step 4 in SEPARATE shell invocations, so a
filename or digest held in a variable is gone by the time the writer needs it -
a successful fetch would then produce an `unresolved` snapshot, and a test that
ran both blocks in one shell would never show it (counter-model review,
gpt-6-astra). `git rev-parse --git-dir` is deterministic, is per-worktree, and
survives across calls.

It is also invisible to the driver guard: measured, `git status --porcelain
--untracked-files=all` reports 0 lines with a file present inside `.git`. So the
state can be written at Step 1 without the hazard that forced the file itself to
Step 4.

**Why the file is not written here.** `flow-live-driver-guard.sh` runs later, in
Step 4, over `git status --porcelain --untracked-files=all` with a 30-minute
freshness window, and `docs/flow-runs/` is not excluded from it. A file written
at Step 1 is a fresh UNTRACKED path when that guard runs, which is the phantom
second driver - the same defect the plan record hit, arriving earlier and so more
certainly fresh.

**It would also have been intermittent, which is worse than broken.** Under 30
minutes from Step 1 to Step 4 the guard fires; over 30 minutes it does not. Fast
ordinary runs would break while slow deliberate ones - exactly the runs where
someone is watching, such as one waiting at the Step 3 gate for a reviewer -
would pass.

A git-directory file is invisible to the guard because it is not in the worktree. The
evidence claim is "this is what the run read, and when", and `read_at` carries the
"when" as a FIELD at least as well as an early write would - the early write is
the only part the guard objects to.

### Why `reconcile` asks HEAD, and restores from HEAD

**Ask HEAD whether the record EXISTS, not the index.** `git ls-files` answers
"is this path in the INDEX", which is a different question and wrong in both
directions (counter-model review, gpt-6-astra). Measured, with the index-based
test:

| state | result |
|---|---|
| committed record with a STAGED DELETION (`git rm --cached`) | file deleted, deletion still staged - an APPROVED record destroyed |
| record STAGED but never committed | `UNAPPROVED scratch` left in place and still staged |

Both are reachable, and the second is the exact failure the untracked branch
exists to prevent. `git cat-file -e HEAD:<path>` asks the question the invariant
is written in - "was this ever committed on this branch" - and
`git checkout HEAD -- <path>` then restores the index as well as the worktree, so
a staged deletion is undone rather than preserved. With the HEAD-based test the
same two states yield `approved by A` with nothing staged, and absent with
nothing staged.

**`HEAD --`, never a bare `--`.** `git checkout -- <path>` restores from the
INDEX, not from HEAD, and the state where those differ is reachable by this
document's own design: Step 6 stages the record, so a run that stages it and then
dies leaves the record tracked AND staged with that run's content. A bare `--`
there restores the STAGED version - a plan approved in a DIFFERENT run - and this
run then commits it at Step 6 as its own approval, which is precisely the failure
the untracked branch above exists to prevent, arriving by the staged path.
Measured: with run B's scratch staged over run A's commit, `git checkout --`
yields run B's text while `git checkout HEAD --` yields run A's and clears the
staged diff. The invariant says "approved on this branch", which means COMMITTED,
and the HEAD anchor is what makes the command mean that.

## Writing the record (Step 4, issue #1080)

**Step 4 is reached only when Step 3's approval was granted**, so this is the
first point at which a record of an APPROVED plan can honestly be written, and
writing it here leaves the approval gate itself byte-identical. A
`No longer needed` verdict stops at Step 3 and never reaches this line, so it
writes no record - there was no plan to approve, and an empty record would
assert that there was.

That placement is deliberate and was corrected here: the first draft wrote the
record inside Step 3, which widened the gate the issue explicitly says not to
widen ("Do not widen Step 3's contract. Only the destination is new") and was
caught by `test_counter_model_review.py::test_adding_the_stage_LEFT_THE_ELI5_
GATE_BYTE_IDENTICAL`, which asserts that section is unchanged from `origin/main`.
The destination is new; the gate is not.

**The record does not name the knowledge-lifecycle document, deliberately, and
this paragraph must not name it either.** That policy has exactly three bounded
entry points among command bodies (`claude-md/lint.md`, `flow/finish.md`,
`project/init.md`, plus their generated mirrors), and
`check-claude-md-behavior.py` reports any fourth as a
`non-boundary-lifecycle-pointer` by matching the FILENAME anywhere in the file -
so a paragraph explaining the rule trips it exactly as a real pointer would.
That is not a flaw in the check; a bounded set of entry points cannot be
enforced by a matcher that tries to tell a citation from an explanation.

The authority names its subjects rather than the other way round: the
knowledge-lifecycle document names flow run records and counter-model receipts
as records of decisions that do not graduate, so the linkage exists where it can
be maintained. The record states its own status in its header instead, which is
what a reader of one actually needs.

**Markdown, and that is a measured constraint rather than a preference.**
`.gitignore` carries a blanket `*.json`, so a JSON record at this path is
ignored - and `git add` skips an ignored path and reports no error, so the record
would vanish from every PR silently. Verified by EXIT CODE, not by reading
`check-ignore`'s output: `docs/flow-runs/issue-N.md` exits 1 (not ignored),
`docs/flow-runs/issue-N.json` exits 0 (ignored, via `.gitignore:54`). A
machine-readable form needs its own `!` negation FIRST, exactly as
`docs/measurements/counter-model/*.json` has at `.gitignore:160` - see the note
at Step 6 item 1 on why the negation is what makes a plain `git add` safe there.

**There is no `auto-granted` value and no code path that writes this file without
an approver** (issue #775). The record is written only after approval, and its
approver field comes from the actual approval event - so there is no value to
validate against. A field that can still be PRODUCED means something can still
skip the gate, and a validator rejecting the value is only a second chance to get
it wrong.

**A verdict of `No longer needed` writes NO record.** The run stops, there is no
plan to approve, and an empty record would assert that one was.

## The snapshot and the baseline (`approve`, Step 4, issues #1081, #1082)

The body read at Step 1 is written into the worktree now, in the same safe
position as the record and for the same reason.

**The approval baseline is stamped here, before any implementation edit** (issue #1082).
The plan record is not COMMITTED until Step 6, which is after the work is
written - so "unchanged since its first commit" cannot detect an implementer who
grows the record and the diff together before that commit. The baseline is
therefore taken here, at the moment the approved plan is written, and kept in the
git directory where the driver guard cannot see it and `git worktree remove`
reaps it.

**The digest covers the FULL body; the 16 KB cap bounds only what is STORED.**
Digesting the truncated copy would mean that for any issue past the cap, a change
BEYOND it produces an identical digest and the check reports no drift - a
blindness rendering as clean, in precisely the case the cap exists to handle.

**The cap is measured, not chosen - and the measurement is a SAMPLE.** Across the
40 most recent issues at the time of writing (2026-09-21) the mean body was 4,271
bytes, the median 3,833, p90 6,877, and the largest 12,898 (#1132). So 16 KB held
every body IN THAT SAMPLE with roughly 3 KB of headroom. It does not establish
that no body in this repository has ever exceeded it, and it is not a prediction
about future ones - which is why exceeding the cap is a supported, explicitly
reported state rather than an error. Re-measure with:

```bash
gh issue list --state all --limit 40 --json number,body \
  --jq '.[] | "\(.body|length) #\(.number)"' | sort -rn | head -5
```

**`updatedAt` is recorded as context and is never the verdict.** It moves on
comments, labels and assignment, not only on body edits, so keying drift on it
would report a changed contract for every comment - and a check that cries wolf
gets ignored, which is worse than not having it.

**Why the record is written after the Step-4 checks, not at the top of Step 4.** The
driver-guard and stale-base checks are explicitly "run BEFORE the first edit", and writing the record IS the
first edit. `flow-live-driver-guard.sh` collects tracked-modified AND untracked
paths touched within 30 minutes; a record written before it is a fresh untracked
file, so the guard would report `suspected` on every ordinary single-driver run
and the procedure would stop to ask about a second driver that does not exist.
Its own text states the premise this breaks: "dirty files here were modified in
the last 30m and you have not written anything yet, so they are NOT yours."
Found by counter-model review (gpt-6-astra); the ordering is load-bearing, not
cosmetic.

## Issue drift (`drift`, Step 6 item 6, issue #1081)

The fetch is I/O that needs `gh` and a live issue; the verdict is a decision
over two local files. `--live-file` replaces only the fetch, so the decision can
be controlled with real inputs instead of a stubbed `gh`.

**A failed fetch and a missing snapshot are UNRESOLVED, never clean.** The
check cannot answer, and an unanswerable question rendered as a clean verdict
is the defect this wave has met most often - including one built deliberately
in this very step for the plan record, where a failed query and a genuine
absence printed the same line and both exited 0. Note the ordering: the
unresolved branches are tested BEFORE the comparison, so no path reaches
`clean` without a digest on both sides.

**Drift prints a DIFF, not a boolean**, because "acceptance criterion 3 gained
a clause" is actionable where "the issue changed" sends someone to re-read the
whole thing. Where the stored copy was truncated the diff covers the stored
prefix only; the digest still covers the whole body, so DETECTION is complete
even when the naming is partial.

## Plan compliance (`compliance`, Step 6 item 7, issue #1082)

It REPORTS; it never blocks. The issue contract already lets an implementer substitute a
better approach and owe the reviewer the reason - this surfaces that the
substitution happened so the reason gets written down.

**First, make new files visible.** `git diff <ref>` compares the ref's tree to
the INDEX for paths the index already knows, so an untracked path is skipped
entirely. Without this the check reports AGREEMENT with an entire unplanned new
file in the tree - measured, and the exact case this issue names. `code_review.md`
fixed that for the REVIEW diff (#1030); this step computes its own
diff, so it inherited nothing.

**The rules the helper encodes, each found the hard way:**

- **Enumerated paths only, never `git add -N .`** - `-N .` stages a tracked
  DELETION rather than a placeholder (`code_review.md`).
- **NUL-delimited, never through a shell variable** (issue #1220). Command
  substitution strips NUL bytes, so N untracked paths were glued into ONE
  pathspec, `add -N` rejected it, and every change adding more than one file
  reported `unknown`. The helper holds the list in memory; the two-file case,
  one name carrying a space, is a committed test.
- **A failed enumeration or a failed intent-to-add is `unknown`.** Either would
  otherwise let agreement be reported without establishing whether new files
  existed.
- **EVERY numbered Section C line must parse.** Skipping an unmatched one drops an
  approved file from the population, and agreement then means "the subset I
  happened to understand matched" - a filename containing a space is enough.
- **`--no-renames`.** With rename detection on, `--name-only` reports only a
  rename's DESTINATION, so renaming an unplanned file onto a planned one reports
  agreement while the removal was never authorised.
- **EXACT exclusions, not prefixes.** Only this issue's plan record, its as-read
  snapshot and its own counter-model receipt are excluded. `issue-42.` as a
  prefix would also accept `issue-42.notes.md`; the receipt directory as a prefix
  would hide edits to OTHER runs' receipts, which #1171's enrolment check does
  not cover.
- **Generated mirrors are DERIVED, not excluded.** A `codex/skills/` path is
  attributed to its source (by path, or by its GENERATED header); it is fine when
  that source is planned and a divergence when it is not. Excluding the mirrors
  outright would hide real drift in the largest category by file count.
- **The record is the check's own input.** Its digest is compared against the
  baseline `approve` stamped at Step 4 - not its first COMMIT, which happens at
  Step 6 after the work and would miss a record grown together with the diff.

**`--name-only` answers "what did this change touch", never "what exists at
head".** A deleted path is listed while `git cat-file -e HEAD:<path>` reports it
absent - measured. For THIS question the listing is correct: a deletion IS a
touch the plan should have named. `head-check` asks the other
question and uses existence at head.

**The verdict says FILE SET deliberately.** A file-level comparison cannot see
whether the change did what was agreed, so a run that rewrites a file
completely differently from its plan reports agreement.

## The record at the PR head (`head-check`, Step 6 item 8, issue #1080)

Ask whether the record EXISTS at the PR's head, not whether its name appears in
a diff.
A record present in the worktree but absent from the PR is the failure this
check exists for, and it is silent at every earlier stage: `git add` skips an
ignored path without an error, and the Step 7 squash flattens whatever it was
given. Checking `git status` locally would confirm the file exists and prove
nothing about what ships. Skip this when the run wrote no record - a
`No longer needed` verdict has none to find.

**Three ways the obvious version of this check is wrong**, all found by
counter-model review (gpt-6-astra) and all reproduced:
- `gh pr diff --name-only` lists DELETED paths too, so a run that removed the
  record passes a name check while the PR head carries no record at all.
  Existence at the head SHA is the question; a diff is not.
- `grep -qx "docs/flow-runs/issue-42.md"` treats `.` as any character and
  accepts the neighbouring name `docs/flow-runs/issue-42Xmd` - reproduced
  exactly. Compare paths literally (`-F`), or better, do not compare strings
  at all, as the helper does.
- `... || echo "STOP: ..."` makes a failed query and a genuine absence print
  the same line and BOTH exit 0, so the advertised STOP cannot stop anything
  and "I could not look" is rendered as "I looked and it is missing". The
  helper separates the two: `absent` exits 1, `unverified` exits 4, and the
  procedure STOPs on both.
