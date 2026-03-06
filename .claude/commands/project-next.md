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

## Step 5: State Materialization (MANDATORY)

You MUST build three explicit lists and write them out before generating any recommendations.
Failure to materialize these lists causes downstream filtering failures. This is a strict gate.

### 5.1 Build IN_FLIGHT_ISSUES

Collect every issue number that meets ANY of these criteria into `IN_FLIGHT_ISSUES`:
- Has a matching branch anywhere (`git branch --list 'issue-{N}-*'`)
- Has a mapped worktree directory (from Step 4)
- Is claimed by an Active or Idle session

### 5.2 Build DEPENDENCY_MAP

Parse all open issues for dependency relationships. For each issue, record its upstream dependencies:

| Detection Pattern | Example | Extraction |
|-------------------|---------|------------|
| "Depends on #N" | `Depends on #100` | upstream = #100 |
| "Blocked by #N" | `Blocked by #100` | upstream = #100 |
| "After #N" | `After #100` | upstream = #100 |
| "Requires #N" | `Requires #100` | upstream = #100 |
| Parent wave incomplete | Child of Wave 5, Wave 5 still open | upstream = Wave 5 issue |
| Checklist reference | `- [ ] #100` in parent body | upstream = parent for #100 |

### 5.3 Build BLOCKED_ISSUES

Use the following graph traversal to compute transitive blocking. Do NOT use a single-pass check -
multi-hop dependencies (A blocks B blocks C) MUST be caught.

```pseudocode
function compute_blocked(dependency_map, in_flight_issues, all_open_issues):
    blocked = set()
    visited = set()

    function dfs(issue):
        if issue in visited:
            return                          # cycle detected - already handled
        visited.add(issue)

        for upstream in dependency_map.get(issue, []):
            if upstream in in_flight_issues:
                blocked.add(issue)          # upstream is active work, not done
            elif upstream in all_open_issues:
                dfs(upstream)               # recurse to check upstream's deps
                if upstream in blocked:
                    blocked.add(issue)      # transitively blocked
            # if upstream is closed/merged, it is satisfied - no block

    for issue in all_open_issues:
        dfs(issue)

    # Handle cycles: any issue still in visited but with unresolved
    # circular refs gets marked blocked
    return blocked
```

An issue is blocked if ANY of these are true:
- It has an explicit dependency (Depends on/Blocked by/Requires/After) on an in-flight issue
- It has an explicit dependency on an open issue that is itself blocked (transitive)
- It is a child of a parent wave that still has incomplete tasks
- It participates in a circular dependency chain

**Important:** Only block on explicit dependency keywords from section 5.2. Do NOT treat every
open issue reference (e.g. "Related to #N" or "See also #N") as a blocking dependency.

### 5.4 Write Out All Three Lists

You MUST explicitly output these three lists in your thinking before proceeding to Step 6.
If you skip this step, your recommendations WILL contain errors.

```
IN_FLIGHT_ISSUES: [#N, #M, ...]
BLOCKED_ISSUES: [#X (blocked by #N), #Y (blocked by #M), ...]
AVAILABLE_ISSUES: [all open issues NOT in either list above]
```

**Worked example** (5 issues, 2 worktrees):
```
Open issues: #10, #11, #12, #13, #14
Worktrees: issue-10-auth, issue-11-api
Dependencies: #12 "Depends on #10", #13 "Requires #12", #14 has no deps

IN_FLIGHT_ISSUES: [#10, #11]           -- have worktrees
BLOCKED_ISSUES:   [#12 (by #10), #13 (by #12, transitive)]
AVAILABLE_ISSUES: [#14]                -- only this is "Ready to Start"
```

### 5.5 Issue-to-Spec Mapping (if .specify/ exists)

For each issue, check if it was created by spec sync:

1. **Label Matching**: Look for labels matching feature names in `.specify/specs/`
2. **Body References**: Check issue body for "Spec:" or "Feature:" references
3. **Wave Title Pattern**: Match issue title with wave names from tasks.md (e.g., "Wave 1: Description")

For each worktree, determine if it links to a spec feature:
- Extract issue number from branch name
- Look up issue labels
- Match label to feature directory in `.specify/specs/`

### 5.6 Orphaned Work

Identify branches/worktrees without corresponding open issues (merged or closed).

---

## Step 6: Verification Gate (MANDATORY)

You MUST execute the following pseudocode logic against EVERY open issue to determine its placement.
Do NOT skip this step. Do NOT assign issues without running them through this gate.

```pseudocode
for issue in all_open_issues:
    if issue.number in IN_FLIGHT_ISSUES:
        assign_to(PRIORITY_2_ACTIVE_WORK)
        continue                              # STOP - do not consider further

    if issue.number in BLOCKED_ISSUES:
        assign_to(BLOCKED_SECTION)
        continue                              # STOP - do not recommend

    if is_critical_or_security_blocker(issue):
        assign_to(PRIORITY_1_CRITICAL)
        continue

    if is_quick_win(issue):
        assign_to(PRIORITY_4_QUICK_WINS)
        continue

    if is_planning_or_discussion(issue):
        assign_to(PRIORITY_5_PLANNING)
        continue

    assign_to(PRIORITY_3_READY_TO_START)
```

