---
description: Create a new feature specification
---

# Create Feature Specification

Create a new feature spec directory with templates for spec, plan, and tasks.

## Arguments

`/spec:create {feature-name}`

- `{feature-name}`: Kebab-case name for the feature (e.g., `user-authentication`, `api-refactor`)

## Execution Steps

### Step 1: Validate Arguments

If no feature name provided, ask:

> "What should the feature be named? Use kebab-case (e.g., `user-authentication`, `payment-flow`)"

Validate the name:
- Must be kebab-case (lowercase, hyphens)
- No spaces or special characters
- Descriptive but concise

### Step 2: Check Prerequisites

```bash
if [ ! -d ".specify" ]; then
    echo "Error: .specify/ not found. Run /spec:init first."
    exit 1
fi

if [ -d ".specify/specs/{feature-name}" ]; then
    echo "Error: Spec already exists at .specify/specs/{feature-name}/"
    exit 1
fi
```

### Step 3: Create Feature Directory

```bash
mkdir -p .specify/specs/{feature-name}
```

### Step 4: Create spec.md

Create `.specify/specs/{feature-name}/spec.md` from template:

```markdown
# Feature Specification: {FEATURE_NAME_TITLE}

> **Branch:** `issue-{N}-{feature-name}`
> **Created:** {DATE}
> **Status:** Draft

---

## Overview

{Describe what this feature does and why it's needed.}

---

## User Stories

### US1: {Primary User Story} [P1]

**As a** {role},
**I want** {capability},
**So that** {benefit}.

**Acceptance Criteria:**
- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] {Criterion 3}

**Test Scenarios:**
1. Given {context}, when {action}, then {result}

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| {Edge case 1} | {Behavior} |

---

## Out of Scope

- {What this feature explicitly does NOT include}

---

## Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | {Requirement} | Must | US1 |

---

## Success Criteria

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Documentation updated

---

## Open Questions

- [ ] {Question 1}

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
```

Replace:
- `{FEATURE_NAME_TITLE}`: Title-cased version (e.g., "User Authentication")
- `{feature-name}`: The provided feature name
- `{DATE}`: Today's date
- `{N}`: Leave as placeholder for issue number

### Step 5: Create plan.md

Create `.specify/specs/{feature-name}/plan.md` from template:

```markdown
# Implementation Plan: {FEATURE_NAME_TITLE}

> **Spec:** [spec.md](./spec.md)
> **Created:** {DATE}
> **Status:** Draft

---

## Summary

{One-paragraph summary of the technical approach.}

---

## Constitution Check

- [ ] Aligns with project principles
- [ ] Follows established patterns
- [ ] Minimizes complexity

---

## Technical Context

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Language | Python 3.11+ | {Why} |
| Testing | pytest | Standard |

---

## Architecture

{Describe component relationships.}

---

## Implementation Phases

### Phase 1: Core

| Task ID | Description | Files |
|---------|-------------|-------|
| T001 | {Task} | `path/file.py` |

---

## Risks

| Risk | Mitigation |
|------|------------|
| {Risk} | {Mitigation} |

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
```

### Step 6: Create tasks.md

Create `.specify/specs/{feature-name}/tasks.md` from template:

```markdown
# Tasks: {FEATURE_NAME_TITLE}

> **Plan:** [plan.md](./plan.md)
> **Created:** {DATE}
> **Status:** Draft

---

## Task Format

`[ID] [P?] [Story] Description`

- **ID**: T001, T002, etc.
- **[P]**: Parallelizable task
- **[Story]**: US1, US2, etc.

---

## Wave 1: Core Implementation

- [ ] **T001** [US1] {Task description} `path/to/file.py`
- [ ] **T002** [US1] {Task description} (depends on T001)

**Checkpoint:** Core functionality works

---

## Wave 2: Integration

- [ ] **T003** [US1] Integration testing
- [ ] **T004** [P] Documentation updates

**Checkpoint:** All tests pass

---

## Issue Sync

Use `/spec:sync {feature-name}` to create GitHub issues.

| Wave | Tasks | Issue | Status |
|------|-------|-------|--------|
| Wave 1 | T001-T002 | - | pending |
| Wave 2 | T003-T004 | - | pending |

---

*Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License)*
```

### Step 7: Output Summary

```
Feature spec created: {feature-name}

Created:
  .specify/specs/{feature-name}/
  ├── spec.md      <- Define requirements here
  ├── plan.md      <- Technical approach
  └── tasks.md     <- Actionable items

Next steps:
1. Edit spec.md with user stories and requirements
2. Edit plan.md with technical approach
3. Edit tasks.md with actionable items
4. Run /spec:sync {feature-name} to create GitHub issues
```

## Examples

```
/spec:create user-authentication
/spec:create api-rate-limiting
/spec:create dashboard-redesign
```

## Notes

- Feature names should be descriptive but concise
- Each feature gets its own spec directory
- Specs can reference each other for dependencies
