# Flow run record - issue #1760

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a73d0353c7234c17a9e20508f97a6d2a -->
## Run 1

- Run-id:            a73d0353c7234c17a9e20508f97a6d2a
- Run-start:         4f34005f441b066282d58809b2138f2007bc3819
- Issue:             #1760
- Base SHA:          4f34005f441b066282d58809b2138f2007bc3819
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, authority model orchestrator-only), by mailbox rev 95 to role cpp-1508 at 2026-11-12T04:32:33-05:00: "#1760 plan: APPROVED, Section C as written, and YES to finish.md and help.md in the SAME PR" (assignment a-residual-grading-g8)
- Recorded at:       2026-11-12T09:45:00Z

### Section B evidence
- `.claude/commands/flow/deploy.md` at 4f34005f: the fallback security scan names `${HOME}/Projects/claude-power-pack`, and the next lines say "If `lib/security` is not available, skip this step." With the checkout absent the command exits 2 (reproduced), so the scan is skipped and the deploy proceeds.
- `.claude/commands/flow/finish.md` carries the same command and "skip this step (warn the user)"; `.claude/commands/flow/help.md` states the skip as policy.
- `lib.security` is a Python package that no plugin bundle ships; it exists only in a checkout. The gate prints `SECURITY_GATE: <name> PASS|FAIL|UNKNOWN`; its own unreadable-config answer is exit 2, the same number uv returns for a missing project.
- No live copy in kyle (1b3d2eb4) or the kyle-candidate clone (ff51017); skillc (26e686a) has only frozen fixture copies.
- This record was written after the three documents were edited; the edits follow the plan approved by mail before any of them.

### Section C - the approved plan
Conditions attached to the approval: the scan resolves CPP from the three known locations and a scan that cannot run STOPS, never reads as a skip; proceed only on exit 0 with the PASS line; the stop message names the three locations; the independent old-versus-new read covers both trimmed documents and the budget argument is made from the restored size; the other hard-coded paths go to the Nit Store as one comment; coordination issues kyle #2381, skillc #713 and kyle-candidate #15 are named in the PR; full suite; review capped at two passes.

1. `.claude/commands/flow/deploy.md` - the fallback scan finds the scanner itself, stops when it is absent, and proceeds only on exit 0 with the PASS line; the skip instruction is removed.
2. `.claude/commands/flow/finish.md` - the same for the manual scan when the finish runner was unavailable.
3. `.claude/commands/flow/help.md` - the policy sentence says the flow stops.
4. `tests/test_flow_deploy_target.py` - the document's blocks executed with the scanner absent, at another known location, failing, passing without the PASS line, and unknown.
5. `tests/test_flow_finish_security_fallback.py` - the same cases against the finish document's block.

Scope: three command documents, each inside its word budget, and two test files.

Risks: a trim removing an instruction; a host with no checkout can no longer deploy or finish through the fallback without a scan, which is the intent and is announced to the three consumer repositories.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: the documents' own bash blocks executed from scratch projects with the scanner absent, elsewhere, and present; red on 4f34005f first |
| Harness | will test: word budgets, Codex mirrors rebuilt and tests/test_codex_skill_sync.py, an independent old-versus-new read of both trimmed documents; a live Claude or Codex run of /flow:deploy or /flow:finish is not covered |
| Driver | not applicable: no driver-specific code |
| Coordination | not applicable: no wave, mailbox or registry code |
| CI provider | not applicable: no pipeline or CI-status code |
| Project state | will test: a non-default deploy target with a stubbed make and a stubbed scan; a real deployment is not covered |
