# Flow: Finish - Quality Gates, Commit, Push, and Create PR

Run quality checks, commit changes, push the branch, and create a pull request.

## Instructions

When the user invokes `/flow:finish`, perform these steps:

### Step 1: Validate Context

```bash
# Ensure we're on a feature branch (not main)
BRANCH=$(git branch --show-current)
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    echo "ERROR: Cannot finish from main/master. Switch to a feature branch or worktree."
    exit 1
fi

# Extract issue number from branch
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")
```

### Step 1b: Stale-base Pre-check (issue #473)

A sibling PR that merged while you were working moves `origin/main` under you; if
you commit onto a stale base, you rediscover the collision only at merge time (the
#462 guard). Surface it now, before the quality gate runs, and if the base moved,
bring it in so the gate below rides the current tree:

```bash
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ] && { CPP_DIR="$dir"; break; }
done
if [ -n "$CPP_DIR" ] && [ -x "$CPP_DIR/scripts/flow-stale-check.sh" ]; then
    # Advisory: names colliding files. The checkout is DECLARED (issue #614, the
    # #592 rule): pass the worktree path as the trailing literal argument rather
    # than trusting the Bash cwd, and check the emitted FLOW_STALE_PATH: line
    # names this run's tree.
    "$CPP_DIR/scripts/flow-stale-check.sh" origin/main /path/to/worktree
fi

git fetch origin main --quiet
if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]; then
    # COMMIT the work FIRST, then merge on the clean tree (issue #635; supersedes
    # the #521 stash-first order). Stashes live in the repo's COMMON git dir -
    # every linked worktree shares ONE stack - and two concurrent sessions doing
    # stash push -> merge -> bare pop silently swapped each other's uncommitted
    # work. A WIP commit is branch-local (a sibling cannot take it) and the
    # eventual squash-merge flattens it. NEVER use `git stash push` or a bare
    # `git stash pop` in a shared-worktree flow.
    if [ -n "$(git status --porcelain)" ]; then
        git add -A
        git commit -m "wip(flow): pre-merge snapshot"
    fi
    if ! git merge --no-edit origin/main; then
        echo "STOP: 'git merge origin/main' hit CONFLICTS. Resolve them, 'git add' + 'git commit', then re-run /flow:finish."
        git diff --name-only --diff-filter=U
        echo "NOTE: your work is safe in the 'wip(flow): pre-merge snapshot' commit on this branch."
        exit 1
    fi
    # Re-sync generated Codex skills if the merge pulled ANY command-family source
    # (issue #506; marketplace copies retired in #662). The LOCAL script re-syncs
    # THIS tree; [ -x ... ] keeps the step CPP-only.
    if [ -x scripts/codex-skill-sync.py ] && git diff --name-only ORIG_HEAD..HEAD | grep -q '^\.claude/commands/.*\.md$'; then
        python3 scripts/codex-skill-sync.py --write || true
    fi
fi
```

This is the early half of the #462 stale-branch guard; the Step-7 `/flow:merge`
guard remains the final backstop.

### Step 2: Run Quality Gates via Deterministic Runner (primary path)

**Primary path:** ONE audited helper owns the deterministic-runner invocation
(issue #613, the #581 pattern): CPP-checkout resolution, the `uv` check, the
documented `PYTHONPATH` / `uv run --project` contract (#430), and the
`make lint` + `make test` + `make typecheck` fallback all live in
`scripts/flow-finish-gate.sh`.
Do NOT re-implement any of it as inline bash - a leading env-var assignment
plus an interpolated `$CPP_DIR` can never match a permission prefix rule, so
the inline shape prompts on every run. Invoke it BARE (#581 discipline):

```bash
~/.claude/scripts/flow-finish-gate.sh
```

(Exit 127 - helper not installed: fall back to
`${CLAUDE_PLUGIN_ROOT}/scripts/flow-finish-gate.sh` (bundled with the plugin,
#590), else the CPP-checkout copy; either may prompt once - tell the user to
run **`/flow:repair`** to restore the prompt-free lane.)

The helper ends with a machine-readable marker:

- `FLOW_FINISH_GATE: ok` (exit 0): gates passed - via the runner, or its
  documented Makefile fallback when the runner is unavailable (the helper
  prints a NOTE naming which path ran). If the runner ran, skip to Step 2d;
  if the fallback ran, continue with Step 2b (the runner includes the security
  scan, the Makefile fallback does not).
- `FLOW_FINISH_GATE: warn` (exit 0, issue #621): the gate PASSED but a test step
  exited 0 having executed no tests (every test skipped, or none collected).
  Continue as for `ok`, but report the counts from the runner's `warnings` array
  verbatim and say plainly that this gate proved nothing about the change - never
  summarize it as "tests passed". Name the missing prerequisite if the skips look
  load-bearing (a live database, a service, a credential) and offer the fuller
  test target if the Makefile has one.
- `FLOW_FINISH_GATE: fail` (exit 1): parse the runner/make output above the
  marker, report the failed step, and **stop**. Do not proceed to PR creation.
- `FLOW_FINISH_GATE: skipped` (exit 0): no runner AND no Makefile lint/test/typecheck
  targets - warn the user, then continue.

### Step 2b: Run Security Quick Scan (fallback only - runner includes this)

**Skip this step if the deterministic runner was used above** (it already includes security_scan).

Only run manually if the runner was unavailable:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" python3 -m lib.security gate flow_finish
```

- If the gate **fails** (critical findings): **stop and report**. Show findings and remediation.
- If the gate produces **warnings** (high findings): display them but proceed.
- If `lib/security` is not available, skip this step (warn the user).

**Gate behavior by severity (defaults - configurable in `.claude/security.yml`):**

| Severity | Effect on `/flow:finish` | What to do |
|----------|--------------------------|------------|
| CRITICAL | **BLOCKS** - flow stops, no PR created | Fix the finding, then re-run `/flow:finish` |
| HIGH | **WARNS** - displayed, flow continues | Review finding; fix if real, suppress if false positive |
| MEDIUM | Passes silently | No action needed |
| LOW | Passes silently | No action needed |

To suppress a known false positive, add it to `.claude/security.yml`:
```yaml
suppressions:
  - id: HARDCODED_SECRET
    path: tests/fixtures/.*
    reason: "Test fixtures with fake credentials"
```

### Step 2d: Documentation Update Check (optional, non-blocking)

If the Makefile has an `update_docs` target:

```bash
if [[ -f "Makefile" ]] && grep -q "^update_docs:" Makefile; then
    echo "Running: make update_docs"
    make update_docs
fi
```

When this target exists, check documentation freshness:

1. **C4 diagrams** - If `docs/architecture/` exists, check if C4 HTML files are older than recent code changes. If stale, warn:
   ```
   Docs may be stale - C4 diagrams last updated {date}, code changed since then.
   Run /documentation:c4 to regenerate.
   ```

2. **CLAUDE.md / README.md** - Scan for obviously stale references (e.g., commands that no longer exist, file paths that don't match). Report as non-blocking warnings.

**This step never blocks the flow** - it is purely informational.

When this PR closes a specification's last task, treat it as a graduation
candidate. Follow the canonical [knowledge lifecycle](../../../docs/agents/knowledge-lifecycle.md)
and run `scripts/knowledge-graduation-check.py` with the reviewed mapping and
this PR's URL before removing the spec. This is an explicit close-out step, not
an automatic network-coupled quality gate.

### Step 2c: Makefile Completeness Check (optional, non-blocking)

Run a quick Makefile validation and report any gaps as warnings - the same
audited helper as Step 2, in its advisory mode (it resolves the CPP checkout,
checks `uv`, and applies the #430 invocation contract itself; #613). Invoke
BARE (#581 discipline):

```bash
~/.claude/scripts/flow-finish-gate.sh --check-summary
```

- `FLOW_FINISH_GATE: warn` - **missing required targets**: display as a warning but **do NOT block**.
  ```
  ⚠️  Makefile check: 1 required target missing (typecheck)
      Run /cicd:check for details or /cicd:init to fix
  ```
- `FLOW_FINISH_GATE: ok` - report briefly - `"Makefile check: OK (6/6 targets present)"`
- `FLOW_FINISH_GATE: skipped` - `lib/cicd` unavailable or no Makefile: skip silently (Step 2 already handles the no-Makefile case)

**This step never blocks the flow** - it is purely informational.

### Step 3: Check for Changes

```bash
# Check for uncommitted changes
git status --porcelain
```

**Guard against silently-ignored new files** (issue #430, Finding 1). A
blanket `.gitignore` rule (e.g. `*.json`) can swallow a file you meant to
commit - `git add` no-ops with no error. Surface it before committing:

Advisory - warns, never blocks; invoke bare at the stable path (#581
discipline; on exit 127 skip it):

```bash
~/.claude/scripts/check-ignored-additions.sh
```

- If it warns, confirm each listed file is genuinely scratch. If any is an
  intended addition, add a `!negation` to `.gitignore` (or narrow the blanket
  rule) and re-stage before committing.

- If there are uncommitted changes, help the user commit them using standard git commit workflow.
- Use conventional commit format: `type(scope): Description (Closes #N)`
- Include `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>` if Claude helped write the code.
- **An already-clean tree here is a LEGITIMATE state, not a failure** (issue
  #635): when the Step-1 stale-base merge ran, the work is already on the
  branch in the `wip(flow): pre-merge snapshot` commit. Skip cleanly and leave
  the WIP commit as-is - the squash-merge flattens branch history and the PR
  title/body carry the conventional message. Do NOT add a STOP for this state.

### Step 4: Push Branch

```bash
# Push with tracking
git push -u origin "$BRANCH"
```

### Step 5: Check for Existing PR

```bash
EXISTING_PR=$(gh pr list --head "$BRANCH" --json number,url --jq '.[0]' 2>/dev/null)
```

- If a PR already exists, report its URL and ask if the user wants to update it.
- If no PR exists, proceed to create one.

### Step 6: Create PR

Use standard PR creation:

```bash
gh pr create \
  --title "type(scope): Description (Closes #ISSUE_NUM)" \
  --body "## Summary
- <bullet points>

## Test plan
- [ ] Tests pass
- [ ] Linting passes

Closes #ISSUE_NUM"
```

- Title: Conventional commit style, derived from changes
- Body: Summary of changes + test plan + `Closes #N`
- Analyze all commits on the branch to draft the summary

### Step 7: Output

```
Quality gates passed:
  ✅ make lint
  ✅ make test
  ✅ security scan (quick)

Branch pushed: issue-42-fix-login → origin

PR created: https://github.com/owner/repo/pull/78
  Title: fix(auth): Resolve login redirect loop (Closes #42)
```

## Error Handling

- **Lint/test failure:** Stop, show output, ask user to fix
- **Push failure:** Report error (likely needs `git pull --rebase`)
- **PR already exists:** Report URL, offer to update
- **No issue number in branch:** Create PR without `Closes #N` reference
- **No Makefile:** Skip quality gates, warn user

## Notes

- Quality gates are optional - if no Makefile exists, the flow still works
- The commit step follows standard git commit conventions (the user controls the message)
- This command works from any worktree directory
