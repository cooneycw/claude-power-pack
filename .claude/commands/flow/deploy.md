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

### Step 4b: Run Security Check

Run security scan before deploying:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security gate flow_deploy
```

- If the gate **fails** (critical or high findings): **stop and report**. Show findings.
- If the gate produces **warnings** (medium findings): display them but proceed.
- If `lib/security` is not available, skip this step.

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

### Step 8: Post-Deploy Verification (optional)

After a successful deployment, automatically run health checks and smoke tests if configured.

**Condition:** Only run if `.claude/cicd.yml` exists AND contains `health.post_deploy: true`.

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

If `CPP_DIR` is found and `.claude/cicd.yml` exists:

1. **Check if post-deploy verification is enabled:**
   ```bash
   if grep -q "post_deploy:" .claude/cicd.yml 2>/dev/null; then
       # Verification enabled
   else
       # Skip — not configured
   fi
   ```

2. **Run health checks:**
   ```bash
   echo "Running post-deploy health checks..."
   PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd health --summary
   HEALTH_EXIT=$?
   ```

3. **Run smoke tests:**
   ```bash
   echo "Running post-deploy smoke tests..."
   PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd smoke --summary
   SMOKE_EXIT=$?
   ```

4. **Report results:**
   - If all pass: `"Deploy verified ✅ — health checks and smoke tests passed"`
   - If any fail: Report failures and suggest `/self-improvement:deployment`

5. **Log verification results** (extends deploy.log format):
   ```bash
   HEALTH_PASS=$( [ "$HEALTH_EXIT" -eq 0 ] && echo "pass" || echo "fail" )
   SMOKE_PASS=$( [ "$SMOKE_EXIT" -eq 0 ] && echo "pass" || echo "fail" )
   echo "$(date -Iseconds) | ${TARGET} | $(git rev-parse --short HEAD) | $(git branch --show-current) | $DEPLOY_EXIT | health:${HEALTH_PASS} | smoke:${SMOKE_PASS}" >> .claude/deploy.log
   ```

   Extended log format: `timestamp | target | commit | branch | deploy_exit | health:pass/fail | smoke:pass/fail`

**Skip conditions:**
- No `.claude/cicd.yml` → skip silently
- No `post_deploy:` in config → skip silently
- `lib/cicd` not available (no CPP_DIR) → skip with warning
- Verification failures do NOT roll back the deployment — they only report

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
