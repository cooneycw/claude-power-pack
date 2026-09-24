# /flow:auto reading and execution - before and after #1211

The first bounded simplification that issue #1211 asked for. The six plan-record
programs pasted into `.claude/commands/flow/auto.md` (#1080, #1081, #1082) now
live in one tested helper, `scripts/flow-plan-record.py`. The procedure calls
that helper and says what each verdict means. The reasoning and incident history
moved to `docs/agents/flow-plan-record.md`, which the procedure links as
background and does not require.

- **Before:** `0adc4d59757e2f2ab4d33a1291439cc992cd03c9` (main when this run
  started editing).
- **After:** the #1211 branch.

## Method

The issue's own method, unchanged. For words, `len(text.split())`; for lines,
`len(text.splitlines())`. `text` is the committed blob (`git show <ref>:<path>`)
for the "before" column and the branch file for "after". These counts are NOT
model tokens, NOT an observed record of what a model read, and NOT a runtime
measurement. They are the reading this procedure REQUIRES.

## Chosen paths

- **Common path.** An ordinary run through Steps 1-9 in which every check is
  clean.
- **Failure / recovery path.** Step 6 item 8 finds the plan record ABSENT at the
  PR head. This must STOP, and recovery must be possible from the step itself.

### What each path must read

| Required reading | Why required | Before | After |
|---|---|---:|---:|
| `.claude/commands/flow/auto.md` | the whole file is the command | 20,671 | 17,102 |
| `.claude/commands/flow/eli5.md` | Step 3: "Load the FULL gate spec first" | 2,354 | 2,354 |
| **Common path, total** | | **23,025** | **19,456** (-15.5%) |
| **Failure path, total** | the same file carries the STOP and its recovery | **23,025** | **19,456** (-15.5%) |
| Codex: `codex/skills/flow-auto/SKILL.md` + `reference.md` | SKILL.md: "Read `reference.md` ... before acting" | 278 + 20,681 | 278 + 17,112 |

**Not required on either path:** `docs/agents/flow-plan-record.md` (3,248 words,
new). The procedure links it three times, each time as "background, not required
reading". A reader who never opens it still has every call, every verdict, every
STOP and the one recovery. Moving the same text behind a MANDATORY link would not
have counted; this link is optional, and nothing in the procedure depends on it.

The other `docs/` links in `auto.md` were already optional before this change and
are unchanged. The Step 3 section is byte-identical, which
`tests/test_counter_model_review.py` asserts.

### Where the reduction is

| `auto.md` region (plan-record family) | Before (words / bash fences) | After |
|---|---:|---:|
| Step 1: reconcile + read the issue | 1,163 / 3 | 265 / 1 |
| Step 4: write the record, snapshot, baseline | 1,435 / 4 | 424 / 2 |
| Step 6 items 6-8: drift, compliance, head-check | 2,072 / 4 | 412 / 3 |
| **Family total** | **4,670 / 11** | **1,101 / 6** (-76% words) |

The Step 3 plan estimated "~5,700 words" and "auto.md down ~4,500". The
measurement is 4,670 words in the family and -3,569 words overall. The estimate
was high: it counted section headings and the record template, which stay.

### Recovery at the step that needs it

- **Before**, item 8 said STOP when the record was missing and gave no recovery.
  It also said STOP when the PR head could not be read at all, and both cases
  exited 1.
- **After**, the two cases have different verdicts and exit codes:
  - `absent` is exit 1, and the step itself names the recovery (stage, commit,
    push, re-run).
  - `unverified` is exit 4, and the step names its check (`gh auth status`, the
    network).
- A missing helper is also a STOP, with `/flow:repair` as the recovery
  (counter-model finding). The pasted blocks could not be missing, so the
  extraction added this failure mode, and the procedure now names it.
- Neither case needs the reference doc.
- Both are committed cases in `tests/test_flow_plan_record.py`, run against the
  helper.

## Execution

### Bash calls an agent issues for the family

- **Before: 10.** Reconcile, fetch, record, write record, write snapshot, stamp,
  drift fetch, drift verdict, compliance, head-check.
- **After: 7.** `reconcile`, `read-issue`, write record, `approve`, `drift`,
  `compliance`, `head-check`.
- Every call is now a bare invocation that matches a permission prefix rule
  (`Bash(~/.claude/scripts/flow-plan-record.py:*)`). Before, the blocks had
  multi-line variable assignments or heredoc Python, which can never match a
  prefix rule (#581).

### Elapsed time on a pinned fixture

**Setup:**
- Fixture: a 40-file repository and a 3,600-byte issue body. The change touches
  one planned file and adds two untracked files, one of them with a space in its
  name, which is the #1220 shape.
- Before side: the old blocks, extracted with the markers the pre-change tests
  used.
- After side: the helper subcommands.
- Both sides reach the SAME verdicts: `ISSUE_DRIFT: clean` and
  `PLAN_COMPLIANCE: agreement (3 planned, 5 touched)`.
- `gh` is excluded from both sides: the body comes from a file, and head-check is
  not timed, because it needs a live PR.
- 15 iterations per side, run twice.

| | calls | median | min-max |
|---|---:|---:|---:|
| before, run 1 | 6 | 142 ms | 132-155 ms |
| after, run 1 | 5 | 301 ms | 266-332 ms |
| before, run 2 | 6 | 159 ms | 145-169 ms |
| after, run 2 | 5 | 313 ms | 293-359 ms |

**The helper is SLOWER, by about 150 ms per run in total.** It was not
a speedup and should not be described as one. The cost is Python start-up plus
`git rev-parse` calls in each of five processes; caching the repeated lookups
did not change it measurably. Against a `/flow:auto` run measured in minutes,
0.15 s is immaterial. It is reported because the issue asks for a measurement,
not an assumption.

### Gate invocations

**Unchanged.**
- `flow-finish-gate.sh` still runs once at Step 6, plus the conditional Step-7
  re-gate. Neither step was touched.
- Nothing about which checks run was reduced. Every check the family ran
  before, it runs now, with the same verdict words.

## What became simpler, what stayed, what was not measured

**Simpler:**
- The procedure lost 3,569 words of required reading and five pasted programs.
- The agent issues three fewer Bash calls, and every one is now allowlistable.
- Behaviour that lived in a document now lives in one script that the tests run
  directly.
- `head-check` had no test before this change and now has four.

**Kept, with the same verdict words:**
- `unresolved` and `unknown` are never rendered as clean.
- `reconcile` still asks HEAD, not the index.
- The digest covers the full body.
- `--no-renames` and the exact exclusions are unchanged.
- The Step-4 baseline is still stamped before implementation.
- The record at the PR head is still a STOP.

**Two distinctions were sharpened:**
- head-check "could not look" (exit 4) is now separate from "absent" (exit 1).
- A missing `origin/main` merge-base is now its own `unknown` rather than an
  empty-base diff.

**Retained duplication, and why:**
- The record template stays inline, because the agent writes the plan text.
- The per-helper resolution fallback paragraph is repeated elsewhere in
  `auto.md`; unifying it touches every step and was out of this slice.
- The twin codex re-sync commentary in Steps 6 and 7 is guarded by
  `tests/test_codex_skill_resync.py`; it was left for a separate change.

**Not measured:**
- Model tokens or billed usage.
- What any model actually reads.
- Task correctness or delivery cost.
- Anything about a real `/flow:auto` run other than this one.

Those belong to #1084's behavioral evaluation and are unproven here. The other
opportunities in #1211 (finish-gate comment weight, `cpp/init.md` and
`cpp/update.md`, #1192, #1206/#1083, #1084) are untouched and stay with their
owners.

## Reproduction

Reading counts:

```python
import subprocess
ref = "0adc4d59757e2f2ab4d33a1291439cc992cd03c9"
for path in [".claude/commands/flow/auto.md", ".claude/commands/flow/eli5.md",
             "codex/skills/flow-auto/SKILL.md", "codex/skills/flow-auto/reference.md"]:
    for label, text in (("before", subprocess.run(["git", "show", f"{ref}:{path}"],
                                                  capture_output=True, text=True).stdout),
                        ("after", open(path).read())):
        print(path, label, len(text.split()), "words", len(text.splitlines()), "lines")
```

Timing: extract the six blocks from `git show <before>:.claude/commands/flow/auto.md`
with the markers `#### Reconcile the plan record (issue #1080)`,
`Record what was read - a decision over local files`,
`#### Also write the as-read snapshot here (issue #1081)`,
`**Stamp the approval baseline now, before any implementation edit**`,
``Verdict - `$SNAP` is the as-read snapshot`` and
`7. **Compare the diff against the approved plan** (issue #1082)`.

Run each block as its own `bash -c` process in a fresh fixture, then run the
helper subcommands in an identical fresh fixture. Time each side end to end and
take the median of 15 iterations per side. Supply the body with `--body-file` /
`--live-file` on the helper side and by writing the git-dir store on the block
side, so neither side calls `gh`.
