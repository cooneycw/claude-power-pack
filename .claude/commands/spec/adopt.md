---
description: Install the official GitHub spec-kit and scaffold it into this project
---

# Adopt Official Spec-Kit

Install GitHub's official [spec-kit](https://github.com/github/spec-kit) toolkit and
scaffold it into the current project. This is the **supported** spec-driven-development
authoring path for CPP: use spec-kit's `/speckit-*` skills to author, then `/flow:auto`
to ship.

`/spec:adopt` delegates to the upstream `specify` CLI so you always get the current,
community-iterated templates and the verification stages CPP lacks (`/speckit-clarify`,
`/speckit-analyze`, `/speckit-checklist`). It replaces CPP's retired home-grown pipeline
(`/spec:init`, `/spec:create`, `/spec:sync`, `/spec:status`; see epic #417 Phase A).

## What This Does

1. Ensures the official `specify` CLI is installed and current (via `uv tool`).
2. Runs `specify init --here --ai claude` in the current project, installing the
   `speckit-*` skills into `.claude/skills/` and the `.specify/` scaffold.
3. Prints the authoring workflow and how to turn `tasks.md` into GitHub issues without
   github-mcp-server (CPP is gh-CLI based - see Step 4).

## Prerequisites

- `uv` (Astral) on PATH - `command -v uv`. Install: <https://docs.astral.sh/uv/>.
- `git` (optional but recommended; spec-kit records the remote for issue creation).

## Execution Steps

### Step 1: Ensure the `specify` CLI is installed and current

```bash
if command -v specify > /dev/null 2>&1; then
    echo "specify present: $(specify version 2>/dev/null | head -1 || echo installed)"
    uv tool upgrade specify-cli 2>/dev/null || true
else
    echo "Installing the official spec-kit CLI from github/spec-kit ..."
    uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
fi
command -v specify > /dev/null 2>&1 || { echo "ERROR: specify CLI not on PATH after install (check ~/.local/bin)."; exit 1; }
```

### Step 2: Guard against an existing scaffold

```bash
if [ -d ".specify" ]; then
    echo "NOTE: .specify/ already exists in this project."
    echo "Re-running will overwrite spec-kit templates. Pass --force to proceed:"
    echo "    specify init --here --ai claude --force"
    # Do NOT auto-force; stop and let the user decide.
    exit 0
fi
```

### Step 3: Scaffold the official spec-kit

```bash
specify init --here --ai claude
echo "--- installed spec-kit skills ---"
ls .claude/skills/ | grep '^speckit-' || echo "(none found - check specify output above)"
```

This installs the upstream `speckit-*` skills (constitution, specify, clarify, plan,
tasks, analyze, checklist, implement, taskstoissues) plus `.specify/`.

### Step 4: Report the supported workflow

Print this to the user:

```
Spec-kit installed. Supported CPP workflow:

  1. /speckit-constitution   - project principles (once per project)
  2. /speckit-specify        - what to build
  3. /speckit-clarify        - de-risk ambiguity   (recommended)
  4. /speckit-plan           - how to build it
  5. /speckit-tasks          - break into tasks.md
  6. /speckit-analyze        - cross-artifact consistency check (recommended)
  --> then create issues:  scripts/speckit-tasks-to-issues.sh
  7. /flow:auto <issue>      - ship each issue through CPP's gate policy

Note: upstream /speckit-taskstoissues requires github-mcp-server (which CPP does
not run). Use the bundled gh-CLI sync instead:

  ./scripts/speckit-tasks-to-issues.sh --dry-run          # preview
  ./scripts/speckit-tasks-to-issues.sh                    # create issues
```

## Notes

- **Per-project, not global.** spec-kit scaffolds `.specify/` into a repo; there is no
  global-skills equivalent. Run `/spec:adopt` once per project that uses SDD.
- **Legacy `/spec:*` were retired.** `/spec:create`, `/spec:sync`, `/spec:status`, and
  `/spec:init` (backed by `lib/spec_bridge`) have been removed in favor of this path
  (epic #417 Phase A).
- **Freshness.** Because this delegates to the CLI, you always get the latest upstream
  templates - CPP no longer vendors a (stale) copy of the spec-kit skills.
