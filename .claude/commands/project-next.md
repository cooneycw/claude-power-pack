---
description: Prioritized next-step report from GitHub issues and worktrees (compact default; --full deep analysis, --brief single pick)
allowed-tools: Bash(gh:*), Bash(git:*), Bash(ls:*), Bash(for :*), Bash(sort:*), Bash(printf:*), Read, Glob, Grep
---

# Project Next Steps Recommendation

Analyze the project's GitHub issues and worktree state, then recommend
prioritized next steps. This command is **read-only**: it never modifies
issues, creates branches, or writes files. Do NOT enter plan mode - this is a
report, not a change.

## Arguments

`$ARGUMENTS` may contain a project name and/or a mode flag, in any order:

- `<project>` (optional): a directory under `~/Projects` to analyze.
  Resolution order: positional argument -> `CLAUDE_PROJECT` env var -> the
  current git repository.
- (no flag, default): **compact report** - state summary, top 3 ready-to-start
  issues, in-flight and blocked tables.
- `--full`: **deep report** - priority tiers 1-5, spec features table,
  worktree status table, categorized backlog.
- `--brief`: **single top recommendation** only.

---

## Step 1: Resolve project and fetch state (one pass)

### 1.1 Resolve the project directory

```bash
# Positional argument wins; then CLAUDE_PROJECT; then current repo
TARGET="<first non-flag token of $ARGUMENTS>"
if [ -n "$TARGET" ] && [ -d "$HOME/Projects/$TARGET" ]; then
  cd "$HOME/Projects/$TARGET"
elif [ -n "$CLAUDE_PROJECT" ] && ! git rev-parse --git-dir >/dev/null 2>&1; then
  [ -d "$HOME/Projects/$CLAUDE_PROJECT" ] && cd "$HOME/Projects/$CLAUDE_PROJECT"
fi
gh repo view --json owner,name,defaultBranchRef \
  --jq '{owner: .owner.login, name: .name, default_branch: .defaultBranchRef.name}'
```

- Named project directory missing: STOP - "~/Projects/{name} doesn't exist".
- Not a git repo and nothing resolved: STOP - "cd to a project or pass a name".
- `gh` errors (no remote, rate limit): report the error (and reset time for
  rate limits), then STOP.

### 1.2 Fetch everything in ONE batched call

```bash
# Single call - never per-issue `gh issue view` loops
gh issue list --state open --json number,title,labels,body --limit 200
```

If no open issues: report "No actionable issues found." and stop (in compact
and brief modes, still show the in-flight/worktree state if any exists).

### 1.3 Scan worktrees and branches

```bash
git worktree list --porcelain
git branch --list 'issue-*'
git fetch origin --quiet 2>/dev/null || true
```

For each worktree: note its branch, mapped issue number (pattern
`issue-{N}-*`), and whether it is dirty (`git -C <path> status --short`).

---

## Step 2: Materialize state (MANDATORY verification gate)

Build these three lists explicitly before writing any recommendation.
Skipping this step causes misclassification - it is a strict gate.

1. **IN_FLIGHT_ISSUES** - every issue with a matching `issue-{N}-*` branch or
   worktree.
2. **DEPENDENCY_MAP** - parse issue bodies for **explicit dependency keywords
   only**: `Depends on #N`, `Blocked by #N`, `Requires #N`, `After #N`, or a
   parent Wave/Phase/epic whose checklist still has unchecked items referencing
   the issue. `Related to #N` / `See also #N` is NOT a dependency.
3. **BLOCKED_ISSUES** - transitive closure over DEPENDENCY_MAP: an issue is
   blocked if ANY upstream dependency is in-flight, still open, or itself
   blocked. Walk the chain - multi-hop (A blocks B blocks C) MUST be caught;
   treat dependency cycles as blocked. Closed/merged upstreams satisfy the
   dependency.

```
IN_FLIGHT_ISSUES: [#N, ...]
BLOCKED_ISSUES:   [#X (by #N), ...]
AVAILABLE_ISSUES: [everything open and in neither list]
```

**Validation (mandatory):** every open issue lands in exactly one list; no
issue from IN_FLIGHT_ISSUES or BLOCKED_ISSUES may appear among the
recommendations. Critical/security issues are the one exception: always
surface them, flagged with their in-flight/blocked state.

---

## Step 3: Rank AVAILABLE_ISSUES

Order by, in sequence:

