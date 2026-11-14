# Flow: Auto - Full Issue Lifecycle in One Shot

Worktree → issue analysis → approved plan → implementation → PR → merge → deploy.

Why each rule exists (#1669):
[flow:auto rationale](../../../docs/reference/flow-auto-rationale.md).

## Arguments

- `ISSUE` (required): GitHub issue number (e.g., `42`)
- `PROJECT` (optional): target repo when the session cwd is not the repo the
  issue belongs to (issue #578). Resolved like `/project:next`: an existing
  directory path first, else `~/Projects/<PROJECT>`; must be a git checkout.

## Capability contract (issue #783)

| | |
|---|---|
| **Scope** | **general** - Claude implements directly, so the deliverable can be a diff, a written finding, a recommendation, or a decision |
| **Web** | **yes** - WebFetch / WebSearch are available for live sources |
| **Container** | **yes** - the Bash tool reaches docker/kubectl/terraform directly, no sandbox denial (issue #835) |
| **Cannot take** | nothing on these axes |

This is the unconstrained driver. The delegated drivers (`/codex:auto`,
`/qwen:auto`, `/gemma:auto`) are IMPLEMENTATION-ONLY and cannot reach a live
source, so **research tickets and anything needing current information belong
here**. In a `/flow:wave`, register with `--driver flow:auto`.

```bash
~/.claude/scripts/flow-driver-capability.sh list          # the whole matrix
~/.claude/scripts/flow-driver-capability.sh show flow:auto
```

## Instructions

When the user invokes `/flow:auto <ISSUE> [PROJECT]`, perform these steps sequentially. Stop immediately if any step fails.

Report at the start:

```
Flow Auto: Issue #42 - Full Lifecycle

Step 1/9: Start (create worktree and branch)
Step 2/9: Analyze (understand issue and codebase)
Step 3/9: ELI5 (plain-language intent + necessity verdict + plan approval gate)
Step 4/9: Implement (write the code)
Step 5/9: Update Docs (regenerate C4 diagrams, review CLAUDE.md/README.md)
Step 6/9: Finish (lint, test, commit, push, create PR)
Step 7/9: Merge (squash-merge PR, clean up worktree)
Step 8/9: Verify CI (confirm pipeline passes on main)
Step 9/9: Deploy (make deploy, if target exists)

Proceeding...
```

---

### Friction Capture (always-on)

Record friction the moment it happens, on every step, success OR failure, and
before any STOP, via the fail-open capture helper:

- a **quality-gate failure or retry** (lint/test/build/deploy)
- **red output** you narrated past or worked around instead of resolving
- a **manual intervention / correction** the user had to make

```bash
~/.claude/scripts/friction-log.sh --class <gate-failure|red-output|manual-intervention> \
  --signal "<what happened>" --fix "<proposed fix, if obvious>" \
  --scope <local|portable> --run "flow:auto #$ISSUE_NUM" --step "<N/9 Name>" --outcome "<retried|worked-around|corrected>"
```

Never log the **permission-prompt** class by hand (issue #482). On exit 127
fall back to `${CLAUDE_PLUGIN_ROOT}/scripts/friction-log.sh` (#590) or the
CPP-checkout copy; if no copy exists, skip capture rather than stopping.
Capture only: fixes are proposed and applied in the retro, not here.

---

### Step 1: Start - Create Worktree

**CRITICAL: You MUST create or enter a worktree before proceeding. NEVER implement changes directly on main/master. This step is NOT optional - if worktree creation fails, STOP immediately.**

Worktrees are created OUTSIDE the repo (issue #627), as a visible sibling
`../<repo>-<branch>` or under `FLOW_WORKTREE_BASE` (#584). Enter with `cd`;
never call `EnterWorktree`. Step 1's plumbing lives in ONE audited helper,
`scripts/flow-start-resolve.sh` (issue #581). Do NOT re-implement any of it as
inline bash.

**Invocation discipline (issue #581):** call flow helpers BARE, with literal
argument values - never wrapped in `if [ -x ... ]`, never chained with `&&` or
`;`, never followed by `echo $?`. Helpers print their own status markers and
exit codes carry the result. This applies to every flow helper in this file.

**1a. Resolve.** Run exactly one of these, substituting the literal issue
number (and project, when `/flow:auto` was given a PROJECT arg):

```bash
~/.claude/scripts/flow-start-resolve.sh 42 --require-preflight --session-cwd /home/user/Projects/my-repo
~/.claude/scripts/flow-start-resolve.sh 42 my-project --require-preflight --session-cwd /home/user/Projects/my-repo
```

**Require preflight (#1571).** The flag validates the local host report before
issue reads, fetches, claims or worktree creation. Required gaps, unknown
observations, and malformed or contradictory reports stop this run. Optional
Codex absence is a warning.

**Pass `--session-cwd` (issue #592).** Pass the directory this session reports
as its cwd VERBATIM as a literal path - never `$(pwd)`. Omitting it reports
`SESSION_CWD_INFERRED=1` and risks only a misdetected `current-branch`/`resume`
lane.

On exit 127, fall back to `scripts/flow-start-resolve.sh` from the CPP checkout
(issue #590; it may prompt once - tell the user to run **`/flow:repair`**). If
no copy exists, **STOP** and report that flow needs a CPP checkout plus
`/flow:repair`.

The helper prints a `key=value` contract ending in `FLOW_START_RESOLVE: ok`.
On `FLOW_START_RESOLVE: error` (with an `ERROR=` line): **STOP** and report it.
Keys: `LANE` (`current-branch|fresh|resume|remote-pickup|local-pickup|cross-repo`),
`CROSS_REPO`, `GIT_LANE` (always `GIT_LANE=1`: enter with `cd`, git cleanup at
Step 7), `SESSION_CWD`, `SESSION_CWD_INFERRED`, `TARGET_REPO`,
`COMPOSE_PROJECT_NAME` (the compose pin for the whole run, issue #626),
`ISSUE_STATE`, `ISSUE_TITLE`, `BRANCH`, `WT_PATH`, `DEFAULT_BRANCH`,
`REMOTE_BRANCH`, `WT_CREATED` (1 = the helper already ran `git worktree add`),
`WT_BASE` (only when `WT_CREATED=1`), `LIVE_DRIVER` / `PR_HEAD` (the #503 resume
hazards), `CLAIM` / `CLAIM_PID` / `CLAIM_SESSION` (the #597 cross-session
claim), `CONFIRM_REQUIRED`.

**1b. Act on the contract** - the only decision left to you:

- `CLAIM=held` (`CONFIRM_REQUIRED=1`): another LIVE session is driving this
  issue (issue #597). **STOP.** Do not create or enter anything. Report the
  owner (`CLAIM_PID`, `CLAIM_SESSION`) and let the user decide; take over only
  if they confirm that session is gone. `CLAIM=stale` is taken over
  automatically.
- `ISSUE_STATE` not `OPEN` (`CONFIRM_REQUIRED=1`): warn and ask whether to
  proceed. On yes, re-run the resolve command with `--allow-closed` appended.
- `LANE=remote-pickup` / `LANE=local-pickup` with `PR_HEAD=<n>:OPEN`
  (`CONFIRM_REQUIRED=1`, `WT_CREATED=0`): the issue branch has an open PR and
  nothing was created (issue #1258). Ask; on yes, re-run with `--allow-pickup`.
- `SHIPPED_BRANCH=<branch>:<n>:MERGED`: a merged issue branch was NOT picked up
  (issue #1258); the run took the fresh lane. Mention it in the Step 2 report.
- `FLOW_START_RESOLVE: error` naming `FLOW_WORKTREE_BASE` (issue #1258): no
  writable place for the worktree. **STOP** and report it.
- `LANE=current-branch`: already on the issue's branch in the session cwd - use
  the current directory (nothing to enter).
- `LANE=fresh` / `LANE=cross-repo` / `LANE=remote-pickup` / `LANE=local-pickup`:
  the helper already created the worktree at `WT_PATH` (`WT_CREATED=1`).
  `cd <WT_PATH>`. When `WT_BASE` names a branch rather than the base ref, the
  checkout reused an existing branch already contained in the base (issue #793).
- `FLOW_START_RESOLVE: error` naming a branch as unmerged/not-an-ancestor
  (issue #793): a pre-existing branch for this issue carries commits the base
  does not have. **STOP** and report it; do not retry blindly. The user may
  need to delete/rename the branch or rebase it themselves.
- `LANE=resume`: a prior session's worktree exists at `WT_PATH`. If
  `CONFIRM_REQUIRED=1` (`LIVE_DRIVER=suspected`, issue #503, and/or `PR_HEAD`
  shows an open/merged PR), **STOP** and require EXPLICIT user confirmation
  before entering. Then `cd <WT_PATH>`.

Resolve `Write`/`Edit` paths from `git rev-parse --show-toplevel` run inside
the worktree (the #486 rule).

#### Verification Gate (MANDATORY - do NOT skip)

Before proceeding to Step 2, from INSIDE the worktree, run bare (literal
values from the 1a contract):

```bash
~/.claude/scripts/flow-start-resolve.sh --verify 42 issue-42-fix-login
```

It fails (`FLOW_START_VERIFY: fail`, exit 1) when the checkout is still on
main/master, and renames a non-conforming branch to `issue-<N>-<slug>`. On
success it prints `BRANCH=`, `WT_ROOT=`, `CLAIM=` and `STASH_GUARD=`. The last
two are ADVISORY, never a precondition: `CLAIM=self` means the worktree is
locked to this session (issue #597); `STASH_GUARD=disabled` means the
repository recorded `cpp.stashGuard=false`; `STASH_GUARD=unknown` means the
shared-stash guard (`scripts/stash-worktree-guard.sh`, issue #1056) was not
found. See `docs/agents/shared-stash-stack.md`.

**If this verification fails, STOP immediately. Report the failure using the error template at the bottom of this file. Do NOT proceed to Step 2.**

Report: `Step 1/9: Start complete - worktree at {path}, verified on branch {branch}`

#### Reconcile the plan record, and record what this run read (issues #1080, #1081)

Run both, bare, on EVERY lane including `current-branch` and `resume`, before
Step 2:

```bash
~/.claude/scripts/flow-plan-record.py reconcile 42
~/.claude/scripts/flow-plan-record.py read-issue 42
```

- `reconcile` leaves `docs/flow-runs/issue-<N>.md` as the last COMMITTED
  record for this issue, or absent, and prints
  `FLOW_PLAN_RECORD: restored|removed|absent`, exit 0. Do not hand-edit the
  record between runs.
- `read-issue` stores the issue body as this run read it. `AS_READ: recorded`
  is exit 0. `AS_READ: unresolved` (exit 4): continue; the Step-4 snapshot
  will say unresolved.

**Helper resolution**, here and at Steps 4 and 6: the stable path first; on exit
127, `${CLAUDE_PLUGIN_ROOT}/scripts/flow-plan-record.py`, else the CPP-checkout
copy (tell the user to run **`/flow:repair`**). If no copy exists, **STOP** and
report it. Background:
[the plan-record reference](../../../docs/agents/flow-plan-record.md).

**Compose-project safety - RUN-WIDE (issue #626).** **Whenever any step
below, or a command you run by hand, invokes `docker compose` in this worktree,
set `COMPOSE_PROJECT_NAME` in the SAME shell call** to the Step-1 contract
value - e.g. `COMPOSE_PROJECT_NAME=<contract value> make docker-up`. Unpinned,
compose names a second, colliding stack after the worktree basename.

---

### Step 2: Analyze - Understand the Issue

1. **Parse the issue body:**
   - Extract acceptance criteria (checkbox items `- [ ]`)
   - Identify referenced files, components, or areas
   - Note any dependencies or constraints mentioned

   **If the body carries a `speckit-context` block** (issue #858), the block is
   a bounded CACHE of the task's declared context - not the authority. Fetch
   the body to a UNIQUE file, check the fetch succeeded, then run the checker:

   ```bash
   BODY_FILE="$(mktemp -t flow-auto-body-XXXXXX.md)"
   if ! gh issue view "$ISSUE_NUM" --json body --jq .body > "$BODY_FILE"; then
       echo "STOP: could not fetch issue #$ISSUE_NUM; not checking context against an empty body."
       exit 1
   fi
   ~/.claude/scripts/speckit-context.py check --body-file "$BODY_FILE" --root .
   ```

   On exit 127: `${CLAUDE_PLUGIN_ROOT}/scripts/speckit-context.py`, else the
   CPP-checkout copy. Inside a generated Codex skill, use the skill's own
   bundled copy, `${CPP_SKILL_DIR:-/dev/null}/scripts/<name>` (issue #1542) -
   never a `scripts/` directory in the target project.

   Act on `SPECKIT_CONTEXT_STATE`:
   - `current` - read the **Reference source** named in the block, including
     the cross-cutting sections it lists, then plan.
   - `changed-in-scope` / `changed-outside-scope` - source bytes changed, which
     is NOT a ruling that acceptance changed. Read the source, decide whether
     it matters under the existing authority model, and say so in the Step 3
     report. Newer bytes do not by themselves override a constraint or plan
     already accepted on the issue. Report any recorded `Acceptance-revision:`
     line with the version it names, and resolve whether it predates the change.
   - `changed-task` - re-read the task line and its story; treat the block's
     requirement list as provisional.
   - `tasks-missing` - plan from the issue body and the source if one resolves;
     report that the task-side mapping could not be re-checked.
   - `block-edited` / `block-damaged` - read the source directly; do not
     refresh the block as a side effect of this run.
   - `source-missing` / `source-unresolved` - plan from the issue body and
     surface any material ambiguity.
   - `absent` - an ordinary issue. Its body IS the contract (see
     [the issue contract](../../../docs/agents/issue-contract.md)).

   The block's **Task wording** line is the task's own sentence, not a ruling:
   resolve whether it proposes an approach you may replace or restates a binding
   constraint. Resolve what would change the work, surface the rest in the
   Step 3 report, and plan from what you have.
   An **Unresolved** or **Capped** note means the context is incomplete - never
   that the task has no constraints. Missing optional structure is not a gate.

2. **Explore the codebase:** read the files the issue references, learn the
   existing patterns, and identify every file to create or modify.

3. **Form an implementation plan:** the specific changes, edge cases and risks.

4. **Report the plan to the user:**

```
Step 2/9: Analysis Complete

Issue #42: "Fix login redirect loop"

Acceptance Criteria:
  - [ ] Login redirects to dashboard after auth
  - [ ] Invalid sessions redirect to /login
  - [ ] Tests pass

Implementation Plan:
  1. Modify src/auth/login.py - fix redirect logic in handle_login()
  2. Update tests/test_auth.py - add redirect test cases
  3. Update config/routes.py - add dashboard route

Files to modify: 3
Estimated scope: Small

Proceeding to ELI5 review...
```

Report: `Step 2/9: Analyze complete - {N} files to modify`

---

### Step 3: ELI5 - Plan + Necessity Gate (Approval Checkpoint)

Before writing any code, run the `/flow:eli5` review using the issue and the Step 2 analysis.

**Load the FULL gate spec first (issue #509)** and produce the report against
THAT spec, including its report template and depth floor. First match wins:

1. the user-scope command link: `~/.claude/commands/flow/eli5.md`
2. a Codex install: `~/.codex/skills/flow-eli5/SKILL.md`
3. inside the CPP repo itself: `.claude/commands/flow/eli5.md`

**If none of them resolves, STOP** and report `ELI5 spec not found` with the
remedy: run `/cpp:init`, or on a Codex install `codex-skill-sync.py --install`.
Do NOT produce the report from the summary below alone. The three sections,
for orientation:

1. **ELI5 overview of intent** - plain language a reviewer can sanity-check.
2. **Necessity / staleness analysis**, anchored to the issue's creation date:
   ```bash
   ISSUE_DATE=$(gh issue view "$ISSUE_NUM" --json createdAt --jq '.createdAt')
   git log --since="$ISSUE_DATE" --oneline -- <relevant/paths>
   gh pr list --state merged --search "merged:>=${ISSUE_DATE%%T*}" --json number,title,mergedAt
   gh issue list --state all --search "<key terms>" --json number,title,state
   ```
   Output one verdict with evidence: **Still needed / Partially addressed / No longer needed / Needs reframing**. Depth floor: enumerate the commit SHAs, merged PR numbers, and duplicate/superseding issue numbers inspected (or an explicit "none").
3. **Proposed changes (pending approval)**. Depth floor: one numbered line per file with its change gist - never "various files" - plus a scope estimate and at least one named risk (or an explicit "no notable risks").

**This is a gate:**

- **Verdict `No longer needed`** -> do NOT implement. Recommend closing the issue with an evidence-based comment and **STOP**:
  ```bash
  gh issue close "$ISSUE_NUM" --comment "Closed via /flow:auto ELI5 review - <reason; cite superseding PR/issue>."
  ```
  Run the close only with reviewer assent; surface the recommendation either way.
- **Verdict `Partially addressed` or `Needs reframing`** -> the plan to approve is the adjusted one (remaining work / corrected approach), not the original issue body.
- **Approval:** Always **pause and wait for reviewer approval** of the plan before continuing to Step 4. This is unconditional.

**The gate has no bypass (issue #775).** There is no flag, trailer, marker,
environment variable, or governance tier that lets Step 3 proceed without a
reviewer approving Section C, and none may be added. Every such channel grants
approval *before the plan exists*, so it is not an approval of the plan - only
standing consent to whatever plan the run later produces.

- `--yes` / `--auto-approve`: recognized, and refused. If a caller passes one,
  say the gate is not skippable and pause anyway - never honor it silently and
  never ignore it silently.
- An `eli5: auto-approve` trailer in the issue body or the HEAD commit message:
  **never read**. Do not scan either for approval. This channel is not chosen by
  whoever invoked the run - an issue body is written by whoever filed the issue,
  and on a worktree freshly branched off main HEAD *is* main's tip commit,
  written by whoever merged last. One merged commit carrying the trailer would
  disarm the gate for every later run branched from that tip, across unrelated
  issues and unrelated sessions.

Unattended runs are not an exception: hand the report to the orchestrator or
reviewer and wait, rather than approving on their behalf.

Report: `Step 3/9: ELI5 complete - verdict: {Still needed|Partially addressed|No longer needed|Needs reframing}; approval: {granted|close recommended}`

There is deliberately no `auto-granted` value: a field that can still be produced means something can still skip the gate (issue #775).

---

### Step 4: Implement - Write the Code

**Re-check for a second driver (issue #597) - run BEFORE the first edit.**
Bare, advisory. Pass the Step-1 `WT_PATH` verbatim as the literal argument -
DECLARED, never inferred from the Bash cwd (issue #1271, the #614 rule);
`FLOW_LIVE_DRIVER_PATH:` must name the run's worktree:

```bash
~/.claude/scripts/flow-live-driver-guard.sh /path/to/worktree
```

- `FLOW_LIVE_DRIVER: clear` - proceed.
- `FLOW_LIVE_DRIVER: suspected` - dirty files here are NOT yours. **STOP** and
  ask the user before editing.
- If anything looks off, `~/.claude/scripts/flow-worktree-claim.sh check .` -
  `FLOW_CLAIM: self` is healthy; `held` means someone took the checkout over.

**Early stale-base check (issue #473) - run BEFORE editing.** Bare, advisory
(warns, never blocks). Pass the worktree path from the Step-1 contract
(`WT_PATH`) verbatim as the trailing literal argument (issue #614, the #592
rule); the emitted `FLOW_STALE_PATH:` line must name the run's worktree:

```bash
~/.claude/scripts/flow-stale-check.sh origin/main /path/to/worktree
```

(Exit 127: `${CLAUDE_PLUGIN_ROOT}/scripts/flow-stale-check.sh` (#590), else
the CPP-checkout copy; if none exists, note it and continue.)

- `FLOW_STALE_BASE: collision` - or a file you are about to touch named under
  "Changed upstream": `git merge --no-edit origin/main` now and resolve any
  conflict before implementing. If git refuses to START the merge, commit
  first (`git add -A` + `git commit -m "wip(flow): pre-merge snapshot"`) and
  merge on the clean tree - never stash: the stash stack is SHARED across every
  worktree (#635). Nothing generated needs staging: `codex/skills/` is ignored
  build output since issue #1670.
- `current` or `moved-clean` with no overlap: proceed.

#### First, write the plan record (issue #1080)

**Step 4 is reached only when Step 3's approval was granted**; a `No longer
needed` verdict writes NO record. **Only after approval is granted, and never
before**, and only after the two checks above, write THIS RUN's approved plan.

**The record is APPEND-ONLY and each run owns one section (issue #1320).**
`begin-run` appends this run's `## Run <n>` header. Then APPEND this run's
fields - never rewrite the file or edit an earlier run's section:

```bash
~/.claude/scripts/flow-plan-record.py begin-run 42
cat >> "docs/flow-runs/issue-42.md" <<'RECORD'
- Issue:             #42
- Base SHA:          <SHA this plan was formed against>
- Necessity verdict: Still needed | Partially addressed | Needs reframing
- Approval:          granted
- Approver:          <who this run understood the approver to be>
- Recorded at:       <ISO 8601 UTC>

### Section B evidence
<the commit SHAs, merged PR numbers and duplicate/superseding issue numbers
 Section B enumerated, or an explicit "none">

### Section C - the approved plan
<the numbered per-file change list, the scope estimate and the named risk(s),
 exactly as approved>
RECORD
```

`begin-run` exits 1 when this worktree has no run identity - run Step 1's
`reconcile` first.

**Adopting found or dirty work (issue #1504).** Only if you deliberately
preserved pre-existing or dirty work by committing it unmodified as its own
commit, run `declare-salvage` with that commit's sha right after `begin-run`
(it refuses a sha that is not an ancestor of HEAD; never infer one from
history):

```bash
~/.claude/scripts/flow-plan-record.py declare-salvage 42 <sha> --reason "<why>"
```

If this run ends with deliberately preserved unfinished work pushed to origin,
follow `/flow:cleanup`'s **Preserved-WIP handoff** procedure before yielding
(#1614) and relay its URL. A failed publication leaves the handoff incomplete;
keep the branch/worktree and report that blocker.

Keep Section C as one numbered line per file, in the form ``N. `path` - gist``:
Step 6 compares the diff against exactly those paths. Markdown only -
`.gitignore` carries a blanket `*.json`. The approver field comes from the
actual approval event (issue #775). Do NOT list this record, its `.as-read.md`
snapshot or the counter-model receipt (issue #1267). `codex/skills/**` mirrors
are ignored build output (#1670): name only the SOURCE.

**Then, before any implementation edit**, write the as-read snapshot and stamp
the approval baseline (issues #1081, #1082):

```bash
~/.claude/scripts/flow-plan-record.py approve 42
```

- exit 0 - the snapshot `docs/flow-runs/issue-42.as-read.md` is written and
  the Step-6 baseline is stamped.
- exit 4 (`AS_READ: unresolved`) - the baseline is stamped but the issue could
  not be read. Proceed; Step 6 will report drift as unresolved, never clean.
- exit 1 - no plan record section for THIS run (#1320). Run `begin-run` and
  append it first.

**Worktree path-resolution rule (issue #486).** Resolve every edit path from
the active worktree root - `git rev-parse --show-toplevel` - never a hand-built
`.claude/worktrees/<name>/...` absolute path. After writing, confirm the change
landed in the worktree (`git status`) and did NOT leak into main, with the
guard in `--strict` mode (issue #576):

  ```bash
  ~/.claude/scripts/flow-worktree-guard.sh --strict
  ```

**Read the `FLOW_WORKTREE_GUARD:` line (issue #1014)**, which is always printed:

- `no-leak` (exit 0): proceed.
- `leak` (exit 3): **Exit 3 is a STOP.** It reports a SIGNATURE, not an author:
  before moving or reverting anything in main, read
  `git -C <main> diff -- <path>` and confirm it is YOUR edit. Only then move
  the change into the worktree and `git -C <main> checkout -- <path>`, and
  re-run the guard. Never revert main content you did not write; if it is
  someone else's, stop and report it.
- `not-applicable` (exit 5): **proceed and report** "leak guard not applicable:
  <detail>".
- `unknown` (exit 4): **proceed and report** "leak guard could not run:
  <detail> - UNCHECKED". Never read or summarise it as "no leak".

Only 3 stops: never run this under `set -e` or behind `|| stop`.

Execute the approved plan from the Step 3 ELI5 gate:

1. **Make all code changes** in the worktree, following the project's existing
   conventions.
2. **Run tests locally** if a quick feedback loop is available.
   **If the local loop starts a compose stack**, pin the project name in the
   SAME call: `COMPOSE_PROJECT_NAME=<Step-1 contract value> make docker-up`
   (issue #626).
3. **Verify the changes** address all acceptance criteria from the issue.

**When the plan turns out to be wrong (issue #859).** Step 2 explored the
codebase and Step 3 reviewed the plan against it, so the approval is informed.
It fixes the intended OUTCOME, not every detail of how to reach it:

1. **Revise within the agreed outcome and constraints - no new approval.** An
   ordinary implementation choice; say what you did in the Step 6 summary.
2. **Investigate an uncertain assumption, bounded and reversible**, inside the
   permissions you already have. A prototype that works may become the
   implementation; remove the unsafe and provisional parts, not the result.
3. **Consequential conflict - return to the existing authority.** A change is
   consequential when it alters promised behaviour, breaks compatibility, or
   crosses a constraint someone set deliberately. Do NOT implement a flaw you
   have evidence against, and do NOT quietly redefine success. Present the
   evidence and a concrete alternative to whoever can agree to it. Prior
   approval, or a standing delegation that actually covers this change, IS
   agreement. Knowing that an approver exists is not agreement. Record it
   briefly once agreed: what changed, why, and what it does to the intended
   outcome. Only consequential deviations earn a record.

An explicit constraint remains binding even when no rationale is recorded for it
(see [the issue contract](../../../docs/agents/issue-contract.md)): a missing
reason is something to surface, never grounds to drop it.
**"No material concern found" is a complete answer.**

**If the change adds or modifies a check, gate, guard, tripwire or allowlist**, ask
the two questions from
[the detector contracts](../../../docs/agents/detector-contracts.md) - does its
success message claim more than its input population supports, and can a
finding tell our thing from a neighbour's - and write the answer in as a test.
Where the narrow answer is deliberately correct, do not widen the check: say
where the larger question is answered instead.

**In a `/flow:wave`, re-register when the scope you derived is wider than the lane
you declared (issue #1266).** Re-run `/flow:register` with the full list before
committing a file outside the declared `--files`; `--files` REPLACES the lane.

If implementation hits a blocker that cannot be resolved:
- **STOP** and report the blocker.
- Suggest manual intervention.

Report: `Step 4/9: Implement complete - {summary of changes}`

---

### Step 5: Update Docs - Regenerate C4 Diagrams and Review Docs

If the Makefile has an `update_docs` target:

```bash
if [[ -f "Makefile" ]] && grep -q "^update_docs:" Makefile; then
    echo "Running: make update_docs"
    make update_docs
fi
```

1. **Regenerate C4 diagrams** - if `docs/architecture/` exists or significant
   code changed, run the `/documentation:c4` workflow (L1-L4 diagrams to
   `docs/architecture/`).
2. **Review CLAUDE.md** and **README.md** - fix any reference, command or
   description the change made stale.
3. **Stage doc changes** - `git add` any modified documentation files.

If no `update_docs` target exists in the Makefile, skip this step. A failure
here is non-blocking: warn and continue.

Report: `Step 5/9: Update Docs complete - {N} files updated` or `Step 5/9: Update Docs skipped (no Makefile target)`

---

### Step 6: Finish - Quality Gates, Commit, Push, PR

```bash
BRANCH=$(git branch --show-current)
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")
```

**Stale-base pre-check (issue #473) - run BEFORE the quality gates and commit.**
Bare (#581; exit 127: `${CLAUDE_PLUGIN_ROOT}/scripts/flow-stale-check.sh`
(#590), else the CPP-checkout copy). Pass the worktree path as the trailing
literal argument (issue #614); `FLOW_STALE_PATH:` must name this run's worktree:

```bash
~/.claude/scripts/flow-stale-check.sh origin/main /path/to/worktree
```

If the base moved, COMMIT the Step-4 work FIRST, then merge on the clean tree
(issue #635). NEVER use `git stash push` or a bare `git stash pop`: the stash
stack is shared by every worktree. Then call the Codex re-sync helper
UNCONDITIONALLY - keyed on the diff, not the base, never re-gated on a path
pattern (#1136). `[ -x ]` is an EXISTENCE guard that keeps the call CPP-only:

```bash
git fetch origin main --quiet
if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]; then
    if [ -n "$(git status --porcelain)" ]; then
        git add -A
        git commit -m "wip(flow): pre-merge snapshot"
    fi
    if ! git merge --no-edit origin/main; then
        echo "STOP: 'git merge origin/main' hit CONFLICTS. Resolve them, 'git add' + 'git commit', then re-run Step 6."
        git diff --name-only --diff-filter=U
        echo "NOTE: your Step-4 work is safe in the 'wip(flow): pre-merge snapshot' commit on this branch."
        exit 1
    fi
fi
if [ -x scripts/codex-skill-resync.sh ]; then
    bash scripts/codex-skill-resync.sh
fi
```

**Acceptance accounting (issue #860).** Before opening the PR, account for
what was delivered: every material acceptance item is demonstrated (name the
test, experiment or reviewed observation), revised (the reason and the
agreement it needed), or deferred (and still owed). Silence is not delivery.
After a #859 revision, reassess earlier evidence against the CURRENT agreed
behaviour.

Set `ACCEPTANCE_COMPLETE=yes` ONLY when every material item is demonstrated,
revised with evidence for the revised behaviour, or resolved by a recorded
transfer or withdrawal. Anything else - including "mostly done" - leaves it
unset, and unset cannot close. **Closing must agree with that judgement.**
When the accounting is not complete, use the non-closing `Refs #N` - in the
commit message, the PR title and the PR body alike, never `Closes #N`. Partial
delivery stays reviewable and mergeable: the disposition changes what CLOSES,
not what may merge. A revision record on its own is never delivery evidence.

Review whatever will become the merge text, reading the closing references
yourself rather than grepping for one spelling, and check the sources in play
rather than rewriting history (the canonical rule is
[the issue contract](../../../docs/agents/issue-contract.md)):

```bash
git log origin/main..HEAD --format=%B
gh pr view "$PR_NUMBER" --json title,body --jq '.title, .body' 2>/dev/null
```

Select the reference here, defaulting to NON-closing and never inheriting a
value from an earlier run. `$ISSUE_REF` feeds the commit message, the PR title
and the PR body:

```bash
ACCEPTANCE_COMPLETE=""     # "yes" only when every material item is demonstrated,
ISSUE_REF="Refs #${ISSUE_NUM}"
if [[ "$ACCEPTANCE_COMPLETE" == "yes" ]]; then
    ISSUE_REF="Closes #${ISSUE_NUM}"
fi
```

**Collapsing the branch to one commit - the SAFE recipe (issue #657).** Prefer
NO collapse at all: the merge helper passes an explicit `--subject`/`--body`
(#655). If you collapse anyway, collapse onto your ORIGINAL base, never a moved
`origin/main`; prove the staged deletions are empty (unless intended) before
committing; THEN bring the moved base in:

```bash
git reset --soft "$(git merge-base HEAD origin/main)"
git diff --staged --diff-filter=D --name-only   # MUST be empty unless intended
git commit -m "type(scope): Description (${ISSUE_REF})"
git merge --no-edit origin/main
```

**Never collapse AFTER the counter-model receipt (item 1 below) has been
written for this branch's current commits (Nit Store #864).** The enrolment
check accepts only the receipted commit or a descendant
(`git merge-base --is-ancestor`). If you must collapse afterwards, re-run the
review and write a fresh receipt; pick up a moved base with `git merge`
instead.

1. **Counter-model review** - a second model reads the branch, BEFORE the
   quality gates below (issue #934,
   [ADR 0007](../../../docs/decisions/0007-counter-model-review.md)).

   **THE RULE IS A PROPERTY, NOT A TOOL NAME: the reviewing model must not be
   the implementing model.** `/codex:code_review` satisfies it today.
   **IT RUNS BY DEFAULT. A SKIP IS A RECORDED STATE, NEVER AN OMISSION.**
   **IT COMES BEFORE THE QUALITY GATES, deliberately**: accepted findings are
   fixed in the worktree, and the gates must see those fixes.

   **1a. Resolve the helper FIRST** (same order as every flow helper,
   #581/#590). A missing helper is a stated gap, not a silent one:

   ```bash
   CM_RECEIPT=~/.claude/scripts/counter-model-receipt.py
   [ -f "$CM_RECEIPT" ] || CM_RECEIPT="${CLAUDE_PLUGIN_ROOT}/scripts/counter-model-receipt.py"
   [ -f "$CM_RECEIPT" ] || CM_RECEIPT="$CPP_DIR/scripts/counter-model-receipt.py"
   [ -f "$CM_RECEIPT" ] || { echo "NOTE: counter-model-receipt.py not installed - \
       the run will be reported in the PR body and NOT recorded in a receipt."; CM_RECEIPT=""; }
   ```

   **Before review, commit an implementation checkpoint (schema 5).** Stage
   only the issue's owned changes, commit them, and review that committed
   artifact. A fix accepted from review needs a new checkpoint and review
   before the receipt is written. See
   [counter-model evidence](../../../docs/agents/counter-model-evidence.md).
   A collector `CODEX_REVIEW: blocked` or missing artifact binding is a failed
   precondition: correct what it names; retry. It is not a skip.

   **Then probe the reviewer (issue #1015).** The ONLY condition that skips a
   review is the inability to run codex:

   ```bash
   BASE="origin/${DEFAULT_BRANCH:-main}"
   git fetch origin --quiet || true
   if ! command -v codex >/dev/null 2>&1; then
       : # record skipped / codex-absent (1d) and go to the quality gates
   fi
   ```

   When `codex` is not on PATH, record skipped / `codex-absent` (1d) and go to
   the quality gates. **The probe is ADDITIVE, never a replacement**: a codex
   that is installed but cannot review must still land in
   `reviewer-unavailable` via 1c. **An empty diff is NOT a skip (owner ruling,
   2026-09-16)**: the review runs and records an ordinary `ran` receipt.

   **Select evidence independently of runtime (issue #1584).** The reviewer
   must differ from every implementing model, including models earlier in the
   same retained session, and must have genuine runtime evidence (a Codex
   thread/rollout or a Claude session). When no eligible reviewer can run,
   record `reviewer-unavailable`; never fabricate a stream or copy a model from
   a banner. On that skip, run `/second-opinion-start` (or another non-Codex
   review) yourself and state its reviewer and verdict in the PR body alongside
   the skip (until #1513 lands); its free-form response is not a receipt.

   **1b. Run the review** (Claude sessions only - a Codex lane takes the skip
   above). Invoke `/codex:code_review` with that BASE and
   `CONTEXT` = `"issue #<N>: <issue title>"`, and **capture the transcript to a
   file**. It returns a findings report and a `## Red cases` section
   (issue #1030).

   **1c. Read the transcript's verdict before believing it:**

   ```bash
   python3 "$CM_RECEIPT" parse /path/to/transcript.md
   ```

   - `COUNTER_MODEL_REVIEW: findings` - triage each as accepted (fix it now,
     under the Step-4 rules), rejected (one-line reason), or deferred (route it
     to the nit store). One re-review after the first accepted fix. Later
     accepted fixes: STOP, ask the approver before each further pass; never
     receipt unreviewed commits or false counts.
   - `COUNTER_MODEL_REVIEW: clean` - record `ran` with zero counts.
   - `COUNTER_MODEL_REVIEW: unparseable` (non-zero) - **This is not a clean
     review.** Record `skipped` with reason `reviewer-unavailable`; never a
     `ran` receipt with zeros.
   - `COUNTER_MODEL_REVIEW: format-mismatch` (non-zero, issue #1259) - **the
     review HAPPENED, so this is never a skip.** Ask the reviewer once to
     restate its findings in the prescribed `### [SEVERITY] title` shape and
     parse again; if it still does not comply, triage by reading and record
     `ran` with your counts.

   **1d. Write the receipt - ALWAYS, including on a skip.** The writer DERIVES
   both identities and REFUSES to write when it cannot; never hand it a model
   name:

   - **Reviewer (issue #1048):** derived from the codex exec stream `$STREAM`.
     On a skip, pass no reviewer evidence (#1046).
   - **Implementer (issue #1047):** `--implementer-session-id
     "$CLAUDE_CODE_SESSION_ID"`, **on the skip path too**. In a CODEX session
     (issue #1453) pass `--implementer-thread-id "$CODEX_THREAD_ID"` explicitly;
     with both ids visible and neither flag, the writer refuses. The delegated
     exec selector is `--implementer-exec-log`.
   - **`--scope`** (REQUIRED on a Codex-exec `ran` write, #1400/#1461),
     **`--network`** (#1450) and **`--local-credentials`** (#1459) carry
     `/codex:code_review`'s `CODEX_REVIEW_SCOPE`, `CODEX_REVIEW_NETWORK` and
     `CODEX_REVIEW_LOCAL_CREDENTIALS` markers, exactly as printed.

   ```bash
   python3 "$CM_RECEIPT" write --dir "$(git rev-parse --show-toplevel)/docs/measurements/counter-model" \
       --issue "$ISSUE_NUM" --branch "$BRANCH" \
       --status ran --reviewer-exec-log "$STREAM" --scope "$CODEX_REVIEW_SCOPE" \
       --review-base "$CODEX_REVIEW_BASE" \
       --network "$CODEX_REVIEW_NETWORK" \
       --local-credentials "$CODEX_REVIEW_LOCAL_CREDENTIALS" \
       --implementer-session-id "$CLAUDE_CODE_SESSION_ID" \
       --passes 2 --accepted 3 --rejected 1 --deferred 0 \
       --red-cases-proposed 4 --red-cases-already-covered 3
   ```

   Past `--passes 2`: `--extra-pass-reason`; past 3 also `--escalated-by`,
   `--escalation-ref`, `--raised-cap`.
   CI enforces the receipt at the merge boundary (issue #1452).

   **Stage the receipt immediately, on every status including a skip (issue
   #1030):**

   ```bash
   git add "$(git rev-parse --show-toplevel)/docs/measurements/counter-model/"*.json
   ```

   Do not rewrite existing receipts (owner ruling, #1048). **The PR
   body block below is a RENDERING of the receipt, never the source.** Append
   it to the PR body in item 5; a skipped stage appends the one-line skip note
   and its receipt path instead:

   ```
   ## Counter-model review

   Reviewer: <model> (must not match any implementing model), N pass(es)
   Findings: X accepted (fixed), Y rejected, Z deferred
   Red cases proposed: P, already covered by our tests: Q
   Receipt: docs/measurements/counter-model/<file>.json
   ```

2. **Quality gates** - ONE audited helper, `scripts/flow-finish-gate.sh`,
   owns the runner invocation and its Makefile fallback
   (`make lint`/`test`/`typecheck`/`verify`). Invoke it BARE:

   ```bash
   ~/.claude/scripts/flow-finish-gate.sh
   ```

   (Exit 127: fall back to `${CLAUDE_PLUGIN_ROOT}/scripts/flow-finish-gate.sh`
   (#590), else the CPP-checkout copy; tell the user to run **`/flow:repair`**.)

   If the project's gate needs the pushed head (it refuses unpushed commits),
   commit and `git push -u origin "$BRANCH"` first, then gate; same at Step 7
   (#1706).

   **A run with no `FLOW_FINISH_GATE:` verdict line did not run the gate: **STOP**
   (issue #1547).** The trigger is the verdict LINE, never the exit code: 127,
   126 (an unset `CPP_SKILL_DIR`), 2, only the `FLOW_FINISH_GATE_EXIT=`
   trailer, or nothing at all, gave no verdict. Work the fallback chain; if no
   copy prints a verdict line, STOP and report that the gate did not run. It is
   NOT `skipped`, and the run never commits, pushes or merges on it.

   Each verdict has its own exit code (issue #1027):
   - `FLOW_FINISH_GATE: ok` (exit 0): proceed to commit.
   - `FLOW_FINISH_GATE: warn` (exit 3, issue #621): a test step exited 0 having
     executed no tests. Proceed, but report the counts verbatim and say plainly
     that this gate proved nothing about the change; never "tests passed".
     `warn` also means a test failed and PASSED on re-run (issue #769): report
     the ids on the `RERUN_PASSED:` line and never call the run a clean pass.
     If the skips look load-bearing, name the missing prerequisite and offer
     the fuller target.
   - `FLOW_FINISH_GATE: warn (zero coverage: <gates>)` (exit 3, issue #1027):
     a MEASURED PART of the named gates examined NOTHING. Proceed, but **repeat
     the runner's warning verbatim rather than paraphrasing it**; never "the
     gates passed".
   - `FLOW_FINISH_GATE: fail` (exit 1): report the failed step, **STOP**.
   - `FLOW_FINISH_GATE: skipped` (exit 4): no runner AND no Makefile gate
     targets - the gate did NOT run and proved nothing; warn the user, then
     proceed.
   - `FLOW_FINISH_GATE: warn (skipped gates: verify)` is the ORDINARY verdict in
     a repository with no `verify:` target (issue #1147); it does not stop the
     flow. In a repo that DOES have one, check the Makefile.

   **Ignored-additions guard** (issue #430). Invoke bare (on exit 127 skip it):
   ```bash
   ~/.claude/scripts/check-ignored-additions.sh
   ```
   **Exit 3 is a STOP** - a new file is swallowed by `.gitignore`. Add a
   `!negation` for any intended file and re-stage; delete genuine scratch.
   Only if you are sure nothing reads the file at run time, re-run with
   `--advisory`.

   **Worktree-leak guard** (issue #486). Invoke bare with
   `--strict`, and handle the `FLOW_WORKTREE_GUARD:` verdict exactly as in
   Step 4 (issue #1014): exit 3 stops - do not commit, and first read
   `git -C <main> diff -- <path>` to confirm the edit is YOURS before moving or
   reverting anything, then re-run the guard AND re-run the quality gates
   above; 4 and 5 proceed and are reported, never as "no leak":
   ```bash
   ~/.claude/scripts/flow-worktree-guard.sh --strict
   ```
   On exit 127 fall back to
   `${CLAUDE_PLUGIN_ROOT}/scripts/flow-worktree-guard.sh --strict` (#590), else
   the CPP-checkout copy; if no copy exists, note it and continue.

3. **Commit** - if there are uncommitted changes:
   - Conventional commit format, using the selected reference:
     `type(scope): Description (${ISSUE_REF})`
   - A `Co-Authored-By: <name> <noreply@anthropic.com>` trailer naming the
     current session's own assistant model - never a literal copied from this
     document (issue #1037)
   - **An already-clean tree here is a LEGITIMATE state, not a failure** (issue
     #635): the work is already in the `wip(flow): pre-merge snapshot` commit.
     Skip this step and leave the WIP commit as-is. Do NOT add a STOP for this
     state.

4. **Push** the branch:
   ```bash
   git push -u origin "$BRANCH"
   ```

5. **Create PR** - if no PR exists:
   ```bash
   gh pr create --title "type(scope): Description (${ISSUE_REF})" --body "..."
   ```
   - If PR already exists, report its URL and continue.
   - PR body: Summary of changes + test plan + `${ISSUE_REF}`
   - Analyze all commits on the branch to draft the summary.

6. **Check whether the issue moved under this run** (issue #1081):
   ```bash
   ~/.claude/scripts/flow-plan-record.py drift 42
   ```
   - `ISSUE_DRIFT: clean` (exit 0) - body digest unchanged since Step 1.
   - `ISSUE_DRIFT: drift` (exit 3) - the body changed; it prints the
     diff. Resolve it under the EXISTING authority model - newer bytes do not by
     themselves override a constraint or a plan already accepted on the issue -
     and say in the PR how.
   - `ISSUE_DRIFT: unresolved` (exit 4) - NOT clean: report it unchecked.

7. **Compare the diff against the approved plan** (issue #1082). It REPORTS; it
   never blocks:
   ```bash
   ~/.claude/scripts/flow-plan-record.py compliance 42
   ```
   Base: `git merge-base HEAD origin/main` unless `--base <ref>`.
   - `PLAN_COMPLIANCE: agreement` (exit 0) - the FILE SET matches Section C
     (file names only).
   - `PLAN_COMPLIANCE: divergence` (exit 3) - names each `TOUCHED BUT NOT
     PLANNED`, `PLANNED BUT NOT TOUCHED` and underivable mirror. Write the
     reason in the PR; never edit the plan to make it agree.
   - `PLAN_COMPLIANCE: unknown` (exit 4) - never report it as agreement.
   - A `, LANES NOT ...` clause: follow its stderr note, commit, re-run.
   - `PLAN_RECORD_STABILITY: THE PLAN RECORD CHANGED` (exit 3) - the approved
     plan moved after Step 4; read the record's own diff first. `unknown`: no
     baseline stamped.

8. **Confirm the plan record reached the PR** (issue #1080). Skip this only when
   the run wrote no record:
   ```bash
   ~/.claude/scripts/flow-plan-record.py head-check 42
   ```
   - `FLOW_PLAN_RECORD: present` (exit 0) - proceed.
   - `FLOW_PLAN_RECORD: absent` (exit 1) - **STOP.** Recover by
     `git add docs/flow-runs/issue-<N>.md`, commit, push, and re-run this check.
   - `FLOW_PLAN_RECORD: unverified` (exit 4) - **STOP.** The PR head could not
     be read; check `gh auth status` and the network, then re-run.

Report: `Step 6/9: Finish complete - PR #XX created`

---

### Step 6b: Route Supplemental Findings to the Nit Store

A supplemental finding is anything true and worth fixing that you discovered
while doing something else, including a deferred counter-model finding from
item 1c (issue #1030). Do not widen this change to fix it, and do not drop it.
Record it.

Resolve the repository's nit store with the shared resolver, bare:

```bash
~/.claude/scripts/nit-store-resolve.sh
```

It answers a number only after GitHub confirms that issue is OPEN and titled
exactly "Nit Store" (#1272, #1273). Act on `NIT_STORE_STATUS`:

- `ok` - post to the number it printed as `NIT_STORE=`, IN the repository it
  printed as `NIT_STORE_REPO=`:
  `gh issue comment <NIT_STORE> --repo <NIT_STORE_REPO> --body "<one finding>"`.
  The `--repo` is not optional. When `NIT_STORE_SOURCE=search` (an unmapped
  repository, resolved by exact title), say so in the closing report.
- `none` (exit 1) - there is no open Nit Store. If the repository has no nit store, file the finding as a normal issue instead.
- `unknown` (exit 3) - GitHub could not be asked, or the answer was ambiguous.
  Post nowhere. Say in the closing report that the finding is unrouted and
  carry it there verbatim, because `unknown` is not `none`.

On exit 127 fall back to `scripts/nit-store-resolve.sh` in the CPP checkout, and
tell the user to run **`/flow:repair`**.

- **One finding per comment.** State the file and line (or the command), what is
  wrong, why it matters, and which issue or PR you were working. The comment is
  the whole record; it is read later without your context.
- **It is not a place to hide a defect that warrants its own ticket now.** A live
  correctness, security, or data-loss problem gets its own issue, and the
  closing report says so.
- **The store is an inbox, not a backlog.** A comment is a disposition, not a fix.
- **Name what you stored, with the comment link, in the closing report.**

Having nothing to store is an ordinary outcome. Do not manufacture a finding.

---

### Step 7: Merge - Squash-Merge and Clean Up

1. **Sync with `origin/main` and re-gate (stale-branch guard, issue #462):**
   Bring the branch current and re-run the gate on the **post-merge tree**
   first, so the gate reflects exactly what lands on `main`. The Codex re-sync
   is called UNCONDITIONALLY here too (never re-gated on a path pattern,
   #1136). It refreshes ignored build output the re-gate reads; there is
   nothing to commit (#1670):

   ```bash
   BRANCH=$(git branch --show-current)
   git fetch origin main
   if [[ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]]; then
       echo "Branch is behind origin/main - merging main in before the squash."
       if ! git merge --no-edit origin/main; then
           echo "STOP: merging origin/main hit conflicts:"
           git diff --name-only --diff-filter=U
           echo "Resolve them, 'git add' + 'git commit', then re-run /flow:merge."
           echo "(Do NOT 'git merge --abort' - that discards the resolution.)"
           exit 1
       fi
   fi
   if [ -x scripts/codex-skill-resync.sh ]; then
       bash scripts/codex-skill-resync.sh
   fi
   ```

   **If the merge changed the branch**, re-run the FULL
   quality gate - the same Step-6 helper, invoked BARE as a separate call (#613;
   the #581 discipline - never fold it back into a compound block). Test for a
   changed branch, not for a merge:

   ```bash
   git rev-parse HEAD                     # compare against the SHA before this step
   ```

   ```bash
   ~/.claude/scripts/flow-finish-gate.sh
   ```

   On `FLOW_FINISH_GATE: fail` (exit 1): **STOP** - the quality gate failed on
   the post-merge tree. Fix, commit, then re-run `/flow:merge`. With no
   `FLOW_FINISH_GATE:` verdict line, the gate did not run: **STOP** as at Step 6,
   whatever the exit code (issue #1547). On `ok` (or
   `skipped` / `warn`, each with a warning - `warn` means a test step exited 0
   having executed no tests, issue #621: report its counts, do not call it
   "tests passed"), push the merge so the PR reflects the post-merge
   tree before squashing:

   ```bash
   git push origin "$BRANCH"
   ```

2. **Merge the PR.** Look up the PR number first:

   ```bash
   gh pr list --head "$BRANCH" --json number --jq '.[0].number'
   ```

   **When CI outlasts main's quiet window (issue #1300)**, wait for green on
   the REQUIRED lane first, then merge in the same breath:

   ```bash
   ~/.claude/scripts/flow-ci-status.sh <pr-head-sha> --path /path/to/worktree --strict-event --wait 1800
   ```

   (`--strict-event` makes the required lane, named by `FLOW_CI_EVENT`, a
   FILTER: an absent required-lane pipeline stays `not-found` and the wait
   continues.) On `stalled` (issue #1552) the pipeline is dead, not slow: do
   not merge and do not keep waiting - report the URL and stalled steps and
   stop for the user, who must cancel the Actions run (`gh run cancel <id>`)
   or have the Woodpecker operator stop its pipeline, then re-run CI. On
   `success`, invoke the merge helper at once, PINNED to the sha that wait was
   keyed on (issue #1543): pass `--match-head-commit <pr-head-sha>` to the
   helper, never to a plain `gh pr merge`. Alternatively pass
   `--wait-ci[=SECS]` to the helper to make its own required-check wait a
   deadline. Updating the branch when the base moved is the CALLER's decision.

   Merge via the layout-aware helper, invoked BARE with the literal PR number
   and branch (#581 discipline). Never use plain `gh pr merge --delete-branch`
   from a linked worktree (issue #461):

   ```bash
   ~/.claude/scripts/gh-pr-merge.sh 78 issue-42-fix-login
   ```

   On exit 127, resolve the plugin copy, then the CPP-checkout copy. If none
   exists, **REFUSE**. There is no raw-merge fallback (issue #1543): a plain
   `gh pr merge --squash` skips every guard the helper runs.
   <!-- merge-helper-resolution -->
   ```bash
   PR_NUMBER=<literal>
   BRANCH=<literal>
   PIN_SHA=<pr-head-sha>   # the SAME literal the flow-ci-status.sh wait above was given; PIN_SHA= only for an unpinned merge
   GH_PR_MERGE=~/.claude/scripts/gh-pr-merge.sh
   [ -x "$GH_PR_MERGE" ] || GH_PR_MERGE="${CLAUDE_PLUGIN_ROOT:-/nonexistent}/scripts/gh-pr-merge.sh"
   if [ ! -x "$GH_PR_MERGE" ]; then
       for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
           if [ -x "$dir/scripts/gh-pr-merge.sh" ] && [ -f "$dir/CLAUDE.md" ]; then
               GH_PR_MERGE="$dir/scripts/gh-pr-merge.sh"
               break
           fi
       done
   fi
   if [ -x "$GH_PR_MERGE" ]; then
       "$GH_PR_MERGE" ${PIN_SHA:+--match-head-commit "$PIN_SHA"} "$PR_NUMBER" "$BRANCH"
       MERGE_RC=$?
   else
       echo "REFUSING: gh-pr-merge.sh is not installed; not merging PR #$PR_NUMBER with a plain 'gh pr merge'." >&2
       echo "  A raw merge skips every guard the helper runs, including the close-keyword guards (issue #1543)." >&2
       echo "  Install the helper with /flow:repair, then resume Step 7." >&2
       MERGE_RC=12
   fi
   ```
   Every CLEAN STOP below leaves the PR open and untouched. None is retried
   blindly or escalated to `--admin` by the run.

   - **`MERGE_RC` 12 is the MISSING-HELPER REFUSAL (issue #1543), and the
     helper never emits it.** Nothing was merged. **STOP** and report that
     `/flow:repair` must run. Never finish the merge by hand with `gh pr merge`.
   - **Helper exit 11 is also a CLEAN STOP (issue #1543):** the PR's head is no
     longer the pinned sha (`GH_PR_MERGE_HEAD_PIN:` names both). It is **never
     retried and never escalated to `--admin`**. Re-verify the current head
     (CI, review) and re-run with its sha.
   - **Helper exit 3 is a FIRST-CLASS CLEAN STOP, not a failure (issue #579):**
     the PR awaits a required human review (`REVIEW_REQUIRED` or
     `CHANGES_REQUESTED`). Report the helper's handoff message and leave the
     worktree, branch, and PR INTACT - do NOT run cleanup, do NOT retry, and
     NEVER re-invoke with `--admin` yourself. End the run here.
   - **Helper exit 4 is also a CLEAN STOP (issue #657):** the operator set
     `GH_PR_MERGE_STRICT_DELETIONS=1` and the PR deletes files. Review the
     `GH_PR_MERGE_DELETIONS:` paths; if intended, re-run without strict mode.
     Flow itself never sets this variable.
   - **Helper exit 5 is also a CLEAN STOP (issue #726):** the squash title,
     body, or a commit subject has a NEGATED close keyword ("does not close
     #N") that GitHub would still honor. Report the printed context, reword it and
     re-run
     (`--allow-negated-close` only after the user consciously confirms).
   - **Helper exit 6 is also a CLEAN STOP, not a failure (issue #767):** the
     base advanced during the check wait. Re-run Step 7 from sub-step 1: sync,
     re-gate, push, merge again.
   - **Helper exit 6 can also come from the final base re-read (issue #1300):**
     `GH_PR_MERGE_BASE_AT_SQUASH: <sha>`. Same remedy.
   - **Helper exit 7 is also a CLEAN STOP (issue #794):** as 5, but the keyword
     is merely adjacent to `#N`. Report the printed context, reword and re-run
     (`--allow-incidental-close`
     only after the user consciously confirms).
   - **Helper exit 8 means the incidental-close guard's own self-check failed
     (issue #794):** a BROKEN CHECK, not a clean scan. Report it; there is no
     override.
   - **Helper exit 9 is also a CLEAN STOP (issue #1262):** a worktree on this
     host holds the PR's branch at a commit that is NOT the PR's head. Report
     the printed path and sha; push or discard that work, then re-run.
     `--allow-local-divergence` is the user's call.
   - **Helper exit 10 is also a CLEAN STOP (issue #1300):** the required-check
     wait ran out (`GH_PR_MERGE_CI_WAIT:` reports why). It is NOT a red check:
     do not re-sync or re-gate. Wait for green and re-run the merge.
   - **`GH_PR_MERGE_ALREADY_MERGED: <n>` with exit 0 is SUCCESS (issue
     #1262):** proceed to cleanup. Never re-gate on a `GH_PR_MERGE_BASE_STALE`
     without first checking this.
   - Markers printed per run (issues #657/#767):
     `GH_PR_MERGE_BASE_MOVED: <old-sha> -> <new-sha>|0|skipped`;
     `GH_PR_MERGE_DELETIONS: <n> <paths...>|0|skipped` - read it: deletions the
     issue scope does not explain are a collapse onto a moved base; and
     `GH_PR_MERGE_COMPLETENESS: ok|violation|skipped` - REPORT a `violation`.
   - If the merge genuinely failed (conflicts, failing checks, PR not
     `MERGED`): **STOP**. A non-zero `gh` exit whose PR is nonetheless `MERGED`
     is NOT a failure - the helper treats it as success.

3. **Capture the worktree and main repo paths (before leaving the worktree):**
   ```bash
   if [[ -f ".git" ]]; then
       WORKTREE_PATH=$(pwd)
       MAIN_REPO=$(cat .git | sed 's/gitdir: //' | sed 's|/.git/worktrees/.*||')
   else
       WORKTREE_PATH=""   # not in a worktree - on a feature branch in the main repo
       MAIN_REPO=$(pwd)
   fi
   ```

4. **Clean up worktree and branch:**

   **Release this run's claim FIRST (issue #597)** - git refuses to remove a
   locked worktree. Bare (#581 discipline; fail-open):

   ```bash
   ~/.claude/scripts/flow-worktree-claim.sh release /path/to/worktree
   ```

   A sibling's live claim is left intact and reported: you are about to remove
   the wrong checkout.

   Cleanup is ALWAYS the git fallback (issue #627); on `LANE=current-branch`
   there is no worktree, so just delete the branch. **CRITICAL: `cd` to the main
   repo BEFORE removing the worktree - never remove a worktree while your cwd is
   inside it. Execute as SEPARATE Bash calls.**

   **Step 7a - Return to the main repo (separate Bash call):**
   ```bash
   cd "$MAIN_REPO"
   pwd  # Verify you are in the main repo, NOT the worktree
   ```

   **Step 7b - Remove the worktree (separate Bash call, AFTER confirming cd
   succeeded).** Invoke the removal helper BARE with the literal path (#581
   discipline):
   ```bash
   ~/.claude/scripts/worktree-remove.sh /path/to/worktree --force --delete-branch
   ```
   Every refusal below is CORRECT, not a flow failure. Report it and stop;
   never retry with an override reflexively, and never with `--steal` - that
   is the user's call. `--force` overrides none of them.

   | exit | meaning | override |
   |---|---|---|
   | 4 | claimed by another LIVE session (#597); the owner is printed | `--steal` |
   | 5 | a live process's cwd is inside AND the tree is dirty | `--steal` |
   | 6 | uncommitted work would be destroyed | `--allow-dirty` |
   | 7 | commits here are on no remote ref | `--allow-unpushed` |
   | 8 | `--delete-branch` asked, but directory name and checked-out branch name different issues | `--steal` |

   - The helper **exits 4** for a sibling's claim; this session's own claim,
     or a dead one, is released automatically.
   - **Exit 5 is the same kind of clean STOP (issue #888):** report the printed
     PIDs and dirty paths. `WORKTREE_REMOVE_OCCUPANCY: unknown` means
     unchecked, not clean.
   - Exits 6 and 7 (issue #899) mean something earlier did not finish - find
     that. On 7, push the branch and re-run.
   - **`worktree-remove.sh` exit 8 is a CLEAN STOP too (issue #1032).** It is
     not `gh-pr-merge.sh`'s 8. Report the `WORKTREE_REMOVE_ATTRIBUTION:` line.
     Re-run without `--delete-branch` to remove just the directory, or rename
     the worktree first.

   If the helper is not installed, REFUSE rather than removing by hand
   (issue #973). Derive the paths in THIS call (`WORKTREE_PATH` must be set in
   it too) and record the refusal in a per-worktree marker FILE:

```bash
MAIN_REPO="$(git rev-parse --show-toplevel)"   # Step 5a already cd'd here

CLEANUP_REFUSED_DIR="$MAIN_REPO/.git/flow-cleanup-refused.d"
CLEANUP_REFUSED_MARKER="$CLEANUP_REFUSED_DIR/$(basename "$WORKTREE_PATH")"
mkdir -p "$CLEANUP_REFUSED_DIR"
rm -f "$CLEANUP_REFUSED_MARKER"   # only THIS worktree's entry; a sibling's survives
cleanup_refused=0
if [[ -x ~/.claude/scripts/worktree-remove.sh ]]; then
    ~/.claude/scripts/worktree-remove.sh "$WORKTREE_PATH" --force --delete-branch
else
    {
        echo "REFUSING: worktree-remove.sh is missing; not removing $WORKTREE_PATH by hand." >&2
        echo "  Every guard this lane relies on lives in that helper (issue #899)." >&2
        echo "  Install it with /flow:repair, then re-run this step." >&2
        false
    } || cleanup_refused=1
[[ "$cleanup_refused" -eq 1 ]] && printf '%s\n' "$WORKTREE_PATH" > "$CLEANUP_REFUSED_MARKER"
fi
```

**The refusal is an OWNER ITEM, not a log line (issues #965, #973).** The
closing-report step reads the marker DIRECTORY, in its own Bash call:

```bash
MAIN_REPO="$(git rev-parse --show-toplevel)"
for m in "$MAIN_REPO"/.git/flow-cleanup-refused.d/*; do
    [[ -e "$m" ]] || continue          # glob with no matches: nothing refused
    echo "TO-DO: worktree $(cat "$m") was NOT removed (worktree-remove.sh missing)"
    rm -f "$m"                          # consumed - do not re-report next run
done
```

The run CONTINUES. The closing report's `## TO-DO (owner)` block carries,
verbatim:

> Worktree `$WORKTREE_PATH` was NOT removed - `worktree-remove.sh` is missing,
> so every guard this lane relies on was unavailable. Install it with
> `/flow:repair` and re-run this step, or remove the worktree yourself after
> checking it holds no unpushed work.

With no worktree (a feature branch in the main repo), just delete the branch:
`git branch -D <branch>`.

5. **Update local main:**
   ```bash
   git -C "$MAIN_REPO" checkout main 2>/dev/null || true
   git -C "$MAIN_REPO" pull origin main
   ```

   **Verify working directory is valid:**
   ```bash
   pwd  # MUST show main repo path, NOT the deleted worktree
   git status  # MUST succeed - if this fails, your CWD was deleted
   ```

6. **Close issue** (if still open). Restate here the `ACCEPTANCE_COMPLETE`
   judgement you reached in Step 6 for THIS issue; never inherit a value and
   never parse it out of the report. Unset cannot close:
   ```bash
   ACCEPTANCE_COMPLETE=""

   if [[ -n "$ISSUE_NUM" ]]; then
       ISSUE_STATE=$(gh issue view "$ISSUE_NUM" --json state --jq '.state' 2>/dev/null)
       if [[ "$ACCEPTANCE_COMPLETE" == "yes" ]]; then
           if [[ "$ISSUE_STATE" == "OPEN" ]]; then
               gh issue close "$ISSUE_NUM" --comment "Closed via /flow:auto - PR #${PR_NUMBER} merged."
           fi
       else
           echo "Acceptance not recorded complete - leaving #${ISSUE_NUM} open."
       fi
   fi
   ```

Report: `Step 7/9: Merge complete - worktree cleaned up`

---

### Step 8: Verify CI (after merge)

ONE audited helper owns this (issue #766). Invoke `scripts/flow-ci-status.sh`
BARE with the literal SHA and checkout path (#581; the checkout is DECLARED,
the #614 rule):

```bash
~/.claude/scripts/flow-ci-status.sh <merge-sha> --path /path/to/main/repo --wait
```

Do NOT hand-roll this with `curl`, `gh run list`, or a grep over
`woodpecker-cli pipeline ls`. The helper matches on the commit and dispatches
only the project's recorded provider lanes: any failure is red, any running
lane keeps the result running, and success requires every selected lane green.
Probing is available only via the explicit `--fallback-provider-probes` flag
and reports `FLOW_CI_SELECTION: fallback`.

The helper prints a machine-readable contract, the failed-step lines (when any)
immediately before the verdict:

```
FLOW_CI_PROVIDER: <selected name[,name...] or none>
FLOW_CI_SELECTION: recorded | unknown | fallback (...)
FLOW_CI_LANES: <per-provider JSON evidence for recorded dispatch>
FLOW_CI_REF: <sha>
FLOW_CI_REPO: <owner/name|->
FLOW_CI_EVENT: <event> (flag | branch-protection on <branch>: <contexts> | default: <why>)
FLOW_CI_PIPELINE: <number|->
FLOW_CI_URL: <url|->
FLOW_CI_WAIT: none | settled | expired (<N>s)
FLOW_CI_RUNS: <n> (<id>:<workflow>:<event>:<result>, ...)   (GitHub Actions lane: every run aggregated, issue #1604)
FLOW_CI_FAILED_STEP: <name>        (repeated, only on failure; `workflow / job / step` on GitHub Actions)
FLOW_CI_PRECODE_FAILURE: <name>    (repeated, only on failure; a failed `clone`-type step, a `*-stage` step exiting 75 (#1411, fetch failed), or an image-pull failure (#1508))
FLOW_CI_FAILURE_ORIGIN: precode | code | canceled | mixed | unknown   (only on failure)
FLOW_CI_STALL_CHECK: checked | unavailable (<why>)   (Woodpecker HTTP and GitHub Actions lanes, issues #1552, #1604)
FLOW_CI_STALLED: past-timeout (...) | terminal-pipeline-live-children
FLOW_CI_STALLED_STEP: <name>       (repeated, a step the server still lists running)
FLOW_CI_STATUS: success | failure | running | pending | stalled | not-found | unknown
```

Act on `FLOW_CI_STATUS`:

- `success` -> proceed to Step 9.
- `failure` -> **STOP**. Do not deploy. Report `FLOW_CI_URL` and every
  `FLOW_CI_FAILED_STEP` line. Read `FLOW_CI_FAILURE_ORIGIN` first (issue
  #1342): `precode` (the `clone`, a `*-stage` stager exiting 75, or an image pull)
  failed before the change's code ran - retry or look at the infrastructure.
  `unknown` is NOT `code`: read the step log.
- `stalled` -> **STOP**. Do not deploy, wait or re-run: the agent lost the
  pipeline (issue #1552). Report `FLOW_CI_URL`, the `FLOW_CI_STALLED` reason
  and every `FLOW_CI_STALLED_STEP`. For Actions, offer `gh run cancel <id>`
  then a re-run; for Woodpecker, stop for its server operator. The helper
  never cancels.
- `failure` WITH a `FLOW_CI_STALLED: terminal-pipeline-live-children` line ->
  handle as `failure`, and report that steps are still listed running.
- `running` / `pending` -> the wait window expired. Report it and let the user
  decide whether to wait; do not deploy on an unknown result. `FLOW_CI_STALL_CHECK: unavailable (...)` means
  staleness was NOT checked; say so.
- `not-found` -> no pipeline carries this SHA. Warn and proceed. **Read
  `FLOW_CI_WAIT` first (issue #1262):** with `FLOW_CI_WAIT: expired (<N>s)`, say
  that no matching pipeline was found AT EXPIRY of that window - not "CI may
  not be wired", and not that one never registered.
- `unknown` -> stop CI-dependent deployment or merge work. Report the named
  evidence gap; an unexamined lane is not green, and a fallback probe's result
  never establishes recorded-provider completeness.

`--wait` defaults to 600s, polling every 15s; omit for one read. Without `--event`, required contexts of the default branch select
the event (`FLOW_CI_EVENT` names the source). Pass `--event` for a
differently protected base. With `--exit-code`, failure/stalled exits 1.
Unknown/not-found exits 2; valid-ref wait expiry takes precedence as 5.
Invalid refs exit 2 before requests.

On exit 127 fall back to `${CLAUDE_PLUGIN_ROOT}/scripts/flow-ci-status.sh`
(#590), else the CPP-checkout copy; tell the user to run **`/flow:repair`**. If
no copy exists, skip CI verification with a warning rather than improvising a
lookup, and say plainly in the final summary that CI was NOT verified.

Report: `Step 8/9: Verify CI complete - pipeline #{N} passed` or
`Step 8/9: Verify CI skipped ({not-found|unknown})`

### Step 9: Deploy (optional)

Only if a Makefile with a `deploy` target exists in the main repo. `/flow:auto`
runs `make deploy` inline. The block skips
when `.claude/deploy.yaml` declares `mode: external` (issue #535) or the sha is
already recorded as deployed (issue #597), pins `COMPOSE_PROJECT_NAME`, and
wraps the deploy in a verification baseline run through `uv` (issue #595):

```bash
cd "$MAIN_REPO"

CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done
VERIFY_ENABLED=0
if [ -n "$CPP_DIR" ] && grep -q "deploy_verification:" .claude/cicd.yml 2>/dev/null; then
    if command -v uv >/dev/null 2>&1; then
        VERIFY_ENABLED=1
    else
        echo "NOTE: deploy verification configured but 'uv' is not installed; skipping baseline + verdict." >&2
    fi
fi

DEPLOY_MODE=$(grep -oP '^\s*mode:\s*\K\S+' .claude/deploy.yaml 2>/dev/null | head -1)

HEAD_SHA=$(git rev-parse --short HEAD)
ALREADY_DEPLOYED=0
if [ -f .claude/deploy.log ] && awk -F'|' -v sha="$HEAD_SHA" '$2 ~ /^[[:space:]]*deploy[[:space:]]*$/ && $3 ~ ("^[[:space:]]*" sha "[[:space:]]*$") && $5 ~ /^[[:space:]]*0[[:space:]]*$/ { found = 1 } END { exit !found }' .claude/deploy.log; then
    ALREADY_DEPLOYED=1
fi

if [ "$ALREADY_DEPLOYED" -eq 1 ]; then
    echo "Deploy skipped: $HEAD_SHA is already recorded as successfully deployed in .claude/deploy.log"
    echo "(issue #597 - a concurrent session deployed this same commit; re-running would be a duplicate deploy)."
elif [ "$DEPLOY_MODE" = "external" ]; then
    echo "Deploy mode 'external' (.claude/deploy.yaml) - deploy runs out of band (host timer / CI on origin/main). Skipping inline 'make deploy'."
elif [[ -f "Makefile" ]] && grep -q "^deploy:" Makefile; then
    if [ -z "$COMPOSE_PROJECT_NAME" ]; then
        DEPLOY_PROJECT=$(grep -oP '^\s*compose_project_name:\s*\K\S+' .claude/deploy.yaml 2>/dev/null | head -1)
        if [ -z "$DEPLOY_PROJECT" ]; then
            GCD=$(git rev-parse --git-common-dir 2>/dev/null)
            if [ -n "$GCD" ]; then
                COMMON_GIT_DIR=$(cd "$GCD" 2>/dev/null && pwd)
                [ -n "$COMMON_GIT_DIR" ] && DEPLOY_PROJECT=$(basename "$(dirname "$COMMON_GIT_DIR")" | tr 'A-Z' 'a-z')
            fi
        fi
        if [ -n "$DEPLOY_PROJECT" ]; then
            export COMPOSE_PROJECT_NAME="$DEPLOY_PROJECT"
            echo "Pinned COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME (issue #535: canonical prod project, not the worktree basename)."
        fi
    fi

    if [ "$VERIFY_ENABLED" -eq 1 ]; then
        echo "Capturing pre-deploy baseline..."
        PYTHONPATH="$CPP_DIR:$PYTHONPATH" env -u UV_PROJECT_ENVIRONMENT "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT-}" "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT_PRESENT=${UV_PROJECT_ENVIRONMENT+x}" "CPP_RUNNER_TARGET_PATH=${PATH-}" "CPP_RUNNER_TARGET_PATH_PRESENT=${PATH+x}" uv run --python 3.11 --no-python-downloads --project "$CPP_DIR" python -m lib.cicd verify --baseline --summary
    fi

    echo "Running: make deploy"
    make deploy
    DEPLOY_EXIT=$?

    VERDICT="none"
    if [ "$VERIFY_ENABLED" -eq 1 ]; then
        echo "Running deploy verification..."
        PYTHONPATH="$CPP_DIR:$PYTHONPATH" env -u UV_PROJECT_ENVIRONMENT "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT-}" "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT_PRESENT=${UV_PROJECT_ENVIRONMENT+x}" "CPP_RUNNER_TARGET_PATH=${PATH-}" "CPP_RUNNER_TARGET_PATH_PRESENT=${PATH+x}" uv run --python 3.11 --no-python-downloads --project "$CPP_DIR" python -m lib.cicd verify
        VERIFY_EXIT=$?
        VERDICT=$( [ "$VERIFY_EXIT" -eq 1 ] && echo "rollback" || echo "proceed/review" )
        if [ "$VERIFY_EXIT" -eq 1 ]; then
            echo "DEPLOY VERIFICATION: ROLLBACK - a probe that passed pre-deploy fails now."
            echo "Recommend rolling back (redeploy previous commit) or investigating with /cicd:health + /cicd:smoke."
        fi
    fi

    mkdir -p .claude
    echo "$(date -Iseconds) | deploy | $(git rev-parse --short HEAD) | main | ${DEPLOY_EXIT} | verify:${VERDICT}" >> .claude/deploy.log
else
    echo "No deploy target in Makefile - skipping deployment."
fi
```

Verification is inert unless `health.deploy_verification.enabled` is set in
`.claude/cicd.yml`. A ROLLBACK verdict is surfaced, never acted on automatically.

Report: `Step 9/9: Deploy complete (verify: {proceed|review|rollback|none})` or
`Step 9/9: Deploy skipped (no Makefile target)` or
`Step 9/9: Deploy skipped ({sha} already deployed by a concurrent session)`

---

### Final Summary

<!-- closing-report-surface -->

**This report follows [the closing-report contract](../../../docs/agents/closing-report-contract.md).**
Three sections, in this order, and the order is the content:

1. `## TO-DO (owner)` - FIRST and always present. Numbered; each item names the
   DECISION, not its background. When there is nothing, say `Nothing blocking.`
   explicitly - an omitted block reads as forgotten, not as none. An FYI is not
   a TO-DO. The qualifying test and the deliberate exclusions live in the
   contract; do not restate them here.
2. `## In plain language` - what was wrong, why it mattered, what is better now,
   under `/flow:eli5` Section A's EXISTING depth floor. One plain-language
   standard in this repo, applied at the other end of the run.
3. `## Evidence` - the status lines below, plus red-case results, gate output,
   review dispositions and CI. Demoted, never deleted.


```
Flow Auto Complete

  Issue:    #42 - Fix login bug
  ELI5:     Still needed (plan approved)
  Changes:  Modified 3 files (src/auth/login.py, tests/test_auth.py, config/routes.py)
  PR:       #78 (squash-merged)
  Branch:   issue-42-fix-login (deleted)
  Worktree: .claude/worktrees/issue-42-fix-login (removed)
  CI:       Woodpecker pipeline #5 passed | GitHub Actions run #123 passed | skipped
  Deploy:   make deploy (success) | skipped
  Verify:   PROCEED | REVIEW | ROLLBACK | not configured
  Friction: 4 signals captured (.claude/friction.jsonl)
  Location: /home/user/Projects/my-project (main)
```

---

### Post-run: Friction Retro (optional, non-blocking)

After the summary, if `.claude/friction.jsonl` recorded any signals this run,
offer the codify step - do not block or auto-run it:

```
Friction retro: this run recorded N friction signal(s). Run /self-improvement:retro
to turn them into confirmed fixes (permission allowlist, Make targets, hooks,
CLAUDE.md, portable learnings)? [y/N]
```

---

## Error Handling

At each step, if something fails:

```
Flow Auto stopped at Step N/9: {Step Name}

  Failed: [description of what failed]
  Fix:    [actionable suggestion]

  To resume manually:
    /flow:start N    (if step 1 failed)
    [investigate]    (if step 2 failed)
    /flow:eli5 N     (if step 3 failed)
    [implement]      (if step 4 failed)
    /documentation:c4 (if step 5 failed)
    /flow:finish     (if step 6 failed)
    /flow:merge      (if step 7 failed)
    [check CI dashboard] (if step 8 failed)
    /flow:deploy     (if step 9 failed)
```

Failure rules no step states: analysis unclear - stop at step 2 and ask the
user; plan rejected at the ELI5 gate - stop at step 3 and revise the plan (or
close) before proceeding; push fails - stop at step 6 and suggest `git pull --rebase`; deploy fails -
report it, do not roll back.

## Notes

### Codex fresh-flow attribution (#1557)

If an original Codex thread has earlier unrelated model contexts, whole-thread
attribution truthfully records all complete observed implementers in schema 4.
The receipt writer may instead use
`--implementer-thread-id THREAD --implementer-flow-run RUN` only when the
original full rollout proves fresh creation, ordered mint/begin/approval, Git plan
bindings and one model from the originating creation turn through snapshot EOF.
Use the original review exec stream and actual review counts. The writer records
schema 3 model-scope evidence, `approval_execution: "unverified"`, and
measured-clean/unmeasured initial cleanliness; observed dirt
refuses. Unsupported fresh-flow history falls back only to truthful whole-thread
attribution; incomplete identity evidence remains a refusal. Never filter a rollout,
choose a manual model window, invent a skip or bypass enrollment. `audit-flow RECEIPT` can
re-derive the captured original prefix. See ADR 0007 for exact supported commands
and the limit: byte hashes and visible model scope do not prove all authorship.
