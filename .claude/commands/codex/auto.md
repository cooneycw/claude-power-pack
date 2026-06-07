---
description: Full issue lifecycle delegated to Codex - worktree, implement, review, quality gates, PR
allowed-tools: Bash(codex:*), Bash(git:*), Bash(gh:*), Bash(ls:*), Bash(cat:*), Bash(grep:*), Bash(curl:*), Bash(python3:*), Bash(PYTHONPATH=*), Bash(mkdir:*), Bash(cd:*), Bash(pwd), Bash(head:*), Bash(tail:*), Bash(wc:*), Bash(test:*), Bash(make:*), Bash(sleep:*)
---

# Codex Auto: Full Issue Lifecycle via Codex CLI

Mirrors `/flow:auto` but delegates implementation (Step 3) to Codex CLI.
Claude Code acts as supervisor/reviewer while Codex writes the code.

## Arguments

- `ISSUE` (required): GitHub issue number (e.g., `42`)

## Instructions

When the user invokes `/codex:auto <ISSUE>`, perform these steps sequentially. Stop immediately if any step fails.

Report at the start:

```
Codex Auto: Issue #<ISSUE> - Full Lifecycle

Step 1/7: Start (create worktree and branch)
Step 2/7: Analyze (understand issue, build Codex prompt)
Step 3/7: Execute Codex (delegate implementation to Codex CLI)
Step 4/7: Review (Claude reviews Codex's diff)
Step 5/7: Quality Gates (lint, test, security - with fix loop)
Step 6/7: Finish (commit, push, create PR)
Step 7/7: Cleanup (optional merge + worktree removal)

Proceeding...
```

---

### Step 1: Start - Create Worktree

**CRITICAL: You MUST create or enter a worktree before proceeding. NEVER implement changes directly on main/master.**

```bash
ISSUE_NUM="<ISSUE>"
REPO=$(basename "$(git rev-parse --show-toplevel)")

# Fetch issue details
gh issue view "$ISSUE_NUM" --json number,title,state,body
```

- If issue is not OPEN, warn the user and ask whether to proceed.
- Extract the title for branch naming.

```bash
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | cut -c1-50)
BRANCH="issue-${ISSUE_NUM}-${SLUG}"
WORKTREE_DIR="../${REPO}-issue-${ISSUE_NUM}"
```

**Check for existing work:**

```bash
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" =~ issue-${ISSUE_NUM}- ]]; then
    # Already in the right worktree
    true
fi

git worktree list | grep "issue-${ISSUE_NUM}"
git fetch origin
git branch -r | grep "issue-${ISSUE_NUM}-"
```

- **Already on issue branch:** Use current directory.
- **Worktree exists:** `cd` into the existing worktree directory.
- **Remote branch exists:** Create worktree tracking the remote branch.
- **Neither exists:** Create fresh from `origin/main`.

#### Verification Gate (MANDATORY)

```bash
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
    echo "ERROR: Still on main/master. STOP."
    exit 1
fi
echo "Verified: on branch '$CURRENT_BRANCH' in $(pwd)"
```

Report: `Step 1/7: Start complete - worktree at {path}, on branch {branch}`

---

### Step 2: Analyze - Build Codex Prompt

Working from the worktree, analyze the issue and build a comprehensive prompt for Codex.

1. **Parse the issue body:**
   - Extract acceptance criteria (checkbox items `- [ ]`)
   - Identify referenced files, components, or areas
   - Note any dependencies or constraints

2. **Explore the codebase:**
   - Read files referenced in the issue
   - Understand existing patterns and conventions
   - Identify all files that need to be created or modified

3. **Build the Codex prompt:**
   Construct a detailed prompt that includes:
   - Issue title and full body
   - Acceptance criteria (extracted)
   - Project conventions from CLAUDE.md (if present)
   - Relevant file paths and their current content summaries
   - Testing expectations (from Makefile targets)
   - Specific instructions: "Implement the changes described in the issue. Follow existing code conventions. Create or modify only the files necessary."

4. **Report the prompt to the user:**

```
Step 2/7: Analysis Complete

Issue #42: "Fix login redirect loop"

Acceptance Criteria:
  - [ ] Login redirects to dashboard after auth
  - [ ] Invalid sessions redirect to /login
  - [ ] Tests pass

Codex Prompt Summary:
  - Context: 3 files referenced, CLAUDE.md conventions included
  - Scope: Modify src/auth/login.py, tests/test_auth.py, config/routes.py
  - Testing: make lint + make test available

Proceeding to Codex execution...
```

