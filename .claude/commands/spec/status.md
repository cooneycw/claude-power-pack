---
description: Show spec/issue alignment status
---

# Spec Status Overview

Display the status of all feature specifications and their alignment with GitHub issues.

## Arguments

`/spec:status [feature-name]`

- `[feature-name]`: Optional. If provided, shows detailed status for that feature only.

## Execution Steps

### Step 1: Check Prerequisites

```bash
if [ ! -d ".specify" ]; then
    echo "No .specify/ directory found. Run /spec:init first."
    exit 0
fi
```

### Step 2: Discover Features

Find all feature spec directories:

```bash
find .specify/specs -mindepth 1 -maxdepth 1 -type d
```

### Step 3: Analyze Each Feature

For each feature, determine:

1. **Spec Status:**
   - `spec.md` exists and has content
   - User stories defined
   - Requirements listed

2. **Plan Status:**
   - `plan.md` exists and has content
   - Architecture defined
   - Phases listed

3. **Tasks Status:**
   - `tasks.md` exists and has content
   - Tasks defined with IDs
   - Waves organized

4. **Issue Sync Status:**
   - Parse Issue Sync table from tasks.md
   - Check each issue exists and its state (open/closed)
   - Identify unsynced waves

### Step 4: Fetch GitHub Issues

Get current issue states:

```bash
# Get all issues with spec-related labels
gh issue list --state all --limit 100 --json number,title,state,labels
```

Match issues to features by:
- Label matching (`{feature-name}`)
- Wave labels (`wave-N`)
- Title patterns (`[Wave N] Feature:`)

### Step 5: Output Summary (All Features)

```
=== Spec Status ===

Feature: user-authentication
  Spec:   ✓ Complete (3 user stories, 5 requirements)
  Plan:   ✓ Complete (2 phases)
  Tasks:  ✓ 8 tasks in 2 waves
  Issues: 2/2 synced
    #42 [Wave 1] Core Implementation - OPEN
    #43 [Wave 2] Integration - OPEN

Feature: api-rate-limiting
  Spec:   ✓ Complete (2 user stories)
  Plan:   ○ Draft (missing architecture)
  Tasks:  ○ 4 tasks, not synced
  Issues: 0/1 synced
    Wave 1: Not synced → Run /spec:sync api-rate-limiting

Feature: dashboard-redesign
  Spec:   ○ Draft (1 user story)
  Plan:   ✗ Missing
  Tasks:  ✗ Missing
  Issues: -

Summary:
  Features: 3
  Synced:   1
  Pending:  2

Next steps:
  - Complete plan for: api-rate-limiting
  - Create tasks for: api-rate-limiting
  - Sync issues for: api-rate-limiting
  - Add plan/tasks for: dashboard-redesign
```

### Step 6: Output Detail (Single Feature)

When a feature name is provided:

```
=== Feature: user-authentication ===

Spec: .specify/specs/user-authentication/spec.md
  Status: Complete
  User Stories:
    US1: User can register with email [P1]
    US2: User can login with credentials [P1]
    US3: User can reset password [P2]
  Requirements: 5 (3 Must, 2 Should)
  Open Questions: 0

Plan: .specify/specs/user-authentication/plan.md
  Status: Complete
  Phases: 2
  Dependencies: 3 packages
  Risks: 2 identified

Tasks: .specify/specs/user-authentication/tasks.md
  Status: Synced
  Waves: 2
  Tasks: 8 total (5 complete, 3 pending)

Issues:
  #42 [Wave 1] Core Implementation
    State: OPEN
    Tasks: 3/5 complete
    Branch: issue-42-user-auth
    Worktree: ../project-issue-42

  #43 [Wave 2] Integration
    State: OPEN
    Tasks: 0/3 complete
    Branch: (not created)

Timeline:
  Created: 2025-12-20
  Last Updated: 2025-12-24
  Issues Created: 2025-12-21
```

## Status Indicators

| Symbol | Meaning |
|--------|---------|
| ✓ | Complete/Synced |
| ○ | Draft/Partial |
| ✗ | Missing |
| - | Not applicable |

## Examples

```
# Show all specs
/spec:status

# Show specific feature
/spec:status user-authentication

# Quick check for unsynced
/spec:status | grep "Not synced"
```

## Integration

Status information can also be seen in:
- `/project-next` (shows spec features alongside issues)
- GitHub issue descriptions (link to spec files)
