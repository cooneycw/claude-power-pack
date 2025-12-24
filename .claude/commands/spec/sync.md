---
description: Sync tasks.md to GitHub issues
---

# Sync Spec Tasks to GitHub Issues

Parse tasks.md and create/update GitHub issues for each wave.

## Arguments

`/spec:sync [feature-name]`

- `[feature-name]`: Optional. If not provided, syncs all features with pending tasks.

## Execution Steps

### Step 1: Find Specs to Sync

If feature-name provided:
```bash
SPEC_DIR=".specify/specs/{feature-name}"
if [ ! -d "$SPEC_DIR" ]; then
    echo "Error: Spec not found at $SPEC_DIR"
    exit 1
fi
```

If not provided, find all specs with tasks.md:
```bash
find .specify/specs -name "tasks.md" -type f
```

### Step 2: Parse tasks.md

For each tasks.md, extract:

1. **Feature name** from directory path
2. **Waves** by parsing `## Wave N:` headers
3. **Tasks** by parsing `- [ ] **T00N** [USN] Description` lines
4. **Issue sync table** at bottom of file

Example parsing:
```
## Wave 1: Core Implementation
- [ ] **T001** [US1] Create user model `lib/models/user.py`
- [ ] **T002** [US1] Add validation (depends on T001)

## Wave 2: Integration
- [ ] **T003** [P] [US1] Integration tests
```

Becomes:
```
Wave 1:
  - T001: Create user model
  - T002: Add validation
Wave 2:
  - T003: Integration tests
```

### Step 3: Check Existing Issues

For each wave, check if an issue already exists:

```bash
# Look for issues with feature-name and wave labels
gh issue list --label "{feature-name}" --label "wave-N" --json number,title,state
```

### Step 4: Create Issues for Pending Waves

For each wave without an issue, create one:

**Issue Title:**
```
[Wave N] {Feature Name Title}: {Wave Description}
```

**Issue Body:**
```markdown
## Parent Spec

Feature: `{feature-name}`
Spec: `.specify/specs/{feature-name}/spec.md`
Plan: `.specify/specs/{feature-name}/plan.md`

## Tasks

{List of tasks from this wave}

- [ ] **T001** [US1] {Description} `{file_path}`
- [ ] **T002** [US1] {Description} (depends on T001)

## Acceptance Criteria

{Extracted from spec.md for relevant user stories}

## Files to Modify

{List of file paths from tasks}

---

*Created from spec via `/spec:sync`*
```

**Issue Labels:**
- `{feature-name}` (feature label)
- `wave-N` (wave label)
- `enhancement` (type)

**Command:**
```bash
gh issue create \
  --title "[Wave 1] {Feature}: {Description}" \
  --body "{body}" \
  --label "{feature-name},wave-1,enhancement"
```

### Step 5: Update tasks.md

After creating issues, update the Issue Sync table in tasks.md:

```markdown
## Issue Sync

| Wave | Tasks | Issue | Status |
|------|-------|-------|--------|
| Wave 1 | T001-T002 | #42 | open |
| Wave 2 | T003-T004 | #43 | open |
```

### Step 6: Output Summary

```
Sync complete for: {feature-name}

Issues created:
  #42 - [Wave 1] User Auth: Core Implementation
  #43 - [Wave 2] User Auth: Integration

Issues already exist (skipped):
  #40 - [Wave 0] User Auth: Research (closed)

Updated:
  .specify/specs/{feature-name}/tasks.md

Next steps:
1. View issues: gh issue list --label {feature-name}
2. Start work: git worktree add -b issue-42-user-auth ../project-issue-42
3. Check status: /spec:status
```

## Dry Run Mode

Add `--dry-run` to preview without creating issues:

```
/spec:sync user-authentication --dry-run
```

Output shows what would be created without making changes.

## Examples

```
# Sync specific feature
/spec:sync user-authentication

# Sync all features
/spec:sync

# Preview changes
/spec:sync user-authentication --dry-run
```

## Issue Template Integration

The created issues follow the project's micro-issue template format, compatible with Issue-Driven Development workflow.

## Notes

- Each wave becomes one GitHub issue
- Tasks within a wave are tracked as checkboxes in the issue
- Issue numbers are written back to tasks.md for traceability
- Re-running sync skips existing issues (idempotent)