Report: `Step 2/7: Analyze complete - Codex prompt built ({N} files referenced)`

---

### Step 3: Execute Codex - Delegate Implementation

Run Codex CLI in the worktree with full sandbox access (safe in disposable worktree).

```bash
# Verify Codex is available
if ! command -v codex &>/dev/null; then
    echo "ERROR: Codex CLI not found."
    echo "Install with: npm install -g @openai/codex"
    echo "Then configure: codex login"
    exit 1
fi
```

Execute Codex with JSONL monitoring:

```bash
WORKTREE_PATH=$(pwd)

codex exec \
    --json \
    -C "$WORKTREE_PATH" \
    --sandbox danger-full-access \
    "$CODEX_PROMPT" 2>&1 | tee /tmp/codex-output-${ISSUE_NUM}.jsonl
```

**Monitor the JSONL stream** - parse and report:
- Plan steps and progress
- File changes / diffs
- Agent messages
- Errors

```bash
# After execution, check exit code
CODEX_EXIT=$?
if [ "$CODEX_EXIT" -ne 0 ]; then
    echo "ERROR: Codex execution failed (exit code: $CODEX_EXIT)"
    echo "Last 20 lines of output:"
    tail -20 /tmp/codex-output-${ISSUE_NUM}.jsonl
    exit 1
fi
```

**Parse JSONL output** for summary:

```bash
# Count file changes
FILES_CHANGED=$(git diff --name-only | wc -l)
LINES_ADDED=$(git diff --stat | tail -1 | grep -oP '\d+ insertion' | grep -oP '\d+' || echo "0")
LINES_REMOVED=$(git diff --stat | tail -1 | grep -oP '\d+ deletion' | grep -oP '\d+' || echo "0")

echo "Codex made changes to $FILES_CHANGED file(s): +$LINES_ADDED -$LINES_REMOVED"
```

If Codex made no changes, STOP and report.

Report: `Step 3/7: Execute Codex complete - {N} files changed (+{added} -{removed})`

---

### Step 4: Review - Claude Reviews Codex's Diff

Cross-model review: Claude Code reviews what Codex wrote.

1. **Read the full diff:**
   ```bash
   git diff
   ```

2. **Review for:**
   - Correctness: Does the implementation match the issue requirements?
   - Conventions: Does it follow the project's coding style?
   - Security: Any injection, XSS, or other vulnerabilities?
   - Completeness: Are all acceptance criteria addressed?
   - Test coverage: Are tests updated or added?

3. **Report review findings:**

```
Step 4/7: Review Complete

Codex Diff Review:
  Files changed: 3
  Correctness: PASS - all acceptance criteria addressed
  Conventions: PASS - matches existing code style
  Security: PASS - no vulnerabilities detected
  Completeness: PASS - tests included

Issues found: 0

Proceeding to quality gates...
```

If review finds CRITICAL issues that Codex cannot fix via re-prompt (e.g., fundamentally wrong approach), STOP and report. Offer to either re-prompt Codex or hand off to manual implementation.

Report: `Step 4/7: Review complete - {PASS|N issues found}`

---

### Step 5: Quality Gates - Lint, Test, Security (with Fix Loop)

Run the deterministic quality gate runner:

```bash
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -n "$CPP_DIR" ]; then
    PYTHONPATH="$CPP_DIR/lib:$PYTHONPATH" python3 -m lib.cicd run --plan finish
    RUNNER_EXIT=$?
fi
```

**Fallback:** Run `make lint` and `make test` directly if runner unavailable.

**Fix Loop (max 2 retries):**

If quality gates fail:

1. **Extract the error output** from the failed step.
2. **Build a fix prompt** for Codex with the error context:
   ```
   The following quality gate failed after your implementation:

   [ERROR OUTPUT]

   Fix the issues while preserving the original implementation intent.
   Only change what is necessary to make the quality gates pass.
   ```
3. **Re-execute Codex** with the fix prompt:
   ```bash
   codex exec \
       --json \
       -C "$WORKTREE_PATH" \
       --sandbox danger-full-access \
       "$FIX_PROMPT" 2>&1 | tee /tmp/codex-fix-${ISSUE_NUM}-${RETRY}.jsonl
   ```
