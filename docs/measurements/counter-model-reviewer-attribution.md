# Attributing the 13 landed counter-model receipts (issue #1048)

**Measured 2026-09-20.** Disposition: **annotate, do not rewrite** (owner ruling,
this issue). The 13 receipts keep their bytes. This file is what says what was
actually true.

## The question

Thirteen receipts under `docs/measurements/counter-model/` record the reviewer
`codex/gpt-5.5`. That value was copied out of a worked example in
`.claude/commands/flow/auto.md`, not observed. #1045 removed the literal and
#1059 made the writer derive the reviewer from the review's own exec log and
refuse when it cannot - so no new receipt can inherit it. Neither touched the 13
already on disk.

#1048 recorded the boundary carefully: **1 of 13 verified wrong** (issue-1017,
checked against its own transcripts by a peer session), **12 unverified** - not
known-wrong, merely unchecked. The disposition was blocked there, because
`docs/scripts.md` recorded that it could never be unblocked:

> "real receipts carry no field connecting them back to the exec log or
> thread_id that produced them, so retroactively verifying anything already on
> disk is structurally impossible"

**That premise is false.** A receipt records `branch`. A Codex rollout records
its own `cwd` - the per-issue worktree directory, which is named for that branch
- and a start timestamp. That is an association, and it is the one real receipts
actually carry.

## The instrument

`scripts/counter-model-reviewer-attribution.py`, controlled at
`controls/counter-model-reviewer-attribution/`, ADR 0008 census row 89.

```
python3 scripts/counter-model-reviewer-attribution.py \
    --receipts-dir docs/measurements/counter-model \
    --rollouts-dir ~/.codex/sessions
```

The repository is derived from git's common dir, not the checkout's basename -
this runs inside a worktree named `claude-power-pack-issue-1048-...`, and a
worktree is linked only when its directory is exactly `<repo>-<branch>`. Where
neither derivation nor `--repo-name` establishes a repository, the scan refuses.

## The result

```
ATTRIBUTION-SUMMARY: examined=29 linked=28 agreed=15 disagreed=13 ambiguous=0 \
                     unlinked=1 extractor_distinct=9 repo=claude-power-pack
```

All 13 disagreements are the same shape: stored `codex/gpt-5.5`, linked rollout
`codex/gpt-6-astra`.

| receipt | issue | linked rollouts | model(s) |
|---|---|---|---|
| `2026-09-15T173825Z-issue-934.json` | #934 | 4 | gpt-6-astra |
| `2026-09-15T190048Z-issue-938.json` | #938 | 2 | gpt-6-astra |
| `2026-09-16T104739Z-issue-1015.json` | #1015 | 2 | gpt-6-astra |
| `2026-09-16T110259Z-issue-1011.json` | #1011 | 2 | gpt-6-astra |
| `2026-09-16T112043Z-issue-1016.json` | #1016 | 2 | gpt-6-astra |
| `2026-09-16T114553Z-issue-1012.json` | #1012 | 2 | gpt-6-astra |
| `2026-09-16T203327Z-issue-1013.json` | #1013 | 2 | gpt-6-astra |
| `2026-09-16T205221Z-issue-1017.json` | #1017 | 2 | gpt-6-astra |
| `2026-09-16T205850Z-issue-937.json` | #937 | 2 | gpt-6-astra |
| `2026-09-16T211340Z-issue-958.json` | #958 | 2 | gpt-6-astra |
| `2026-09-16T212911Z-issue-922.json` | #922 | 2 | gpt-6-astra |
| `2026-09-16T213245Z-issue-1022.json` | #1022 | 2 | gpt-6-astra |
| `2026-09-16T213932Z-issue-961.json` | #961 | 2 | gpt-6-astra |

No linked rollout for any of the 13 records `gpt-5.5`, and **no rollout on this
host records it at all** - 0 of 452.

## Why this reading is trusted, stated as controls rather than as confidence

A sweep that reports one value everywhere is the defect this issue is about, so
the reading is worth nothing until the instrument is shown to discriminate.

1. **The extractor discriminates.** Across the host's rollouts it reads **9
   distinct model values** (`gpt-6-astra` 278, `gpt-5.6-sol` 160,
   `qwen3.8-code:latest` 7, `qwen3-235b-a22b` 2, and five singletons including a
   deliberate `definitely-not-a-model`). `extractor_distinct=9` is printed in the
   summary above, on every run. The zero for `gpt-5.5` is a measured absence, not
   a blind one.
