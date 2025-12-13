---
description: Overview of all GitHub issue management commands
---

# GitHub Issue Management Commands

Manage issues in the claude-power-pack repository directly from Claude Code.

## Available Commands

| Command | Description |
|---------|-------------|
| `/github:issue-create` | Create a new issue with guided prompts |
| `/github:issue-list` | List and search issues |
| `/github:issue-view` | View issue details and comments |
| `/github:issue-update` | Update an existing issue |
| `/github:issue-close` | Close an issue |

## Quick Examples

### Create an issue
```
/github:issue-create
```
Then follow the prompts to select issue type and provide details.

### List open issues
```
/github:issue-list
```

### View a specific issue
```
/github:issue-view 42
```

### Close an issue with comment
```
/github:issue-close 42
```

## Issue Types

When creating issues, you can choose from:

- **Best Practice** - Suggest a new best practice or technique
- **Correction** - Report errors or outdated information
- **Feature Request** - Request new commands, skills, or capabilities
- **Bug Report** - Report bugs in MCP server or commands

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated
- Run `gh auth status` to verify authentication

## Target Repository

All commands operate on: `cooneycw/claude-power-pack`