4. **Re-run quality gates.**
5. If still failing after 2 retries, STOP and report.

```
RETRY_COUNT=0
MAX_RETRIES=2

while [ "$RUNNER_EXIT" -ne 0 ] && [ "$RETRY_COUNT" -lt "$MAX_RETRIES" ]; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Quality gates failed. Re-prompting Codex (attempt $RETRY_COUNT/$MAX_RETRIES)..."

    # Build fix prompt with error context
    # Re-execute Codex
    # Re-run quality gates

    if [ "$RUNNER_EXIT" -eq 0 ]; then
        echo "Quality gates passed after $RETRY_COUNT fix attempt(s)."
    fi
done

if [ "$RUNNER_EXIT" -ne 0 ]; then
    echo "ERROR: Quality gates still failing after $MAX_RETRIES retries."
    echo "Manual intervention required."
    exit 1
fi
```

Report: `Step 5/7: Quality gates passed (attempt {N}/{MAX})`

---

### Step 6: Finish - Commit, Push, Create PR

```bash
BRANCH=$(git branch --show-current)
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")
```

1. **Commit** the changes:
   - Use conventional commit format: `type(scope): Description (Closes #N)`
   - Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
   - Note Codex as implementer in the commit body

2. **Push** the branch:
   ```bash
   git push -u origin "$BRANCH"
   ```

3. **Create PR** if no PR exists:
   ```bash
   gh pr create --title "type(scope): Description (Closes #ISSUE_NUM)" --body "..."
   ```
   - PR body includes:
     - Summary of changes
     - Note that implementation was delegated to Codex CLI
     - Claude Code review findings
     - Test plan
     - `Closes #N`

Report: `Step 6/7: Finish complete - PR #{N} created`

---

### Step 7: Cleanup (Optional)

Ask the user if they want to merge and clean up now, or leave the PR for review:

```
PR #{N} created. What would you like to do?

  1. Merge now (squash-merge, clean up worktree)
  2. Leave for review (keep worktree, manual merge later)
```

If merge now, follow the same merge/cleanup pattern as `/flow:auto` Step 6:

1. Squash-merge the PR
2. Update local main
3. **cd to main repo BEFORE removing worktree** (critical)
4. Remove worktree and branch
5. Close issue if still open

If leave for review, report the PR URL and worktree location.

Report: `Step 7/7: Cleanup complete - PR merged, worktree removed` or `Step 7/7: PR #{N} left for review`

---

### Final Summary

```
Codex Auto Complete

  Issue:      #{N} - {title}
  Implementer: Codex CLI (codex exec)
  Reviewer:    Claude Code (cross-model review)
  Changes:    Modified {N} files ({summary})
  Fix Loop:   {N} retry(s) needed / no retries needed
  PR:         #{N} (created / squash-merged)
  Branch:     issue-{N}-{slug} (active / deleted)
  Worktree:   {path} (active / removed)
  Location:   {current working directory}
```

---

## Error Handling

At each step, if something fails:

```
Codex Auto stopped at Step N/7: {Step Name}

  Failed: [description of what failed]
  Fix:    [actionable suggestion]

  To resume manually:
    /flow:start {ISSUE}     (if step 1 failed)
    [investigate]            (if step 2 failed)
    /codex:exec "<prompt>"   (if step 3 failed)
    [review diff manually]   (if step 4 failed)
    /flow:check              (if step 5 failed)
    /flow:finish             (if step 6 failed)
    /flow:merge              (if step 7 failed)
```

Key failure scenarios:
- **Codex not installed:** Stop at step 3, suggest `npm install -g @openai/codex`
- **Codex execution fails:** Stop at step 3, show last 20 lines of JSONL output
- **Codex makes no changes:** Stop at step 3, suggest reviewing the prompt
- **Review finds critical issues:** Stop at step 4, offer to re-prompt or hand off
- **Quality gates fail after retries:** Stop at step 5, show error output
- **Push/PR fails:** Stop at step 6, suggest manual resolution

## Notes

- Codex CLI runs with `--sandbox danger-full-access` which is safe in a disposable worktree
- `--json` flag streams JSONL events for monitoring plan steps, diffs, and messages
- Cross-model review catches issues that same-model review might miss
- Fix loop re-prompts Codex with error context, max 2 retries before stopping
- Worktree cleanup follows the same safe pattern as flow:auto (cd out before removing)
