# Flow run record - issue #1366

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=c6d7dc52fae24e5d9b2cbb1e72c11638 -->
## Run 1

- Run-id:            c6d7dc52fae24e5d9b2cbb1e72c11638
- Run-start:         1e69afb6d6bb64200dadeb3ff81cd2cac49b5041
- Issue:             #1366
- Base SHA:          1e69afb6d6bb64200dadeb3ff81cd2cac49b5041
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (session user, "approved" - runner route)
- Recorded at:       2026-10-04T16:10:00Z

### Section B evidence
Commits on origin/main since 2026-10-04T15:09:02Z: none. Merged PRs since filing: none.
Issues inspected: #1211 (closed, unrelated), #1365 (open, carved out by the issue), #1367 and
skillc #249 (downstream consumers, no overlap). No open PR references #1366.

### Section C - the approved plan
1. `lib/cicd/evidence.py` - new: cpp.execution-evidence/v1 record built from runner step records; identity, declared vs observed, per-check facts, atomic write to git-common-dir, retention 50, begin/terminal/interrupted, export env, verify reader
2. `lib/cicd/runner.py` - retain final RunState before cleanup; run_plan writes begin/terminal records when CPP_EXECUTION_EVIDENCE is set
3. `lib/cicd/cli.py` - `evidence verify|show` subcommand
4. `.claude/commands/flow/check.md` - lint/test/typecheck via `lib.cicd run --plan check` with evidence on; make fallback kept; reader step in report
5. `codex/skills/flow-check/SKILL.md` - regenerated mirror via codex-skill-sync.py --write
6. `tests/test_execution_evidence.py` - new: good/bad/unknown controls + privacy
7. `controls/execution-evidence-verify/control.json` - new committed negative control for the verify reader (with run-case.sh and cases)
8. `docs/agents/execution-evidence.md` - new: paths, storage/retention, compatibility, reader example with exact claim
9. `docs/measurements/execution-evidence/flow-check-pilot.json` - one real pilot record
10. `.gitignore` - negation for the pilot artifact directory

Scope: ~10 files, ~900-1100 lines. Risks: /flow:check now runs lint/test/typecheck through the runner (resume, uv fallback, progress output); schema must stay distinct from skillc #249's verdict.
