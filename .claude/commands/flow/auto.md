# Flow: Auto - Full Issue Lifecycle in One Shot

Complete end-to-end workflow: start worktree → analyze issue → implement → finish (PR) → merge → deploy.

## Arguments

- `ISSUE` (required): GitHub issue number (e.g., `42`)

## Instructions

When the user invokes `/flow:auto <ISSUE>`, perform these steps sequentially. Stop immediately if any step fails.

Report at the start:

```
Flow Auto: Issue #42 - Full Lifecycle

Step 1/8: Start (create worktree and branch)
Step 2/8: Analyze (understand issue and codebase)
Step 3/8: Implement (write the code)
Step 4/8: Update Docs (regenerate C4 diagrams, review CLAUDE.md/README.md)
Step 5/8: Finish (lint, test, commit, push, create PR)
Step 6/8: Merge (squash-merge PR, clean up worktree)
Step 7/8: Verify CI (confirm pipeline passes on main)
Step 8/8: Deploy (make deploy, if target exists)

Proceeding...
```

---

### Step 1: Start - Create Worktree

**CRITICAL: You MUST create or enter a worktree before proceeding. NEVER implement changes directly on main/master. This step is NOT optional - if worktree creation fails, STOP immediately.**

Create a worktree and branch for the issue. If one already exists, `cd` into it.

```bash
ISSUE_NUM="$1"
REPO=$(basename "$(git rev-parse --show-toplevel)")

# Fetch issue details
gh issue view "$ISSUE_NUM" --json number,title,state,body
```

- If issue is not OPEN, warn the user and ask whether to proceed.
- Extract the title for branch naming.

```bash
# Sanitize title for branch name
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | cut -c1-50)
BRANCH="issue-${ISSUE_NUM}-${SLUG}"
WORKTREE_DIR="../${REPO}-issue-${ISSUE_NUM}"
```

**Check for existing work:**

```bash
# Check if already on the issue's branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" =~ issue-${ISSUE_NUM}- ]]; then
    # Already in the right worktree - skip creation
fi

# Check if worktree already exists
git worktree list | grep "issue-${ISSUE_NUM}"

# Check if remote branch exists
git fetch origin
git branch -r | grep "issue-${ISSUE_NUM}-"
```

- **Already on issue branch:** Verify you are NOT on main/master. Use current directory.
- **Worktree exists:** `cd` into the existing worktree directory.
- **Remote branch exists:** Create worktree tracking the remote branch, then `cd` into it:
  ```bash
  git worktree add -b "$LOCAL_BRANCH" "$WORKTREE_DIR" "$REMOTE_BRANCH"
  cd "$WORKTREE_DIR"
  ```
- **Neither exists:** Create fresh from `origin/main`, then `cd` into it:
  ```bash
  git fetch origin main
  git worktree add -b "$BRANCH" "$WORKTREE_DIR" origin/main
  cd "$WORKTREE_DIR"
  ```

#### Verification Gate (MANDATORY - do NOT skip)

Before proceeding to Step 2, verify you are in the correct working directory:

```bash
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    echo "ERROR: Still on main/master after Step 1. Worktree creation failed or cd was skipped."
    echo "STOP: Cannot proceed. You MUST be on an issue branch, not main."
    exit 1
fi
echo "Verified: on branch '$CURRENT_BRANCH' in $(pwd)"
```

**If this verification fails, STOP immediately. Report the failure using the error template at the bottom of this file. Do NOT proceed to Step 2.**

Report: `Step 1/8: Start complete - worktree at {path}, verified on branch {branch}`

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
Step 2/8: Analysis Complete

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

Proceeding to implementation...
```

Report: `Step 2/8: Analyze complete - {N} files to modify`

---

### Step 3: Implement - Write the Code

Execute the implementation plan from Step 2:

1. **Make all code changes** in the worktree.
2. **Follow existing conventions** - match the code style, patterns, and structure of the project.
3. **Run tests locally** if a quick feedback loop is available (e.g., `make test` or the project's test command).
4. **Verify the changes** address all acceptance criteria from the issue.

If implementation hits a blocker that cannot be resolved:
- **STOP** and report the blocker.
- Suggest manual intervention.

Report: `Step 3/8: Implement complete - {summary of changes}`

---

### Step 4: Update Docs - Regenerate C4 Diagrams and Review Docs

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

Report: `Step 4/8: Update Docs complete - {N} files updated` or `Step 4/8: Update Docs skipped (no Makefile target)`

---

### Step 5: Finish - Quality Gates, Commit, Push, PR

```bash
BRANCH=$(git branch --show-current)
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")
```

1. **Quality gates** - if Makefile exists:
   - Run `make lint` (if target exists)
   - Run `make test` (if target exists)
   - If either fails: **STOP**. Report the failure and exit.

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

Report: `Step 5/8: Finish complete - PR #XX created`

---

### Step 6: Merge - Squash-Merge and Clean Up

1. **Merge the PR:**
   ```bash
   PR_NUMBER=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number')
   gh pr merge "$PR_NUMBER" --squash --delete-branch
   ```
   - If merge fails (conflicts, checks): **STOP**. Report and exit.

2. **Update local main:**
   ```bash
   if [[ -f ".git" ]]; then
       MAIN_REPO=$(cat .git | sed 's/gitdir: //' | sed 's|/.git/worktrees/.*||')
   else
       MAIN_REPO=$(pwd)
   fi
   git -C "$MAIN_REPO" checkout main 2>/dev/null || true
   git -C "$MAIN_REPO" pull origin main
   ```

