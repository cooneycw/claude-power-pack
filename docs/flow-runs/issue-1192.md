# Flow run record - issue #1192

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1192
- Base SHA:          d74ca89
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          wave `claude-improvements` orchestrator, session
                     `claude-improvements-new`, mailbox rev 7, acked after the content
                     was held.
- Recorded at:       2026-09-23T14:20:00Z

## Section B evidence

- Commits touching the lane since the issue was filed (2026-09-21T20:57:56Z): #1203 (isolate the
  six flow-finish-gate controls), #1195 (migrate flow-finish-gate onto gate-lib, Closes #1061),
  #1194 (eval verified-result artifact). None addresses the grammar bound or the silent refusal.
  #1195 restructured the shell, so the shell was re-read at d74ca89 rather than taken from the
  issue's description of it.
- The issue's citation still holds at d74ca89: `lib/cicd/steps.py:876` is
  `if makefile.is_file() and makefile_grammar_refusal(project_root) is None:`, gating the query.
- #1152, #1147 and #1165 are CLOSED. Nothing supersedes this; #1192 bounds #1152's delivered
  behaviour rather than competing with it.
- Searched "gate dedup subsumption grammar" across all states: only #1192 and the Nit Store.
- Provenance: nit-store record #864 comment 5764488055, found in wave `kyle-improvements` while
  building a fixture to defend the OPPOSITE design, reproduced there with a positive control,
  filed at the owner's direction.

MEASURED HERE, with a negative control so the refusal is a verdict rather than the output of a
function that always refuses. Entirely inside CPP; no other repository was read:

    plain rules only                  -> None            <- the negative control
    -include $(VAR)                   -> 'line 1: an include'
    -include .env  (a plain path)     -> 'line 1: an include'
    include config.mk                 -> 'line 1: an include'
    ifneq conditional                 -> 'line 1: a conditional'
    assignment containing $(MAKE)     -> 'line 1: an assignment whose value contains $(MAKE)'

CPP's own Makefile returns None. This repository is inside the grammar, benefits from the dedup,
and therefore CANNOT OBSERVE THIS BUG IN ITS OWN TREE - which is why a different repository had
to surface it, and why the silent refusal is the harm rather than the refusal itself.

NOT VERIFIED, and recorded as a real gap rather than a formality: the claim that the bound never
reaches kyle rests on kyle's Makefile line 9. kyle is outside this wave's lane; the orchestrator
ruled that it must not be read, and it was not. The fix does not depend on it, and the issue
itself records that kyle has shipped a workaround and is no longer exposed.

## Section C - the approved plan

1. `lib/cicd/runner.py` - `RunResult` carries `subsumed_gates` but no refusals field, so the
   runner logs `NOT SUBSUMED: <reason>` and never serialises it. Add `subsumption_refusals`,
   populate it where the refusals are already computed, and emit it from `to_dict`.
2. `scripts/flow-finish-gate.sh` - read that field and print `SUBSUMPTION REFUSED: <reason>`.
   Today the shell prints on success and is silent on refusal, so "outside the grammar, paying
   double" and "nothing to deduplicate" are indistinguishable to the only reader who pays.
3. `lib/cicd/steps.py` - state the WIDTH of the bound where the bound is implemented: every
   include form is refused, including an `-include` of a plain path, which is wider than the two
   hazards the docstring names. Record beside it that CPP's own makefile is inside the grammar
   and cannot observe this, and the OSCILLATION TRIGGER: the refusal stays wide, and what would
   move it is someone making an included file's contents statically VERIFIABLE - never a
   consumer asking. If that lands the admission widens because the verification widened, never
   the reverse.
4. `tests/test_runner.py` - the refusal reaches `to_dict`, with a conforming fixture as the
   negative control so a field that is always populated cannot pass.
5. `tests/test_flow_finish_gate.py` - the shell PRINTS the refusal, and stays SILENT when there
   is nothing to refuse. The silence is as load-bearing as the printed line.
6. `docs/flow-runs/issue-1192.md` - this record.
7. `docs/flow-runs/issue-1192.as-read.md` - the as-read snapshot.

Scope: 7 files, approximately 150 lines net.

Risks: R1 the grammar is NOT widened, by orchestrator ruling - admitting an include of a variable
reopens the hazard the grammar exists to close, and the safe narrowing excludes the variable path
that motivated the issue, so the admission is either unsafe or useless to the named consumer.
R2 the record annotation the issue asks for lives in `docs/scripts.md`, which is declared by
worker-B (live) and still declared by worker-A (released, session ended) - no grant; the bound
goes in steps.py, which is the better home rather than the fallback. R3 #1195 restructured the
shell since filing, so the new output line has to be placed against the gate-lib shape rather
than the shape the issue describes.
