<!-- flow-run n=1 id=2e97b7e7b04049379beafd5d88969a7d -->
## Run 1 - issue #1759 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1759
- Read at:      2026-11-12T05:55:13Z
- updatedAt:    2026-11-12T05:54:21Z   (context only - moves on comments and labels)
- Body digest:  5e414da0f67b60c77a6bace549e9d02fdcbd057fb6af545e9dad297864060139   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2704 of 2704 (cap 16384)

### Body as read
Tier: 2

Origin: not traced - the runner path was added to `/flow:deploy` as its primary path at some point after the `TARGET` argument existed; I did not look for the change.

Severity: HIGH (raised 2026-11-12 by the wave orchestrator), a **live correctness problem**: the command can deploy something other than what was asked for. Filed as its own issue, not a Nit Store comment, for that reason. Found 2026-11-12 by the counter-model review of #1712 (pass 2) and confirmed by reading the document and the plan.

## Outcome
`/flow:deploy <TARGET>` runs the target it was given.

## What happens now (origin/main `3e52bf6d`)
- `.claude/commands/flow/deploy.md` takes an optional `TARGET` (line 7: 'Makefile target to run (default: deploy)'), and Step 3 validates that `TARGET` has a rule in the Makefile.
- Step 4b, the PRIMARY path, then runs `python -m lib.cicd run --plan deploy` whenever a CPP checkout is found. It does not pass `TARGET`.
- That plan's last step is hard-coded: `lib/cicd/steps.py:905-911`, `command="make deploy"`.
- Step 5, the fallback that does run `make "$TARGET"`, is skipped whenever the runner was used.
- Step 6 logs `${TARGET}` in `.claude/deploy.log`.

So on any host with CPP installed, `/flow:deploy deploy-staging` validates `deploy-staging`, runs **`make deploy`**, and logs that `deploy-staging` was deployed. A project whose `deploy` is production and whose `deploy-staging` is staging deploys production when asked for staging. Not reproduced by running it (that would deploy something); read from the three places above.

The same gap is what lets a fresh scaffold be reported as deployed after #1712: `/flow:deploy lint` passes Step 3 because `lint:` exists, the runner runs `make deploy`, and if the project has a file or directory named `deploy`, make answers 'up to date' and exits 0.

## Acceptance
- With a non-default `TARGET`, the command either runs exactly that target or stops with a named reason. It never runs a different one.
- The log line names the target that actually ran.
- A committed case: a Makefile with `deploy` and `deploy-staging` that each write a different marker file; `/flow:deploy deploy-staging`'s blocks, run in order, leave only the staging marker.
- A stated answer for the runner: does the deploy plan take a target, or is the runner path reserved for the default target and every other target routed through the validated fallback?

## Constraint
`flow/deploy.md` is at its word budget (1,561 of 1,561), and `lib/cicd` and `.claude/commands/flow/` are under the #1673 freeze: fixes only. If the runner's plan or its verdict lines change, that is output Kyle and skillc read and needs the coordination route.

Related: #1712.

<!-- end of body -->
