# Issue #972 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #972
- Read at:      2026-09-24T10:56:17Z
- updatedAt:    2026-09-20T14:34:31Z   (context only - moves on comments and labels)
- Body digest:  c7f80d73ede97a3b1057c833311313ecd729d73688de7ec0c5af4a56a014e327   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2287 of 2287 (cap 16384)

## Body as read
## What this is

#960 adopted `shellcheck` and gated CI at `--severity=error`, which the tree now passes with **zero suppressions** and no `.shellcheckrc`. This issue is the counted residual that decision left behind, filed rather than disabled, because a disabled check is invisible and an issue is not.

## The numbers

Measured on adoption (shellcheck v0.10.0, 96 files derived by `scripts/shellcheck-gate.sh`):

| severity | findings |
|---|---|
| error | 0 (gated) |
| warning | 31 |
| note | 144 |
| **below the gate** | **175 across 35 files** |

Top codes:

| code | count | what it is |
|---|---|---|
| SC2317 | 65 | command appears unreachable |
| SC2016 | 25 | single quotes do not expand |
| SC2015 | 20 | `A && B \|\| C` is not if-then-else |
| SC2034 | 19 | variable appears unused |
| SC2178 | 12 | variable used as array then as string |
| SC2002 | 7 | useless `cat` |

Reproduce with `sh scripts/shellcheck-gate.sh --severity style`.

## Why it was not fixed in #960

The adoption ticket's own scope section is explicit: *"Adopt the tool and wire it. Fixing the findings it produces is separate work and should not be bundled - the size of the backlog is unknown until the tool runs, and a single PR that both introduces a gate and fixes everything it finds cannot be reviewed."* #960 fixed exactly the 2 distinct SC1087 errors that blocked the gate from being green at all, and nothing else.

## What needs deciding, not just doing

This is not simply a fix-them-all ticket. **SC2317 is 37% of the backlog on its own**, and unreachable-command findings in this repo are likely dominated by functions defined and invoked indirectly - a pattern shellcheck routinely cannot follow. Triaging that class is the first question, and the honest outcome may be that some of it is a per-file `# shellcheck disable` with a reason rather than a code change.

Whatever is decided, per ADR 0008's adoption convention (added by #960): a suppression carries its reason in the same commit, and raising the gate's severity is what closes this issue - not annotating around it.

## Related

- Adopted by #960; convention recorded in ADR 0008.
- Sibling adoption tickets #961 (`pip-audit`) and #962 (`bandit`) inherit the same convention and will produce their own residual of this shape.