1. **Critical** - labels `security`, `blocker`, or `bug` + `priority-high`.
2. **Priority labels** - `p1` before `p2` before unlabeled.
3. **Phase order** - lower `phase-N` label (or Wave/Phase number in the title)
   first.
4. **Tie-break** - lower issue number (first-filed).

Note quick wins (labels `documentation`, `chore`, or obviously small scope) in
the rationale - they are good picks when a worktree is already active.

If no priority/phase labels exist at all, fall back to issue-number order and
warn: "No priority labels detected - ordering by issue number."

---

## Step 4: Spec sync check (only if `.specify/` exists)

```bash
for d in .specify/specs/*/; do
    [ -d "$d" ] || continue
    feat=$(basename "$d")
    have_spec=$([ -s "${d}spec.md" ] && echo "y" || echo "n")
    have_plan=$([ -s "${d}plan.md" ] && echo "y" || echo "n")
    have_tasks=$([ -s "${d}tasks.md" ] && echo "y" || echo "n")
    echo "${feat}|${have_spec}|${have_plan}|${have_tasks}"
done 2>/dev/null || echo "no .specify/specs"
```

Surface a pointer ONLY when a feature has a `tasks.md` with no matching GitHub
issues yet: "Spec `{feat}` has tasks not yet synced - run
`scripts/speckit-tasks-to-issues.sh`, then `/flow:auto <issue>` per issue."
In `--full` mode, show the full feature table instead.

---

## Step 5: Output

### Default (compact)

```markdown
## {REPO} - Next Steps

**State:** {N} open | {K} in-flight ({#a, #b}) | {M} blocked

### Ready to start (top 3)
1. #{N} {title}  [{p1|p2|-}, {phase|-}]
   {one-line rationale} -> /flow:auto {N}
2. ...
3. ...

### In flight
| # | branch | status |
|---|--------|--------|
| {N} | issue-{N}-... | clean|dirty |

### Blocked
| # | by | reason |
|---|-----|--------|
| {X} | #{N} | in-flight|open dep|transitive |

{spec-sync pointer, only if applicable}
(--full for the 5-tier report, --brief for a single pick)
```

Omit any empty section. Rationales are one line each - do not expand into
per-issue analysis.

### --brief

```markdown
Recommended next issue:

  #{N}  {title}
  Priority: {p1|p2|-} | Phase: {phase|-} | Blocked by: none
  Rationale: {one sentence}

  -> /flow:auto {N}
```

### --full

The deep report - all sections:

1. **Current State Summary** - repo, open-issue counts by category (critical /
   bugs / features / docs / tech-debt / planning), worktree list, uncommitted
   work.
2. **Spec Features table** (if `.specify/` exists) - feature | spec | plan |
   tasks | action.
3. **Priority tiers:**
   - Priority 1: Critical/blocking (surfaced even when in-flight/blocked,
     flagged).
   - Priority 2: Active work - IN_FLIGHT_ISSUES only, with worktree path,
     branch status, uncommitted changes.
   - Blocked (not actionable) - table with issue | title | blocked-by |
     reason. No effort estimates; never suggest starting these.
   - Priority 3: Ready to start - gate-passed issues, with Why / Effort /
     `/flow:auto` command per issue.
   - Priority 3b: Pending spec sync (if applicable).
   - Priority 4: Quick wins (gate-passed only).
   - Priority 5: Planning/discussion issues.
4. **Worktree Status table** - directory | branch | issue | status.
5. **Recommendations** - cleanup candidates (merged/stale worktrees).

The tier assignments come EXACTLY from the Step 2 gate - an issue in
IN_FLIGHT_ISSUES or BLOCKED_ISSUES must never appear in tiers 3-5.

---

## Edge cases

- **All open issues blocked:** report the unique set of blockers and which
  in-flight work resolves them.
- **Top pick already has a worktree:** it belongs in the in-flight table, not
  the recommendations - recommend the next available issue instead.
- **Worktree without an open issue** (merged/closed): list under a one-line
  cleanup note - "run `/flow:cleanup`".

## Notes

- To act on a recommendation: `/flow:auto {N}` (full lifecycle) or
  `/flow:start {N}` (worktree only).
- For a quick orientation without issue analysis, use `/project-lite`.
- Optional per-project tuning via a "Project-Next Configuration" block in
  CLAUDE.md (priority labels, hierarchy style: wave / epic / parent-child /
  flat).
