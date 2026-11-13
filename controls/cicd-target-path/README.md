# Target PATH control

Run discrimination with:

```sh
python3 scripts/check-negative-controls.py --strict --control controls/cicd-target-path
```

This intentionally prints `NEGATIVE_CONTROL_PROVENANCE: unverified`; strict
mode alone does not request a historical byte comparison. To verify provenance:

```sh
python3 scripts/check-negative-controls.py --strict --verify-provenance --control controls/cicd-target-path
```

Verification requires Git, a full/non-shallow history, the actual anchor blob
`35c51d81424999849f496f325a51ecc7b7ea9367:lib/cicd/__main__.py`, and that commit
retained by named `refs/remotes/origin/main` (preferred), or local
`refs/heads/main` as fallback. Detached HEAD itself is not a main reference.
A main-history clone is sufficient; no feature branch is needed. Deepen a
shallow checkout and explicitly fetch main if necessary. With those prerequisites,
this control prints provenance `ok`, historical `compared=1 uncompared=0`,
and retention `on_main=1 off_main=0 unknown=0`. Missing
history/ref is UNCOMPARED; known side-only retention is OFF_MAIN. Neither is a
verified pass under strict verification.

The nine BAD cases cover actual owned interpreter lookup and eight independent
refusal populations. Two GOOD cases are unmarked and no-op caller policy. The
historical anchor ignores PATH records. Native tests cover all refusal mutants,
the missing-restoration assignment, exact marker consumption, actual uv startup
and separation between target and CPP interpreters. No PATH values are printed.
