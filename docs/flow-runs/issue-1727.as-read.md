<!-- flow-run n=1 id=efb1ed5b744a4ec48a2745c264bcce10 -->
## Run 1 - issue #1727 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1727
- Read at:      2026-11-12T06:52:29Z
- updatedAt:    2026-11-12T06:51:53Z   (context only - moves on comments and labels)
- Body digest:  b75ed5d97e4b50da42385af96c9e58118419a06ed17e71cbd799b149e44f78ac   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3157 of 3157 (cap 16384)

### Body as read
Source: Nit Store #864 seq 651 (comment 6567427128, 2026-11-02), joined onto #1692 at the rollover and raised to its own issue by the wave orchestrator's ruling on 2026-11-11 (medium: a gate that can let work through). Filed by the session working #1692.

## Problem

`DeterministicRunner.run()` decides whether to honour a previous failed run by comparing the tree's signature now with the one stored when the state was written (#804): a mismatch discards the stale state and starts fresh, and a carry is marked verified only when both signatures were available and equal.

`DeterministicRunner.resume(run_id)`, the explicit entry point behind `python -m lib.cicd resume <run_id>`, makes no such comparison. Read at `545267b9`: between `def resume` and `def status` in `lib/cicd/runner.py` there is no call to `compute_tree_signature`; it loads the state, calls `_warn_carried_over` and goes straight to `_execute`.

So an explicit resume after the tree changed (the ordinary case: a step failed, the fix was made, the run is resumed) keeps every earlier step's result, including the steps the fix may have broken, and can end in a success that describes a tree that no longer exists.

**Severity: medium.** A gate letting work through, on a path that needs a deliberate command to reach.

## Who calls the explicit resume (surveyed 2026-11-11)

| Repository | Callers of `lib.cicd resume` / `resume_run` |
|---|---|
| CPP | `lib/cicd/cli.py` (`cmd_resume`) and one test (`tests/test_runner.py`, the corrupt-state case). No script, no command document, no Makefile target, no CI step. `scripts/flow-finish-gate.sh` never calls it; it calls `run`, whose auto-resume is the checked path. |
| kyle | none found |
| skillc | none found |
| kyle-candidate | not searched: no checkout on this host |

Method: grep for `lib.cicd resume`, `cicd resume`, `resume_run(` and `cmd_resume` across `.py`, `.sh`, `.md`, `.yml`, `Makefile`, excluding virtualenvs, generated Codex mirrors, control anchors and skillc's frozen CPP fixture profiles. A caller that builds the command line dynamically would not be found this way.

## Two ways to close it

1. Make `resume()` apply the same signature rule as `run()`: refuse (or start fresh) on a mismatch, mark the carry unverified when a signature is missing. This is a defect fix.
2. Remove the explicit `resume` subcommand, since nothing found calls it and `run` already resumes safely. That deletes a path, which is what #1673 wants, but it removes a CLI surface, so it falls under the owner's 2026-11-11 ruling on output and interfaces kyle and skillc may use (coordination issues first).

## Acceptance

- An explicit resume of a failed run whose tree has changed since does not report success on carried results. Committed red case: a state file with a stored signature, a tree that differs, `resume` invoked; the pre-fix code carries and the fixed code does not.
- The must-not-flip case: an explicit resume on an unchanged tree still resumes.
- If option 2 is chosen instead: the caller survey is repeated including kyle-candidate, and the removal is named in the three coordination issues.

Refs #1692, #804, #1673.

<!-- end of body -->
