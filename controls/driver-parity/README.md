# Driver parity control

These are owned text fixtures, not live delegated runs. `base-tree` copies the
four command documents from main `65921ba3`, appending fixture-only approval,
compliance, reconcile, read-issue and begin-run calls to each driver to make a
covered baseline. The table retains the owner-approved equivalents and gaps.
The main-gap case removes those appended calls again, exposing fifteen missing
pairs. The other cases change one coverage or policy condition at a time.

The fixture mirror is a source-text stand-in. It tests inventory comparison;
it does not attest generation or helper bundling. `tests/test_driver_parity.py`
separately builds and reads the real flow-auto Codex mirror. The stub generator
and driver declaration files state only the packaging population for fixtures.

Eleven BAD and three GOOD cases run through the real checker. The constructed
anchor checks a fixed helper list, omits all plan-record verbs and trusts waiver
metadata. It misses all BAD cases and agrees on the GOOD cases. Its provenance
is constructed, never historical. UNKNOWN/crash output is not a detection.

Issue #1811 tracks the still-owed work. Approval and compliance are never waived;
the real repository assertion stays red until #1809 supplies its required calls.
The eventual landing closes #1810 while #1811 remains open.
