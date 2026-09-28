# Flow run record - issue #1277

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1277
- Base SHA:          e1dc763
- Necessity verdict: Needed
- Approval:          granted
- Approver:          run45:orch (fleet orchestrator), mailbox message 2165 in reply to ELI5 message 2164
- Recorded at:       2026-09-28T17:05:00Z

## Section B evidence
- Reproduced on e1dc763: `sweep.py --self-test` reports 5/5 caught; `mutation-probe.py --manifest docs/research/class-enumeration-2026-09-15/mutations.json` reports cmdpos/quote/comment CAUGHT, interp/ast UNCAUGHT.
- Both gaps are battery gaps: `_probe` never calls `closure()`, so the ast mutation (closure's `.py` dispatch) is unreachable; the only interp case is also rejected by the quote check, so no case depends on token-start alone.
- Nothing automated consumes `--self-test` (not in Makefile, .woodpecker.yml, tests/, verify-coverage.json); the readers are dated prose.

## Section C - the approved plan (option 1: retire --self-test)
1. `docs/research/class-enumeration-2026-09-15/sweep.py` - remove `self_test()`, the `mutate` plumbing and its call in `main()`; route `.py` cases through `closure()`; add a real-line interp control case where token-start alone decides
2. `docs/research/class-enumeration-2026-09-15.md` - fix the command line (:215) and add one dated note pointing at the probe and #1277; the dated findings text is untouched

Scope: 2 files, ~60 lines. Acceptance: mutation-probe 3/5 before, 5/5 after; each new or rerouted case fails under its own mutation.
Out of scope: the red bucket control (#1268, separate PR).
