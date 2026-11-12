<!-- flow-run n=1 id=a71218fb4c8a43dbac263079e3b347b5 -->
## Run 1 - issue #1732 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1732
- Read at:      2026-11-12T03:17:00Z
- updatedAt:    2026-11-12T01:11:55Z   (context only - moves on comments and labels)
- Body digest:  e29edea81d576b5d20454f3670ece2463f6a7770d336f4470ad010ec123442b4   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3074 of 3074 (cap 16384)

### Body as read
Tier: 2

Source: found working #1719 (row 687 of the Nit Store #864 rollover), measured at origin/main `48d4c479` on 2026-11-11, reproduced by the wave orchestrator. Filed on the orchestrator's ruling as its own issue, medium.

## Outcome
`scripts/check-negative-controls.py --verify-provenance` exists to show that each control's anchor really is the artifact its registration claims. Over the real tree it has not been able to finish: it ends in a Python traceback on the first control whose constructed anchor has no `sha` key, and thirteen registered controls are in that shape. Nothing noticed, because nothing runs the flag on the real tree: it is in no Makefile target and no CI step, and the tests that pass it run fixture trees. So the provenance check's green has never been produced by the tree it exists to verify.

## Measured
- `python3 scripts/check-negative-controls.py --control controls/flow-preflight --verify-provenance` ends `KeyError: 'sha'` at `_provenance`, line 2663, exit 1.
- Cause: the guard is `anchor.get("sha") in ("0000000", "n/a", "")`, which is false for a missing key, and the next statement indexes `anchor['sha']`. `_anchor_kind_problem` requires a sha for `kind=historical` only, so a constructed anchor with no sha is a well-formed registration.
- The thirteen: `cicd-environment-handoff`, `cicd-makefile-write`, `cicd-target-python`, `cpp-host-atomic`, `cpp-host-ci`, `cpp-host-install-receipt`, `doctor-ci`, `flow-cpp-runtime`, `flow-finish-missing-tools`, `flow-preflight`, `flow-start-preflight`, `flow-wave-completion`, `project-next-preflight`.
- 47 other constructed anchors write the field as `n/a`, `-` or `no-check` and read `unverified`, which is the documented verdict for an anchor with no historical commit to compare with.
- `git grep verify-provenance -- Makefile .woodpecker.yml` finds nothing.

## What #1719 does, and does not
#1719 fixes the crash only: a non-historical anchor with no sha key, or no origin, reads `unverified` like its siblings, with a test over every such registered control. It does not make anything run the flag, and it does not decide the schema question.

## Acceptance
- `--verify-provenance` runs over every registered control in `make verify` or in CI, and reaches a verdict for each.
- A committed case shows it red on a tampered anchor: an anchor whose bytes differ from its recorded digest, and a historical anchor whose bytes differ from the commit it names.
- A decision, recorded here, on whether a constructed anchor must carry an explicit `sha` value (`n/a`) so that an omitted key is a registration error, with the thirteen registrations brought into line if so.
- The run's cost is stated (it reads git objects for every historical anchor), so whoever wires it knows what it adds to the gate.

## Constraint
Freeze (#1673): this wires an existing check and adds a case; it is not a new feature under the frozen flow and cicd paths. Owner ruling 2026-11-11 (#1673): verdict lines, markers and exit codes that kyle or skillc read stay as they are.

Parent: #1719 (child of #1673)

<!-- end of body -->
