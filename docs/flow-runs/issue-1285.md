# Flow run record - issue #1285

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1285
- Base SHA:          4deccd2
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), approving cooneycw/kyle#1396 option (a), whose plan names this CPP half
- Recorded at:       2026-09-27T00:00:00Z

## Section B evidence
Filed this run from kyle#1396; no prior CPP issue or PR (searched bwrap / bubblewrap /
workspace-write container: none open or merged on this). Measurements in the issue body.

## Section C - the approved plan
1. `.claude/commands/codex/auto.md` - Step 4 invocation reads ${CODEX_AUTO_SANDBOX:-workspace-write}, refuses any other value; capability table and Notes state the fence cost
2. `templates/delegated-driver-values/codex.md` - FIX_REEXEC slot: same guard and variable for the fix loop
3. `tests/test_codex_auto_sandbox.py` - executes the guard extracted from the rendered document: unset, danger-full-access, and a refused bogus value; no literal workspace-write left on a codex exec invocation
4. `docs/flow-runs/issue-1285.md` - this record

Scope: small. Generated mirrors (codex/skills) re-synced by the existing helper.
Risks: a caller setting danger-full-access drops #735's mechanical network fence for
that run (owner accepted for Kyle containers); the textual fence and overrun
verification remain.
