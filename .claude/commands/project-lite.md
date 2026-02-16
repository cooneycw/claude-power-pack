---
description: Quick project reference with minimal context usage (context-efficient alternative to /project-next)
allowed-tools: Bash(gh repo view:*), Bash(git worktree list:*), Bash(cat:*), Bash(head:*), Read
---

# Project Lite - Quick Reference

Generate a context-efficient project overview. This command uses minimal tokens (~500-800) compared to `/project-next` (15-30K tokens).

**Use this when:**
- Starting a session and want quick orientation
- Context is already high and you need project info
- You know what you want to work on (don't need issue analysis)

**Use `/project-next` when:**
- You need issue prioritization and recommendations
- You want worktree analysis and cleanup suggestions
- You're unsure what to work on next

---

## Step 1: Detect Repository

Run these commands to detect the current repository:

```bash
# Get basic repo info
gh repo view --json owner,name,defaultBranchRef --jq '{owner: .owner.login, name: .name, branch: .defaultBranchRef.name}' 2>/dev/null || echo "Not a GitHub repo"
```

If not a GitHub repo, output a simple message and stop.

---

## Step 2: Read CLAUDE.md (if exists)

Check for project-specific conventions:

```bash
# Check if CLAUDE.md exists
head -100 CLAUDE.md 2>/dev/null || echo "No CLAUDE.md found"
```

Extract and summarize only these sections if present:
- **Quick References** - Key files and locations
- **Key Conventions** - Coding standards
- **Commands** - Available slash commands
- **Worktree/Branch Patterns** - If using IDD

---

## Step 3: Check Worktree State

Quick worktree summary (skip if not using worktrees):

```bash
git worktree list 2>/dev/null | head -10
```

---

## Step 3b: Check Session Coordination State

If coordination scripts are available, show active locks and sessions:

```bash
# Check active locks
~/.claude/scripts/session-lock.sh list 2>/dev/null || echo "Coordination not installed"

# Check active sessions
~/.claude/scripts/session-register.sh status 2>/dev/null | head -20
```

**Include in output if any locks or sessions found:**
- Active locks (who holds what)
- Active sessions (which worktrees have live sessions)

---

## Step 4: Output Format

Generate this compact summary:

```markdown
## {repo_name} - Quick Reference

**Repo:** {owner}/{name} ({default_branch})
**Path:** {current_path}

### Conventions
{extracted from CLAUDE.md or inferred:}
- **Language:** {Python 3.x / TypeScript / etc.}
- **Package Manager:** {uv / npm / etc.}
- **Quality Checks:** {pre-commit hooks / CI / etc.}

### Worktrees
{if multiple worktrees:}
| Path | Branch | Issue |
|------|--------|-------|
| {main} | main | - |
| {worktree} | issue-N-desc | #N |

{if single worktree:}
Single worktree (main repo only)

### Active Coordination
{if coordination installed and any locks/sessions:}
**Locks:** {count} active
- `pytest-{repo}` held by session-xyz (expires in 120s)
- ...

**Sessions:** {count} active
- session-abc in {worktree} (issue #123)
- ...

{if no locks/sessions:}
No active locks or sessions.

### Key Files
- `CLAUDE.md` - {present/missing}
- `README.md` - {present/missing}
- `.github/ISSUE_TEMPLATE/` - {present/missing}

### Available Commands
{list if detected in .claude/commands/ or CLAUDE.md}

---
For issue analysis and prioritized recommendations, run `/project-next`.
```

---

## Step 5: Token Usage Note

After output, add:

> **Token usage:** ~{X} tokens (vs ~20K for /project-next)

---

## Notes

### Customization via CLAUDE.md

Projects can add a `## Quick Reference` section to their CLAUDE.md that this command will extract verbatim, allowing project-specific customization of the lite output.

Example:

```markdown
## Quick Reference

| Setting | Value |
|---------|-------|
| Python | 3.11+ |
| Environment | Conda |
| Coverage | 80% min |
| Line length | 88 |

**Worktree pattern:** `{repo}-issue-{N}`
**Branch pattern:** `issue-{N}-{description}`
```

### When to Use Each Command

| Scenario | Command | Token Cost |
|----------|---------|------------|
| Quick orientation | `/project-lite` | ~500-800 |
| Full issue analysis | `/project-next` | ~15-30K |
| View specific issue | `/github:issue-view N` | ~1-2K |
| List open issues | `/github:issue-list` | ~2-5K |
