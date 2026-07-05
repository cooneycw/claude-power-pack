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

### Step 3b: Deploy Compose-Project Safety + Out-of-Band Opt-Out (issue #535)

`make deploy` (both the deterministic runner in Step 4b and the fallback in Step 5)
shells out to `docker compose`, which derives `COMPOSE_PROJECT_NAME` from the
current directory basename when it is unset. Run from a worktree or a `/tmp`
recovery clone, that basename diverges from the prod project
(`agentic-asst-issue-516` vs `agentic-asst`), collides with compose files that pin
prod `container_name` values, and the failed rollback leaks orphaned
`<basename>_*` volumes/networks. Handle both escapes before any deploy runs:

```bash
DEPLOY_MODE=$(grep -oP '^\s*mode:\s*\K\S+' .claude/deploy.yaml 2>/dev/null | head -1)

# 1. Out-of-band deploy: a repo whose real deploy path is a host timer / CI on
#    origin/main declares `mode: external` in .claude/deploy.yaml. Do NOT stage a
#    throwaway per-worktree compose stack from a dev box.
if [ "$DEPLOY_MODE" = "external" ]; then
    echo "Deploy mode 'external' (.claude/deploy.yaml) - deploy runs out of band (host timer / CI on origin/main)."
    echo "Nothing to do here; skipping /flow:deploy."
    exit 0
fi

# 2. Otherwise pin COMPOSE_PROJECT_NAME (when unset) to a STABLE name so compose
#    never uses the worktree/tmp basename: an explicit .claude/deploy.yaml override,
#    else the CANONICAL primary-checkout name from git's common dir. Exported here
#    so BOTH the runner (Step 4b) and the fallback (Step 5) inherit it.
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

### Step 4c: Capture Deploy-Verification Baseline (pre-deploy)

Before deploying, snapshot the currently-running system so the post-deploy run
(Step 8) can detect regressions. Only runs when
`health.deploy_verification.enabled` is set in `.claude/cicd.yml`.

```bash
# Locate CPP source for lib/cicd
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -n "$CPP_DIR" ] && grep -q "deploy_verification:" .claude/cicd.yml 2>/dev/null; then
    echo "Capturing pre-deploy baseline..."
    PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd verify --baseline --summary
fi
```

- Captures health + smoke probes into `.claude/deploy-baseline.json`.
- Fail-open: if `lib/cicd` is unavailable or no probes are configured, skip -
  the deploy is never blocked by baseline capture.

### Step 4b: Run Deploy via Deterministic Runner (primary path)

**Primary path:** Use the deterministic CI/CD runner for reproducible deploy with security gate:

```bash
# Locate CPP source for lib/cicd
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -n "$CPP_DIR" ]; then
    PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd run --plan deploy
    RUNNER_EXIT=$?
fi
```

- If runner **succeeds** (exit 0): deploy completed (includes security scan + make deploy), skip to Step 6.
- If runner **fails** (exit non-zero): parse JSON output, report the failed step, and **stop**.
- If runner is **not available**: fall back to manual execution below.

**Fallback path** (only if runner unavailable):

Run security scan before deploying:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security gate flow_deploy
```

- If the gate **fails** (critical or high findings): **stop and report**. Show findings.
- If the gate produces **warnings** (medium findings): display them but proceed.
- If `lib/security` is not available, skip this step.

### Step 5: Run Deploy (fallback only - runner includes this)

**Skip this step if the deterministic runner was used above** (it already runs make deploy).

Only run manually if the runner was unavailable:

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
       # Skip - not configured
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

3b. **Run deploy verification (baseline comparison + verdict):**

   When a baseline was captured in Step 4c, diff the post-deploy probes against
   it and emit an actionable verdict. This is the deploy-confidence gate - it
   catches a deploy that made things *worse* than before, which raw health/smoke
   cannot.

   ```bash
   echo "Running deploy verification..."
   PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd verify
   VERIFY_EXIT=$?
   ```

   - `VERIFY_EXIT == 0` (PROCEED or REVIEW): keep the deployment. On REVIEW,
     surface the flagged probes to the user.
   - `VERIFY_EXIT == 1` (ROLLBACK): a probe that passed in the baseline fails
     now. **Report the regression prominently** and recommend rolling back
     (redeploy the previous commit or run the rollback target) or investigating
     with `/cicd:health` + `/cicd:smoke`. Verification does not roll back
     automatically - the human decides.

4. **Report results:**
   - If verification PROCEEDs (or health + smoke pass with no baseline):
     `"Deploy verified ✅ - no regression vs baseline"`
   - If verification returns ROLLBACK: Report the regression and recommend
     rollback + `/self-improvement:deployment`
   - If any raw check fails: Report failures and suggest `/self-improvement:deployment`

5. **Log verification results** (extends deploy.log format):
   ```bash
   HEALTH_PASS=$( [ "$HEALTH_EXIT" -eq 0 ] && echo "pass" || echo "fail" )
   SMOKE_PASS=$( [ "$SMOKE_EXIT" -eq 0 ] && echo "pass" || echo "fail" )
   VERDICT=$( PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd verify --summary 2>/dev/null | grep -oiE 'proceed|review|rollback' | head -1 | tr 'A-Z' 'a-z' )
   echo "$(date -Iseconds) | ${TARGET} | $(git rev-parse --short HEAD) | $(git branch --show-current) | $DEPLOY_EXIT | health:${HEALTH_PASS} | smoke:${SMOKE_PASS} | verify:${VERDICT:-none}" >> .claude/deploy.log
   ```

   Extended log format: `timestamp | target | commit | branch | deploy_exit | health:pass/fail | smoke:pass/fail | verify:proceed/review/rollback/none`

**Skip conditions:**
- No `.claude/cicd.yml` → skip silently
- No `post_deploy:` in config → skip silently
- `lib/cicd` not available (no CPP_DIR) → skip with warning
- Verification failures do NOT roll back the deployment - they only report

## Error Handling

- **No Makefile:** Report error with guidance to create one
- **Target not found:** List available targets
- **Deploy fails:** Report exit code, show output
- **Not on main:** Warn but allow (user may want staging deploy from branch)

## Notes

- Deployment always goes through `make` - the Makefile is the single source of truth
- The `.claude/deploy.log` provides an audit trail of all deployments
- The optional `.claude/deploy.yaml` adds metadata without changing the Makefile
- This command works from any directory that has a Makefile
