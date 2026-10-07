# Execution evidence - the `/flow:check` pilot (issue #1366)

A small, machine-readable record of what the CPP runner actually executed during
`/flow:check`, kept after the run so an auditor or CI can inspect it without
replaying the agent. It is a pilot: one skill, built on the runner's existing
step records, not a telemetry platform.

The governing specification - the usage-record fields, the boundary with
skillc's evaluation verdicts, and which ticket owns each #1366/#1367 acceptance
item - is [`.specify/specs/per-skill-audit/spec.md`](../../.specify/specs/per-skill-audit/spec.md) (#1368).

## Why it exists

The runner already records every step in its own state file (`<git-dir>/cpp-
runs/<run_id>.json` in a git repository since issue #1409, `.claude/runs/
<run_id>.json` otherwise), but that file is a RESUME file: `RunState.cleanup()`
deletes it the moment a run succeeds. So a green `/flow:check` left nothing
behind but the agent's own results table - a claim, not a record. The
execution record is written by the helper, from the step records it settled,
and it survives.

## What is covered

| `/flow:check` step | executed by | in the record |
|---|---|---|
| Step 2: lint, test, typecheck | `flow-finish-gate.sh --plan check --evidence flow-check` -> `lib.cicd run --plan check` | yes, one entry per step |
| Step 2 fallback (no runner: no CPP checkout or no `uv`) | the helper's Makefile lane | no - it prints `CPP_EXECUTION_EVIDENCE: none` |
| Step 4: security gate | agent-run `lib.security gate flow_finish` | no |
| Step 5: Makefile completeness | `flow-finish-gate.sh --check-summary` | no |
| Step 5b: ignored additions | `check-ignored-additions.sh` | no |

The reader's claim names the plan it covers and says that steps outside it are
not attested. Further emitters are a decision for after the pilot.

## Storage, retention and export

- **Where:** `<git-common-dir>/cpp-evidence/<skill>/<invocation_id>.json`. The
  COMMON git dir, like the friction log (#471), so a record written inside a
  flow worktree survives that worktree's removal. It is never inside the working
  tree, so it is never committed and never changes the tree it describes.
- **How:** written to a temp file, fsynced, then renamed into place. A reader sees
  the previous version or the new one, never half of one.
- **Lifecycle:** a non-terminal `begin` record is written first, then exactly one
  terminal record (`completed`, `failed`, or `interrupted` on an exception such
  as Ctrl-C). A terminal record is never rewritten. A process killed outright
  (SIGKILL, power loss) leaves the begin record, `terminal: false` - visible as
  a missing terminal event, never as a success.
- **Retention:** the newest 50 records per skill; older ones are pruned on each
  terminal write. Deleting the clone deletes them. This is local evidence, not
  an archive.
- **Export (opt-in):** `CPP_EXECUTION_EVIDENCE_EXPORT=<dir>` also writes a copy
  there, under the same file name - a CI artifact directory, say. Keep the export
  directory outside the working tree, or gitignored: a file added to the tree
  changes the content signature the reader compares against. Nothing forces
  anyone to commit a record.

## What a record binds

Schema `cpp.execution-evidence/v1`, `record_kind: cpp-usage-record`.

- `invocation_id` (fresh per invocation) and the runner's `run_id`. A resumed
  run keeps its `run_id` and gets a new `invocation_id`.
- `plan_record_run_id`: the `/flow` plan-record run identity (#1080) when this
  worktree has one. Optional - a standalone `/flow:check` needs no issue and no
  approval.
- `observed.repository`: origin URL with any credentials, query and fragment
  stripped; the git common dir; the worktree; the branch.
- `observed.tree_at_start` / `tree_at_end`: HEAD, a `dirty` flag, and the #804
  content signature (a scratch-index `git write-tree`). `dirty` alone cannot
  tell one edit from two to the same file; the signature can.
- `observed.helper`: the CPP commit and SHA-256 digests of the runner modules
  that wrote the record.
- `observed.skill_source`: the digest of the canonical command source in the
  helper's own checkout. Not proof of which copy the agent read.
- `observed.checks[]`, per step: `status` as the runner settled it (`success`,
  `failed`, `skipped`, `subsumed`, `not-run`, `pending`); `exit_code` (null when
  the command never ran - never a made-up 0); `attempted_at` / `completed_at`;
  `executed_in_this_invocation`; `population` (`measured: false` with a null
  count when the tool stated no number - never turned into 0; a measured 0 is a
  real 0); `reason` for a skip, not-run or subsumed step; and `evidence`, which
  holds SHA-256 digests and byte counts of the runner's retained output tail
  only.
- `declared`: what the CALLER said through the environment - the skill name
  (`CPP_EXECUTION_EVIDENCE`), an optional source path (`CPP_SKILL_SOURCE`) and
  an optional parent invocation (`CPP_PARENT_INVOCATION_ID`). Recorded, never
  verified, and kept apart from `observed`.

Never stored: raw command output, error text, the environment, or credentials.
`tests/test_execution_evidence.py::test_privacy_no_credentials_or_environment`
pins that with a synthetic token in the origin URL and the command output and a
synthetic secret in the environment.

## Reading a record

```bash
python3 scripts/execution-evidence-verify.py <record.json>            # vs THIS checkout
python3 scripts/execution-evidence-verify.py <record.json> --path <checkout>
python3 scripts/execution-evidence-verify.py <record.json> --no-current
python3 scripts/execution-evidence-verify.py latest flow-check        # newest made in THIS worktree
```

The store is shared by every worktree, so the reader never lets a record vouch
for itself. Freshness is compared against the CALLER's checkout (the current
directory, or `--path`), never the worktree named inside the record. A record
made in another worktree is `not-supported` here, and `latest` returns only this
worktree's records. Prefer the path the run printed over `latest`.

The verdict is re-derived from the per-check facts, not read from the record's
own `outcome`/`qualifications` summary. A summary saying `completed` over a gate
that did not pass, a success with a non-zero exit, a measured zero population, a
declared gate with no entry, a terminal record with no terminal event, runner
warnings or a recorded targeted re-run each read `not-supported`, whatever the
summary says. A malformed nested record is `unknown`, never a crash. This
catches contradiction, not authorship: a consistent forgery still reads
`supported`.

(`python -m lib.cicd evidence verify|show|latest` is the same reader.)

| verdict | exit | when |
|---|---|---|
| `supported` | 0 | terminal `completed` with a matching terminal event, every declared gate present and `success`/`subsumed` with exit 0, no gate examining nothing, no qualification, warning or re-run, file name equals the invocation id with no duplicate in its directory, and (unless `--no-current`) made in this worktree with the current HEAD and content signature equal to the record's |
| `not-supported` | 3 | anything else that could be decided: failed, stopped (an aggregate failed and gates were `not-run`), interrupted, no terminal event, a gate skipped or examining nothing, runner warnings or a targeted re-run, a summary contradicting its facts, the tree changed during the run, another worktree's record, stale HEAD, the same file edited again since, or a copied/duplicate invocation |
| `unknown` | 4 | unreadable file, unknown schema, missing or malformed required fields (nested ones included), or the current tree could not be identified to compare against |

### Reader example - the pilot artifact

[`docs/measurements/execution-evidence/e5fd38dc103949e2b3f84d7b060862b6.json`](../measurements/execution-evidence/e5fd38dc103949e2b3f84d7b060862b6.json)
is a real record: `/flow:check` Step 2 run on this branch at commit `b8f783b`,
copied out of the store under its own file name (a renamed copy reads as
replayed). Its HEAD has since moved, so it is read without the freshness check:

```text
$ python3 scripts/execution-evidence-verify.py \
    docs/measurements/execution-evidence/e5fd38dc103949e2b3f84d7b060862b6.json --no-current
EXECUTION_EVIDENCE_CLAIM: The CPP runner at commit b8f783bce4cc856957eb8edeca2889f01e6235b5
  executed plan 'check' in https://github.com/cooneycw/claude-power-pack at HEAD
  b8f783bce4cc856957eb8edeca2889f01e6235b5 with working-tree signature
  09bdb65ed841cbebbe51f7b76e65babbcf18e75e (dirty=False): lint success (population not
  measured); test success (7515 test); typecheck success (364 source file). It does NOT
  attest who invoked it, that the file is unmodified, or that any step outside this plan
  ran. Freshness against the current tree was NOT checked.
EXECUTION_EVIDENCE: supported
```

(Wrapped here for width; the tool prints one line.)

**The exact claim it supports:** at that commit and tree, the helper observed
ruff, pytest and mypy exit 0, with 7515 tests executed and 364 source files
type-checked. Lint's population is `not measured`: ruff stated no file count on
this run, and the record says so instead of printing a 0. It does not claim
that `/flow:check`'s security, completeness or ignored-file steps ran, who
started the run, or that the file has not been edited since. Each check also
carries its own `carried_from_previous_run` (issue #1410): this sample's own
producer always writes it, `False` here since nothing was carried.

**The retired sample.**
[`cbf9931314ed45d2927fa5e150daa9d2.json`](../measurements/execution-evidence/cbf9931314ed45d2927fa5e150daa9d2.json)
is the PRE-#1410 historical sample - kept byte-identical, never regenerated,
because skillc pins it by name and sha256
(`evals/subjects/cpp-codex-flow-check/gate_reconciliation.py` and
`tests/fixtures/cpp-usage-record/README.md`). Its checks predate the per-check
`carried_from_previous_run` field the producer now writes (the fact lived only
at `observed.runner.carried_from_previous_run`, record-level); do not treat its
shape as the current producer contract.

## Authority - what this is not

A record is **inspectable evidence, not tamper-proof attestation**. It is a
writable local file: anyone who can write to the git directory can edit it, and
the reader cannot detect a consistent forgery. It is a CPP **usage** record,
distinct from skillc's independently assembled evaluation verdict
([skillc #249](https://github.com/cooneycw/skillc/issues/249)). skillc observes
it as one input under its own authority, and ordinary CI re-runs the checks it
relies on. Do not treat `supported` as a reason to skip CI.

The `supported` verdict is consumed in another repository, so the reader has a
committed negative control (ADR 0008 row 115):
`controls/execution-evidence-verify`. Its bad cases are a same-file re-edit
after the run, a replayed file name, and a `completed` summary over a gate that
never ran. Its constructed anchor trusts the record's own summary and misses all
three.

## Compatibility

- The opt-in is an environment variable, so an older runner ignores it, runs the
  plan, and writes no record. An older `flow-finish-gate.sh` rejects
  `--evidence` with a usage error (exit 2); `/flow:check` then re-runs without it
  and reports that no record was written.
- The runner's stdout JSON is unchanged. The record path is printed on stderr
  only (`CPP_EXECUTION_EVIDENCE: <outcome> <path>`).
- The reader refuses an unknown `schema` as `unknown` rather than guessing. A
  later `v2` gets a reader that names it.
- `--plan check` is exempt from the counter-model enrolment check that
  `flow-finish-gate.sh` enforces for `finish`. `/flow:check` produces no PR,
  which is the same reason `--check-summary` was already exempt.
