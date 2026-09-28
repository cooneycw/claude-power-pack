# Flow run record - issue #1342

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=ab9a48bcb8c941dba9227e10998d21cf -->
## Run 1

- Run-id:            ab9a48bcb8c941dba9227e10998d21cf
- Run-start:         75fb4497140b5a0584a19c8761a98e83ce66e612
- Issue:             #1342
- Base SHA:          75fb4497140b5a0584a19c8761a98e83ce66e612
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cpp-wave2 orchestrator (run48:cpp2-orch), mailbox message 2440, approved WITH the FLOW_CI_FAILURE_ORIGIN line
- Recorded at:       2026-09-28T22:30:00Z

### Section B evidence
- commits: none touching scripts/toolchain-provenance.sh, scripts/flow-ci-status.sh, their tests or docs/scripts.md since 2026-09-28T21:40:13Z
- PRs: none (#1089 merged, predates the issue - created toolchain-provenance under #1029)
- dup/super: none (#1268 parent, #864 Nit Store)
- sibling worktrees: none with commits on these paths

### Section C - the approved plan
1. `scripts/toolchain-provenance.sh` - measure HEAD's committer-date age; emit it in quiet behind/diverged lines, the human report, JSON `head_age_seconds`, and `TOOLCHAIN_HEAD_AGE=`; `-`/null when unreadable, never 0
2. `tests/test_toolchain_provenance.py` - red case with a backdated HEAD commit, blind case, key-contract addition
3. `scripts/flow-ci-status.sh` - `FLOW_CI_PRECODE_FAILURE: <step>` for failed type==clone steps, plus `FLOW_CI_FAILURE_ORIGIN: precode|code|mixed|unknown` on failure; STATUS stays last; exit codes unchanged; CLI type read in a separate call that fails open
4. `tests/test_flow_ci_status.py` - API/CLI precode and code cases, CLI type-call failure, GHA unknown, STATUS-last
5. `docs/scripts.md` - both contracts updated
6. `.claude/commands/flow/auto.md` - Step 8 contract block and failure bullet

Scope: 6 source files, ~150-220 lines. Risks: CLI `.step.Type` unverified (fails open to unknown); committer date is a commit claim, not checkout time; pre-code narrowed to type==clone (jq-stage network red to Nit Store).