2. **The instrument refuses when it cannot discriminate.** `extractor_distinct
   <= 1` downgrades any finding to `ATTRIBUTION-UNKNOWN`. The committed case
   `bad-blind-extractor` supplies a disagreement byte-identical to
   `bad-disagreement` and differs only in the rollout population; the verdict
   must differ with it. Deleting that branch turns 3 tests red, including
   `test_a_blind_extractor_WITHDRAWS_the_finding_its_twin_reports`.
3. **The linkage agrees with ground truth.** The 16 receipts written after #1059
   had their reviewers *derived* by the writer's thread-anchored lookup, so they
   are independent of this method. It agrees with **15**, disagrees with **0**,
   and could not link **1**. That is the `agreed=15` in the summary - the control
   is inside the instrument's own output, not a separate claim. It also separated
   the `gpt-5.6-sol` receipts from the `gpt-6-astra` ones, which is the exact
   discrimination required.
4. **It reproduces the one independently verified case.** issue-1017 was checked
   against its own `codex exec` transcripts by a peer session, which read
   `gpt-6-astra`. This method returns `gpt-6-astra`. A positive control on the
   only specimen where an answer was already known.
5. **Ambiguity is not resolved into a guess.** `ambiguous=0` here, but a receipt
   whose linked rollouts disagree - or whose linked rollouts include one that
   declares no model at all - is verified neither way rather than resolved by
   proximity or recency.
6. **A neighbour cannot supply the answer.** The sessions directory spans every
   repository on the host, and `<another-repo>-issue-9001-alpha` ends with the
   same branch as ours. Linking requires the worktree basename to equal
   `<repo>-<branch>` exactly. Tightening this did not move the result - the same
   28 links, the same 13 disagreements - which is worth more than the loose scan
   that preceded it: the conclusion survives a stricter instrument.

## The review that shaped this

A counter-model review (2 passes) raised **5 findings, all accepted and fixed**,
4 of them against this instrument rather than against the corpus:

1. a linked rollout declaring no model was silently dropped, leaving the rest
   looking unanimous - so an unreadable candidate that could itself have been
   the reviewer produced a confident agreement;
2. branch-suffix matching could attribute a neighbouring repository's rollout;
3. a non-string `recorded_at` aborted the scan of every other receipt;
4. an empty case registration passed the self-test, so deleting the population
   left it green while exercising nothing;
5. the generated `codex/skills/flow-auto/` copy of the instrument was synced
   before those fixes and still carried all four.

Findings 1, 2 and 4 are the same class as the defect being investigated: an
instrument reporting more than its input supports. They are pinned by the
committed cases `bad-unreadable-candidate`, `bad-foreign-repo`, and the
required-case assertion in `--selftest`.

## What this does NOT establish

- **It is an inference, not an identity.** It anchors on a directory name and a
  time window. The writer's own derivation (#1059) anchors on a thread id, which
  is strictly stronger. The 15/16 agreement rate is this method's measured error
  bound; it is not zero-by-construction.
- **Which rollout in a worktree was the review.** An attempt to anchor on
  review-shaped text matched *every* candidate, so it discriminated nothing and
  is claimed as nothing. It does not matter for the conclusion: within each
  worktree every candidate agreed, so any choice among them yields the same
  model.
- **That the 12 were "known wrong" before now.** They were not. #1048's boundary
  was correct when written. This file changes it with evidence rather than
  asserting it was always so.
- **A permanent result.** `~/.codex/sessions` is host-local and is pruned. Re-run
  later and `linked` will fall as rollouts age out; `unlinked` is not a finding.
  This file is the durable record precisely because the input is not.

## Disposition

**Annotate, do not rewrite.** The 13 receipts are unchanged, `issue-1017`
included.

Each receipt records what its run believed at write time, and that is itself the
evidence of how a documented literal propagated across thirteen independent runs
- the thing that made this worth an issue rather than a typo fix. Rewriting them
would destroy that and leave a corpus that merely looks correct. The receipts say
what was recorded; this file says what was true; the instrument lets anyone
re-derive it.

The standing rule in `.claude/commands/flow/auto.md` is kept, with its rationale
corrected: it said rewriting "would assert that a different model reviewed work
it never saw". On the evidence that is backwards - `gpt-5.5` is the model that
never saw the work. The rule survives for the better reason, which is that a
contemporaneous record is worth more than a tidy one.

Refs #1045, #1046, #1047, #1059, #1091, #934, ADR 0007, ADR 0008