### Post-Gate Validation (MANDATORY)

After running the gate, execute this validation. Do NOT skip it.

```pseudocode
# Validation 1: No in-flight or blocked issues leaked into recommendable tiers
for tier in [PRIORITY_3, PRIORITY_4, PRIORITY_5]:
    for issue in tier:
        assert issue not in IN_FLIGHT_ISSUES    # FAIL = move to Priority 2
        assert issue not in BLOCKED_ISSUES      # FAIL = move to Blocked section
        for upstream in DEPENDENCY_MAP.get(issue, []):
            if upstream in all_open_issues:
                assert upstream not in IN_FLIGHT_ISSUES  # FAIL = move issue to Blocked
                assert upstream not in BLOCKED_ISSUES    # FAIL = move issue to Blocked

# Validation 2: Coverage - every open issue accounted for exactly once
assigned = P1 + P2 + BLOCKED + P3 + P3b + P4 + P5
assert len(assigned) == len(all_open_issues)    # FAIL = find and classify missing issues
```

If any assertion fails, fix the assignment before generating output. If you cannot resolve
a classification, report it as an error to the user rather than silently misclassifying.

**STRICTLY FORBIDDEN:** An issue in `IN_FLIGHT_ISSUES` MUST NOT appear in Priority 3, 4, or 5.
An issue in `BLOCKED_ISSUES` MUST NOT appear in Priority 3, 4, or 5. No exceptions.

---

## Step 7: Generate Recommendations

Output the prioritized list based EXACTLY on the Step 6 verification gate results.

### Priority 1: Critical/Blocking
- Security issues, breaking bugs, deployment blockers
- These bypass the in-flight/blocked filter (critical issues are always surfaced)

### Priority 2: Active Work (In Progress)
- ONLY issues from `IN_FLIGHT_ISSUES`
- Include worktree path, branch status, uncommitted changes, session claim

### Blocked (Not Actionable)
- Issues from `BLOCKED_ISSUES`
- For each, show WHY it is blocked: "Blocked by #N (in-flight)" or "Blocked by #N (not started)"
- Do NOT assign effort estimates or suggest starting these

### Priority 3: Ready to Start
- Issues that passed the Step 6 gate with no blockers
- Child issues of COMPLETED parent waves only
- Issues with clear acceptance criteria

### Priority 3b: Pending Spec Sync (if .specify/ exists)
- Features with tasks.md containing unsynced waves
- **Why:** Spec work is defined but not yet tracked in GitHub issues
- **Action:** `/spec:sync {feature-name}`

### Priority 4: Quick Wins
- Low effort issues, documentation updates, simple fixes
- MUST have passed the Step 6 gate

### Priority 5: Planning/Discussion
- Wave/Phase planning issues, feature discussions, architecture decisions
- MUST have passed the Step 6 gate

---

## Step 8: Output Format

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
   - **Command:** `git worktree add -b issue-{N}-desc ../{repo}-issue-{N}`

2. **[READY]** Issue #{N}: {Title}
   - **Why:** {reasoning}
   - **Effort:** {estimate}

3. **[QUICK WIN]** Issue #{N}: {Title}
   - **Why:** {reasoning}

### Blocked Issues (Not Actionable)

| Issue | Title | Blocked By | Reason |
|-------|-------|------------|--------|
| #{X} | {Title} | #{N} | In-flight (active worktree) |
| #{Y} | {Title} | #{M} | Not started (open dependency) |

### Worktree Status

| Directory | Branch | Issue | Spec Feature | Status | Session |
|-----------|--------|-------|--------------|--------|---------|
| {path} | issue-{N}-desc | #{N} | user-auth | Uncommitted changes | session-abc (active) |
| {path} | issue-{M}-desc | #{M} | api-refactor | Clean | - |
| {path} | issue-{K}-desc | #{K} | - | Clean | - |

*Spec Feature column shows the linked feature from `.specify/specs/` if the issue was created via `/spec:sync`*

### Recommendations
- **Cleanup:** {worktrees with merged branches}
- **Stale:** {worktrees with no recent commits}
```

---

## Step 9: Present Follow-up Options

After presenting recommendations, offer:

1. **Start Priority #1** - Create worktree and begin work on top priority
2. **View Issue Details** - Get full details on any specific issue
3. **Create New Issue** - Document discovered work
4. **Clean Up** - Remove stale worktrees/branches
5. **Refresh** - Re-scan for updates
6. **Sync Pending Specs** - Run `/spec:sync {feature}` for features with pending waves (if .specify/ exists)
7. **View Spec Status** - Run `/spec:status` for detailed spec alignment (if .specify/ exists)

---

## Step 10: Handle User Selection

When the user selects an issue to work on, follow this sequence:

### 9.1 Create Worktree (if needed)

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
