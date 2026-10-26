# Choosing a flow command and permission setup

Start with `/project:next` when you need help choosing an issue. Use
`/flow:doctor` to diagnose the environment before starting work.

## Choose how to work

Use `/flow:auto ISSUE` for the complete issue lifecycle. It pauses at the ELI5
plan and necessity checkpoint before implementation; invoking it does not remove
that checkpoint. Choose individual commands when you want to control each stage.

| Command | When to use it |
|---|---|
| `/flow:auto ISSUE` | Drive start, analysis, approved implementation, PR, merge, CI verification and deployment. |
| `/flow:start ISSUE` | Create or resume an issue worktree and branch. |
| `/flow:eli5 ISSUE` | Review the issue's intent, whether it is still needed, and the proposed plan before coding. |
| `/flow:check` | Check quality without committing or creating a PR. |
| `/flow:finish` | Run quality gates, commit, push and create the PR. |
| `/flow:merge` | Merge the PR and clean up its worktree and branch. |
| `/flow:deploy [target]` | Run the project's Makefile deployment target. |
| `/flow:sync` | Commit/push work in progress for pickup on another machine. |
| `/flow:status` | See active worktrees, dirty state and PR status. |
| `/flow:doctor` | Diagnose prerequisites, helpers and allowlist setup. |
| `/flow:repair` | Install missing flow helpers at their stable paths. |
| `/flow:cleanup` | Retire landed worktrees and prune stale references or merged branches. |
| `/flow:register ROLE` | Identify a worker session's role in a coordinated wave. |
| `/flow:wave NAME` | Coordinate multiple workers over dependency-ordered issues. |
| `/flow:help` | Open the command overview and detailed workflow examples. |

For a manual sequence, start an issue, implement the approved plan, check it,
finish the PR, then merge and deploy when appropriate. A check is not a commit;
a PR is not a merge. Read the requested action before approving it.

## Understand the setup choices

`/cpp:init` presents different choices with different effects:

- **Installation tier:** which CPP components to install.
- **Project permission profile:** Cautious, Standard, Trusted or Custom rules in
  `.claude/settings.local.json`: Cautious for the fewest automatic permissions, Standard for
  common development tools, Trusted for broad grants, or Custom to choose
  categories. Pick the scope you want to authorize for that project.
- **Optional user-level flow allowlist:** selected command rules merged into
  `~/.claude/settings.json`, applying across repositories. The merge preserves
  existing rules; `/cpp:update` can refresh it later.

The allowlist reduces repeated Claude Code permission prompts for GitHub/git
reads, worktree plumbing and named helper scripts. It also includes mutating
helpers, including PR merge and worktree removal. Review the scope before
opting in. Installation and permission choices do not supply missing tools.

The flow template does not add raw `git commit`, `git push`, `gh pr create` or
`gh pr merge` grants, broad git/gh namespaces, or file-dumper rules. Other
existing settings or profiles may already allow those operations. An allowlist
match governs a tool prompt; it does not replace the workflow's plan approval,
quality gates or authorization for the requested action. CPP's optional hooks
observe or advise; they do not block commands or redact output.

These settings describe Claude Code. In Codex, generated skills such as
`flow-auto` provide the workflow, while Codex's own approval and sandbox settings
govern execution.

## Why a helper may still prompt

Rules match the installed helper's stable path. For example, invoke
`~/.claude/scripts/flow-preflight.sh --harness claude` directly. Wrapping a helper
in an assignment, conditional or `cd ... &&` command can prevent that match.
Calling it directly does not grant permission that is absent from your settings.
A path rule also trusts future contents of that helper, so review updates.

For missing helpers, use `/flow:repair`; for setup choices, use `/cpp:init` or
`/cpp:update`. The [detailed allowlist reference](https://github.com/cooneycw/claude-power-pack/blob/main/templates/claude-settings-permissions.md)
explains included rules and caveats.

Preflight reports local gaps; it does not prove login, remote permissions or
email privacy. CPP selects installed Python 3.11 without downloading it; target
Python policy remains separate. Gate `ok` and `warn` describe execution and
coverage: inspect named skips and warnings before comparing results on one tree.
