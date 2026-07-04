---
description: List and search GitHub issues in claude-power-pack
allowed-tools: Bash(gh issue list:*), Bash(gh auth status:*)
---

# List GitHub Issues

List and search issues in the claude-power-pack repository.

## Default Behavior

If the user just runs `/github:issue-list` without specifying filters, show open issues:

```bash
gh issue list --repo cooneycw/claude-power-pack --state open --limit 20
```

## Available Filters

Ask the user if they want to apply any filters:

### State Filter
- `open` (default) - Open issues only
- `closed` - Closed issues only
- `all` - All issues

### Label Filter
Common labels:
- `best-practice` - Best practice suggestions
- `correction` - Documentation corrections
- `feature-request` - Feature requests
- `bug` - Bug reports
- `enhancement` - Enhancements
- `documentation` - Documentation related

### Search Filter
Search issue titles and bodies:
```bash
gh issue list --repo cooneycw/claude-power-pack --search "QUERY"
```

### Author/Assignee Filter
- `--author USERNAME` - Issues created by specific user
- `--assignee USERNAME` - Issues assigned to specific user
- `--assignee @me` - Issues assigned to current user

## Command Examples

```bash
# Open issues (default)
gh issue list --repo cooneycw/claude-power-pack --state open --limit 20

# Filter by label
gh issue list --repo cooneycw/claude-power-pack --label "best-practice"

# Search issues
gh issue list --repo cooneycw/claude-power-pack --search "MCP token"

# Closed issues
gh issue list --repo cooneycw/claude-power-pack --state closed --limit 10

# My issues
gh issue list --repo cooneycw/claude-power-pack --author @me

# Combine filters
gh issue list --repo cooneycw/claude-power-pack --state open --label "bug" --limit 10
```

## Output Format

Present results in a clean table format:

```
#    TITLE                                    LABELS              UPDATED
42   Use Plan Mode for complex refactors      best-practice       2h ago
38   MCP server fails on Python 3.12          bug                 1d ago
35   Add /test:setup command                  feature-request     3d ago
```

## Follow-up Options

After listing issues, offer:
1. View a specific issue: `/github:issue-view NUMBER`
2. Refine search with different filters
3. Create a new issue: `/github:issue-create`
