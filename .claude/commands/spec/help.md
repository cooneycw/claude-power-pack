---
description: Overview of all spec-driven development commands
---

# Spec-Driven Development Commands

Manage feature specifications following the GitHub Spec Kit workflow.

## Overview

Spec-Driven Development (SDD) ensures quality by requiring specifications before implementation:

```
Constitution (principles) → Spec (what) → Plan (how) → Tasks (work) → Issues → Code
```

## Available Commands

| Command | Description |
|---------|-------------|
| `/spec:init` | Initialize .specify/ structure in project |
| `/spec:create` | Create a new feature specification |
| `/spec:sync` | Sync tasks.md to GitHub issues |
| `/spec:status` | Show spec/issue alignment status |
| `/spec:help` | This help overview |

## Directory Structure

After `/spec:init`, your project will have:

```
.specify/
├── memory/
│   └── constitution.md    # Project principles (edit this!)
├── specs/
│   └── {feature-name}/    # Created by /spec:create
│       ├── spec.md        # Requirements
│       ├── plan.md        # Technical design
│       └── tasks.md       # Actionable items
└── templates/
    ├── spec-template.md
    ├── plan-template.md
    └── tasks-template.md
```

## Typical Workflow

1. **Initialize** (once per project):
   ```
   /spec:init
   ```
   Then edit `.specify/memory/constitution.md` with your project principles.

2. **Create Feature Spec**:
   ```
   /spec:create user-authentication
   ```
   This creates `.specify/specs/user-authentication/` with templates.

3. **Write Specification**:
   - Edit `spec.md` with user stories and requirements
   - Edit `plan.md` with technical approach
   - Edit `tasks.md` with actionable items

4. **Sync to Issues**:
   ```
   /spec:sync user-authentication
   ```
   Creates GitHub issues from tasks.md with proper labels.

5. **Check Status**:
   ```
   /spec:status
   ```
   Shows which specs have pending tasks or missing issues.

## Integration with IDD

Spec commands integrate with Issue-Driven Development:

- Tasks become GitHub issues with wave labels
- Issues link back to spec files
- `/project-next` shows spec status alongside issues

## Attribution

Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).

See [GitHub Blog: Spec-Driven Development](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/) for methodology details.
