# Flow run record - issue #1543

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=6df135253539434f8bbf8de26a581e1e -->
## Run 1

- Run-id:            6df135253539434f8bbf8de26a581e1e
- Run-start:         b318a14b9e7935f2c50c0940144a5ff0ff9389ed
- Issue:             #1543
- Base SHA:          b318a14b
- Necessity verdict: Still needed
- Approval:          granted (GATE: GO-WITH-CONDITIONS, orchestrator outbox rev 2)
- Approver:          cpp-group orchestrator (cpp-orch), authority-model=orchestrator-only, policy rev 1
- Recorded at:       2026-10-23T11:42:00Z

### Section B evidence
commits: none touching the lane paths since 2026-10-23T11:21:44Z (origin/main b318a14b).
PRs: none merged since filing. dup/super: none; related closed #726 #772 #1191 #1412 #794 #1262;
#1542 open, same files, different defect. Host: 4 worktrees, no unpushed commits on these paths.

### Section C - the approved plan
1. `scripts/gh-pr-merge.sh` - add `--match-head-commit <sha>` (40-hex, else exit 2), carried in BASE_FLAGS to every `gh pr merge`; pre-wait and pre-squash head re-read, mismatch is CLEAN STOP exit 11, never retried or admin-escalated
2. `.claude/commands/flow/merge.md` - replace the plain `gh pr merge` fallback with stable/plugin/CPP-checkout resolution and a refusal with a distinct MERGE_RC naming /flow:repair; document exit 11 and the refusal code
3. `.claude/commands/flow/auto.md` - same at Step 7.2; exit-11 bullet; pass the pin in the CI-wait recipe
4. `tests/test_gh_pr_merge.py` - wiring test over 4 surfaces, behavioural no-helper red with the skillc#515 body, helper exit-5 pin on that body, pin passthrough, head-mismatch red, no admin retry on server-side head rejection, malformed sha
Scope: 4 sources plus regenerated codex mirrors, about 250 lines. Risk: removes the unguarded merge on hosts without /flow:repair (intended); codex cwd-relative resolution (#1542) left untouched.

Conditions (orchestrator): distinct refusal MERGE_RC named in both exit lists; reuse the existing resolution pattern; exit 11 documented as never retried or escalated, with a test; the CI wait and the pin key on the same sha; reds (a) (b) (e) run on pre-fix code; mirrors via codex-skill-sync.py only; #1542 residual in the PR body.
Same-sha note: the required-check wait reads the PR's CURRENT head rollup, so the helper verifies head == pin BEFORE the wait (the rollup it waits on belongs to the pinned sha) and again immediately before the squash; GitHub's server-side pin covers the final race.
