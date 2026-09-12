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
  summarize it as "tests passed". `warn` also means a test failed on the first
  attempt and PASSED when re-run against only its failed ids (issue #769) - the
  ids are on the `RERUN_PASSED:` line above the marker. Proceed, but report those
  ids and never call the run a clean pass. Name the missing prerequisite if the
  skips look load-bearing (a live database, a service, a credential) and offer
  the fuller test target if the Makefile has one.
- `FLOW_FINISH_GATE: fail` (exit 1): parse the runner/make output above the
  marker, report the failed step, and **stop**. Do not proceed to PR creation.
- `FLOW_FINISH_GATE: skipped` (exit 0): no runner AND no Makefile lint/test/typecheck
  targets - warn the user, then continue.

### Step 2b: Run Security Quick Scan (fallback only - runner includes this)

**Skip this step if the deterministic runner was used above** (it already includes security_scan).

Only run manually if the runner was unavailable:

```bash
PYTHONPATH="${HOME}/Projects/claude-power-pack" uv run --project "${HOME}/Projects/claude-power-pack" python -m lib.security gate flow_finish
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

**Acceptance accounting (issue #860).** The quality gates above are evidence about
CHECKS. Before opening the PR, account for what was actually delivered: every
material acceptance item is demonstrated (name the behavioural test, experiment or
reviewed observation), revised (give the reason and the agreement it needed), or
deferred (and still owed). A couple of sentences of prose is enough for a small
change - there is no required per-item line and no separate artifact. Silence is not
delivery: an item nobody mentions is unresolved.

Assess the evidence against the CURRENT agreed behaviour. After a #859 revision,
evidence that satisfied the earlier promise has to be reassessed against the new
one - sometimes it still suffices, often it does not, and that judgement belongs in
the report rather than being assumed either way. A revision record on its own is
never delivery evidence, and
a revision record on its own is not delivery evidence.

The report stays ordinary prose - there is no field to fill in, and nothing is
parsed out of it. Carry the judgement into the one place it has to act: the closing
step sets `ACCEPTANCE_COMPLETE=yes` ONLY when every material item is demonstrated,
revised with evidence for the revised behaviour, or resolved by a transfer or
withdrawal that recorded its authority and destination. Anything else - including
"mostly done" - leaves it unset, and unset cannot close.

**Closing must agree with that judgement.** When the accounting is not complete, the
selected reference is the non-closing `Refs #N` - in the commit message, the PR title
and the PR body alike, never `Closes #N` - so the merge cannot close a promise the
report says was not kept.

Then review whatever will actually become the merge text: the PR title and body, and
the branch commits where they feed the squash. `gh-pr-merge.sh` passes an explicit
subject and body derived from the PR (#655), so on that path an older commit's wording
does not reach the squash - but a plain `gh pr merge --squash` can compose it from the
commits, and that is when a stale closing reference still matters. Check the sources in
play rather than rewriting history on the assumption that they always feed it:

```bash
git log origin/main..HEAD --format=%B
gh pr view "$PR_NUMBER" --json title,body --jq '.title, .body' 2>/dev/null
```

Read the closing references there yourself rather than grepping for one spelling -
the merge helper rejects negated and incidental forms too, and a narrow pattern
misses exactly the ones that surprise you.

The canonical rule is [the issue contract](../../../docs/agents/issue-contract.md);
this is where it is executed. Partial delivery stays reviewable and mergeable - the
disposition changes what CLOSES, not what may merge.

**Wording an unresolved report.** Reword closing references to a plain mention -
`Refs #N`, or "part of #N" - in the commit messages, the PR title and the PR body. Do
not print a closing keyword beside an issue number even to illustrate what to remove:
`gh-pr-merge.sh` refuses a squash carrying a negated or incidental closing keyword next
to an issue number (exits 5 and 7), and it cannot tell an example from an instruction.
A report that demonstrates the mistake interrupts the merge it was trying to protect.

```bash
# Reference selection (issue #860). Default to a NON-closing reference; a closing one
# is used only after your own acceptance accounting for THIS issue. Reset it here
# rather than inheriting a value from an earlier run.
ACCEPTANCE_COMPLETE=""     # "yes" only when every material item is demonstrated,
                           # revised with evidence, or resolved by a recorded transfer
ISSUE_REF="Refs #${ISSUE_NUM}"
if [[ "$ACCEPTANCE_COMPLETE" == "yes" ]]; then
    ISSUE_REF="Closes #${ISSUE_NUM}"
fi
```

`$ISSUE_REF` then feeds the commit message, the PR title and the PR body, so an
incomplete accounting cannot publish a closing reference anywhere.

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
- Conventional commit format, using the selected reference:
  `type(scope): Description (${ISSUE_REF})`
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
  --title "type(scope): Description (${ISSUE_REF})" \
  --body "## Summary
- <bullet points>

## Test plan
- [ ] Tests pass
- [ ] Linting passes

${ISSUE_REF}"
```

- Title: Conventional commit style, derived from changes
- Body: Summary of changes + test plan + `${ISSUE_REF}`
- Analyze all commits on the branch to draft the summary

### Step 6b: Route Supplemental Findings to the Nit Store

A supplemental finding is anything true and worth fixing that you discovered
while doing something else: a defect noticed in passing, a rough edge found
while closing this issue, a contract narrower than its callers assume. Do not
widen this change to fix it, and do not drop it. Record it.

Resolve the repository's nit store:

```bash
# Key on the REMOTE, never the directory name. This step always runs from a
# per-issue worktree (`.../claude-power-pack-issue-865`), so a basename test
# falls through every time and the explicit mapping below never fires - leaving
# a full-text search as the only path, which is the opposite of the intent.
REPO=$(basename -s .git "$(git remote get-url origin 2>/dev/null)")
[ -n "$REPO" ] || REPO=$(gh repo view --json name -q .name 2>/dev/null)

case "$REPO" in
    kyle)              NIT_STORE=1004 ;;
    claude-power-pack) NIT_STORE=864 ;;
    codex-power-pack)  NIT_STORE=227 ;;
    *) NIT_STORE=$(gh issue list --search "Nit Store" --state open \
                     --json number --jq '.[0].number' 2>/dev/null) ;;
