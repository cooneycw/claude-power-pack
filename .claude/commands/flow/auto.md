# Flow: Auto — Full Issue Lifecycle in One Shot

Complete end-to-end workflow: start worktree → analyze issue → implement → finish (PR) → merge → deploy.

## Arguments

- `ISSUE` (required): GitHub issue number (e.g., `42`)

## Instructions

When the user invokes `/flow:auto <ISSUE>`, perform these steps sequentially. Stop immediately if any step fails.

Report at the start:

```
Flow Auto: Issue #42 — Full Lifecycle

Step 1/6: Start (create worktree and branch)
Step 2/6: Analyze (understand issue and codebase)
Step 3/6: Implement (write the code)
Step 4/6: Finish (lint, test, commit, push, create PR)
Step 5/6: Merge (squash-merge PR, clean up worktree)
Step 6/6: Deploy (make deploy, if target exists)

Proceeding...
```

---

### Step 1: Start — Create Worktree

Create a worktree and branch for the issue. If one already exists, use it.

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
    # Already in the right worktree — skip creation
fi

# Check if worktree already exists
git worktree list | grep "issue-${ISSUE_NUM}"

# Check if remote branch exists
git fetch origin
git branch -r | grep "issue-${ISSUE_NUM}-"
```

- **Already on issue branch:** Skip creation, use current directory.
- **Worktree exists:** Use it, skip creation.
- **Remote branch exists:** Create worktree tracking the remote branch.
- **Neither exists:** Create fresh from `origin/main`:
  ```bash
  git fetch origin main
  git worktree add -b "$BRANCH" "$WORKTREE_DIR" origin/main
  ```

Report: `Step 1/6: Start complete — worktree at {path}`

---

### Step 2: Analyze — Understand the Issue

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
Step 2/6: Analysis Complete

Issue #42: "Fix login redirect loop"

Acceptance Criteria:
  - [ ] Login redirects to dashboard after auth
  - [ ] Invalid sessions redirect to /login
  - [ ] Tests pass

Implementation Plan:
  1. Modify src/auth/login.py — fix redirect logic in handle_login()
  2. Update tests/test_auth.py — add redirect test cases
  3. Update config/routes.py — add dashboard route

Files to modify: 3
Estimated scope: Small

Proceeding to implementation...
```

Report: `Step 2/6: Analyze complete — {N} files to modify`

---

### Step 3: Implement — Write the Code

Execute the implementation plan from Step 2:

1. **Make all code changes** in the worktree.
2. **Follow existing conventions** — match the code style, patterns, and structure of the project.
3. **Run tests locally** if a quick feedback loop is available (e.g., `make test` or the project's test command).
4. **Verify the changes** address all acceptance criteria from the issue.

If implementation hits a blocker that cannot be resolved:
- **STOP** and report the blocker.
- Suggest manual intervention.

Report: `Step 3/6: Implement complete — {summary of changes}`

---

### Step 4: Finish — Quality Gates, Commit, Push, PR

```bash
BRANCH=$(git branch --show-current)
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")
```

1. **Quality gates** — if Makefile exists:
   - Run `make lint` (if target exists)
   - Run `make test` (if target exists)
   - If either fails: **STOP**. Report the failure and exit.

2. **Commit** — if there are uncommitted changes:
   - Use conventional commit format: `type(scope): Description (Closes #N)`
   - Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`

3. **Push** the branch:
   ```bash
   git push -u origin "$BRANCH"
   ```

4. **Create PR** — if no PR exists:
   ```bash
   gh pr create --title "type(scope): Description (Closes #ISSUE_NUM)" --body "..."
   ```
   - If PR already exists, report its URL and continue.
   - PR body: Summary of changes + test plan + `Closes #N`
   - Analyze all commits on the branch to draft the summary.

Report: `Step 4/6: Finish complete — PR #XX created`

---

### Step 5: Merge — Squash-Merge and Clean Up

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
   ```bash
   if [[ -f ".git" ]]; then
       WORKTREE_PATH=$(pwd)
       if [[ -f ~/.claude/scripts/worktree-remove.sh ]]; then
           ~/.claude/scripts/worktree-remove.sh "$WORKTREE_PATH" --force --delete-branch
       else
           cd "$MAIN_REPO"
           git worktree remove "$WORKTREE_PATH" --force
           git branch -D "$BRANCH" 2>/dev/null || true
       fi
   else
       git branch -D "$BRANCH" 2>/dev/null || true
   fi
   ```

4. **Close issue** (if still open):
   ```bash
   if [[ -n "$ISSUE_NUM" ]]; then
       ISSUE_STATE=$(gh issue view "$ISSUE_NUM" --json state --jq '.state' 2>/dev/null)
       if [[ "$ISSUE_STATE" == "OPEN" ]]; then
           gh issue close "$ISSUE_NUM" --comment "Closed via /flow:auto — PR #${PR_NUMBER} merged."
       fi
   fi
   ```

Report: `Step 5/6: Merge complete — worktree cleaned up`

---

### Step 6: Deploy (optional)

Only if a Makefile with a `deploy` target exists in the main repo:

```bash
cd "$MAIN_REPO"
if [[ -f "Makefile" ]] && grep -q "^deploy:" Makefile; then
    echo "Running: make deploy"
    make deploy

    mkdir -p .claude
    echo "$(date -Iseconds) | deploy | $(git rev-parse --short HEAD) | main | $?" >> .claude/deploy.log
else
    echo "No deploy target in Makefile — skipping deployment."
fi
```

Report: `Step 6/6: Deploy complete` or `Step 6/6: Deploy skipped (no Makefile target)`

---

### Final Summary

```
Flow Auto Complete

  Issue:    #42 — Fix login bug
  Changes:  Modified 3 files (src/auth/login.py, tests/test_auth.py, config/routes.py)
  PR:       #78 (squash-merged)
  Branch:   issue-42-fix-login (deleted)
  Worktree: ../my-project-issue-42 (removed)
  Deploy:   make deploy (success) | skipped
  Location: /home/user/Projects/my-project (main)
```

---

## Error Handling

At each step, if something fails:

```
Flow Auto stopped at Step N/6: {Step Name}

  Failed: [description of what failed]
  Fix:    [actionable suggestion]

  To resume manually:
    /flow:start N    (if step 1 failed)
    [investigate]    (if step 2 failed)
    [implement]      (if step 3 failed)
    /flow:finish     (if step 4 failed)
    /flow:merge      (if step 5 failed)
    /flow:deploy     (if step 6 failed)
```

Key failure scenarios:
- **Issue not found:** Stop at step 1
- **Issue closed:** Warn at step 1, ask to proceed
- **Analysis unclear:** Stop at step 2, ask user for clarification
- **Implementation blocker:** Stop at step 3, report what's blocking
- **Lint/test fails:** Stop at step 4, show test output
- **Push fails:** Stop at step 4, suggest `git pull --rebase`
- **PR merge conflicts:** Stop at step 5, suggest manual resolution
- **Deploy fails:** Report but don't roll back (deploy is best-effort)
- **Inside worktree being removed:** `worktree-remove.sh` handles this safely

## Notes

- This is the "one command to ship" — takes an issue number and delivers it end-to-end
- The analyze step ensures Claude understands the issue before writing code
- Each step builds on the previous one; there's no skipping
- The deploy step is always optional — it only runs if a deploy target exists
- After completion, the user is in the main repo on the main branch
- For step-by-step control, use individual commands: `/flow:start`, `/flow:finish`, `/flow:merge`, `/flow:deploy`
