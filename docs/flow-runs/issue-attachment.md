# Flow run record - the flow-finish-gate attachment coupling

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system and it does not graduate.

- Issue:             none. The wave orchestrator's brief is the contract; the
                     owner's no-growth rule means no ticket was filed, and the
                     orchestrator will rule at finish on whether one is owed.
- Base SHA:          cbd7dcf
- Necessity verdict: Still needed
- Approval:          granted - GO-WITH-CONDITIONS
- Approver:          CPP-improvements-orch (wave claude-improvements, policy
                     rev 4, authority-model orchestrator-only)
- Recorded at:       2026-09-22T12:45:00Z

## Section B evidence

Measured in this worktree at cbd7dcf, not inherited from the brief:

- ATTACHMENT is the variable. One sha, three head states, same case:
  attached to a feature branch -> `fail (counter-model line missing)`;
  DETACHED at the same sha -> `ok`; attached to `main` at the same sha -> `fail`.
- ALL FOUR failures flip on attachment alone. Six controls, attached vs detached
  at cbd7dcf: flow-finish-gate, -declared-gates, -plan-reconciliation and
  -subsumption go UNSIGNALLED -> PASS; -derivation and -resume PASS both ways.
- THE ANCHOR CAUSES NONE OF THEM. Only 2 of 6 patterns are the anchored
  `^FLOW_FINISH_GATE: fail$`; three are reason-specific and correct for their
  subjects; one is already unanchored. `-derivation` is anchored AND passes both
  ways, which on its own refutes the anchor as the cause. flow-finish-gate's own
  BAD cases emit a BARE `FLOW_FINISH_GATE: fail`, which the anchor matches today,
  so the anchor is a LATENT fragility and not a live defect.
- MECHANISM, read at scripts/flow-finish-gate.sh:499-503: the branch is a
  deliberate NARROWING - a receipt matches only if its recorded branch equals the
  current branch AND its head is reachable. Detached drops the narrowing.
  Correction to the brief and to my own earlier statement: "main never writes a
  receipt" is false - 2 of 67 receipts record branch=main - but BOTH carry an
  empty head, so the accurate sentence is that no receipt both records
  branch=main and carries a resolvable head.
- ONLY GOOD CASES ARE CONTAMINATED. Exactly one GOOD case per failing control;
  every BAD case still reds correctly in place, because a failing gate step
  short-circuits before the counter-model check.
- THE ISOLATION MECHANISM ALREADY EXISTS IN-TREE. `-derivation` and `-resume`
  copy their case to a `mktemp -d` and run there, outside any git repository;
  they are the two that pass both ways. Running the failing `good-all-green`
  through that same pattern yields `ok` plus an explicit
  `not-enrolled: this repository carries no counter-model receipts directory`.
- BLAST RADIUS: battery `--strict` attached exit 1, detached exit 0.
  tests/test_negative_controls.py:1584 asserts a green `--strict` battery as a
  PRECONDITION, so `make test` is red on main permanently.

## Section C - the approved plan

1. `controls/flow-finish-gate/run-case.sh` (new) - ONE shared case runner for all
   six controls. It isolates by copying the case to a temp directory outside any
   repository, which is the mechanism two of the six already prove works. It
   reports `FLOW_FINISH_GATE_CONTROL: unavailable - ...` and never a clean
   result when it cannot build the isolated context.
2. `controls/flow-finish-gate/control.json` - invocation -> the shared runner;
   add `unavailable_signal`. DETECT_SIGNAL UNCHANGED.
3. `controls/flow-finish-gate-declared-gates/control.json` - same.
4. `controls/flow-finish-gate-derivation/control.json` - same.
5. `controls/flow-finish-gate-plan-reconciliation/control.json` - same.
6. `controls/flow-finish-gate-resume/control.json` - same.
7. `controls/flow-finish-gate-subsumption/control.json` - same.
8. THE DISCRIMINATING PAIR, committed as cases with every pattern unchanged, so
   the pair decides rather than a judgement call: (i) a gate that genuinely
   CRASHES - non-zero, no signal - must NOT score as detected; (ii) a gate that
   REFUSES ARTICULATELY - signal plus a reason - must score as detected.
9. A case that deliberately runs on the REAL-repo path, named so a later reader
   knows it is load-bearing rather than left over, selected by a marker file in
   the case directory rather than by a second invocation.
10. `tests/test_negative_controls.py` - the :1584 precondition. Preference is to
    remove the ambient dependency; failing that within scope, a NAMED skip
    through the #926 hook, and the close report says which was taken and why.
11. `tests/test_flow_finish_gate.py` - regression coverage for the runner.

Scope: 1 new runner, 6 control.json, 2 test files, ~300-600 lines.

### Named risks

1. An isolated fixture can DRIFT from how the gate really runs, trading a false
   red for a false GREEN, which is strictly worse. Binding condition: at least
   one case stays on the real-repo path deliberately and says so in its name.
2. A runner that cannot isolate must report UNAVAILABLE, never clean - a battery
   that silently runs fewer cases is the unscanned-reads-as-clean failure.
3. Changing a detect_signal for a LATENT problem is how tolerance creeps in, and
   a looser pattern would score a genuine crash as a detection. No pattern
   changes in this work; the committed pair decides whether one is owed.
