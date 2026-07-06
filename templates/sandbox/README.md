# Bash sandbox scoped settings (ADR 0002, issue #548)

`settings-bash-sandbox.json` is the scoped, fail-closed sandbox block validated by
the Phase 1 trial (`scripts/sandbox-phase1-trial.sh`). It is NOT installed by
`/cpp:init` or `/cpp:update` today - Phase 4 (#551) decides opt-in packaging. Use
it as a starting point for a single-project trial by copying its `sandbox` block
into a project's `.claude/settings.json` (project scope, never a blanket
`~/.claude/settings.json` rollout without the interactive `/sandbox` check first).

Each key, and why it is set this way (see the ADR decisions):

- `enabled: true` - turns the OS-enforced bash sandbox on.
- `failIfUnavailable: true` - a missing `bwrap`/`socat` hard-fails at startup
  instead of silently running commands unsandboxed (ADR D1, closes threat T2).
- `autoAllowBashIfSandboxed: true` - a command the sandbox can fully contain is
  auto-allowed with no prompt. This is the native counterpart to a gate hook and,
  by construction, only auto-allows what the sandbox provably contains (ADR D4).
- `allowUnsandboxedCommands: false` - strict mode: the `dangerouslyDisableSandbox`
  escape parameter is ignored, so escape never becomes a free no-prompt path
  (ADR T3). The `/sandbox` panel labels this "Strict sandbox mode".
- `excludedCommands: []` - nothing runs outside the sandbox. Any future entry is a
  reviewed exception paired with an `ask`/`deny` rule (ADR D3, threat T7).
- `network.allowedDomains: ["*.github.com"]` - the minimum for `gh` + `git fetch`;
  everything else is denied by default inside the sandbox (threat T5). Widen only
  per-project, and note the domain-fronting caveat in the sandboxing docs.

## Linux/WSL2 prerequisites

The Linux sandbox needs both `bubblewrap` and `socat`
(`sudo apt-get install bubblewrap socat`). If
`sysctl kernel.apparmor_restrict_unprivileged_userns` returns `1` (Ubuntu 24.04+
default), add the `bwrap` AppArmor profile from the sandboxing docs. On the trial
box both were satisfied (`bwrap` + `socat` present, `apparmor_userns=0`).

## Verify before trusting

Run `scripts/sandbox-phase1-trial.sh` to re-check E1-E6 on a given box/binary. The
sandbox is a real but not complete isolation boundary; read the "Limitations"
section of https://code.claude.com/docs/en/sandboxing before relying on it.
