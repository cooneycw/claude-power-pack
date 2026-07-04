# Flow: Auto - Full Issue Lifecycle in One Shot

Complete end-to-end workflow: start worktree → analyze issue → ELI5 plan + necessity gate → implement → finish (PR) → merge → deploy.

## Arguments

- `ISSUE` (required): GitHub issue number (e.g., `42`)

## Instructions

When the user invokes `/flow:auto <ISSUE>`, perform these steps sequentially. Stop immediately if any step fails.

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

Throughout this run, record friction the moment it happens - do NOT wait for the
end. The richest friction is on runs that fail partway, so capture must fire on
every step, success OR failure, and before any STOP. Whenever you hit one of these,
append a record via the fail-open capture helper (it never blocks the flow):

- a **quality-gate failure or retry** (lint/test/build/deploy)
- **red output** you narrated past or worked around instead of resolving
- a **manual intervention / correction** the user had to make

```bash
scripts/friction-log.sh --class <gate-failure|red-output|manual-intervention> \
  --signal "<what happened>" --fix "<proposed fix, if obvious>" \
  --scope <local|portable> --run "flow:auto #$ISSUE_NUM" --step "<N/9 Name>" --outcome "<retried|worked-around|corrected>"
```

The fourth class, **permission-prompt**, is NOT model-captured here: the model
cannot tell an approved tool call from an auto-allowed one. It is captured by the
harness `PermissionRequest` hook (`scripts/hook-permission-census.sh`, registered
in `~/.claude/settings.json` by `/cpp:init` / `/cpp:update`), which records a
risk-rated record with a derived allow-rule candidate on every prompt shown -
across every session, not just flow runs (issue #482). Do not log this class by
hand.

Records go to the main repo's `.claude/friction.jsonl` (a queue drained by
`/self-improvement:retro`). The helper resolves that durable buffer automatically
via `git-common-dir`, so signals captured inside this run's worktree survive its
removal at Step 7 (issue #471) - no env var or per-call path needed.
This is capture only - proposing and applying fixes happens in the retro, not here.

---

### Step 1: Start - Create Worktree

**CRITICAL: You MUST create or enter a worktree before proceeding. NEVER implement changes directly on main/master. This step is NOT optional - if worktree creation fails, STOP immediately.**

Worktree mechanics ride Claude Code's **native worktrees**: the `EnterWorktree`
tool creates a checkout under `.claude/worktrees/<name>` on a new branch and
switches the session into it. CPP keeps and enforces the issue-anchored
`issue-<N>-<slug>` branch name (the gate policy the native tool does not absorb).

```bash
ISSUE_NUM="$1"

# Fetch issue details
gh issue view "$ISSUE_NUM" --json number,title,state,body
```

- If issue is not OPEN, warn the user and ask whether to proceed.
- Extract the title for branch naming.

```bash
# Sanitize title for branch name (cut keeps within EnterWorktree's 64-char limit)
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | cut -c1-50)
BRANCH="issue-${ISSUE_NUM}-${SLUG}"
```

**Check for existing work, then pick exactly one path:**

```bash
# Check if already on the issue's branch
CURRENT_BRANCH=$(git branch --show-current)

# Check if a worktree already exists for this issue
git worktree list | grep "issue-${ISSUE_NUM}"

# Check if a remote branch exists (cross-machine pickup)
git fetch origin
git branch -r | grep "issue-${ISSUE_NUM}-"
```

- **Already on issue branch** (`$CURRENT_BRANCH` matches `issue-${ISSUE_NUM}-`):
  verify you are NOT on main/master and use the current directory. This is a
  resumed run - remember it so Step 7 uses the git cleanup fallback, not
  `ExitWorktree`.
- **Worktree exists** (prior session): before entering, guard against a
  CONCURRENT live driver (issue #503). On a box running several Claude sessions,
  another session may be mid-implementation in this very worktree; entering it
  lets two drivers fight over one checkout, and THIS run's Step-7 cleanup can
  delete the other driver's cwd. Run BOTH resume checks first:
  ```bash
  WT_PATH="<path from git worktree list>"
  CPP_DIR=""
  for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
    [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ] && { CPP_DIR="$dir"; break; }
  done
  # 1. Fresh dirty-file mtimes => a live driver is SUSPECTED (advisory, fail-open).
  [ -x "$CPP_DIR/scripts/flow-live-driver-guard.sh" ] && \
    "$CPP_DIR/scripts/flow-live-driver-guard.sh" "$WT_PATH"
  # 2. An already-shipped branch is the other resume hazard (concurrent-sessions discipline).
  gh pr list --head "$BRANCH" --json number,state,url --jq '.[]'
  ```
  If the guard prints `FLOW_LIVE_DRIVER: suspected` (a dirty file touched within
  ~30m) OR `gh pr list --head` shows an open/merged PR, STOP and require EXPLICIT
  user confirmation that no other live session owns this worktree before calling
  `EnterWorktree(path="$WT_PATH")`. If both are clear, switch in with
  `EnterWorktree(path="<path from git worktree list>")`. Resumed run - Step 7 uses
  the git cleanup fallback.
- **Remote branch exists, no local worktree** (cross-machine pickup): the native
  tool cannot check out an existing remote branch, so add it with git, then switch
  in:
  ```bash
  REMOTE_BRANCH=$(git branch -r | grep "issue-${ISSUE_NUM}-" | head -1 | xargs)
  LOCAL_BRANCH="${REMOTE_BRANCH#origin/}"
  git worktree add -b "$LOCAL_BRANCH" ".claude/worktrees/${LOCAL_BRANCH}" "$REMOTE_BRANCH"
  ```
  then call `EnterWorktree(path=".claude/worktrees/${LOCAL_BRANCH}")`. Step 7 uses
  the git cleanup fallback (a `path`-entered worktree is not removed by
  `ExitWorktree`).
- **Neither exists** (fresh start): create and enter natively by calling the
  `EnterWorktree` tool with `name="${BRANCH}"`. This branches from
  `origin/<default-branch>` (default `worktree.baseRef: fresh`) and switches the
  session into `.claude/worktrees/${BRANCH}`. Do NOT shell out to `git worktree
  add` for the fresh path. This is a session-created worktree - Step 7 removes it
  with `ExitWorktree`.

#### Verification Gate (MANDATORY - do NOT skip)

Before proceeding to Step 2, verify you are in the worktree and enforce the
issue-anchored branch name (the moat every later step relies on):

```bash
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    echo "ERROR: Still on main/master after Step 1. EnterWorktree did not switch the session."
    echo "STOP: Cannot proceed. You MUST be on an issue branch, not main."
    exit 1
fi

# Native worktree creation derives the branch from the worktree name; normalize
# to the issue-anchored convention so downstream steps can parse the issue number.
if [[ "$CURRENT_BRANCH" != "$BRANCH" && ! "$CURRENT_BRANCH" =~ ^issue-${ISSUE_NUM}- ]]; then
    git branch -m "$BRANCH"
    CURRENT_BRANCH="$BRANCH"
fi
echo "Verified: on branch '$CURRENT_BRANCH' in $(pwd)"
```

**If this verification fails, STOP immediately. Report the failure using the error template at the bottom of this file. Do NOT proceed to Step 2.**

Report: `Step 1/9: Start complete - worktree at {path}, verified on branch {branch}`

---

### Step 2: Analyze - Understand the Issue

Working from the worktree, analyze the issue and codebase to form an implementation plan.

1. **Parse the issue body:**
   - Extract acceptance criteria (checkbox items `- [ ]`)
   - Identify referenced files, components, or areas
   - Note any dependencies or constraints mentioned

2. **Explore the codebase:**
   - Read files referenced in the issue
   - Understand existing patterns and conventions
   - Identify all files that need to be created or modified

3. **Form an implementation plan:**
   - List the specific changes needed
   - Note any edge cases or risks

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

Before writing any code, run the `/flow:eli5` review using the issue and the Step 2 analysis. This is the post-analysis, pre-implementation communication and approval gate.

**Load the FULL gate spec first (issue #509) - the bullets below are orientation,
not the spec.** Read it from whichever surface this installation has (first match
wins), then produce the report against THAT spec, including its report template
and depth floor:

1. the installed global skill: `~/.claude/skills/flow-eli5/SKILL.md`
2. the installed `flow` plugin's `eli5.md` command (`plugins/flow/commands/eli5.md` in a marketplace checkout)
3. inside the CPP repo itself: `.claude/commands/flow/eli5.md`

Do NOT produce the report from the summary below alone - outside the CPP repo the
repo-relative path does not exist, and the summary omits the template and floor.
The three sections, for orientation:

1. **ELI5 overview of intent** - what the issue is really trying to accomplish, in plain language a reviewer can sanity-check for a misread.
2. **Necessity / staleness analysis** - whether the issue is still worth doing given anything merged since it was filed. Anchor the check to the issue's creation date:
   ```bash
   ISSUE_DATE=$(gh issue view "$ISSUE_NUM" --json createdAt --jq '.createdAt')
   git log --since="$ISSUE_DATE" --oneline -- <relevant/paths>
   gh pr list --state merged --search "merged:>=${ISSUE_DATE%%T*}" --json number,title,mergedAt
   gh issue list --state all --search "<key terms>" --json number,title,state
   ```
   Output one verdict with evidence: **Still needed / Partially addressed / No longer needed / Needs reframing**. Depth floor: the evidence must enumerate the actual commit SHAs, merged PR numbers, and duplicate/superseding issue numbers inspected (or an explicit "none") - a bare verdict does not satisfy the gate.
3. **Proposed changes (pending approval)** - the files and edits that will close the issue, framed as a plan awaiting reviewer approval. Depth floor: one numbered line per file with its change gist - never "various files" - plus a scope estimate and at least one named risk (or an explicit "no notable risks").

**This is a gate:**

- **Verdict `No longer needed`** -> do NOT implement. Recommend closing the issue with an evidence-based comment and **STOP**:
  ```bash
  gh issue close "$ISSUE_NUM" --comment "Closed via /flow:auto ELI5 review - <reason; cite superseding PR/issue>."
  ```
  Run the close only with reviewer assent; surface the recommendation either way.
- **Verdict `Partially addressed` or `Needs reframing`** -> the plan to approve is the adjusted one (remaining work / corrected approach), not the original issue body.
- **Approval:** By default, **pause and wait for reviewer approval** of the plan before continuing to Step 4. For unattended runs, accept `--yes` (alias `--auto-approve`) on `/flow:auto`, or an `eli5: auto-approve` trailer in the issue body or HEAD commit message, to proceed without pausing. Auto-approve never overrides a `No longer needed` verdict.

Report: `Step 3/9: ELI5 complete - verdict: {Still needed|Partially addressed|No longer needed|Needs reframing}; approval: {granted|auto-granted|close recommended}`

---

### Step 4: Implement - Write the Code

**Early stale-base check (issue #473) - run BEFORE editing.** A sibling PR that
merges during implementation moves `origin/main` under you; discovering it only
at the Step-7 #462 guard means your edits were already made against stale copies
of the very files the sibling changed. Surface it now:

```bash
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ] && { CPP_DIR="$dir"; break; }
done
if [ -n "$CPP_DIR" ] && [ -x "$CPP_DIR/scripts/flow-stale-check.sh" ]; then
    "$CPP_DIR/scripts/flow-stale-check.sh" origin/main   # advisory: warns, never blocks
fi
```

- If it reports `FLOW_STALE_BASE: collision` - or names a file you are about to
  touch under "Changed upstream" - bring the base in now, before piling edits on
  a stale tree: `git merge --no-edit origin/main`, resolve any conflict in the
  named file(s), then implement. If the merge touched any
  `.claude/commands/**/*.md`, re-run the LOCAL `scripts/plugin-sync.sh --write`
  and `python3 scripts/codex-prompt-sync.py --write`, then stage `plugins/` and
  `codex/prompts/`, so the in-repo generated surfaces do not drift - the parity
  gates check all 15 families (issue #506; codex prompts #446/#511).
- If it reports `current` or `moved-clean` with no overlap, proceed - the Step-7
  #462 guard remains the final backstop.

**Worktree path-resolution rule (issue #486) - a native `EnterWorktree` session
edits the worktree, but the worktree lives *inside* the main repo at
`.claude/worktrees/<name>/`.** A `Write`/`Edit` given a hand-built ABSOLUTE
`.claude/worktrees/<name>/...` path has been observed to land in the MAIN repo
working tree instead of the worktree (flow:auto #442 x2, #471) - work looks done
but is written to the wrong tree. So, for every edit in this step:

- Resolve edit paths from the active worktree root - `git rev-parse
  --show-toplevel` - never a hand-built `.claude/worktrees/<name>/...` absolute
  path. A path under `$(git rev-parse --show-toplevel)/...`, or a plain relative
  path from the session cwd, targets the worktree correctly.
- After writing, confirm the change landed in the worktree (`git status` shows it)
  and did NOT leak into main. The guard makes the leak check verifiable:
  ```bash
  if [ -n "$CPP_DIR" ] && [ -x "$CPP_DIR/scripts/flow-worktree-guard.sh" ]; then
      "$CPP_DIR/scripts/flow-worktree-guard.sh"   # advisory: warns on a leak, never blocks
  fi
  ```
  If it warns that main has tracked modifications mirroring files you edited, the
  edit leaked: move the change into the worktree, then `git -C <main> checkout --
  <path>` to revert main before continuing.

Execute the approved plan from the Step 3 ELI5 gate:

1. **Make all code changes** in the worktree.
2. **Follow existing conventions** - match the code style, patterns, and structure of the project.
3. **Run tests locally** if a quick feedback loop is available (e.g., `make test` or the project's test command).
4. **Verify the changes** address all acceptance criteria from the issue.

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

Then perform these documentation tasks:

1. **Regenerate C4 diagrams** - If `docs/architecture/` exists or significant code changes were made, run the `/documentation:c4` workflow:
   - Analyze the project architecture
   - Generate L1-L4 C4 diagrams to `docs/architecture/`
   - Screenshot via Playwright if available

2. **Review CLAUDE.md** - Check that repository structure, command references, and component descriptions match the current state. Fix any stale references.

3. **Review README.md** - Check that the project description, setup instructions, and feature list reflect the changes just implemented. Fix any inaccuracies.

4. **Stage doc changes** - `git add` any modified documentation files.

If no `update_docs` target exists in the Makefile, skip this step.

Report: `Step 5/9: Update Docs complete - {N} files updated` or `Step 5/9: Update Docs skipped (no Makefile target)`

---

### Step 6: Finish - Quality Gates, Commit, Push, PR

```bash
BRANCH=$(git branch --show-current)
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")
```

**Stale-base pre-check (issue #473) - run BEFORE the quality gates and commit**,
so the commit lands on a current tree and the gate reflects what will merge (the
#462 Step-7 guard stays the final backstop):

```bash
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ] && { CPP_DIR="$dir"; break; }
done
if [ -n "$CPP_DIR" ] && [ -x "$CPP_DIR/scripts/flow-stale-check.sh" ]; then
    "$CPP_DIR/scripts/flow-stale-check.sh" origin/main
fi

# If the base moved, merge it in now so the gate + commit ride the current tree.
git fetch origin main --quiet
if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]; then
    if ! git merge --no-edit origin/main; then
        echo "STOP: resolve the listed conflicts, 'git add' + 'git commit', then re-run Step 6."
        git diff --name-only --diff-filter=U
        exit 1
    fi
    # Keep the in-repo generated surfaces from drifting when the merge pulled ANY
    # command-family source: the packaged plugin copies AND the Codex CLI prompts
    # are both regenerated from .claude/commands/ and share the exact sibling-merge
    # drift race the flow-* skill mirror had - the parity gates cover all 15
    # families, not just flow (issue #506; codex prompts landed in #446/#511). Use
    # the LOCAL scripts (they derive repo-root from their own path, so they re-sync
    # THIS worktree, not $CPP_DIR); [ -x ... ] keeps each CPP-only, a no-op
    # elsewhere. The Step-6 commit below stages the regenerated files.
    if [ -x scripts/plugin-sync.sh ] && git diff --name-only ORIG_HEAD..HEAD | grep -q '^\.claude/commands/.*\.md$'; then
        scripts/plugin-sync.sh --write || true
    fi
    if [ -x scripts/codex-prompt-sync.py ] && git diff --name-only ORIG_HEAD..HEAD | grep -q '^\.claude/commands/.*\.md$'; then
        python3 scripts/codex-prompt-sync.py --write || true
    fi
fi
```

1. **Quality gates** - use the deterministic runner as primary path:

   **Primary path:** Call the CI/CD runner for reproducible quality gates:
   ```bash
   CPP_DIR=""
   for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
     if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
       CPP_DIR="$dir"
       break
     fi
   done

   RUNNER_RAN=0
   if [ -n "$CPP_DIR" ] && command -v uv >/dev/null 2>&1; then
       # Invoke through uv so lib/cicd's deps (pydantic) resolve and the
       # interpreter is pinned >= 3.11. Bare `python3 -m lib.cicd` uses the
       # system interpreter (often 3.10, no venv) inside a fresh worktree and
       # dies on ModuleNotFoundError - silently degrading to the fallback in
       # exactly the environment /flow:auto always creates (issue #430).
       # PYTHONPATH must point at CPP_DIR (the PARENT of lib/) so `-m lib.cicd`
       # resolves for external projects too, not just when dogfooding CPP.
       PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" python -m lib.cicd run --plan finish
       RUNNER_EXIT=$?
       RUNNER_RAN=1
   fi

   if [ "$RUNNER_RAN" -eq 0 ]; then
       REASON=$([ -z "$CPP_DIR" ] && echo "CPP checkout not found" || echo "uv not installed")
       echo "NOTE: deterministic runner unavailable ($REASON); using Makefile fallback." >&2
   fi
   ```

   - If runner ran and **succeeds** (exit 0): quality gates passed, proceed to commit.
   - If runner ran and **fails**: parse JSON output, report the failed step, **STOP**.

   **Fallback** (only when the runner did not run, `RUNNER_RAN=0`): Run `make lint` and `make test` directly (these bootstrap the venv via `uv run`).
   - If either fails: **STOP**. Report the failure and exit.

   **Ignored-additions guard** (issue #430, Finding 1): before committing, warn
   if a blanket `.gitignore` rule silently swallowed a new file you meant to
   track (`git add` no-ops with no error):
   ```bash
   if [ -n "$CPP_DIR" ] && [ -x "$CPP_DIR/scripts/check-ignored-additions.sh" ]; then
       "$CPP_DIR/scripts/check-ignored-additions.sh"   # advisory: warns, never blocks
   fi
   ```
   If it warns, add a `!negation` to `.gitignore` for any intended file and re-stage.

   **Worktree-leak guard** (issue #486): in a native-worktree session, confirm no
   edit leaked into the MAIN repo working tree before committing (a stray dirty
   file on main is otherwise committed later by whoever works there next):
   ```bash
   if [ -n "$CPP_DIR" ] && [ -x "$CPP_DIR/scripts/flow-worktree-guard.sh" ]; then
       "$CPP_DIR/scripts/flow-worktree-guard.sh"   # advisory: warns on a leak, never blocks
   fi
   ```
   If it warns, an edit landed in main instead of the worktree: move it into the
   worktree and revert main (`git -C <main> checkout -- <path>`), then re-gate.

2. **Commit** - if there are uncommitted changes:
   - Use conventional commit format: `type(scope): Description (Closes #N)`
   - Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`

3. **Push** the branch:
   ```bash
   git push -u origin "$BRANCH"
   ```

4. **Create PR** - if no PR exists:
   ```bash
   gh pr create --title "type(scope): Description (Closes #ISSUE_NUM)" --body "..."
   ```
   - If PR already exists, report its URL and continue.
   - PR body: Summary of changes + test plan + `Closes #N`
   - Analyze all commits on the branch to draft the summary.

Report: `Step 6/9: Finish complete - PR #XX created`

---

### Step 7: Merge - Squash-Merge and Clean Up

1. **Sync with `origin/main` and re-gate (stale-branch guard, issue #462):**
   A branch cut earlier - common on resumed or cross-machine worktrees - can have
   fallen behind `main` while the PR was open. Squash-merging it then fails at the
   last step on a content conflict (the flow:auto #433 run hit a CLAUDE.md
   collision), forcing a manual `git merge origin/main` + resolve + re-gate
   mid-flow. Bring the branch current and re-run the gate on the **post-merge
   tree** first, so the squash is deterministic and the gate reflects exactly what
   lands on `main`:

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
       # Re-run the FULL quality gate on the MERGED tree (not the pre-merge branch)
       # - same deterministic runner as Step 6, with the same Makefile fallback.
       CPP_DIR=""
       for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
         [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ] && { CPP_DIR="$dir"; break; }
       done
       # If the merge pulled ANY command-family source, re-sync the in-repo
       # generated surfaces - the packaged plugin copies AND the Codex CLI prompts
       # (all families, not just flow - issue #506; codex prompts #446/#511) - then
       # COMMIT them: this branch is squashed straight after `git push` below with
       # no further commit step, so uncommitted plugins/ or codex/prompts/ would
       # leave the squash carrying stale copies and fail the parity gates on main -
       # the exact race this guards. LOCAL scripts re-sync THIS worktree; [ -x ... ]
       # keeps each CPP-only.
       if [ -x scripts/plugin-sync.sh ] && git diff --name-only ORIG_HEAD..HEAD | grep -q '^\.claude/commands/.*\.md$'; then
           scripts/plugin-sync.sh --write || true
       fi
       if [ -x scripts/codex-prompt-sync.py ] && git diff --name-only ORIG_HEAD..HEAD | grep -q '^\.claude/commands/.*\.md$'; then
           python3 scripts/codex-prompt-sync.py --write || true
       fi
       if ! git diff --quiet -- plugins/ codex/prompts/; then
           git add plugins/ codex/prompts/
           git commit -m "chore(generated): re-sync plugin + codex prompt copies after merging origin/main (#506)"
       fi
       if [ -n "$CPP_DIR" ] && command -v uv >/dev/null 2>&1; then
           PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" python -m lib.cicd run --plan finish
           REGATE_EXIT=$?
       else
           echo "NOTE: deterministic runner unavailable; re-gating via Makefile fallback." >&2
           make lint && make test
           REGATE_EXIT=$?
       fi
       if [ "$REGATE_EXIT" -ne 0 ]; then
           echo "STOP: quality gate failed on the post-merge tree. Fix, commit, then re-run /flow:merge."
           exit 1
       fi
       # Push the merge so the PR reflects the post-merge tree before squashing.
       git push origin "$BRANCH"
   fi
   ```

2. **Merge the PR:**
   ```bash
   PR_NUMBER=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number')

   # Merge robustly across worktree layouts. Run from inside a linked worktree,
   # `gh pr merge --delete-branch` fails AFTER the remote squash succeeds - gh
   # tries to switch this worktree off the merged branch onto the default branch,
   # which is checked out in the primary worktree ("fatal: 'main' is already
   # checked out"), and exits non-zero. The merge still landed; treating that exit
   # as a failure is a false STOP (issue #461). The helper drops --delete-branch in
   # a linked worktree, deletes the remote branch itself, and verifies the PR
   # reached MERGED before reporting failure. Local worktree/branch cleanup is left
   # to step 4 below, so the native ExitWorktree path is unaffected.
   if [[ -x ~/.claude/scripts/gh-pr-merge.sh ]]; then
       ~/.claude/scripts/gh-pr-merge.sh "$PR_NUMBER" "$BRANCH"
       MERGE_RC=$?
   else
       # Inline fallback (helper not installed): same linked-worktree guard.
       if [[ -f ".git" ]]; then
           gh pr merge "$PR_NUMBER" --squash
           git push origin --delete "$BRANCH" >/dev/null 2>&1 || true
       else
           gh pr merge "$PR_NUMBER" --squash --delete-branch
       fi
       # Trust PR state over the local exit code.
       [[ "$(gh pr view "$PR_NUMBER" --json state --jq '.state' 2>/dev/null)" == "MERGED" ]]
       MERGE_RC=$?
   fi
   ```
   - If the merge genuinely failed (`MERGE_RC` non-zero - conflicts, failing
     checks, PR not `MERGED`): **STOP**. Report and exit. A non-zero `gh` exit
     whose PR is nonetheless `MERGED` is NOT a failure - the helper already treats
     it as success and continues to cleanup.

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

   **If Step 1 created the worktree this session via `EnterWorktree(name=...)`**
   (the fresh-start path), remove it natively - a single tool call that deletes the
   worktree and its branch and restores the session to the main repo, with no
   manual `cd`-before-remove dance:

   `ExitWorktree(action="remove", discard_changes=true)`

   `discard_changes=true` is required because the squash-merge leaves the local
   branch with commits not on `main`; discarding the now-merged local branch is
   correct. After this the session cwd is back in the main repo.

   **Otherwise** (Step 1 resumed an existing worktree, entered via
   `EnterWorktree(path=...)`, or you are on a feature branch in the main repo)
   `ExitWorktree` will not remove it, so use the git fallback. **CRITICAL: `cd` to
   the main repo BEFORE removing the worktree - never remove a worktree while your
   cwd is inside it. Execute as SEPARATE Bash calls.**

   **Step 7a - Return to the main repo (separate Bash call):**
   ```bash
   cd "$MAIN_REPO"
   pwd  # Verify you are in the main repo, NOT the worktree
   ```

   **Step 7b - Remove the worktree (separate Bash call, AFTER confirming cd succeeded):**
   ```bash
   if [[ -n "$WORKTREE_PATH" && "$WORKTREE_PATH" != "$MAIN_REPO" ]]; then
       if [[ -f ~/.claude/scripts/worktree-remove.sh ]]; then
           ~/.claude/scripts/worktree-remove.sh "$WORKTREE_PATH" --force --delete-branch
       else
           git worktree remove "$WORKTREE_PATH" --force
           git branch -D "$BRANCH" 2>/dev/null || true
       fi
   else
       # On a feature branch in the main repo (no worktree) - just delete the branch
       git branch -D "$BRANCH" 2>/dev/null || true
   fi
   ```

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

6. **Close issue** (if still open):
   ```bash
   if [[ -n "$ISSUE_NUM" ]]; then
       ISSUE_STATE=$(gh issue view "$ISSUE_NUM" --json state --jq '.state' 2>/dev/null)
       if [[ "$ISSUE_STATE" == "OPEN" ]]; then
           gh issue close "$ISSUE_NUM" --comment "Closed via /flow:auto - PR #${PR_NUMBER} merged."
       fi
   fi
   ```

Report: `Step 7/9: Merge complete - worktree cleaned up`

---

### Step 8: Verify CI (after merge)

After merging to main, verify that the CI pipeline passes before deploying.

1. **Detect CI system and poll for results:**

```bash
cd "$MAIN_REPO"
COMMIT_SHA=$(git rev-parse HEAD)
SHORT_SHA=$(git rev-parse --short HEAD)
REPO_FULL=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
```

2. **Check Woodpecker CI** (if `WOODPECKER_API_TOKEN` is set):

```bash
if [[ -n "$WOODPECKER_API_TOKEN" ]]; then
    WOODPECKER_SERVER="${WOODPECKER_SERVER:-https://woodpecker.essent-ai.com}"
    echo "Polling Woodpecker CI for commit $SHORT_SHA..."

    # Woodpecker v3 API requires numeric repo ID, not owner/name
    # First resolve repo ID via lookup endpoint
    REPO_ID=$(curl -s -H "Authorization: Bearer $WOODPECKER_API_TOKEN" \
        -H "Accept: application/json" \
        "$WOODPECKER_SERVER/api/repos/lookup/$REPO_FULL" | jq -r '.id' 2>/dev/null)

    if [[ -z "$REPO_ID" || "$REPO_ID" == "null" ]]; then
        echo "WARNING: Could not resolve Woodpecker repo ID for $REPO_FULL. Skipping CI verification."
    else
        # Poll up to 10 minutes (60 attempts, 10s apart)
        for i in $(seq 1 60); do
            PIPELINE_JSON=$(curl -s -H "Authorization: Bearer $WOODPECKER_API_TOKEN" \
                -H "Accept: application/json" \
                "$WOODPECKER_SERVER/api/repos/$REPO_ID/pipelines?per_page=5" | \
                jq --arg sha "$COMMIT_SHA" '[.[] | select(.commit == $sha)] | .[0]' 2>/dev/null)

            if [[ -n "$PIPELINE_JSON" && "$PIPELINE_JSON" != "null" ]]; then
                STATUS=$(echo "$PIPELINE_JSON" | jq -r '.status')
                PIPELINE_NUM=$(echo "$PIPELINE_JSON" | jq -r '.number')

                case "$STATUS" in
                    success)
                        echo "Woodpecker pipeline #$PIPELINE_NUM passed."
                        break
                        ;;
                    failure|error|killed)
                        echo "Woodpecker pipeline #$PIPELINE_NUM FAILED (status: $STATUS)."
                        echo "View: $WOODPECKER_SERVER/repos/$REPO_FULL/pipeline/$PIPELINE_NUM"
                        # STOP - do not deploy
                        exit 1
                        ;;
                    *)
                        echo "Pipeline #$PIPELINE_NUM status: $STATUS (attempt $i/60)..."
                        sleep 10
                        ;;
                esac
            else
                if [[ $i -ge 60 ]]; then
                    echo "WARNING: No Woodpecker pipeline found for $SHORT_SHA after 10 minutes."
                    break
                fi
                sleep 10
            fi
        done
    fi
fi
```

3. **Check GitHub Actions** (fallback if no Woodpecker token):

```bash
if [[ -z "$WOODPECKER_API_TOKEN" ]]; then
    echo "Polling GitHub Actions for commit $SHORT_SHA..."

    for i in $(seq 1 60); do
        RUN_JSON=$(gh run list --commit "$COMMIT_SHA" --json status,conclusion,databaseId,name --jq '.[0]' 2>/dev/null)

        if [[ -n "$RUN_JSON" && "$RUN_JSON" != "null" ]]; then
            GH_STATUS=$(echo "$RUN_JSON" | jq -r '.status')
            GH_CONCLUSION=$(echo "$RUN_JSON" | jq -r '.conclusion')
            RUN_ID=$(echo "$RUN_JSON" | jq -r '.databaseId')

            if [[ "$GH_STATUS" == "completed" ]]; then
                if [[ "$GH_CONCLUSION" == "success" ]]; then
                    echo "GitHub Actions run #$RUN_ID passed."
                    break
                else
                    echo "GitHub Actions run #$RUN_ID FAILED (conclusion: $GH_CONCLUSION)."
                    echo "View: gh run view $RUN_ID"
                    exit 1
                fi
            else
                echo "Run #$RUN_ID status: $GH_STATUS (attempt $i/60)..."
                sleep 10
            fi
        else
            if [[ $i -ge 60 ]]; then
                echo "WARNING: No GitHub Actions run found for $SHORT_SHA after 10 minutes."
                break
            fi
            sleep 10
        fi
    done
fi
```

4. **No CI detected:**

If neither `WOODPECKER_API_TOKEN` is set nor GitHub Actions runs are found, skip with a warning:

```
WARNING: No CI system detected. Skipping verification.
```

- If CI **passes**: proceed to Step 9.
- If CI **fails**: **STOP**. Report the failure and exit. Do not deploy broken code.
- If CI **not found** after timeout: warn and proceed (non-blocking).

Report: `Step 8/9: Verify CI complete - pipeline #{N} passed` or `Step 8/9: Verify CI skipped (no CI detected)`

---

### Step 9: Deploy (optional)

Only if a Makefile with a `deploy` target exists in the main repo. Because
`/flow:auto` runs `make deploy` inline (it does NOT call `/flow:deploy`), the
deploy-verification gate is wired in here too - otherwise the flagship
"one command to ship" path would deploy without validating the deployment.

```bash
cd "$MAIN_REPO"

# Locate CPP source for lib/cicd (deploy verification)
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done
VERIFY_ENABLED=0
if [ -n "$CPP_DIR" ] && grep -q "deploy_verification:" .claude/cicd.yml 2>/dev/null; then
    VERIFY_ENABLED=1
fi

if [[ -f "Makefile" ]] && grep -q "^deploy:" Makefile; then
    # Pre-deploy: capture the baseline (before make deploy) so the post-deploy
    # verify can detect regressions.
    if [ "$VERIFY_ENABLED" -eq 1 ]; then
        echo "Capturing pre-deploy baseline..."
        PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd verify --baseline --summary
    fi

    echo "Running: make deploy"
    make deploy
    DEPLOY_EXIT=$?

    # Post-deploy: verify against the baseline and emit a proceed/rollback verdict.
    VERDICT="none"
    if [ "$VERIFY_ENABLED" -eq 1 ]; then
        echo "Running deploy verification..."
        PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd verify
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

- Verification is fail-open and inert unless `health.deploy_verification.enabled`
  is set in `.claude/cicd.yml`. A ROLLBACK verdict is surfaced to the user but
  never rolls back automatically - it is an actionable signal, not an action.

Report: `Step 9/9: Deploy complete (verify: {proceed|review|rollback|none})` or
`Step 9/9: Deploy skipped (no Makefile target)`

---

### Final Summary

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

After the summary, if `.claude/friction.jsonl` recorded any signals this run, offer
the codify step - do not block or auto-run it:

```
Friction retro: this run recorded N friction signal(s). Run /self-improvement:retro
to turn them into confirmed fixes (permission allowlist, Make targets, hooks,
CLAUDE.md, portable learnings)? [y/N]
```

Declining is free - capture already persisted the signals for a later retro. This
offer also appears at the end of `/flow:merge`.

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

Key failure scenarios:
- **Issue not found:** Stop at step 1
- **Issue closed:** Warn at step 1, ask to proceed
- **Analysis unclear:** Stop at step 2, ask user for clarification
- **ELI5 verdict `No longer needed`:** Stop at step 3, recommend closing the issue instead of implementing
- **Plan rejected at ELI5 gate:** Stop at step 3, revise the plan (or close) before proceeding
- **Implementation blocker:** Stop at step 4, report what's blocking
- **Doc update fails:** Non-blocking at step 5, warn and continue
- **Lint/test fails:** Stop at step 6, show test output
- **Push fails:** Stop at step 6, suggest `git pull --rebase`
- **PR merge conflicts:** Stop at step 7, suggest manual resolution
- **CI pipeline fails:** Stop at step 8, link to pipeline/run for investigation
- **CI not detected:** Non-blocking at step 8, warn and continue to deploy
- **Deploy fails:** Report but don't roll back (deploy is best-effort)
- **Inside worktree being removed:** `ExitWorktree(action="remove")` restores the session cwd for session-created worktrees; the git fallback path uses `worktree-remove.sh`, which also handles removing from inside safely

## Notes

- This is the "one command to ship" - takes an issue number and delivers it end-to-end
- The analyze step ensures Claude understands the issue before writing code
- The ELI5 step (Step 3) is a human checkpoint: it restates intent in plain language, verifies the issue is still worth doing, and gates implementation on plan approval. Use `--yes` (or an `eli5: auto-approve` trailer) for fully unattended runs; a `No longer needed` verdict never auto-implements
- Each step builds on the previous one; there's no skipping
- Worktrees are native: Step 1 uses the `EnterWorktree` tool (checkout under `.claude/worktrees/`, branched from `origin/<default-branch>`) and Step 7 uses `ExitWorktree` for session-created worktrees, with a `git worktree` fallback for resumed or cross-machine worktrees. The issue-anchored `issue-<N>-<slug>` branch name, the ELI5 gate, and quality gates are CPP policy layered on top of the native mechanics
- The deploy step is always optional - it only runs if a deploy target exists
- After completion, the user is in the main repo on the main branch
- For step-by-step control, use individual commands: `/flow:start`, `/flow:eli5`, `/flow:finish`, `/flow:merge`, `/flow:deploy`
- Friction capture runs throughout (always-on, fail-open, `scripts/friction-log.sh` -> `.claude/friction.jsonl`) and the run offers `/self-improvement:retro` at the end to codify fixes - the grill-me cycle (issue #426)