3. **Clean up worktree and branch:**

   **CRITICAL: You MUST `cd` to the main repo BEFORE removing the worktree. NEVER remove a worktree while your working directory is inside it - this kills all subsequent bash commands. Execute these as SEPARATE Bash calls, not in a single script.**

   **Step 6a - Exit the worktree (separate Bash call):**
   ```bash
   cd "$MAIN_REPO"
   pwd  # Verify you are in the main repo
   ```

   **Step 6b - Remove the worktree (separate Bash call, AFTER confirming cd succeeded):**
   ```bash
   if [[ -f ~/.claude/scripts/worktree-remove.sh ]]; then
       ~/.claude/scripts/worktree-remove.sh "$WORKTREE_PATH" --force --delete-branch
   else
       git worktree remove "$WORKTREE_PATH" --force
       git branch -D "$BRANCH" 2>/dev/null || true
   fi
   ```

   **Step 6c - Verify working directory is valid:**
   ```bash
   pwd  # MUST show main repo path, NOT the deleted worktree
   git status  # MUST succeed - if this fails, your CWD was deleted
   ```

   If you are NOT in a worktree (just on a feature branch in main repo):
   ```bash
   git branch -D "$BRANCH" 2>/dev/null || true
   ```

4. **Close issue** (if still open):
   ```bash
   if [[ -n "$ISSUE_NUM" ]]; then
       ISSUE_STATE=$(gh issue view "$ISSUE_NUM" --json state --jq '.state' 2>/dev/null)
       if [[ "$ISSUE_STATE" == "OPEN" ]]; then
           gh issue close "$ISSUE_NUM" --comment "Closed via /flow:auto - PR #${PR_NUMBER} merged."
       fi
   fi
   ```

Report: `Step 6/8: Merge complete - worktree cleaned up`

---

### Step 7: Verify CI (after merge)

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

- If CI **passes**: proceed to Step 8.
- If CI **fails**: **STOP**. Report the failure and exit. Do not deploy broken code.
- If CI **not found** after timeout: warn and proceed (non-blocking).

Report: `Step 7/8: Verify CI complete - pipeline #{N} passed` or `Step 7/8: Verify CI skipped (no CI detected)`

---

### Step 8: Deploy (optional)

Only if a Makefile with a `deploy` target exists in the main repo:

```bash
cd "$MAIN_REPO"
if [[ -f "Makefile" ]] && grep -q "^deploy:" Makefile; then
    echo "Running: make deploy"
    make deploy

    mkdir -p .claude
    echo "$(date -Iseconds) | deploy | $(git rev-parse --short HEAD) | main | $?" >> .claude/deploy.log
else
    echo "No deploy target in Makefile - skipping deployment."
fi
```

Report: `Step 8/8: Deploy complete` or `Step 8/8: Deploy skipped (no Makefile target)`

---

### Final Summary

```
Flow Auto Complete

  Issue:    #42 - Fix login bug
  Changes:  Modified 3 files (src/auth/login.py, tests/test_auth.py, config/routes.py)
  PR:       #78 (squash-merged)
  Branch:   issue-42-fix-login (deleted)
  Worktree: ../my-project-issue-42 (removed)
  CI:       Woodpecker pipeline #5 passed | GitHub Actions run #123 passed | skipped
  Deploy:   make deploy (success) | skipped
  Location: /home/user/Projects/my-project (main)
```

---

## Error Handling

At each step, if something fails:

```
Flow Auto stopped at Step N/8: {Step Name}

  Failed: [description of what failed]
  Fix:    [actionable suggestion]

  To resume manually:
    /flow:start N    (if step 1 failed)
    [investigate]    (if step 2 failed)
    [implement]      (if step 3 failed)
    /documentation:c4 (if step 4 failed)
    /flow:finish     (if step 5 failed)
    /flow:merge      (if step 6 failed)
    [check CI dashboard] (if step 7 failed)
    /flow:deploy     (if step 8 failed)
```

Key failure scenarios:
- **Issue not found:** Stop at step 1
- **Issue closed:** Warn at step 1, ask to proceed
- **Analysis unclear:** Stop at step 2, ask user for clarification
- **Implementation blocker:** Stop at step 3, report what's blocking
- **Doc update fails:** Non-blocking at step 4, warn and continue
- **Lint/test fails:** Stop at step 5, show test output
- **Push fails:** Stop at step 5, suggest `git pull --rebase`
- **PR merge conflicts:** Stop at step 6, suggest manual resolution
- **CI pipeline fails:** Stop at step 7, link to pipeline/run for investigation
- **CI not detected:** Non-blocking at step 7, warn and continue to deploy
- **Deploy fails:** Report but don't roll back (deploy is best-effort)
- **Inside worktree being removed:** `worktree-remove.sh` handles this safely

## Notes

- This is the "one command to ship" - takes an issue number and delivers it end-to-end
- The analyze step ensures Claude understands the issue before writing code
- Each step builds on the previous one; there's no skipping
- The deploy step is always optional - it only runs if a deploy target exists
- After completion, the user is in the main repo on the main branch
- For step-by-step control, use individual commands: `/flow:start`, `/flow:finish`, `/flow:merge`, `/flow:deploy`
