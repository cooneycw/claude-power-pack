---
description: Overview of spec-driven development commands
---

# Spec-Driven Development Commands

Spec-driven development in CPP is the **official GitHub spec-kit** for authoring plus
`/flow:auto` for shipping. CPP's home-grown pipeline (`/spec:create`, `/spec:sync`,
`/spec:status`, `/spec:init`, backed by `lib/spec_bridge`) was retired in favor of
upstream spec-kit (epic #417 Phase A, decision on #418): spec-kit's prompts are
community-iterated and its plugin ships verification stages CPP lacked
(`/speckit-clarify`, `/speckit-analyze`, `/speckit-checklist`).

## Overview

Spec-Driven Development (SDD) ensures quality by requiring specifications before implementation:

```
Constitution (principles) → Spec (what) → Plan (how) → Tasks (work) → Issues → Code
```

## Available Commands

| Command | Description |
|---------|-------------|
| `/spec:adopt` | **(supported)** Install the official spec-kit CLI + scaffold it into the project |
| `/spec:help` | This help overview |

Authoring itself is done with the upstream `/speckit-*` skills that `/spec:adopt`
installs, not with CPP-specific commands.

## Supported Workflow

1. **Adopt spec-kit** (once per project):
   ```
   /spec:adopt
   ```
   Installs the `specify` CLI and runs `specify init --here --ai claude`, which drops
   the `/speckit-*` skills into `.claude/skills/` and scaffolds `.specify/`.

2. **Author with the upstream skills:**
   ```
   /speckit-constitution   # project principles (once per project)
   /speckit-specify        # what to build
   /speckit-clarify        # de-risk ambiguity      (recommended)
   /speckit-plan           # how to build it
   /speckit-tasks          # break into tasks.md
   /speckit-analyze        # cross-artifact consistency check (recommended)
   ```

3. **Turn tasks into GitHub issues** (gh-CLI, no github-mcp-server needed):
   ```
   ./scripts/speckit-tasks-to-issues.sh --dry-run   # preview
   ./scripts/speckit-tasks-to-issues.sh             # create issues
   ```
   > Upstream `/speckit-taskstoissues` requires github-mcp-server (which CPP does not
   > run); the bundled gh-CLI script is the CPP-supported substitute.

4. **Ship each issue** through CPP's gate policy:
   ```
   /flow:auto <issue>
   ```

## Directory Structure

`/spec:adopt` delegates to `specify init`, which scaffolds `.specify/` with the current
upstream templates:

```
.specify/
├── memory/
│   └── constitution.md    # Project principles (edit this!)
├── specs/
│   └── {feature-name}/    # spec.md, plan.md, tasks.md
└── templates/
```

## Integration with IDD

- Tasks become GitHub issues via `scripts/speckit-tasks-to-issues.sh`
- Each issue ships through `/flow:auto` (worktree → ELI5 gate → implement → PR → merge)
- `/project:next` surfaces open issues for prioritization

## Attribution

Based on [GitHub Spec Kit](https://github.com/github/spec-kit) (MIT License).

See [GitHub Blog: Spec-Driven Development](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/) for methodology details.
