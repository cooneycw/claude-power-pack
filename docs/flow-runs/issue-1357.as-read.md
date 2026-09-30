<!-- flow-run n=1 id=82991e90b13b4d4fb2ddeeb5581ba4ca -->
## Run 1 - issue #1357 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1357
- Read at:      2026-09-30T14:03:53Z
- updatedAt:    2026-09-30T14:03:44Z   (context only - moves on comments and labels)
- Body digest:  7adc0804e0450474179cc6e0588a7571b9f974671985741d3f7548d459c18f6c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2739 of 2739 (cap 16384)

### Body as read
## Problem

Under Codex, the generated `project-next` skill fails with a misleading error:

```
project-next: cannot resolve GitHub repository: gh repo view: error connecting to api.github.com
```

while a bare `gh repo view` in the same Codex session succeeds. Codex then misdiagnoses it ("the earlier connection failure has cleared", "gh generally couldn't reach GitHub").

## Root cause

- Codex runs commands in its workspace sandbox with **network disabled**, unless an approved prefix rule matches. `~/.codex/rules/default.rules` has `prefix_rule(pattern=["gh"], decision="allow")`, so a *top-level* `gh …` runs unsandboxed.
- `python3 scripts/project-next.py …` matches no rule, so it runs sandboxed; its child `gh repo view` (`lib/project_next/collect.py:298`) inherits the no-network sandbox. Prefix rules apply to the top-level argv only.
- The Codex skill generator (`scripts/codex-skill-sync.py`, `ADAPTATIONS` at ~L121) translates worktrees, AskUserQuestion, subagents, MCP, CLAUDE.md — but has **no network adaptation**. Claude Code's Bash tool has network, so source commands never mention it; the generated skill never tells Codex the helper needs network/escalation.

## Reproduction (verified 2026-09-30)

```
codex sandbox gh repo view --json nameWithOwner                     # -> error connecting to api.github.com
codex sandbox python3 scripts/project-next.py . --compact           # -> the exact error above
python3 scripts/project-next.py . --compact                         # (host) -> exit 0, full report
codex sandbox bash -c 'echo $CODEX_SANDBOX_NETWORK_DISABLED'        # -> 1 (unset on host)
```

## Proposed fix (two layers)

1. **Generator (primary).** Add a network adaptation to `codex-skill-sync.py` that fires when a skill's bundled scripts/libs (not just the command body — project-next's `gh` call lives in `lib/project_next/collect.py`) invoke network tools (`gh`, `git fetch`/`push`/`pull`, `aws`, …). The bullet tells Codex: run that helper with escalated (unsandboxed) permissions; a connection error from inside the sandbox means "no network", not "GitHub down".
2. **project-next (diagnostic).** When `CODEX_SANDBOX_NETWORK_DISABLED=1` and a `gh` call fails, report that the sandbox has no network and to rerun with escalation, instead of the bare connection error.

## Acceptance / negative controls

- Generator check: FAILS on the current generated `project-next` skill (no network bullet), PASSES once emitted; a skill with no network-calling helpers must NOT get the bullet.
- Diagnostic: under `codex sandbox` the new message appears; outside the sandbox the ordinary error path is unchanged.
- Regenerated/checked-in Codex skills updated (`codex-skill-sync.py --check` green).

