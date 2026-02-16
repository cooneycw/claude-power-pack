# Flow: Finish — Quality Gates, Commit, Push, and Create PR

Run quality checks, commit changes, push the branch, and create a pull request.

## Instructions

When the user invokes `/flow:finish`, perform these steps:

### Step 1: Validate Context

```bash
# Ensure we're on a feature branch (not main)
BRANCH=$(git branch --show-current)
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    echo "ERROR: Cannot finish from main/master. Switch to a feature branch or worktree."
    exit 1
fi

# Extract issue number from branch
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")
```

### Step 2: Run Quality Gates (if Makefile targets exist)

Check for standard Makefile targets and run them:

```bash
if [[ -f "Makefile" ]]; then
    # Run lint if target exists
    if grep -q "^lint:" Makefile; then
        echo "Running: make lint"
        make lint
    fi

    # Run tests if target exists
    if grep -q "^test:" Makefile; then
        echo "Running: make test"
        make test
    fi
fi
```

- If tests or lint fail, **stop and report**. Do not proceed to PR creation.
- If no Makefile exists, skip quality gates (warn the user).

### Step 2b: Run Security Quick Scan

Run the native security scanner as a quality gate:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security gate flow_finish
```

- If the gate **fails** (critical findings): **stop and report**. Show findings and remediation.
- If the gate produces **warnings** (high findings): display them but proceed.
- If `lib/security` is not available, skip this step (warn the user).

### Step 3: Check for Changes

```bash
# Check for uncommitted changes
git status --porcelain
```

- If there are uncommitted changes, help the user commit them using standard git commit workflow.
- Use conventional commit format: `type(scope): Description (Closes #N)`
- Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` if Claude helped write the code.

### Step 4: Push Branch

```bash
# Push with tracking
git push -u origin "$BRANCH"
```

### Step 5: Check for Existing PR

```bash
EXISTING_PR=$(gh pr list --head "$BRANCH" --json number,url --jq '.[0]' 2>/dev/null)
```

- If a PR already exists, report its URL and ask if the user wants to update it.
- If no PR exists, proceed to create one.

### Step 6: Create PR

Use standard PR creation:

```bash
gh pr create \
  --title "type(scope): Description (Closes #ISSUE_NUM)" \
  --body "## Summary
- <bullet points>

## Test plan
- [ ] Tests pass
- [ ] Linting passes

Closes #ISSUE_NUM"
```

- Title: Conventional commit style, derived from changes
- Body: Summary of changes + test plan + `Closes #N`
- Analyze all commits on the branch to draft the summary

### Step 7: Output

```
Quality gates passed:
  ✅ make lint
  ✅ make test
  ✅ security scan (quick)

Branch pushed: issue-42-fix-login → origin

PR created: https://github.com/owner/repo/pull/78
  Title: fix(auth): Resolve login redirect loop (Closes #42)
```

## Error Handling

- **Lint/test failure:** Stop, show output, ask user to fix
- **Push failure:** Report error (likely needs `git pull --rebase`)
- **PR already exists:** Report URL, offer to update
- **No issue number in branch:** Create PR without `Closes #N` reference
- **No Makefile:** Skip quality gates, warn user

## Notes

- Quality gates are optional — if no Makefile exists, the flow still works
- The commit step follows standard git commit conventions (the user controls the message)
- This command works from any worktree directory
