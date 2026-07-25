---
description: Codex reviews the code on the current branch (read-only) and returns structured findings - the cross-model pre-PR review stage
allowed-tools: Bash(codex:*), Bash(git:*), Bash(mktemp:*), Bash(cat:*), Bash(rm:*), Bash(test:*), Bash(wc:*), Bash(command -v codex), Read
---

# Codex Code Review: Cross-Model Review of the Current Branch

Have OpenAI Codex (`gpt-5.5`) review the code changes on the current branch as an
independent second model, and relay its findings in a structured format a caller
can act on. Codex runs **read-only**: it reads the diff and the surrounding files,
it cannot modify anything. The review is advisory - Claude (or the user) triages
the findings and decides what to fix.

This is the reviewer counterpart to the other Codex commands:

- **`/codex:code_review`** (this) - Codex reviews code Claude wrote. Read-only, structured findings.
- **`/codex:ask`** - ask Codex a free-form read-only question.
- **`/codex:exec`** - hand Codex a coding task (writes files).
- **`/codex:auto`** - full issue lifecycle delegated to Codex, with Claude reviewing.
- **`/second-opinion:start`** - review via *other* external LLMs through the MCP server.

The primary consumer is `/flow:auto_codex`, which inserts this review between
Implement and Finish so findings are fixed before the PR exists. It is equally
usable standalone from any branch or worktree.

## Arguments

- `BASE` (optional): the base ref to diff against (e.g. `origin/main`). Default:
  `origin/<default-branch>` resolved from the repo, falling back to `origin/main`.
- `CONTEXT` (optional): extra reviewer context - typically the issue number or a
  one-line statement of intent, so Codex reviews against the intended change
  rather than guessing it.

## Instructions

When the user invokes `/codex:code_review [BASE] [CONTEXT]` (or a workflow calls
it as a stage), perform these steps:

### Step 1: Preflight

```bash
if ! command -v codex >/dev/null 2>&1; then
    echo "CODEX_REVIEW: unavailable (Codex CLI not found - npm install -g @openai/codex; codex login)"
    exit 3
fi
codex --version
```

Exit 3 is the "unavailable" contract: a calling workflow treats it as
degrade-and-continue (warn, skip the review stage), never as a hard failure of
the run. Standalone, report it to the user and stop here.

### Step 2: Collect the diff

Resolve the base and capture what the review is about. Include committed and
uncommitted work - pre-PR review runs before the Finish-stage commit exists:

```bash
BASE="${BASE:-origin/$(git remote show origin 2>/dev/null | grep -oP 'HEAD branch: \K\S+' || echo main)}"
git fetch origin --quiet || true

DIFF_FILE=$(mktemp /tmp/codex-review-diff.XXXXXX.patch)
git diff "$BASE" > "$DIFF_FILE"
git diff --stat "$BASE"
wc -l "$DIFF_FILE"
```

If the diff is empty, report "nothing to review vs $BASE" and stop (exit 0) - an
empty review is a success, not a failure.

For very large diffs (thousands of lines), note it and proceed - Codex can also
open files itself in the read-only sandbox - but name the most important files in
the prompt so the review focuses where the risk is.

### Step 3: Run the review

Pipe the diff on stdin and ask for structured findings. Same sandbox posture as
`/codex:ask`: read-only, no network escalation, `--output-last-message` for the
clean answer.

```bash
FINDINGS=$(mktemp /tmp/codex-review.XXXXXX.md)

cat "$DIFF_FILE" | codex exec \
    --sandbox read-only \
    --color never \
    --skip-git-repo-check \
    --output-last-message "$FINDINGS" \
    "You are reviewing a code change as an independent reviewer. The unified diff is provided on stdin; you may also open the files in this repository (read-only) for surrounding context. Review intent/context: ${CONTEXT:-none provided}.

Review for: correctness bugs, security issues, missed edge cases, broken or missing tests, and meaningful simplifications. Do NOT restyle working code or comment on formatting.

Return ONLY a findings report in exactly this format:

## Findings

### [SEVERITY] short title
- File: <path>:<line>
- Issue: <one-paragraph description of the defect and the failure scenario>
- Suggestion: <concrete fix>

Severity is one of CRITICAL, HIGH, MEDIUM, LOW. Order findings most severe first. If the change is sound, return '## Findings' followed by 'None - no defects found.' Do not pad with praise or restate the diff."

CODEX_EXIT=$?
```

Deep reviews of large diffs can run for many minutes; for anything non-trivial
run the command in the background and poll, exactly as documented in
`/codex:ask` under "Long-running delegations".

### Step 4: Relay the findings

```bash
echo "===== Codex (gpt-5.5) code review ====="
cat "$FINDINGS"
rm -f "$DIFF_FILE" "$FINDINGS"
```

Present the findings **attributed to Codex** - never silently merged into your
own assessment. Then, standalone, add your own labeled triage: for each finding,
agree (worth fixing), disagree (with the reason), or defer (real but out of
scope). Do not apply fixes in this command - it is read-only by design; fixing
is the caller's decision (`/flow:auto_codex` Step 5 does exactly that).

If `CODEX_EXIT` is non-zero, report the failure honestly and do not fabricate
findings; a calling workflow treats it like the exit-3 unavailable case.

## Notes

- Uses the user's **Codex account** (real quota/billing per call). One review
  pass plus at most one re-review is the intended cadence - never loop.
- Read-only sandbox: safe to run inside a live repo; Codex cannot write or reach
  the network. Codex always reaches OpenAI to run the model itself.
- The findings format above is the contract `/flow:auto_codex` parses for its
  triage table - keep the prompt's format block intact if you adjust the prompt.
- For a review by non-OpenAI models, use `/second-opinion:start` instead.
