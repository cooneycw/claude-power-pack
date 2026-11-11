<!-- flow-run n=1 id=e962e19e987242568c6b89462a36bb30 -->
## Run 1 - issue #1689 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1689
- Read at:      2026-11-11T21:59:05Z
- updatedAt:    2026-11-11T21:58:55Z   (context only - moves on comments and labels)
- Body digest:  01437649968f922e78ed8522db76026f207272b72f87a97280afad11426c2b8f   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2748 of 2748 (cap 16384)

### Body as read
Tier: 2

Source: owner ruling, 2026-11-11, in the /flow:auto session for #1672 ("yes they should be scrubbed"). Promoted out of the Nit Store: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6807165982. This repository is PUBLIC.

## Outcome
Tracked files embed the host account name inside filesystem paths: `/home/<account>/...` and the Claude transcript directory form `-home-<account>-Projects/<session>.jsonl`. They show the local account name and home layout of the machine the work ran on. No tracked file should carry them, and nothing should be able to add one again.

## Measured (origin/main at 15521b1e)
- Path forms (`/home/<account>`, `-home-<account>-`): 52 lines in 29 files. By directory: `docs/measurements` 17 files (counter-model receipts, fields `path` / `transcript` / `rollout`), `docs/flow-runs` 6, `docs/research` 2, `controls/behavioral-eval` 2, `docs/decisions` 1, `docs/agents` 1.
- Source of new ones: `scripts/counter-model-receipt.py` records the transcript path relative to `~/.claude/projects` (line 1486), and Claude names that directory after the session cwd, which contains the account name.
- No email address is present in any tracked file.
- Other placeholder homes already in use and fine: `/home/clean` (457), `/home/user` (25).

## Acceptance
- No tracked file matches the account-in-path forms. Existing occurrences are replaced with a neutral placeholder (for example `/home/user`, `-home-user-Projects`), not deleted, so the surrounding record still reads.
- `counter-model-receipt.py` stops recording the account name in new receipts (for example the session file name alone, or a redacted directory), and receipt validation still passes for old and new receipts.
- A tripwire in `make verify` fails when a tracked file carries the running account's name in a path form. Committed red case: a fixture file containing such a path fails it; the clean tree passes.

## Decisions for the owner (state them at the plan gate)
1. Existing receipts are edited by this change. That departs from the standing "do not rewrite existing receipts" ruling (#1048) for these path fields only.
2. Git history keeps the old strings after this lands. Removing them from history means rewriting public `main`; this issue does NOT do that unless the owner asks.
3. The bare GitHub handle also appears 103 times outside paths (`Deciders:` lines in ADRs, `Approver:` lines in flow-run records, `LICENSE`, `owner/repo` references). The handle is the repository's public owner, so this issue leaves those alone unless the owner widens it.

## Constraint
Already-published issue and PR comments are out of scope for the code change; list any that carry a path form in the PR so they can be edited by hand.

<!-- end of body -->
