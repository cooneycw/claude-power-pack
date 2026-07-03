# Flow Read-Only Permission Allowlist

`claude-settings-permissions.json` is a user-level Claude Code permission
allowlist covering the read-only and worktree-plumbing Bash commands that
`/flow:auto` (and the other `/flow:*` commands) run before any code is
written - issue reads, worktree creation, staleness checks, and the
branch-slug text pipeline. Without it, every flow run in every repo triggers
a permission prompt per command.

It is merged into `~/.claude/settings.json` (user scope, applies across all
repos on the machine) by `/cpp:init` and refreshed by `/cpp:update`. The merge
is additive and idempotent: existing settings and rules are preserved, the
union is deduplicated, and re-running adds nothing. `/flow:doctor` reports
whether the allowlist is installed.

## What is included, and why

| Group | Rules | Used by |
|-------|-------|---------|
| GitHub reads | `gh issue view/list`, `gh pr view/list/checks`, `gh run view/list`, `gh repo view` | issue fetch (flow Step 1), ELI5 staleness check, CI verification |
| Git reads | `git status/log/diff/show/branch/rev-parse`, `git config --get`, `git remote -v` | analysis, ELI5 anchored history check, verification gates |
| Git plumbing | `git fetch`, `git worktree` | worktree create/list/remove (flow Steps 1 and 7) |
| Text pipeline | `echo/tr/cut/sed/basename` | the branch-slug sanitization pipeline in flow Step 1 |
| Filesystem reads | `grep/rg/ls/find/head/tail/wc`, `cd`, `pwd` | codebase exploration, directory verification gates |

## What is deliberately excluded

- **`git commit`, `git push`, `git merge`, `gh pr create`, `gh pr merge`** -
  CPP's gate policy: shipping actions stay behind explicit approval (or the
  deterministic `/flow:finish` path the user invokes on purpose).
- **`cat`** - reads file contents into terminal output. In CPP repos the
  PostToolUse masking hook redacts secrets, but this allowlist is user-level
  and applies in repos WITHOUT that hook; excluding `cat` keeps secret-file
  reads behind a prompt. (Claude's Read tool is governed separately.)
- **`git remote` (bare)** - `git remote add/remove` writes `.git/config`;
  only the exact read form `git remote -v` is allowed.

## Known caveat: `sed`

`Bash(sed:*)` is included because the flow Step 1 slug pipeline pipes through
`sed` twice, and a compound command only auto-approves when every segment is
allowed. The trade-off: `sed -i` (in-place file editing) is also covered by
the prefix rule, so sed-based file edits will not prompt. If that bothers
you, remove the `"Bash(sed:*)"` line from `~/.claude/settings.json` and
accept one prompt per flow run.

## Relationship to the /cpp:init permission profiles (Step 3b)

`/cpp:init` Step 3b writes per-PROJECT profiles (Cautious/Standard/Trusted)
to `.claude/settings.local.json`. Those govern one repo, are written only
when the file is absent, and predate the flow-plumbing needs (`git worktree`,
`git rev-parse`, the slug pipeline, `gh run` are not in the Standard
profile). This template is the USER-level floor that makes `/flow:*` quiet
everywhere; project profiles layer additional, repo-specific trust on top.
Claude Code merges permission rules across scopes, so the two compose.

## Origin

Codified 2026-07-03 from a friction retrospective: months of tolerated
`/flow:auto` pre-ELI5 permission prompts (issue #427). This template is also
the reference artifact for the grill-me cycle (#426) - its first acceptance
case is emitting exactly this list from a flow transcript.