esac

# Never post into an empty number. A finding silently posted nowhere is the
# exact failure this step exists to prevent, so fail loudly instead.
if [ -z "$NIT_STORE" ]; then
    echo "No nit store for '${REPO:-unknown}' - file the finding as a normal issue." >&2
    exit 1
fi
gh issue comment "$NIT_STORE" --body "<one finding>"
```

`--search` is full text, not an exact title match, so it can select any open
issue merely mentioning the phrase. It is the last resort, not the normal path;
if it is what resolved the number, say so in the closing report.

If the repository has no nit store, file the finding as a normal issue instead.

- **One finding per comment.** State the file and line (or the command), what is
  wrong, why it matters, and which issue or PR you were working when you found
  it. The comment is the whole record; it is read later without your context.
- **The store is an inbox, not a backlog.** Comments are reviewed and aggregated
  into real issues later, so a comment is a disposition, not a fix.
- **It is not a place to hide a defect that warrants its own ticket now.** A live
  correctness, security, or data-loss problem gets its own issue, and the closing
  report says so.
- **Name what you stored, with the comment link, in the Step 7 output.** A
  finding recorded but never reported is indistinguishable from one dropped.

Having nothing to store is an ordinary outcome. Do not manufacture a finding to
fill this step.

### Step 7: Output

```
Quality gates passed:
  ✅ make lint
  ✅ make test
  ✅ security scan (quick)

Branch pushed: issue-42-fix-login → origin

PR created: https://github.com/owner/repo/pull/78
  Title: fix(auth): Resolve login redirect loop (Closes #42)

Supplemental findings: 1 stored in the nit store (#864)
  - scripts/deploy.sh:42 unquoted $PATH expansion
    https://github.com/owner/repo/issues/864#issuecomment-123456789
```

## Error Handling

- **Lint/test failure:** Stop, show output, ask user to fix
- **Push failure:** Report error (likely needs `git pull --rebase`)
- **PR already exists:** Report URL, offer to update
- **No issue number in branch:** Create PR with no issue reference at all
- **No Makefile:** Skip quality gates, warn user

## Notes

- Quality gates are optional - if no Makefile exists, the flow still works
- The commit step follows standard git commit conventions (the user controls the message)
- This command works from any worktree directory
