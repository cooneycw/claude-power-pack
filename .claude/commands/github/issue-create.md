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

## Issue Creation Flow

### Step 1: Ask Issue Type

Ask the user which type of issue they want to create:

1. **Best Practice Suggestion** - Suggest a new technique or tip
2. **Documentation Correction** - Report errors or outdated info
3. **Feature Request** - Request new commands/skills/capabilities
4. **Bug Report** - Report bugs in MCP server or commands

### Step 2: Gather Information

Based on the issue type, gather the required information:

**For Best Practice:**
- Title (required)
- Category (Skills, MCP, Session Management, etc.)
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
- Problem/use case
- Proposed solution

**For Bug Report:**
- Component affected
- Bug description
- Steps to reproduce
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

## Example Interaction

```
User: /github:issue-create

Claude: What type of issue would you like to create?
1. Best Practice Suggestion
2. Documentation Correction
3. Feature Request
4. Bug Report

User: 1

Claude: Great! Let's create a best practice suggestion.

What's the title of this practice?

User: Use session resets after git commits

Claude: Which category does this practice belong to?
- Skills & Activation
- MCP Optimization
- Session Management
- Context Efficiency
- CLAUDE.md Configuration
- Hooks & Automation
- Workflow Patterns
- Plan Mode
- Code Quality
- Other

User: Session Management

Claude: Please describe the practice and why it's useful.

User: After completing a feature and committing, reset your Claude Code session...

[Claude creates the issue and returns the URL]
```
