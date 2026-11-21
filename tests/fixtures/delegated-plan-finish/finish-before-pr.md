### Step 7: Finish - Commit, Push, Create PR

**Last empty-diff backstop (issue #798).** Step 4 already fails closed on an
empty diff, and this repeats the check at the boundary that actually ships,
because the fix loop in Step 6 can also leave the tree unchanged:

```bash
BRANCH=$(git branch --show-current)
ISSUE_NUM=$(echo "$BRANCH" | grep -oP 'issue-\K[0-9]+' || echo "")

# EXPLICIT BASE, never `@{u}` (issue #1261). The worktree tracks its own
# not-yet-pushed name, so `@{u}` does not resolve here, and the old
# `2>/dev/null || echo 0` turned that into "nothing ahead" - an empty-diff STOP
# on a branch full of commits, or silence on the check it existed to make.
#
# CONTENT, not commit count (counter-model review, #1261): a change followed by
# its exact revert - committed OR still pending in the working tree - is commits
# ahead with an EMPTY PR diff. So compare what WILL be committed (the working
# tree's tracked content, plus any untracked file) against the merge base, and
# treat a failed comparison as a STOP.
git fetch origin --quiet || true
DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
if [ -z "$DEFAULT_BRANCH" ]; then
    for b in main master; do
        git rev-parse --verify -q "refs/remotes/origin/$b" >/dev/null && { DEFAULT_BRANCH=$b; break; }
    done
fi
if [ -z "$DEFAULT_BRANCH" ] || ! MERGE_BASE=$(git merge-base HEAD "origin/$DEFAULT_BRANCH"); then
    echo "STOP: could not resolve a merge base with origin/${DEFAULT_BRANCH:-<default branch>} - the empty-diff backstop cannot run, so it cannot pass."
    exit 1
fi
if ! TARGET_ROOT=$(git rev-parse --show-toplevel); then
    echo "DELEGATED_PRODUCT_CHANGE: fail - target checkout is unknown"
    exit 1
fi
EVIDENCE_LIBRARY="$(git -C "$TARGET_ROOT" rev-parse --absolute-git-dir)/delegated-product-evidence.sh"
if [ ! -f "$EVIDENCE_LIBRARY" ] || ! source "$EVIDENCE_LIBRARY" || ! delegated_product_paths 42; then
    echo "DELEGATED_PRODUCT_CHANGE: fail - shared evidence definition unavailable; repeat Step 1"
    exit 1
fi
git -C "$TARGET_ROOT" diff --quiet "$MERGE_BASE" -- "${DELEGATED_PRODUCT_PATHS[@]}"
CONTENT_RC=$?
if [ "$CONTENT_RC" -gt 1 ] || ! UNTRACKED=$(git -C "$TARGET_ROOT" ls-files --others --exclude-standard -- "${DELEGATED_PRODUCT_PATHS[@]}"); then
    echo "STOP: could not compare the working tree with $MERGE_BASE - the empty-diff backstop cannot run, so it cannot pass."
    exit 1
fi
if [ "$CONTENT_RC" -eq 0 ] && [ -z "$UNTRACKED" ]; then
    echo "DELEGATED_PRODUCT_CHANGE: fail - no content change outside this issue's evidence; refusing an empty product diff"
    exit 1
fi
echo "DELEGATED_PRODUCT_CHANGE: ok - final product changes exist"
# Keep this call in THIS shell block: MERGE_BASE is not shared across tool calls.
~/.claude/scripts/flow-plan-record.py compliance 42 --base "$MERGE_BASE"
```

**Record actual lane evidence and relay compliance before the closing reference.**
For each `will test` or `will refuse` lane, write a row (`Lane` / `Result`
`passed`, `failed`, `not run` or `refused as expected` / `Evidence`; only a
referenced pass or refusal counts) in
`docs/flow-runs/issue-42.lanes-demonstrated.md`, below this run's marker line as
the compliance note prints it. No lane file at approval, or no `will
test`/`will refuse`, owes no file/question. Never fill rows merely because a
test was promised.

The compliance call stays in the SAME shell block as `MERGE_BASE`. After
writing evidence, rerun that full block. Relay stdout/stderr/status into PR
and closing evidence: agreement 0, divergence/stability finding 3, unknown 4
(never agreement). This is reporting, not a new blocking quality gate. Relay
`LANES NOT DEMONSTRATED` counts/names and `LANES NOT CHECKED` reasons; follow
the stderr remedy. Never discard output/status or edit the approved promise.
Commit record/snapshot/owed evidence. Missing reports never establish
`ACCEPTANCE_COMPLETE=yes`.

Both product guards use the SAME Step-1 exclusions. Everything else, including
another issue's records/receipts, is product. The final check covers committed,
pending and untracked work, refusing evidence-only reverts and receipt-only
diffs.

1. **Commit** the changes:
   - Conventional commit format using the selected reference:
     `type(scope): Description (${ISSUE_REF})`
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

   The closing reference follows the acceptance accounting: use it only when every
   material item is demonstrated, revised with evidence, or resolved by a recorded
   transfer. Otherwise reference the issue without a closing keyword (`Refs #N`), in
   the commit message, the PR title and the PR body alike. Do not print a closing
   keyword beside an issue number even as an illustration - the merge helper refuses a
   squash that carries one incidentally (exits 5 and 7).
   **Acceptance disposition before closing (issue #860).** Account for the material
   acceptance items first - demonstrated, revised with evidence, or deferred - and
   record the accounting in the PR body as ordinary prose. When it is unresolved, use `Refs #N` in the commit
   message, the PR title and the PR body instead of `Closes #N`, and check the earlier
   branch commits too (read `git log origin/main..HEAD --format=%B` and the PR text yourself),
   since the squash text may be derived from them - `gh-pr-merge.sh`
   passes an explicit subject and body from the PR (#655), so check which sources are
   actually in play rather than assuming a rewrite is needed. A delegated run that delivered part of
   the work is still mergeable; it just must not close the promise. The canonical rule
   is docs/agents/issue-contract.md.
   - Include a `Co-Authored-By: <name> <noreply@anthropic.com>` trailer naming
     the current session's own assistant model - never copy a model+version
     literal from this document, which goes stale every time the assistant
     model changes and was already wrong in 8 places at once (issue #1037)
   - Note Codex as implementer in the commit body

2. **Push** the branch:
   ```bash
   git push -u origin "$BRANCH"
   ```

```bash
~/.claude/scripts/flow-plan-record.py finish 42
```

3. **Create PR** if no PR exists:
   ```bash
   gh pr create --title "type(scope): Description (${ISSUE_REF})" --body "..."
   ```
   - PR body includes:
     - Summary of changes
     - Note that implementation was delegated to Codex CLI
     - Claude Code review findings
     - Test plan
     - `${ISSUE_REF}` - the selected reference, non-closing unless the
       accounting is complete

Report: `Step 7/8: Finish complete - PR #{N} created`

---

