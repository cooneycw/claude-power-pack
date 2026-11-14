# Delegated plan and lane records (#1809)

The executable order, commands, stop conditions and verdict handling live in
`templates/delegated-driver-core.md`, rendered into the three delegated auto
commands. This reference explains that procedure; it does not define another
approval mechanism or lane parser.

## One run, one approved record

The drivers previously presented a prompt and waited for approval but created
no canonical plan record. Reusing the existing helper requires its lifecycle:
reconcile, record the issue body as read, begin this run's section, append what
was genuinely approved, then approve before implementation. Reconcile restores
committed history rather than deleting it and keeps ownership in the active
worktree's git directory. A child implementation thread is not the approving
orchestration session.

The record and issue snapshot are append-only by run. Earlier sections cannot
stand in for the current approval. Section C's numbered source paths are what
compliance compares with the changed file set; inventing them after seeing the
diff would erase the comparison. Scope and risks terminate the file list. The
parent writes the record, snapshot and demonstrated evidence; the fenced model
receives the approved implementation and lane-test obligations and must not
rewrite approval history to make a later comparison agree.

Approval has two different unavailable states. An unreadable lane list prevents
approval and names that uncertainty. A missing issue-body snapshot instead
retains the existing AS_READ-unresolved exit 4: the baseline is stamped, the run
can continue, and its source evidence is explicitly unresolved. Neither state
means the issue was unchanged or the lanes were demonstrated.

## Plan, observation and evidence

The project supplies the lane names. The helper's existing project_lanes and
lanes_refusal implementations decide whether the approval table answers them;
no driver owns a second parser. No adopted lane file means no lane table or
question is owed. A reasoned one-line waiver remains visible to the approver,
not a hidden permission to skip the table.

The table's truth is not machine-checked. Claude remains the independent
reviewer of the delegated implementation and receives the same lane question
as the Codex review surface. Recorded model observations on illustrative
omitted/complete plans do not establish live Claude obedience.

Demonstrated rows live separately so that recording results does not modify the
approved plan's digest. An absent promised result is named on compliance's
existing verdict, and unreadable evidence is not scored as demonstrated. These
are advisory reports, not new quality-gate exit meanings. An acceptance closing
reference still needs the actual acceptance accounting.

## Why evidence is not product work

Creating plan records before delegation makes the old raw status count nonzero
even if implementation writes nothing. A pre-review product check therefore
ignores only this issue's orchestration evidence. The final check must use the
same definition: a quality-gate fix can revert the product after review while
leaving the metadata behind. Counter-model receipts also are evidence, so the
same definition closes the older receipt-only finish gap.

The shared definition is written once into the worktree git directory and
loaded in each fresh guard shell. It excludes exactly this issue's plan,
as-read and demonstrated paths and directly contained counter-model receipt
names ending in -issue-N.json. Another issue's records or receipts, and other
files under those directories, remain product. Directory-wide exclusions
would hide unrelated changes. Failure to load the definition is a stop, never
a clean result. The finish block resolves its merge base and invokes compliance
in one shell; variables in another tool call are not shared state.

## Packaging and readers

These are existing-format flow-run artifacts newly produced by delegated runs,
not a new schema. Kyle coordination is about that additive route; no parser
migration is implied. The exact helper verbs added are reconcile, read-issue,
begin-run, approve and compliance. Other driver-parity gaps remain separate.

Codex, Qwen and Gemma command families remain intentionally unpackaged as Codex
skills. The installed Codex lane exercises the existing flow-auto bundle's
standalone helper, not nonexistent delegated mirrors. The shared core/vendor
check keeps the three Claude command procedures synchronized.
