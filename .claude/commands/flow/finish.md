# Flow: Finish - Quality Gates, Commit, Push, and Create PR

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

**Gate behavior by severity (defaults - configurable in `.claude/security.yml`):**

| Severity | Effect on `/flow:finish` | What to do |
|----------|--------------------------|------------|
| CRITICAL | **BLOCKS** - flow stops, no PR created | Fix the finding, then re-run `/flow:finish` |
| HIGH | **WARNS** - displayed, flow continues | Review finding; fix if real, suppress if false positive |
| MEDIUM | Passes silently | No action needed |
| LOW | Passes silently | No action needed |

To suppress a known false positive, add it to `.claude/security.yml`:
```yaml
suppressions:
  - id: HARDCODED_SECRET
    path: tests/fixtures/.*
    reason: "Test fixtures with fake credentials"
```

### Step 2d: Documentation Update Check (optional, non-blocking)

If the Makefile has an `update_docs` target:

```bash
if [[ -f "Makefile" ]] && grep -q "^update_docs:" Makefile; then
    echo "Running: make update_docs"
    make update_docs
fi
```

When this target exists, check documentation freshness:

1. **C4 diagrams** - If `docs/architecture/` exists, check if C4 HTML files are older than recent code changes. If stale, warn:
   ```
   Docs may be stale - C4 diagrams last updated {date}, code changed since then.
   Run /documentation:c4 to regenerate.
   ```

2. **CLAUDE.md / README.md** - Scan for obviously stale references (e.g., commands that no longer exist, file paths that don't match). Report as non-blocking warnings.

**This step never blocks the flow** - it is purely informational.

### Step 2c: Makefile Completeness Check (optional, non-blocking)

If `lib/cicd` is available, run a quick Makefile validation and report any gaps as warnings:

```bash
# Locate CPP source for lib/cicd
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done
```

If `CPP_DIR` is found and a Makefile exists:

```bash
PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd check --summary
CHECK_EXIT=$?
```

- If check reports **missing required targets**: display as a warning but **do NOT block**.
  ```
  ⚠️  Makefile check: 1 required target missing (typecheck)
      Run /cicd:check for details or /cicd:init to fix
  ```
- If check passes: report briefly - `"Makefile check: OK (6/6 targets present)"`
- If `lib/cicd` is not available: skip silently
- If no Makefile exists: skip silently (Step 2 already handles this)

**This step never blocks the flow** - it is purely informational.

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

- Quality gates are optional - if no Makefile exists, the flow still works
- The commit step follows standard git commit conventions (the user controls the message)
- This command works from any worktree directory
