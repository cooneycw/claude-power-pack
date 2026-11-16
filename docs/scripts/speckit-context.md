# `speckit-context` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `speckit-context`

- speckit-context - resolves, renders and refreshes the task-context cache in a generated issue (#858). A generated issue used to carry its provenance and dependencies and nothing about the behaviour it was meant to produce, so a receiving agent could not tell which words were the goal and which were somebody's suggested mechanism. The rendered block is a CACHE, not a second authority: the spec it names stays authoritative, every part traces to a source section and carries a digest, so drift is visible instead of silent. `check` emits `SPECKIT_CONTEXT_STATE`, whose values separate facts a consumer must act on differently - `changed-in-scope`/`changed-outside-scope` are a byte difference and NOT a ruling that acceptance changed, `changed-task` means the task line or its story tag moved so the cached mapping no longer holds, `block-edited`/`block-damaged` mean the block is unreliable, and `absent` is an ordinary issue whose body is the contract. A failed `gh` leaves an empty body and an empty body reports `absent`, which is why `/flow:auto` Step 2 checks the fetch succeeded before believing the verdict


## What a run does with each state

Moved here from `/flow:auto` Step 2 (#1850, owner ruling G3-5); the procedure points here.

After `speckit-context.py check` in `/flow:auto` Step 2, act on `SPECKIT_CONTEXT_STATE`:
- `current` - read the **Reference source** named in the block, including
  the cross-cutting sections it lists, then plan.
- `changed-in-scope` / `changed-outside-scope` - source bytes changed, which
  is NOT a ruling that acceptance changed. Read the source, decide whether
  it matters under the existing authority model, and say so in the Step 3
  report. Newer bytes do not by themselves override a constraint or plan
  already accepted on the issue. Report any recorded `Acceptance-revision:`
  line with the version it names, and resolve whether it predates the change.
- `changed-task` - re-read the task line and its story; treat the block's
  requirement list as provisional.
- `tasks-missing` - plan from the issue body and the source if one resolves;
  report that the task-side mapping could not be re-checked.
- `block-edited` / `block-damaged` - read the source directly; do not
  refresh the block as a side effect of this run.
- `source-missing` / `source-unresolved` - plan from the issue body and
  surface any material ambiguity.
- `absent` - an ordinary issue. Its body IS the contract (see
  [the issue contract](../agents/issue-contract.md)).

The block's **Task wording** line is the task's own sentence, not a ruling:
resolve whether it proposes an approach you may replace or restates a binding
constraint. Resolve what would change the work, surface the rest in the
Step 3 report, and plan from what you have.
An **Unresolved** or **Capped** note means the context is incomplete - never
that the task has no constraints. Missing optional structure is not a gate.
