Deliberately contains NO shell file, which is the whole of the input.

`scripts/shellcheck-gate.sh --root <this directory>` must refuse: it reports
`UNKNOWN - 0 shell files matched ... 0 examined is not 0 findings` and exits 2,
because a gate that examined nothing prints the same confident zero as a gate
that examined everything and found nothing (#952).

Registered `expect: "UNKNOWN"` (issue #1129). Before that expectation existed
this directory could not be a case at all: the refusal does not match the
control's `detect_signal`, so it scored UNSIGNALLED and took the whole control
down instead of exercising the branch.

DO NOT ADD A SHELL FILE HERE. Doing so makes the gate examine something, the
refusal never fires, the case observes GOOD or BAD, and the control reports
BLIND - which would read as an alarm about `shellcheck-gate.sh` rather than
about this directory.

The gate skips `controls/*/cases/*` when scanning the repository itself, so this
file is never part of the main population; it is only ever reached through this
control, with `--root` pointing here.
