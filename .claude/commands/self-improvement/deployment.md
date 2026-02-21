# Self-Improvement: Deployment — Retrospective Makefile Analysis

Examine recent errors from the current session and deploy history, then propose concrete Makefile improvements to prevent recurrence.

## Arguments

None. This command operates on conversation context and project state.

## Instructions

When the user invokes `/self-improvement:deployment`, perform these steps:

### Step 1: Gather Context — Recent Errors

Review the current conversation for:
- Failed `make` commands (any target) and their stderr output
- Failed deployment attempts (`make deploy`, `make deploy-staging`, etc.)
- Build/test failures (`make test`, `make lint`)
- Missing target errors ("No rule to make target...")
- Dependency failures (target prerequisites failing)
- Any other build or deployment errors

Summarize what went wrong, including:
- Which Makefile targets were involved
- The exact error messages
- How many times the same error pattern occurred

If no errors are visible in the conversation, inform the user:

```
No recent errors found in this session.

To use this command effectively:
  1. Run it after a failed deployment or build
  2. Or describe what went wrong: "The deploy failed because..."
```

### Step 2: Gather Context — Deploy History

```bash
if [ -f ".claude/deploy.log" ]; then
    echo "=== Recent Deploy History ==="
    tail -20 .claude/deploy.log
else
    echo "No deploy.log found"
fi
```

Analyze the deploy log for:
- Repeated failures (exit_code != 0)
- Patterns in which targets fail
- Time gaps suggesting abandoned deploy attempts
- Whether failures cluster on certain branches

### Step 3: Gather Context — Current Makefile

```bash
if [ -f "Makefile" ]; then
    cat Makefile
else
    echo "NO_MAKEFILE"
fi
```

If no Makefile exists, recommend creating one from the template:

```
No Makefile found. Create one from the CPP template:

  cp ~/Projects/claude-power-pack/templates/Makefile.example Makefile

Then customize targets for your project.
```

Stop here — no further analysis is possible without a Makefile.

### Step 4: Analyze — Pattern Detection

Cross-reference the errors (Step 1) with the Makefile contents (Step 3) to identify:

**Missing targets:**
- Errors referencing targets that do not exist
- Targets called by `/flow` commands but not defined (e.g., `/flow:finish` expects `lint` and `test`)

**Dependency gaps:**
- Targets that should depend on others but run independently
- Example: `deploy` should depend on `test` and `lint` but does not

**Error handling gaps:**
- Targets that fail silently (no error checking)
- Missing `.PHONY` declarations causing stale file conflicts
- Missing `@` prefix on informational echo commands (noise vs. signal)

**Missing standard targets:**
Compare against the CPP standard set and report which are absent:

| Target | Used By | Purpose |
|--------|---------|---------|
| `lint` | `/flow:finish` | Code linting (auto-discovered) |
| `test` | `/flow:finish` | Test suite (auto-discovered) |
| `format` | Manual | Code formatting |
| `deploy` | `/flow:deploy` | Production deployment |
| `deploy-staging` | `/flow:deploy staging` | Staging deployment |
| `clean` | Manual | Remove build artifacts |

**uv integration issues:**
- Commands using bare `python`/`pytest`/`ruff` instead of `uv run` (causes environment isolation failures)
- Missing virtual environment setup

### Step 5: Propose Improvements

Present findings in this format:

```
## Deployment Retrospective

### What Went Wrong

1. **[Error category]**: [description]
   - Observed: [what happened]
   - Root cause: [why it happened]

### Makefile Improvements

#### Fix 1: [Short title]

**Problem:** [what's wrong]
**Solution:** [what to change]

Before:
  deploy:
      rsync -avz . server:/app

After:
  deploy: test lint
      rsync -avz . server:/app

#### Fix 2: [Short title]
...

### Missing Standard Targets

| Target | Status | Recommendation |
|--------|--------|---------------|
| lint | Missing | Add: `uv run ruff check .` |
| test | Present | OK |
| ...  | ...     | ... |

### .PHONY Declarations

  .PHONY: test lint format deploy deploy-staging clean
```

### Step 6: Offer to Apply

Ask the user:

```
Would you like me to apply these Makefile improvements?

Changes:
  - [list of specific changes]
```

If the user approves, edit the Makefile using the Edit tool. If not, the analysis stands as documentation.

## Output Format

```
Self-Improvement: Deployment Retrospective
==========================================

Session Errors Analyzed: N
Deploy Log Entries:      N (M failures)
Makefile Targets:        N defined

[Analysis sections from Step 5]

Proposed Changes: N improvements
Apply changes? [y/N]
```

## Error Handling

- **No errors in session:** Report that no errors were found; suggest running after a failure or describing the issue
- **No Makefile:** Recommend creating one from the CPP template and stop
- **No deploy.log:** Note absence, proceed with session-only analysis
- **Makefile is read-only:** Report the issue and output the proposed changes as a diff

## Notes

- This is a **retrospective** command — it looks backward at what happened, not forward
- It never modifies the Makefile without explicit user approval
- The deploy.log at `.claude/deploy.log` provides historical context beyond the current session
- Pair with `/flow:doctor` for a forward-looking health check of your workflow environment
- Reference template: `~/Projects/claude-power-pack/templates/Makefile.example`
- All Makefile targets should use `uv run` for Python commands to ensure environment isolation
