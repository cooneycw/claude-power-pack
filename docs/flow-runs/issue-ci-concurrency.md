# Flow run record - ci-concurrency

HISTORICAL RECORD of what was agreed BEFORE the code was written. It is not a
description of the shipped system and it does not graduate.

- Issue:             ci-concurrency (no GitHub number; owner-directed wave work)
- Base SHA:          d3f474b
- Necessity verdict: Still needed
- Approval:          granted (orchestrator, durable lane rev 5)
- Approver:          CPP-improvements-orch, under authority-model=orchestrator-only
- Recorded at:       2026-09-23

## Section B evidence

- Reproduced the CI failure byte-for-byte with a `grep` shim that fails to exec
  on its Nth call: call 1 -> "missing section(s): delivered" (CI's exact text),
  call 2 -> "in-scope", call 3 -> "residual". Control with the real grep: ok.
- `ci/woodpecker/pr/woodpecker` is the ONLY entry in main's branch-protection
  required_status_checks. The failing pipeline is the governing one.
- Pipelines 2504 (push, success) and 2505 (pull_request, failure) built the SAME
  commit 21218a2; both `validate` steps started at epoch 1790159509.
- Agent runs WOODPECKER_MAX_WORKFLOWS=2; the suite runs pytest -n 4.

## TWO EXPLANATIONS THAT WERE WRONG, recorded because both were plausible

1. SHARED LEDGER PATH. Mine. `WAVE_ROOT` (:203) resolves to a per-agent,
   per-uid directory, so two concurrent runs share it - true, and irrelevant:
   its only other reference is :917, inside the `record` verb. The failing test
   calls `validate`, which never reaches it.
2. TRUNCATION. Losing the tail of the body reports ALL THREE sections missing.
   CI reported ONE. That asymmetry is what identified the real mechanism, and it
   was nearly lost: an earlier summary of mine said "truncated after line 9" and
   was believed until the raw CI log was re-read.

## Section C - the approved plan

1. `scripts/flow-wave-lexicon.sh` parse_ledger - replace the per-section
   `printf | grep -Eq ... ||` with bash `=~` over lines split by parameter
   expansion. Removes the exec so the could-not-run state stops existing.
2. `scripts/flow-wave-lexicon.sh` parse_merge - the same conflation pointing the
   other way: a `grep` that cannot run makes the OR false and a vague predicate
   is ACCEPTED. Fixed in the same change per condition (i).
3. `tests/test_flow_wave_lexicon.py` - the shim-based negative control, plus the
   accepted/rejected spellings pinned from the grep implementation BEFORE the
   change (condition (ii)).
4. This record.

Scope: Small. Risks: bash `=~` is ERE like `grep -E` and the pattern is
byte-identical, so the risk is engine behaviour rather than translation; pinned
both directions. NOT PROPOSED: any change to .woodpecker.yml, MAX_WORKFLOWS or
agent count (condition (iv)).

## What this fix does NOT claim

parse_ledger is not fork-free. `$(block_lines ...)` and `$(trim ...)` remain,
and a command substitution forks a subshell even for a pure-builtin function.
Their failure yields an empty block and therefore the ALL-THREE shape, which is
distinguishable from the one-section shape fixed here. Removing them means
changing `block_lines` to return through a variable, which its other callers
share - a separate change, deliberately not smuggled in.
