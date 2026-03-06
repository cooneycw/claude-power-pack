---
description: Run quality checks (lint + security) without committing
allowed-tools: Bash(make:*), Bash(grep:*), Bash(test:*), Bash(python3:*), Bash(PYTHONPATH=*), Bash(git:*), Read
---

# Flow: Check - Run Quality Gates Without Committing

Run lint and security checks to verify code quality. Does not commit, push, or create a PR.

Use this to validate your changes before running `/flow:finish`.

## Instructions

When the user invokes `/flow:check`, perform these steps:

### Step 1: Detect Available Checks

```bash
CHECKS_RUN=0
CHECKS_PASS=0
CHECKS_WARN=0
CHECKS_FAIL=0

# Detect Makefile targets
HAS_LINT=false
HAS_TEST=false
if [[ -f "Makefile" ]]; then
    grep -q "^lint:" Makefile && HAS_LINT=true
    grep -q "^test:" Makefile && HAS_TEST=true
fi

# Detect security scanner
HAS_SECURITY=false
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/lib/security/__init__.py" ]; then
    CPP_DIR="$dir"
    HAS_SECURITY=true
    break
  fi
done

# Detect Makefile completeness checker
HAS_CICD=false
if [ -n "$CPP_DIR" ] && [ -f "$CPP_DIR/lib/cicd/__init__.py" ]; then
    HAS_CICD=true
fi
```

### Step 2: Run Lint

```bash
if [[ "$HAS_LINT" == "true" ]]; then
    echo "Running: make lint"
    make lint
    LINT_EXIT=$?
    CHECKS_RUN=$((CHECKS_RUN + 1))
    if [[ $LINT_EXIT -eq 0 ]]; then
        CHECKS_PASS=$((CHECKS_PASS + 1))
    else
        CHECKS_FAIL=$((CHECKS_FAIL + 1))
    fi
fi
```

### Step 3: Run Tests

```bash
if [[ "$HAS_TEST" == "true" ]]; then
    echo "Running: make test"
    make test
    TEST_EXIT=$?
    CHECKS_RUN=$((CHECKS_RUN + 1))
    if [[ $TEST_EXIT -eq 0 ]]; then
        CHECKS_PASS=$((CHECKS_PASS + 1))
    else
        CHECKS_FAIL=$((CHECKS_FAIL + 1))
    fi
fi
```

### Step 4: Run Security Quick Scan

```bash
if [[ "$HAS_SECURITY" == "true" ]]; then
    echo "Running: security gate (flow_finish)"
    PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.security gate flow_finish
    SEC_EXIT=$?
    CHECKS_RUN=$((CHECKS_RUN + 1))
    if [[ $SEC_EXIT -eq 0 ]]; then
        CHECKS_PASS=$((CHECKS_PASS + 1))
    elif [[ $SEC_EXIT -eq 2 ]]; then
        # Exit code 2 = warnings only (HIGH findings)
        CHECKS_WARN=$((CHECKS_WARN + 1))
    else
        CHECKS_FAIL=$((CHECKS_FAIL + 1))
    fi
fi
```

### Step 5: Run Makefile Completeness Check (optional)

```bash
if [[ "$HAS_CICD" == "true" ]] && [[ -f "Makefile" ]]; then
    PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd check --summary
    CICD_EXIT=$?
    CHECKS_RUN=$((CHECKS_RUN + 1))
    if [[ $CICD_EXIT -eq 0 ]]; then
        CHECKS_PASS=$((CHECKS_PASS + 1))
    else
        CHECKS_WARN=$((CHECKS_WARN + 1))  # Non-blocking
    fi
fi
```

### Step 6: Report Results

Present a summary report:

```markdown
## Flow Check Results

| Check | Status | Details |
|-------|--------|---------|
| Lint (`make lint`) | PASS/FAIL/SKIP | All checks passed / 3 errors / No Makefile |
| Tests (`make test`) | PASS/FAIL/SKIP | 211 passed / 2 failed / No Makefile |
| Security scan | PASS/WARN/FAIL/SKIP | Clean / 1 HIGH warning / 1 CRITICAL / lib/security not available |
| Makefile completeness | PASS/WARN/SKIP | 6/6 targets / 1 missing / lib/cicd not available |

**Summary: {CHECKS_PASS} passed, {CHECKS_WARN} warnings, {CHECKS_FAIL} failed ({CHECKS_RUN} checks run)**
```

Status symbols:
- **PASS** - Check succeeded
- **WARN** - Non-blocking issue found (proceed with caution)
- **FAIL** - Blocking issue found (fix before `/flow:finish`)
- **SKIP** - Check not available (no Makefile, lib not installed)

### Final Message

Based on results:
- **All pass:** "Ready for `/flow:finish`."
- **Warnings only:** "Warnings found but non-blocking. Review before `/flow:finish`."
- **Failures:** "Failing checks must be fixed before `/flow:finish`."

## Notes

- This command is **read-only** - it never commits, pushes, or modifies files
- It runs the same checks as `/flow:finish` Step 2, extracted for standalone use
- Use it to validate changes before committing or as a pre-flight check
- The security gate uses the same `.claude/security.yml` configuration as `/flow:finish`
