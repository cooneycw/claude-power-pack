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
| Flow helper scripts | `~/.claude/scripts/{flow-start-resolve, flow-stale-check, flow-worktree-guard, flow-live-driver-guard, gh-pr-merge, worktree-remove}.sh` | the audited flow helper family (issue #581): Step-1 resolve + verify gate, stale-base / leaked-edit / live-driver guards (Steps 4 and 6), PR squash-merge + worktree cleanup (Step 7) |

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

## The flow helper-script rules (issue #581)

The compound bash blocks flow Step 1 used to run (variable assignments, loops,
command substitution) could never match a prefix rule, so they prompted on
every run even with the full allowlist installed - the #482 census evidence
behind #581. The plumbing now lives in the audited helper family above,
installed at the stable `~/.claude/scripts/` path by `/cpp:init` /
`/cpp:update`, with one rule per script. Three caveats, stated plainly:

- **A path rule trusts the script's FUTURE content too** - the rule matches
  the path, not a content hash. Acceptable for a user-owned repo whose
  scripts arrive by user-confirmed `/cpp:update`; if that trust model does
  not fit your box, remove the script rules and accept the prompts.
- **`gh-pr-merge.sh` and `worktree-remove.sh` are mutating helpers** - PR
  squash-merge (flow Step 7, after the quality gates and the user-invoked
  flow) and worktree/branch removal. They are deliberately included (the
  point of #581 is a zero-prompt flow), while raw `git push`, `git commit`,
  and `gh pr create/merge` stay excluded - the Step 6 shipping gate is
  unchanged, and the allowlisted surface is the audited helper, not the bare
  shipping command.
- **Rules only match BARE invocations.** `~/.claude/scripts/foo.sh 42` is
  auto-allowed; `foo.sh 42; echo $?` or `if [ -x ... ]; then ...` is a
  compound command and prompts. The flow docs (auto.md Steps 1/4/6/7,
  start.md) encode this invocation discipline; helpers print their own status
  markers so no wrapper is ever needed.

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
