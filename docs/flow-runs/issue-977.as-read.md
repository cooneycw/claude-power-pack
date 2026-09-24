# Issue #977 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #977
- Read at:      2026-09-24T10:56:57Z
- updatedAt:    2026-09-20T14:34:32Z   (context only - moves on comments and labels)
- Body digest:  ea1faae409f39a1048691291d4f89ead5baf8ac06e04436de46deec607128cad   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1986 of 1986 (cap 16384)

## Body as read
## What

#939 added an UNKNOWN-not-clean warning: a test step that exits 0 and produces output no parser recognizes is reported as UNKNOWN rather than a bare SUCCESS, because silence and a clean result were previously indistinguishable to `flow-finish-gate.sh`.

`lib/cicd/outcomes.py` recognizes pytest, jest and unittest. A project whose test step uses any other runner - Go's `go test`, Rust's `cargo test`, a shell harness, TAP output - produces output, so it hits the warning **on every run, forever**.

## Why this is a decision and not a bug

The warning is honest: CPP genuinely cannot tell what that suite did, and #952's rule is that a parse which examined nothing reads UNKNOWN rather than clean. But a warning that fires on every run of a legitimate configuration is one people learn to ignore, which is how a warning stops being worth having - the same reasoning #890 used when it worried aloud about making the skipped-security-scan warn "permanent noise".

So there is a real tension and it is wider than #939:

- **Accept it.** Unparseable means unknown, and a project wanting a clean gate should use a runner CPP parses or teach it one.
- **Scope the warning** to steps whose output looks like a test runner CPP *should* have parsed, leaving genuinely foreign runners silent. Narrower, but "looks like" is a guess and guessing is what #939 removed.
- **Make it configurable** per project, which moves the judgement to the person who knows which runner they use.

## Scope note

#939 deliberately did **not** settle this. Its warning is scoped to steps that actually produced output, so a silent step (`command: true`) stays a bare success and #628/#890's contract is intact - that bound is pinned by `test_a_test_step_that_printed_nothing_is_still_a_bare_success`. What is left open is only the foreign-runner case.

Found while implementing #939 (PR #976); raised rather than decided because it changes gate behaviour for every CPP consumer, not just this repository.
