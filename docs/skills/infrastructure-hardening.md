# Infrastructure Hardening

Patterns for hardening infrastructure pipelines after repeated failures. Load this when you detect repeated failures from the same root cause category, or when the user asks about validation gates, runtime contracts, canary validation, or sentinel files.

## Core Principle

After two or more failures from the same root cause, stop patching symptoms. Propose systemic hardening: explicit contracts, validation gates, and canary checks that prevent the entire *class* of failure.

## Validation Gate Patterns

### 1. Explicit Runtime Contract

Replace implicit environment detection with a purpose-built validation script that runs as the first pipeline step.

```bash
#!/usr/bin/env bash
# runtime-contract.sh - Assert all preconditions before pipeline proceeds
set -euo pipefail

ERRORS=0
check() { if ! "$@" >/dev/null 2>&1; then echo "FAIL: $*"; ERRORS=$((ERRORS+1)); fi; }

check test -f /opt/app/sentinel.ready
check command -v python3
check python3 -c "import required_module"
check test -n "${DATABASE_URL:-}"
check curl -sf http://localhost:2773/health

if [ "$ERRORS" -gt 0 ]; then
    echo "Runtime contract failed ($ERRORS checks). Aborting pipeline."
    exit 1
fi
echo "Runtime contract passed."
```

**When to use:** Shell compatibility failures, implicit detection failures (e.g., checking for `.git`), missing dependency errors.

### 2. Sentinel File

Replace implicit detection (like checking if `.git` exists) with an explicit marker file written during build.

```bash
# During build/bake:
echo "$(date -Iseconds) | $(git rev-parse HEAD)" > /opt/app/.build-sentinel

# During deploy validation:
if [ ! -f /opt/app/.build-sentinel ]; then
    echo "ERROR: Build sentinel missing - artifact was not built correctly"
    exit 1
fi
```

**When to use:** When a pipeline relies on detecting artifacts or state by their side effects rather than explicit markers.

### 3. Canary Validation

Validate an artifact on a single instance before promoting to the fleet.

```bash
# validate-canary.sh - Test on one instance before fleet rollout
CANARY_INSTANCE="$1"
ARTIFACT="$2"

# Deploy to canary only
deploy_to "$CANARY_INSTANCE" "$ARTIFACT"

# Capability check - not just liveness
if ! curl -sf "http://${CANARY_INSTANCE}:8080/ready"; then
    echo "FAIL: Canary liveness check failed"
    rollback "$CANARY_INSTANCE"
    exit 1
fi

# Verify the service can actually perform its function
if ! curl -sf "http://${CANARY_INSTANCE}:8080/health/deep"; then
    echo "FAIL: Canary capability check failed"
    rollback "$CANARY_INSTANCE"
    exit 1
fi

echo "Canary passed. Proceeding with fleet rollout."
```

**When to use:** Deployment failures that only surface under real traffic or in production environments.

### 4. Auth Bootstrap Validation

Validate credentials and tokens before any deploy work begins.

```bash
# Validate early, not at first use
check_auth() {
    # Verify credentials exist AND are usable
    aws sts get-caller-identity >/dev/null 2>&1 || return 1
    # Verify we can actually access the resource we need
    aws secretsmanager describe-secret --secret-id "$SECRET_NAME" >/dev/null 2>&1 || return 1
}

if ! check_auth; then
    echo "Auth bootstrap failed. Fix credentials before proceeding."
    exit 1
fi
```

**When to use:** Repeated auth/permission failures, token expiration issues, credential bootstrapping errors.

### 5. Capability-Based Readiness

Check that a service can *do its job*, not just that it responds to pings.

```bash
# Bad: liveness only
curl -sf http://localhost:8080/ping

# Good: capability check - verify the service can access its dependencies
curl -sf http://localhost:8080/health/deep
# Returns 200 only if DB connected, secrets loaded, required APIs reachable
```

**When to use:** Services that pass liveness checks but fail on first real request because dependencies are not ready.

### 6. Deploy Lock

Prevent concurrent deploys on shared infrastructure.

```bash
LOCK_FILE="/var/lock/deploy-${SERVICE_NAME}.lock"
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "Another deploy is running for $SERVICE_NAME. Waiting..."
    flock 200
fi
# ... deploy proceeds with exclusive lock
```

**When to use:** Resource contention errors, port conflicts, Docker host contention.

## Pattern Detection

The `lib/cicd/failure_patterns` module can scan `.claude/runs/` and `.claude/deploy.log` to automatically detect repeated failure categories:

```python
from lib.cicd.failure_patterns import analyze_failure_patterns
report = analyze_failure_patterns()
if report.has_patterns:
    print(report.summary())
```

Failure categories detected: `shell-compat`, `implicit-detection`, `config-drift`, `auth-bootstrap`, `dependency-missing`, `resource-contention`.

## When to Propose Hardening

1. **Two or more failures from the same root cause** in run history or deploy log
2. **User explicitly mentions** repeated pipeline/deploy failures
3. **Post-mortem context** - user describes an incident that was a symptom fix

Do not just fix the bug - harden the pipeline against the category of failure.

## Related

- `/self-improvement:deployment` - Retrospective analysis (now includes pattern detection)
- `/cicd:health` - Runtime health checks
- `/cicd:smoke` - Post-deploy smoke tests
- `docs/skills/cicd-verification.md` - CI/CD verification patterns
