---
description: Scan GitHub issues and worktree to recommend prioritized next steps (generic)
allowed-tools: Bash(gh issue list:*), Bash(gh issue view:*), Bash(gh repo view:*), Bash(git worktree:*), Bash(git worktree list:*), Bash(git status:*), Bash(git branch:*), Bash(git log:*), Bash(tree:*), Bash(ls:*), Bash(printf:*), Bash(grep:*), Bash(tmux rename-window:*), Bash(*terminal-label.sh:*), Bash(*session-register.sh:*), Bash(*claim-issue.sh:*)
---

# Project Next Steps Recommendation

Analyze the current project's GitHub issues and worktree state to recommend prioritized next steps.

**IMPORTANT:** Use Plan Mode for this analysis. Enter plan mode immediately to gather information before making recommendations.

---

## Step 1: Enter Plan Mode

Before doing anything else, enter plan mode to systematically gather context.

---

## Step 2: Detect Project Context

### 2.1 Repository Detection

Detect the current repository:

```bash
# Get repository info
gh repo view --json owner,name,description,defaultBranchRef --jq '{owner: .owner.login, name: .name, desc: .description, default_branch: .defaultBranchRef.name}'
```

If this fails, the user is not in a GitHub repository. Stop and inform them.

### 2.2 Prefix Detection

Determine the terminal label prefix using this priority:

1. **Check CLAUDE.md** for a "Terminal Prefix" or "Project Prefix" configuration
2. **Derive from repo name**: Take first letter of each hyphen-separated word, uppercase
   - `nhl-api` → `NHL`
   - `claude-power-pack` → `CPP`
   - `my-django-app` → `MDA`
3. **Fallback**: First 4 characters of repo name, uppercase

### 2.3 Worktree Detection

Check if worktrees are in use:

```bash
# List all worktrees
git worktree list

# Parse to identify:
# - Main repo path
# - Worktree paths and branches
# - Issue numbers from branch names (pattern: issue-{N}-*)
```

If only one worktree (the main repo), note that worktrees are not in use.

---

## Step 3: Gather GitHub Issues

Fetch open issues with metadata:

```bash
# List all open issues
gh issue list --state open --limit 50

# For important issues, get details
gh issue view <NUMBER>
```

### 3.1 Categorize Issues

Group issues by type based on labels and title patterns:

| Category | Detection Method |
|----------|------------------|
| **CRITICAL** | Labels: `bug` + `priority-high`, `security`, `blocker` |
| **BUGS** | Labels: `bug` (without priority-high) |
| **FEATURES** | Labels: `feature`, `enhancement`, `feature-request` |
| **DOCUMENTATION** | Labels: `documentation`, `docs` |
| **TECH DEBT** | Labels: `refactor`, `cleanup`, `technical-debt`, `chore` |
| **PLANNING** | Title starts with "Wave", "Phase", or "Plan" |
| **OTHER** | No matching labels |

### 3.2 Detect Issue Hierarchy

Look for parent-child relationships:

| Pattern | Example | Detection |
|---------|---------|-----------|
| Wave/Phase | `Wave 5c.3: Title` | Title regex: `^(Wave|Phase)\s+[\d.]+[a-z]?[\d.]*:` |
| Parent Reference | `**Parent Issue:** #63` | Body contains `Parent Issue:.*#\d+` |
| Epic Link | `Part of #25` | Body contains `Part of #\d+` or `Related:.*#\d+` |

---

## Step 4: Analyze Worktree State

For each worktree, check:

```bash
# Check status of each worktree
git -C <worktree_path> status --short

# Check recent commits
git -C <worktree_path> log --oneline -5

# Check branch info
git -C <worktree_path> branch -vv
```

Look for:
- **Uncommitted changes** - Work in progress
- **Stale branches** - No commits in 7+ days
- **Merged but open** - Branch merged to main but issue still open
- **Divergence** - Branches that need rebasing

---

## Step 4b: Check Session Coordination State

If coordination scripts are installed, check for active sessions and locks:

```bash
# Check active locks
~/.claude/scripts/session-lock.sh list 2>/dev/null

# Check active sessions
~/.claude/scripts/session-register.sh status 2>/dev/null
```

### Session Coordination Analysis

For each worktree, check if another session is working on it using tiered staleness:

| Status | Heartbeat Age | Meaning |
|--------|---------------|---------|
| 🟢 **Active** | < 5 min | Actively using Claude Code |
| 🟡 **Idle** | 5 min - 1 hour | Stepped away briefly |
| 🟠 **Stale** | 1 - 4 hours | Gone for extended period |
| ⚫ **Abandoned** | > 24 hours | Auto-released next day |

**Conflict Prevention:**
- **Active/Idle**: Block claim, suggest alternative issues
- **Stale**: Allow override with warning
- **Abandoned**: Auto-released, freely available

**Include in recommendations:**
- Mark issues with active/idle sessions as claimed with status indicator
- Show time since last heartbeat for context
- Highlight locks that may block operations

---

## Step 4c: Get Claimed Issues

Check which issues are already claimed by other active Claude Code sessions:

```bash
# Get the repo info
REPO_INFO=$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')

# List all active claims for this repository
~/.claude/scripts/session-register.sh list-claims "$REPO_INFO" 2>/dev/null
```

### Claim Filtering

When presenting issues, the `list-claims` output now includes a `status` field with tiered values:

1. **Parse claim list**: Each claim includes `status: "active"|"idle"` and `heartbeat_age`
2. **Current session's claim is OK**: Don't filter the current session's own claim
3. **Active/Idle sessions block**: Claims from sessions with status "active" or "idle" are blocked
4. **Stale sessions allow override**: Show warning but don't block

