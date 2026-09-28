<!-- flow-run n=1 id=2b9e211fddcf4745ada957c5fa2cbcd2 -->
## Run 1 - issue #1333 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1333
- Read at:      2026-09-28T18:11:33Z
- updatedAt:    2026-09-28T17:20:51Z   (context only - moves on comments and labels)
- Body digest:  f77401cf2ed380ec4d2b5d1340ccea255bca21a56f00c5fe82d7fb7fbc786992   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1505 of 1505 (cap 16384)

### Body as read
## What is wrong

`tests/test_detector_contracts.py` (the count-word map at ~:296-304) turns the English count word in `docs/agents/detector-contracts.md`'s index headings into an integer through a literal dict. Today the dict runs to `"thirty-five"`. `test_the_index_heading_matches_its_population` and its sibling `test_the_properties_heading_matches_its_population` both depend on it.

Every time the index grows past the last word in the dict, a CORRECT change fails with `unrecognised count word: <n>`, even though the count and the population agree. The map has already been extended by hand at least once (#1109 added `twenty-six`, and it now reaches `thirty-five`). So the Nit Store item is only partially delivered: the symptom was patched, and the pattern that produces it remains.

## Why it is pattern-level, not a one-line fix

A correct change that looks like a broken one trains readers to edit the test to get past it. The dict is ALSO what lets the test fail at all, so careless edits are how the real check gets lost. Extending the dict again just moves the cliff. The remedy is a decision between:
- parsing number words generally, or
- writing the count as a digit in the document.

## Acceptance

- Growing the index by one row never fails the test while count and population agree.
- A genuine mismatch still fails, with its red case shown.

Found while working #1273 (Nit Store sweep, item 21; nit https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5748930509).

