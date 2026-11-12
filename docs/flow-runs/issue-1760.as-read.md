<!-- flow-run n=1 id=a73d0353c7234c17a9e20508f97a6d2a -->
## Run 1 - issue #1760 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1760
- Read at:      2026-11-12T09:30:47Z
- updatedAt:    2026-11-12T05:56:52Z   (context only - moves on comments and labels)
- Body digest:  2b0974e272595f10447755f791b236ca81cef61c0dabe0505c91f02d41bf00fd   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2761 of 2761 (cap 16384)

### Body as read
Tier: 2

Origin: not traced - I did not look for the change that wrote the fallback gate line.

Severity: medium (a security gate that is skipped by instruction on some hosts). Found 2026-11-12 while working #1759; measured, see below. Filed by the wave orchestrator's condition: file it, do not fix it inside #1759.

## Outcome
`/flow:deploy`'s fallback path runs the deploy security gate wherever the runner path would have found CPP.

## What happens now
`.claude/commands/flow/deploy.md`, Step 4b, has two ways to reach the security gate:

- The runner block searches three locations for a CPP checkout (`~/Projects/claude-power-pack`, `/opt/claude-power-pack`, `~/.claude-power-pack`) and runs the deploy plan, which includes the gate.
- The fallback path, used when the runner does not run, has one line with the location hard-coded:
  `PYTHONPATH="${HOME}/Projects/claude-power-pack" uv run --project "${HOME}/Projects/claude-power-pack" python -m lib.security gate flow_deploy`
  followed by the instruction: 'If `lib/security` is not available, skip this step.'

**Measured** (the line run with HOME pointing at a directory that has no `Projects/claude-power-pack`): `error: Project directory `Projects/claude-power-pack` does not exist`, exit 2. The command itself is loud. The document then tells the agent that an unavailable `lib/security` means skip, so the deploy proceeds with no security gate.

## Who meets it
- Before #1759: only a host with no CPP checkout in any of the three locations, where skipping is arguably correct.
- **After #1759:** also any host whose CPP checkout is at `/opt/claude-power-pack` or `~/.claude-power-pack`, whenever `/flow:deploy` is given a target other than `deploy`. #1759 routes non-default targets to the fallback path (the runner's plan can only run `make deploy`), so on those hosts a non-default target is deployed with the gate skipped, where before it ran the runner's gate (and then the wrong target).
- A host with CPP at `~/Projects/claude-power-pack` is unaffected: the fallback gate line finds it. `tests/test_flow_deploy_target.py` (from #1759) shows the gate is called on that path.

## Acceptance
- The fallback gate uses the checkout the runner block already located (`$CPP_DIR`), and only falls back to 'not available' when none of the three locations has one.
- 'Could not run the gate' and 'the gate is not installed' are told apart in the document: the first stops, the second skips and says so.
- A committed case: CPP at `/opt`-style location (a temporary directory standing in), a non-default target; the gate is called before `make`.

## Constraint
`flow/deploy.md` is at its word budget (1,561 of 1,561); `.claude/commands/flow/` is under the #1673 freeze, fixes only.

Related: #1759.

<!-- end of body -->
