---
description: Initialize .specify/ structure for spec-driven development
---

# Initialize Spec-Driven Development

Set up the `.specify/` directory structure for spec-driven development in this project.

## What This Does

1. Creates the `.specify/` directory structure
2. Copies template files for specs, plans, and tasks
3. Creates a starter `constitution.md` for project principles

## Execution Steps

### Step 1: Check if Already Initialized

```bash
if [ -d ".specify" ]; then
    echo "Already initialized: .specify/ directory exists"
    ls -la .specify/
    exit 0
fi
```

If `.specify/` exists, show its contents and stop.

### Step 2: Create Directory Structure

Create the following directories:

```bash
mkdir -p .specify/memory
mkdir -p .specify/specs
mkdir -p .specify/templates
mkdir -p .specify/scripts
```

### Step 3: Create Constitution Template

Create `.specify/memory/constitution.md` with this content:

```markdown
# Project Constitution

> Governing principles for {PROJECT_NAME}.
> All specifications and implementations must align with these principles.

---

## Core Principles

### P1: {First Principle}

{Description of the principle and how it guides development.}

### P2: {Second Principle}

{Description of the principle and how it guides development.}

### P3: {Third Principle}

{Description of the principle and how it guides development.}

---

## Development Workflow

1. Write specification before code
2. Review spec for completeness
3. Create technical plan
4. Break into tasks
5. Sync tasks to issues
6. Implement with tests

---

## Governance

- All PRs must align with constitution
- Violations require documented justification
- Constitution changes require team discussion

---

## Attribution

Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).

---

*Created: {DATE}*
```

Replace `{PROJECT_NAME}` with the repository name and `{DATE}` with today's date.

### Step 4: Copy Templates

Copy the spec, plan, and tasks templates from claude-power-pack if available, or create minimal versions:

**spec-template.md:**
```markdown
# Feature Specification: {FEATURE_NAME}

## Overview
{Brief description}

## User Stories

### US1: {Story Title}
**As a** {role}, **I want** {capability}, **So that** {benefit}.

**Acceptance Criteria:**
- [ ] {Criterion}

## Requirements
| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | {Requirement} | Must |

## Success Criteria
- [ ] All acceptance criteria met
- [ ] Tests passing
```

**plan-template.md:**
```markdown
# Implementation Plan: {FEATURE_NAME}

## Summary
{Technical approach}

## Architecture
{Component design}

## Dependencies
| Package | Purpose |
|---------|---------|

## Phases
| Phase | Tasks | Dependencies |
|-------|-------|--------------|
```

**tasks-template.md:**
```markdown
# Tasks: {FEATURE_NAME}

## Format
`[ID] [P?] [Story] Description`

## Wave 1
- [ ] **T001** [US1] {Task description}

## Issue Sync
| Task | Issue | Status |
|------|-------|--------|
```

### Step 5: Add to .gitignore (Optional)

Ask the user if they want to add any `.specify/` patterns to `.gitignore`:

> "The `.specify/` directory has been created. Do you want to add any exclusions to .gitignore? (Typically, everything is tracked)"

### Step 6: Output Summary

```
Spec-driven development initialized!

Created:
  .specify/
  ├── memory/
  │   └── constitution.md    <- Edit with your project principles
  ├── specs/                 <- Feature specs go here
  ├── templates/             <- Reusable templates
  │   ├── spec-template.md
  │   ├── plan-template.md
  │   └── tasks-template.md
  └── scripts/               <- Automation scripts

Next steps:
1. Edit .specify/memory/constitution.md with your project principles
2. Use /spec:create {feature-name} to create your first spec
3. See /spec:help for full workflow
```

## Notes

- Constitution should be customized for each project
- Templates can be modified to match team preferences
- Based on GitHub Spec Kit (MIT License)
