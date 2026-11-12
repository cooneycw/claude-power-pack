---
description: Create a new GitHub issue in claude-power-pack
allowed-tools: Bash(gh issue create:*), Bash(gh auth status:*)
---

# Create GitHub Issue

Create a new issue in the claude-power-pack repository.

## Prerequisites Check

First, verify GitHub CLI authentication:
```bash
gh auth status
```

If not authenticated, the user needs to run `gh auth login`.

## What the Body Must Make Legible

Whatever the type, the body an agent later implements from is a contract. Write it so
a reader can tell these apart: the intended **outcome** and why it matters, the
**constraints** that bound it and the rationale behind each, the **acceptance** that
shows the outcome was reached, any **proposed approach** (a revisable hypothesis, not
an order), and **assumptions** worth checking.

These are distinctions, not required headings. A routine bug report that says what
broke, what should happen instead, how to reproduce it and where the behaviour
came from has already satisfied the contract; do not pad it with an invented proposed solution or assumptions nobody
holds. Keep a suggested fix phrased as a suggestion, so an implementer who finds a
better one is free to use it and report the substitution.

The canonical definition, the outcome-versus-proposal test, and worked examples are
in [the issue contract](../../../docs/agents/issue-contract.md). For work large
enough to warrant a specification, reference the spec and the sections that govern
the issue rather than copying them.

## Issue Creation Flow

### Step 1: Ask Issue Type

Ask the user which type of issue they want to create:

1. **Best Practice Suggestion** - Suggest a new technique or tip
2. **Documentation Correction** - Report errors or outdated info
3. **Feature Request** - Request new commands/skills/capabilities
4. **Bug Report** - Report bugs in MCP server or commands

### Step 2: Gather Information

Based on the issue type, gather the required information, one question at a time:

**For Best Practice:**
- Title (required)
- Category: Skills & Activation, MCP Optimization, Session Management, Context
  Efficiency, CLAUDE.md Configuration, Hooks & Automation, Workflow Patterns, Plan
  Mode, Code Quality, or Other
- Description (required)
- Example (optional)
- Source (optional)

**For Correction:**
- Document name
- Section/location
- Current content
- Suggested correction
- Reason for change

**For Feature Request:**
- Feature type (command, skill, MCP, etc.)
- Feature name
- Problem/use case (the outcome wanted, and why it matters)
- Proposed approach (optional, and recorded as revisable)
- Constraints, each with the rationale behind it (optional)

**For Bug Report:**
- Component affected
- Bug description
- Steps to reproduce
- Origin: which issue or pull request delivered the behaviour that broke.
  Write it in the body as an `Origin:` line - `#N`, `never worked`, or
  `not traced - <what was tried>` - from the Origin list in
  [the closing-report contract](../../../docs/agents/closing-report-contract.md#a-report-that-closes-a-defect-says-where-it-came-from).
  Ask the user; never guess a number. Blank is not an answer.
- Error message (if any)
- Environment details

### Step 3: Create Issue

Use the `gh` CLI to create the issue:

```bash
gh issue create \
  --repo cooneycw/claude-power-pack \
  --title "TITLE" \
  --body "BODY" \
  --label "LABELS"
```

**Labels by type:**
- Best Practice: `enhancement,best-practice`
- Correction: `documentation,correction`
- Feature Request: `enhancement,feature-request`
- Bug Report: `bug`

### Step 4: Confirm

After creation:
1. Display the issue URL
2. Offer to open in browser: `gh issue view NUMBER --web --repo cooneycw/claude-power-pack`
