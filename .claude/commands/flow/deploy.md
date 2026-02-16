# Flow: Deploy via Makefile

Run deployment using the project's Makefile targets.

## Arguments

- `TARGET` (optional): Makefile target to run (default: `deploy`)

## Instructions

When the user invokes `/flow:deploy [TARGET]`, perform these steps:

### Step 1: Verify on Main Branch

```bash
BRANCH=$(git branch --show-current)
if [[ "$BRANCH" != "main" && "$BRANCH" != "master" ]]; then
    echo "WARNING: Deploying from branch '$BRANCH' (not main)."
    echo "Consider merging first with /flow:merge."
    # Ask user to confirm or abort
fi
```

### Step 2: Check Makefile Exists

```bash
if [[ ! -f "Makefile" ]]; then
    echo "ERROR: No Makefile found in $(pwd)"
    echo "Create a Makefile with a 'deploy' target, or run your deploy command directly."
    exit 1
fi
```

### Step 3: Verify Target Exists

```bash
TARGET="${1:-deploy}"

if ! grep -q "^${TARGET}:" Makefile; then
    echo "ERROR: No '${TARGET}' target in Makefile"
    echo ""
    echo "Available targets:"
    grep -E "^[a-zA-Z_-]+:" Makefile | sed 's/:.*//' | sort
    exit 1
fi
```

### Step 4: Check Deploy Metadata (optional)

If `.claude/deploy.yaml` exists, read it for confirmation requirements:

```yaml
# .claude/deploy.yaml (optional)
targets:
  deploy:
    description: Deploy to production
    requires_confirmation: true
  deploy-staging:
    description: Deploy to staging
```

- If `requires_confirmation: true`, ask the user to confirm before proceeding
- If no deploy.yaml, proceed without extra confirmation

### Step 5: Run Deploy

```bash
echo "Running: make $TARGET"
make "$TARGET"
```

### Step 6: Log Deployment

Append to `.claude/deploy.log`:

```bash
mkdir -p .claude
echo "$(date -Iseconds) | ${TARGET} | $(git rev-parse --short HEAD) | $(git branch --show-current) | $?" >> .claude/deploy.log
```

Format: `timestamp | target | commit | branch | exit_code`

### Step 7: Output

On success:
```
Deployment complete ✅

  Target:  make deploy
  Commit:  abc1234
  Branch:  main
  Time:    2026-02-16T14:30:00-05:00

  Log: .claude/deploy.log
```

On failure:
```
Deployment failed ❌

  Target:  make deploy
  Exit:    1

Review the output above for errors.
```

## Error Handling

- **No Makefile:** Report error with guidance to create one
- **Target not found:** List available targets
- **Deploy fails:** Report exit code, show output
- **Not on main:** Warn but allow (user may want staging deploy from branch)

## Notes

- Deployment always goes through `make` — the Makefile is the single source of truth
- The `.claude/deploy.log` provides an audit trail of all deployments
- The optional `.claude/deploy.yaml` adds metadata without changing the Makefile
- This command works from any directory that has a Makefile
