# Flow: Auto — Finish, Merge, and Deploy in One Shot

Chain the full tail end of the development workflow: quality gates → PR → merge → deploy.

## Instructions

When the user invokes `/flow:auto`, perform these steps sequentially. Stop immediately if any step fails.

### Step 1: Validate Context

```bash
BRANCH=$(git branch --show-current)
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    echo "ERROR: Cannot run /flow:auto from main. Switch to a feature branch or worktree."
    exit 1
fi

ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")
```

Report what's about to happen:

```
Flow Auto: issue-42-fix-login → finish → merge → deploy

Step 1/3: Finish (lint, test, commit, push, create PR)
Step 2/3: Merge (squash-merge PR, clean up worktree)
Step 3/3: Deploy (make deploy, if target exists)

Proceeding...
```

### Step 2: Finish

Execute the full `/flow:finish` workflow:

1. **Quality gates** — if Makefile exists:
   - Run `make lint` (if target exists)
   - Run `make test` (if target exists)
   - If either fails: **STOP**. Report the failure and exit.

2. **Commit** — if there are uncommitted changes:
   - Help the user commit with conventional commit format
   - Include `Closes #N` in the commit message

3. **Push** — push the branch:
   ```bash
   git push -u origin "$BRANCH"
   ```

4. **Create PR** — if no PR exists:
   ```bash
   gh pr create --title "type(scope): Description (Closes #ISSUE_NUM)" --body "..."
   ```
   - If PR already exists, report its URL and continue

Report: `✅ Step 1/3: Finish complete — PR #XX created`

### Step 3: Merge

Execute the full `/flow:merge` workflow:

1. **Merge the PR**:
   ```bash
   PR_NUMBER=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number')
   gh pr merge "$PR_NUMBER" --squash --delete-branch
   ```
   - If merge fails (conflicts, checks): **STOP**. Report and exit.

2. **Update local main**:
   ```bash
   # Determine main repo path
   if [[ -f ".git" ]]; then
       MAIN_REPO=$(cat .git | sed 's/gitdir: //' | sed 's|/.git/worktrees/.*||')
   else
       MAIN_REPO=$(pwd)
   fi
   git -C "$MAIN_REPO" checkout main 2>/dev/null || true
   git -C "$MAIN_REPO" pull origin main
   ```

3. **Clean up worktree and branch**:
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

Report: `✅ Step 2/3: Merge complete — worktree cleaned up`

### Step 4: Deploy (optional)

Only if a Makefile with a `deploy` target exists in the main repo:

```bash
cd "$MAIN_REPO"
if [[ -f "Makefile" ]] && grep -q "^deploy:" Makefile; then
    echo "Running: make deploy"
    make deploy

    # Log deployment
    mkdir -p .claude
    echo "$(date -Iseconds) | deploy | $(git rev-parse --short HEAD) | main | $?" >> .claude/deploy.log
else
    echo "No deploy target in Makefile — skipping deployment."
fi
```

Report: `✅ Step 3/3: Deploy complete` or `⏭️ Step 3/3: Deploy skipped (no Makefile target)`

### Step 5: Summary

```
Flow Auto Complete ✅

  Issue:    #42 — Fix login bug
  PR:       #78 (squash-merged)
  Branch:   issue-42-fix-login (deleted)
  Worktree: ../my-project-issue-42 (removed)
  Deploy:   make deploy (success) | skipped
  Location: /home/user/Projects/my-project (main)
```

## Error Handling

At each step, if something fails:

```
Flow Auto stopped at Step N/3 ❌

  Failed: [description of what failed]
  Fix:    [actionable suggestion]

  To resume manually:
    /flow:finish   (if step 1 failed)
    /flow:merge    (if step 2 failed)
    /flow:deploy   (if step 3 failed)
```

Key failure scenarios:
- **Lint/test fails:** Stop at step 1, show test output
- **Push fails:** Stop at step 1, suggest `git pull --rebase`
- **PR merge conflicts:** Stop at step 2, suggest manual resolution
- **Deploy fails:** Report but don't roll back (deploy is best-effort)
- **Inside worktree being removed:** `worktree-remove.sh` handles this safely

## Notes

- This is the "happy path" command — when everything is ready and you want to ship
- Each step builds on the previous one; there's no skipping
- The deploy step is always optional — it only runs if a deploy target exists
- After completion, the user is in the main repo on the main branch
