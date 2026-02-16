---
description: Scan GitHub issues and worktree to recommend prioritized next steps (generic)
allowed-tools: Bash(gh:*), Bash(git:*), Bash(ls:*), Bash(PYTHONPATH=:*), Bash(for :*), Bash(~/.claude/:*), Bash(sort:*), Bash(printf:*), Read, Glob, Grep
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

Detect the current repository with fallback to `CLAUDE_PROJECT` environment variable:

```bash
# Priority 1: Check for CLAUDE_PROJECT environment variable
if [ -n "$CLAUDE_PROJECT" ]; then
  # If set and not already in a git repo, change to project directory
  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    PROJECT_DIR="$HOME/Projects/$CLAUDE_PROJECT"
    if [ -d "$PROJECT_DIR" ]; then
      cd "$PROJECT_DIR"
    fi
  fi
fi

# Priority 2: Standard git repo detection
gh repo view --json owner,name,description,defaultBranchRef --jq '{owner: .owner.login, name: .name, desc: .description, default_branch: .defaultBranchRef.name}'
```

If this fails:
- If `CLAUDE_PROJECT` is set but directory doesn't exist, inform user: "CLAUDE_PROJECT is set to '{value}' but ~/Projects/{value} doesn't exist"
- If not in a git repo and `CLAUDE_PROJECT` not set, suggest: "Set CLAUDE_PROJECT environment variable or cd to a project directory"

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

### 2.4 Spec-Driven Development Detection

Check if the project uses spec-driven development:

```bash
# Check for .specify directory with feature specs
ls -d .specify/specs/*/ 2>/dev/null | head -10
```

If `.specify/specs/` exists with feature directories, get spec status:

```bash
# Get spec status using Python module (requires lib/spec_bridge)
PYTHONPATH="$PWD/lib:$PYTHONPATH" python -c "
from lib.spec_bridge import get_all_status
status = get_all_status()
for f in status.features:
    indicator = lambda fs: '✓' if fs.exists and fs.complete else ('○' if fs.exists else '✗')
    print(f'{f.name}|{indicator(f.spec)}|{indicator(f.plan)}|{indicator(f.tasks)}|{f.synced_count}|{f.pending_count}')
" 2>/dev/null || echo "spec_bridge not available"
```

Note for output:
- Feature names and their spec/plan/tasks status
- Which features have pending sync (waves without GitHub issues)
- Which features are complete (all waves synced)
- Action needed for features ready to sync

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

### 5.1 Issue-to-Spec Mapping (if .specify/ exists)

For each issue, check if it was created by spec sync:

1. **Label Matching**: Look for labels matching feature names in `.specify/specs/`
2. **Body References**: Check issue body for "Spec:" or "Feature:" references
3. **Wave Title Pattern**: Match issue title with wave names from tasks.md (e.g., "Wave 1: Description")

For each worktree, determine if it links to a spec feature:
- Extract issue number from branch name
- Look up issue labels
- Match label to feature directory in `.specify/specs/`

This enables the output table to show spec feature associations

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

### Priority 3b: Pending Spec Sync (if .specify/ exists)
- Features with tasks.md containing unsynced waves
- **Why:** Spec work is defined but not yet tracked in GitHub issues
- **Action:** `/spec:sync {feature-name}`

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

### Spec Features (if .specify/ exists)

📋 **Spec-Driven Development:**

| Feature | Spec | Plan | Tasks | Synced | Pending | Action |
|---------|------|------|-------|--------|---------|--------|
| {name} | ✓/○/✗ | ✓/○/✗ | ✓/○/✗ | {N} | {M} | {action} |

**Legend:**
- ✓ = File exists and has content
- ○ = File exists but empty/incomplete
- ✗ = File missing
- **Synced** = Waves with GitHub issues created
- **Pending** = Waves needing `/spec:sync`

**Example:**
| Feature | Spec | Plan | Tasks | Synced | Pending | Action |
|---------|------|------|-------|--------|---------|--------|
| user-auth | ✓ | ✓ | ✓ | 3 | 2 | `/spec:sync user-auth` |
| api-refactor | ✓ | ✓ | ○ | 0 | 0 | Add tasks to tasks.md |
| dashboard | ✓ | ✓ | ✓ | 5 | 0 | Complete |

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

| Directory | Branch | Issue | Spec Feature | Status | Session |
|-----------|--------|-------|--------------|--------|---------|
| {path} | issue-{N}-desc | #{N} | user-auth | Uncommitted changes | session-abc (active) |
| {path} | issue-{M}-desc | #{M} | api-refactor | Clean | - |
| {path} | issue-{K}-desc | #{K} | - | Clean | - |

*Spec Feature column shows the linked feature from `.specify/specs/` if the issue was created via `/spec:sync`*

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

## Step 8: Present Follow-up Options

After presenting recommendations, offer:

1. **Start Priority #1** - Create worktree and begin work on top priority
2. **View Issue Details** - Get full details on any specific issue
3. **Create New Issue** - Document discovered work
4. **Clean Up** - Remove stale worktrees/branches
5. **Refresh** - Re-scan for updates
6. **Sync Pending Specs** - Run `/spec:sync {feature}` for features with pending waves (if .specify/ exists)
7. **View Spec Status** - Run `/spec:status` for detailed spec alignment (if .specify/ exists)

---

## Step 9: Handle User Selection

When the user selects an issue to work on, follow this sequence:

### 9.1 Check Availability

```bash
# Verify issue is still available (may have been claimed since analysis)
~/.claude/scripts/claim-issue.sh --check {NUMBER}
```

If claimed, inform user and suggest alternatives.

### 9.2 Claim the Issue

```bash
# Get repo info for claim
REPO_INFO=$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')

# Claim the issue (registers in session coordination)
~/.claude/scripts/session-register.sh claim "$REPO_INFO" {NUMBER} "{Title}"
```

### 9.3 Create Worktree (if needed)

If the issue doesn't have an existing worktree:

```bash
# Create worktree for the issue
git worktree add -b issue-{N}-{description} ../{repo}-issue-{N}
```

### 9.4 Confirmation

Report to user:
- Issue #{N} claimed by this session
- Worktree created (if applicable)
- Shell prompt will show `[PREFIX #N]` when in worktree
- Ready to begin work

---

## Notes for Non-Worktree Repositories

If the repository doesn't use worktrees (only main worktree detected):

1. Skip worktree analysis sections
2. Focus on branch-to-issue mapping
3. Suggest worktree setup for complex projects:
   > "Consider using git worktrees for parallel issue development. See `ISSUE_DRIVEN_DEVELOPMENT.md` for guidance."

---

## Configuration via CLAUDE.md

Projects can optionally add this configuration block to their CLAUDE.md:

```markdown
## Project-Next Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| **Prompt Prefix** | NHL | Short prefix for shell prompt context |
| **Issue Pattern** | wave | Hierarchy style: wave, epic, parent-child, flat |
| **Priority Labels** | critical, urgent | Labels indicating critical priority |
```