Display claimed issues with their tier status:
- 🟢 `[CLAIMED - Active (2m)]` - definitely in use
- 🟡 `[CLAIMED - Idle (15m)]` - probably still in use, warn before taking

---

## Step 5: Cross-Reference Analysis

Compare issues against worktree state:

1. **Issue-to-Branch Mapping**: Match issue numbers in branch names (`issue-{N}-*`)
2. **Issue-to-Worktree Mapping**: Map worktree directories to issue numbers
3. **Orphaned Work**: Branches without corresponding open issues
4. **Blocked Issues**: Issues waiting on parent completion

---

## Step 6: Generate Recommendations

Create a prioritized list of next steps:

### Priority 1: Critical/Blocking
- Security issues
- Breaking bugs
- Deployment blockers

### Priority 2: Active Work (In Progress)
- Issues with existing worktrees
- Issues with uncommitted changes

### Priority 3: Ready to Start
- Child issues of completed parent waves
- Issues with clear acceptance criteria
- Issues with no blockers

### Priority 4: Quick Wins
- Low effort issues
- Documentation updates
- Simple fixes

### Priority 5: Planning/Discussion
- Wave/Phase planning issues
- Feature discussions
- Architecture decisions

---

## Step 7: Output Format

Present findings as:

```markdown
## {REPO_NAME} - Recommended Next Steps

### Current State Summary
- **Repository:** {owner}/{name}
- **Open Issues:** {count} ({critical} critical, {bugs} bugs, {features} features)
- **Worktrees:** {count} active
  - {worktree_path} ({branch}) - Issue #{N}
- **Uncommitted Work:** {list or "None"}

### Issue Hierarchy
- **Waves/Phases in Progress:** {list with status}
- **Blocked Issues:** {count} (waiting on parent completion)

### Priority Actions

1. **[CRITICAL]** Issue #{N}: {Title}
   - **Why:** {reasoning}
   - **Effort:** Small/Medium/Large
   - **Status:** {In worktree | Branch exists | Ready to start}
   - **Command:** `git worktree add -b issue-{N}-desc ../{repo}-issue-{N}`

2. **[HIGH]** Issue #{N}: {Title}
   - **Parent:** #{parent_N} ({status})
   - **Why:** {reasoning}
   - **Effort:** {estimate}

3. **[MEDIUM]** Issue #{N}: {Title}
   - **Why:** {reasoning}

### Worktree Status

| Directory | Branch | Issue | Status | Session |
|-----------|--------|-------|--------|---------|
| {path} | issue-{N}-desc | #{N} | Uncommitted changes | session-abc (active) |
| {path} | issue-{M}-desc | #{M} | Clean | - |

### Active Coordination

**Locks:**
- `pytest-{repo}` held by session-xyz (120s remaining)
- ...

**Sessions:**
- session-abc: working on #{N} in {worktree} (last heartbeat: 5s ago)
- ...

### Claimed by Other Sessions

| Issue | Title | Session | Status | Last Heartbeat |
|-------|-------|---------|--------|----------------|
| #{N} | {Title} | tmux-%2 | 🟢 Active | 2m ago |
| #{M} | {Title} | pid-1234 | 🟡 Idle | 25m ago |

*Active/Idle claims are blocked. Stale claims (>4h) can be overridden with warning.*

### Recommendations
- **Cleanup:** {worktrees with merged branches}
- **Stale:** {worktrees with no recent commits}
```

---

## Step 8: Set Terminal Label

Before presenting follow-up options, set the terminal label:

```bash
# Set terminal to project selection mode
~/.claude/scripts/terminal-label.sh project "{PREFIX}"
```

Replace `{PREFIX}` with the detected project prefix.

---

## Step 9: Present Follow-up Options

After presenting recommendations, offer:

1. **Start Priority #1** - Create worktree and begin work on top priority
2. **View Issue Details** - Get full details on any specific issue
3. **Create New Issue** - Document discovered work
4. **Clean Up** - Remove stale worktrees/branches
5. **Refresh** - Re-scan for updates

---

## Step 10: Handle User Selection

When the user selects an issue to work on, follow this sequence:

### 10.1 Check Availability

```bash
# Verify issue is still available (may have been claimed since analysis)
~/.claude/scripts/claim-issue.sh --check {NUMBER}
```

If claimed, inform user and suggest alternatives.

### 10.2 Claim the Issue

```bash
# Get repo info for claim
REPO_INFO=$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')

# Claim the issue (registers in session coordination)
~/.claude/scripts/session-register.sh claim "$REPO_INFO" {NUMBER} "{Title}"
```

### 10.3 Set Terminal Label

```bash
# Set terminal label to reflect active issue
~/.claude/scripts/terminal-label.sh issue "{PREFIX}" {NUMBER} "{Short Title}"
```

### 10.4 Create Worktree (if needed)

If the issue doesn't have an existing worktree:

```bash
# Create worktree for the issue
git worktree add -b issue-{N}-{description} ../{repo}-issue-{N}
```

### 10.5 Confirmation

Report to user:
- Issue #{N} claimed by this session
- Terminal label set
- Worktree created (if applicable)
- Ready to begin work

---

## Notes for Non-Worktree Repositories

If the repository doesn't use worktrees (only main worktree detected):

1. Skip worktree analysis sections
2. Focus on branch-to-issue mapping
3. Suggest worktree setup for complex projects:
   > "Consider using git worktrees for parallel issue development. Run `/django:worktree-explain` to learn more."

---

## Configuration via CLAUDE.md

Projects can optionally add this configuration block to their CLAUDE.md:

```markdown
## Project-Next Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| **Terminal Prefix** | NHL | Short prefix for terminal labels |
| **Issue Pattern** | wave | Hierarchy style: wave, epic, parent-child, flat |
| **Priority Labels** | critical, urgent | Labels indicating critical priority |
```
