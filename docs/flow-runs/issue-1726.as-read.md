<!-- flow-run n=1 id=9a339207415a4b488d0161bffa83ef10 -->
## Run 1 - issue #1726 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1726
- Read at:      2026-11-12T03:18:00Z
- updatedAt:    2026-11-12T00:54:40Z   (context only - moves on comments and labels)
- Body digest:  9a5224dd007ffcae8e27fb6da448ad86250fd2776cffce9a00fccd08678f98d7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3385 of 3385 (cap 16384)

### Body as read
Tier: 2

Source: the #1693 survey of the merge and cleanup tail, read at origin/main `4c8aa79a` on 2026-11-11. Filed on the wave orchestrator's ruling (wave cpp-improvement): a refusal in a deleting or merging script that nothing can show firing is medium severity, and ADR 0008 requires a committed red case for a gate that lets work through. Not fixed by #1693, which is a behaviour-preserving trim.

## Outcome
These five helpers decide whether a pull request merges and whether a checkout is deleted. Each refusal in them exists because something was once lost. For the refusals below, no test and no registered control makes the refusal fire, so a change that broke one would stay green. Each one gets a case that fires it, or a recorded reason why it cannot be reached.

## Findings
How these were found: a grep of `tests/` and `controls/` for each exit code's message and marker. A test that reaches a line without naming its message would be missed, so confirm each before writing its case.

**`scripts/gh-pr-merge.sh`**
- Exit 8, line 1756: the incidental-close classifier failed its own self-check (#794). Nothing triggers it; the only mention in tests or controls is a historical anchor. This is a check on a check, and it cannot currently be shown to fail.

**`scripts/worktree-remove.sh`**
- Exit 7 at line 754: commits on no remote, the empty `MATCHED_HEAD` branch (#899). The other exit-7 sites are tested.
- Exit 9 at lines 808 and 1365: the `PRESCAN: unknown` branches, where the permission scan itself fails. The found-an-undeletable-path sites are tested.
- Exit 12 at lines 623 and 630: `readlink` failure and empty resolved path (#1524).
- Exit 13 at line 676: `mktemp` failure (#1524).
- Exit 1 at lines 207, 294, 304, 876, 885: usage and resolution errors.

**`scripts/flow-worktree-claim.sh`**
- No negative-control directory exists for this script at all; everything is exercised by tests only.
- Exit 1 from `check --exit-code` on a held claim, line 451: no test and no caller.
- Exit 2 usage variants (unknown verb, unknown option, missing value): only the issueless-claim path is tested.

**`scripts/flow-worktree-sweep.sh`**
- `controls/flow-worktree-sweep` runs only the dry run (good exit 0). `--apply`, and the `partial` exit 3, are not in the control.
- Exit 1 at lines 143, 157, 165 (`--repo` with no value, unknown argument, not a git repository): nothing.

**`scripts/flow-worktree-guard.sh`**
- `controls/flow-worktree-guard` covers exits 4, 5 and 0. Exit 3, the leak verdict that is the script's whole purpose, is not in the control (tests cover it).
- Eight `unknown` (exit 4) emitters have no test or control: lines 164, 195, 200, 210, 213, 248, 250, 308.

## Acceptance
- Each refusal above has a test or a registered control case that makes it fire, shown red when the refusal is removed, or a one-line recorded reason why it is unreachable.
- `flow-worktree-claim.sh` has a registered negative control, or a recorded reason why its verdict is not consumed by a decision that does not re-derive it.
- The guard's control includes an exit-3 case and the sweep's control includes an `--apply` case.

## Constraint
Freeze (#1673): this adds tests and control cases, no feature. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is.

Parent: #1693 (child of #1673)

<!-- end of body -->
