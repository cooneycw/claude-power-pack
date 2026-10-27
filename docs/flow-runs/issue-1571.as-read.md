<!-- flow-run n=1 id=08df5709c36340519123a809328bd1e7 -->
## Run 1 - issue #1571 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1571
- Read at:      2026-10-27T10:50:38Z
- updatedAt:    2026-10-26T14:01:23Z   (context only - moves on comments and labels)
- Body digest:  a4be196402e74f4316045bd506168614eaaea47ef70b909a1c74915e758ad4d7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3885 of 3885 (cap 16384)

### Body as read
## Context

One session on a fresh-ish host (`proxVMwoodpecker20`, Ubuntu 22.04, Linux 6.8) running `/project:next woodpecker-baseline` then `/flow:auto 1 woodpecker-baseline` (cooneycw/woodpecker-baseline PR #3). The run reached a merge, but only after six environment gaps, each found mid-run by a hard failure. `/cpp:init`, `/cpp:status` and `/flow:doctor` never flagged any of them up front.

User's words: "we've had a few deficits so far, including the fact that the flow, allowlist, etc. menu was poorly documented / explained."

## Deficits observed (in order hit)

1. **`gh` too old, reported as an inventory problem.** Ubuntu's `gh 2.4.0` (2022) rejects `closingIssuesReferences` and `blockedBy`. `project-next` reported `resolve_inventory` / "inventory incomplete" with the raw `Unknown JSON field` error, not "gh is too old, need >= X". Fixed by installing gh 2.103.2 from cli.github.com.
2. **`~/.claude/lib/project_next/ownership.json` missing.** The `/project:next` command says to read it for the contract pin, but it isn't installed under `~/.claude/lib/` (the engine still ran, as v1.6). Either the doc path or the installer is wrong.
3. **No `uv`.** `flow-finish-gate.sh` fell back to the Makefile. In that repo it failed with exit 127 (`uv: not found`, `ruff: not found`) and reported `FLOW_FINISH_GATE: fail`, which reads the same as a real lint failure. A missing tool should be its own verdict, or caught by preflight.
4. **The runner's Python selection breaks on a 3.10 host.** CPP's `pyproject.toml` has `requires-python = ">=3.11"` with no upper bound and no `.python-version`. With only system 3.10 present, `uv run --project <CPP>` downloaded CPython 3.15, and `pydantic-core 2.41.5` failed to build (PyO3 0.26 supports up to 3.14). Fixed by hand with `uv python install 3.13` and `uv python pin --global 3.13`. Suggest a `.python-version` (or an upper bound) in CPP.
5. **No git identity, and email-privacy push rejection.** `git commit` failed with "Author identity unknown". With GitHub email privacy on, pushes using a private address are rejected. Preflight should check `user.email` and suggest the `<id>+<login>@users.noreply.github.com` address.
6. **`codex` absent.** The counter-model review was recorded `skipped / codex-absent`. That's correct handling, but nothing told the user beforehand that the default review stage can't run on this host.

## Also noticed

- **Non-deterministic gate verdict:** two consecutive `flow-finish-gate.sh` runs on the same tree returned `FLOW_FINISH_GATE: ok` (exit 0), then `warn (skipped gates: typecheck)` (exit 3).
- **`/flow:auto` is long and hard to follow:** the command doc runs about 1,500 lines, and the allowlist / "invoke helpers bare" / permission-prompt rules are spread across it. The user found the flow + allowlist surface poorly explained.

## Asks

- [ ] A single preflight (in `/flow:doctor`, run by `/cpp:init` and at the start of `/flow:auto` and `/project:next`) that checks: `gh` minimum version, `uv` present, a usable Python in the supported range, `git config user.email`, optional `codex`, and the installed `ownership.json`. It reports all gaps at once with copy-paste fixes.
- [ ] `project-next`: map `Unknown JSON field` from `gh` to "gh too old (have X, need >= Y)".
- [ ] `flow-finish-gate.sh`: report "tool not installed" (exit 127 from a gate) separately from a gate failure.
- [ ] Pin the runner's Python (a `.python-version`, or `requires-python` with an upper bound).
- [ ] Make the gate verdict deterministic, or document why `ok` and `warn (skipped gates: typecheck)` can both come from one tree.
- [ ] A short, plain-language guide to the flow command family and the permission allowlist: what each `/flow:*` does, when to use it, what gets allowlisted and why. Linked from `/flow:help` and `/cpp:help`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
