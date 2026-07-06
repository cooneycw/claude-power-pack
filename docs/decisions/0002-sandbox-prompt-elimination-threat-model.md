# ADR 0002: Sandbox-backed prompt elimination - Phase 0 threat model and guard design

- Status: Proposed (Phase 0 exit-bar artifact; gates Phase 1+)
- Date: 2026-07-06
- Deciders: cooneycw (owner)
- Issue: #541 (Phase 0 of a 5-phase enhancement)
- Supersedes: nothing
- Related: #482 / PR #490 (PermissionRequest census hook - the telemetry this feeds and must not corrupt), #519 (compound-command severity walk in the census), #534 / PR #540 (Codex restricted-sandbox awareness in the quality-gate runner - a DIFFERENT sandbox; see "Scope boundary"), anthropics/claude-code#43713 (the auto-allow static-analyzer bug this works around), https://code.claude.com/docs/en/sandboxing

## TL;DR

The dominant residual permission-prompt class in CPP flows is un-allowlistable
by construction: compound commands with `$(...)` substitution, `VAR=$(cmd)`
assignments, and `for`/`if` control flow. Claude Code's permission engine cannot
prefix-match these, and the census classifier withholds an allow candidate for
them by design. Claude Code now ships the counterpart mechanism natively: the
bash sandbox plus an auto-allow mode where the sandbox boundary is the approval.

This ADR is the Phase 0 threat model and guard design. It does three things and
scaffolds nothing:

1. **Reframes** the issue around what is now native. When #541 was filed the plan
   centred on a third-party PreToolUse "allow everything not asking to escape"
   hook (the Ten0 pattern from the #43713 thread). Claude Code now exposes a
   native `sandbox.autoAllowBashIfSandboxed` setting. The native setting is the
   primary mechanism; a CPP gate hook is justified ONLY as a narrow workaround for
   the residual #43713 static-analyzer gap, and only if empirical verification
   clears three currently-undocumented interactions.
2. **Decides the fail-closed posture, the census interaction, and the
   `excludedCommands` policy** - the parts that are pure design and do not need a
   live sandbox to settle.
3. **Names the empirical verification checklist and the go/no-go exit bar** that
   Phase 1 must clear before any settings block or hook is scaffolded. On this box
   those checks are currently BLOCKED on a missing `socat` prerequisite.

## Context

### The problem, quantified

The census (#482, #519) and the friction ledger show the dominant residual prompt
class can never be fixed by an allowlist rule. From the live buffers on
2026-07-05: 34 of 59 pending records rate `OTHER` with no allow candidate -
`$(...)` substitutions, `VAR=$(cmd)` assignments, `for`/`if`/heredoc control
flow. The classifier withholds candidates for these deliberately (unknown is not
safe), and the permission engine cannot prefix-match them regardless. Ledger
fingerprint `2711b88` recorded 251 of 254 prompts in one flow run as
`cd "$(git rev-parse --show-toplevel)" && <cmd>` compounds.

Codex runs the same command shapes without a single prompt because it uses
containment (`--sandbox read-only` or a disposable full-access worktree) rather
than per-command consent. The friction ledger is Claude-Code-only telemetry, so
this asymmetry is otherwise invisible to the retro.

### Scope boundary (what this is NOT)

This ADR concerns the **Claude Code native bash sandbox** that gates permission
prompts on the developer's own box. It is unrelated to #534 / PR #540, which made
the CPP quality-gate runner aware of the **Codex restricted sandbox** (setting
`UV_CACHE_DIR`, pinning `UV_PYTHON`, skipping network steps). Same word, two
different sandboxes. Nothing here changes `lib/cicd/`.

### Current-state facts (this box, 2026-07-06)

| Fact | Value | Consequence |
|------|-------|-------------|
| Claude Code version | 2.1.175 | Recent enough to have the native `sandbox.*` block, but docs may lead the binary; re-confirm key names via the `/sandbox` panel in Phase 1 |
| `bwrap` (bubblewrap) | present at `/usr/bin/bwrap` | Filesystem/process isolation primitive available |
| `socat` | MISSING | Sandbox network brokering primitive absent. On Linux the sandbox needs both; until `socat` is installed the sandbox is unavailable and NO empirical check can run |
| `kernel.apparmor_restrict_unprivileged_userns` | `0` | Unprivileged user namespaces are not AppArmor-restricted, so `bwrap` can create namespaces without a custom profile. If a future host sets this to `1` (Ubuntu 24.04 default), a bwrap profile is required |
| `sandbox.*` in `~/.claude/settings.json` | unset | No sandbox behaviour today; this is a clean slate, and the fallback-when-unavailable path is therefore live and must be reasoned about |

### The mechanism landscape (the reframing)

Research against the official sandboxing, permissions, and hooks docs (Phase 0)
established the following. Items marked (documented) are stated in the docs; items
marked (inferred) are logical consequences the docs do not state directly; items
marked (undocumented) have NO doc support and are the empirical-verification
blockers.

Native settings, believed available as of 2.1.175 (key names from the docs and
the shipped `settings-bash-sandbox.json` example; re-confirm in Phase 1):

- `sandbox.enabled` (default off until set) - turns the bash sandbox on.
- `sandbox.autoAllowBashIfSandboxed` (default `false`) - when `true`, a command
  the sandbox can fully contain is auto-allowed with no prompt. THIS is the native
  counterpart to the Ten0 hook. Default behaviour without it is "regular
  permissions mode": still prompt even when sandboxed. (documented)
- `sandbox.allowUnsandboxedCommands` (default `false`) - when `false`, the
  `dangerouslyDisableSandbox` escape parameter is ignored entirely (strict mode).
  (documented)
- `sandbox.failIfUnavailable` (default `false`) - when `false`, a missing
  `bwrap`/`socat` degrades to a warning and commands run UNSANDBOXED; when `true`,
  startup hard-fails instead. (documented)
- `sandbox.excludedCommands` (default `[]`) - commands that run outside the
  sandbox entirely. (documented)
- `sandbox.network.allowedDomains` / `deniedDomains` (default `[]`) - domain
  allow/deny for sandboxed network. `*.github.com` covers `gh` and `git fetch`.
  (documented)

The residual gap (anthropics/claude-code#43713): even with
`autoAllowBashIfSandboxed: true`, the static analyzer that decides "can the
sandbox fully contain this?" returns "ask" (prompts) on shapes it cannot parse -
`$VAR`, `"$VAR"`, `$(...)`, `$'...'`, `{a,b,c}`. Those are exactly CPP's two
dominant shapes. Partially fixed in 2.1.139, but the residual-pattern list in the
thread still includes command substitution and quoted expansion. Confirmed
relevant here: 2.1.175.

The Ten0 workaround from the same thread: a PreToolUse hook that returns
`permissionDecision: allow` for any Bash call NOT requesting
`dangerouslyDisableSandbox`, deferring on escape calls so the normal escape prompt
fires. Its entire value rests on one undocumented question (see the threat model,
T1): does a PreToolUse `allow` suppress the analyzer's prompt while leaving the
command INSIDE the sandbox? If `allow` bypasses the sandbox, the hook is not a
workaround, it is a hole.

## Threat model

Assets to protect: the developer's filesystem outside the repo, credentials
(`~/.aws`, `~/.claude`, ssh keys), the network egress path, and the integrity of
the census/friction telemetry. Trust boundary: the sandbox is the boundary
between model-issued shell commands and the host. The whole point of auto-allow is
to remove the human from the per-command loop, so the sandbox and the deny rules
become the ONLY enforcement left. Every failure mode below is "what if the
boundary is not actually where we think it is".

| # | Threat | Failure mode | Mitigation / decision |
|---|--------|--------------|-----------------------|
| T1 | Hook allow bypasses the sandbox | A CPP gate hook returns `allow`; if `allow` executes the command unsandboxed instead of sandboxed, every compound command now runs on the host with no prompt and no containment. Catastrophic. | Phase 1 empirical check E1 is a HARD gate. If E1 shows `allow` bypasses the sandbox, the gate hook is abandoned and we rely on the native `autoAllowBashIfSandboxed` alone (which by construction only auto-allows commands the sandbox contains). |
| T2 | Auto-allow with sandbox silently unavailable | `socat` missing (true today) plus `failIfUnavailable: false` means commands run unsandboxed. If a gate hook also auto-allows, unsandboxed commands run with no prompt. | Decision D1 (fail-closed): set `failIfUnavailable: true`, and the gate hook must DEFER (no decision) whenever it cannot positively confirm the sandbox is active. Never allow on uncertainty. |
| T3 | Escape hatch normalises to no-prompt | The model learns to set `dangerouslyDisableSandbox: true` to get out of the sandbox; if that path is auto-allowed, escape becomes free. | Keep `allowUnsandboxedCommands: false` (escape parameter ignored). If a use case ever needs escape, the gate hook must DEFER on any call carrying `dangerouslyDisableSandbox`, so the normal escape prompt fires (Ten0's explicit carve-out). Escape always costs a prompt. |
| T4 | Deny rules silently weakened | An operator assumes auto-allow still honours `permissions.deny`; if hook `allow` outranked deny, a denied command would run. | Documented behaviour: deny and ask rules are evaluated regardless of a PreToolUse hook's decision; a matching deny blocks even when the hook returned `allow`. Phase 1 check E2 confirms this empirically before trusting it. Deny list stays the real backstop for `rm -rf ~`, credential paths, `.git/hooks`. |
| T5 | Network exfiltration via sandboxed command | Auto-allowed `curl`/`gh`/`git fetch` reach arbitrary hosts and exfiltrate repo contents. | `network.allowedDomains` scoped to the minimum (`*.github.com` for the flow surface); everything else denied by default inside the sandbox. Widen only per-project, never at user scope. |
| T6 | Census telemetry corrupted | If auto-allowed commands still fire the PermissionRequest census hook, the friction buffer fills with `shown` records for prompts that were never actually shown, poisoning the retro's "N prompts would vanish" signal. If they do NOT fire it, friction.jsonl silently becomes a residual-prompt metric with no migration note. | Decision D2: Phase 1 check E3 determines which case holds; the retro (Phase 3) is updated to match, and the change is documented so the metric's meaning is not silently redefined. |
| T7 | `excludedCommands` becomes an un-audited allow hole | Commands listed in `excludedCommands` run outside the sandbox; if auto-allow also applies to them, they are unsandboxed AND unprompted. | Decision D3: ship an EMPTY `excludedCommands`. Any addition is a deliberate, reviewed exception that must be paired with a `permissions.ask` or `deny` rule so exclusion never silently combines with auto-allow. |

## Decisions (settled in Phase 0, no live sandbox required)

**D1 - Fail-closed posture.** The configuration and any future gate hook must
fail closed:

- Sandbox settings ship with `failIfUnavailable: true` so a missing prerequisite
  hard-fails at startup rather than silently running unsandboxed. This closes T2's
  silent-fallback path.
- A gate hook, IF one is ever shipped, must DEFER (emit no decision, exit 0) - not
  allow - whenever any of these is true: sandbox settings are unreadable;
  `sandbox.enabled` is false or absent; the payload does not let the hook confirm
  the sandbox is active for this call; a prerequisite (`bwrap`/`socat`) is missing;
  or the Bash call carries `dangerouslyDisableSandbox`. Allow is emitted ONLY on
  positive confirmation that the command will be sandboxed. connorbrinton's #43713
  warning is the load-bearing rule: a hook that allows without confirming the
  sandbox is enabled auto-allows every command UNSANDBOXED.

**D2 - Census interaction.** The census hook stays as-is in Phase 0. Phase 1's E3
check decides empirically whether auto-allowed commands still raise a
PermissionRequest. Phase 3 then either (a) documents that friction.jsonl has
become a residual-prompt metric (auto-allowed commands no longer recorded), or
(b) adds a filter so census records are not written for sandbox-auto-allowed
commands. Either way the metric's meaning gets an explicit migration note; it is
never silently redefined. Separately, the known census classifier gaps
(`VAR=$(cmd)` env-assignment stripping that swallows the command word;
`for`/`if`/`[` rating `OTHER`) are noted here for Phase 3 but NOT fixed in this
ADR.

**D3 - `excludedCommands` policy.** Ship `excludedCommands: []`. Exclusion plus
auto-allow equals unsandboxed-and-unprompted (T7), so any future entry is a
reviewed exception that must be paired with an `ask`/`deny` rule. No blanket
exclusions.

**D4 - Prefer native over hook.** The native `autoAllowBashIfSandboxed` is the
primary mechanism precisely because it only auto-allows what the sandbox provably
contains - it cannot create T1. A CPP gate hook is adopted ONLY if Phase 1 proves
(E1) that a hook `allow` keeps the command sandboxed AND the residual #43713 gap
is wide enough to matter after the native setting is on. If E1 fails, we ship the
native setting alone and accept prompts on the residual `$(...)` shapes until
#43713 is fixed upstream. Security beats prompt-count.

## Empirical verification checklist (Phase 1 exit bar)

These CANNOT be settled from docs - the docs are silent or only support an
inference. They are BLOCKED on this box until `socat` is installed and the sandbox
is enabled in a scoped trial. Each must pass before any user-level rollout.

- [ ] **E1 (T1, hard gate):** With the sandbox enabled, a PreToolUse hook that
  returns `allow` for a filesystem-write command runs it INSIDE the sandbox (write
  to `/etc` or `$HOME` outside the repo is blocked), not on the host. Method:
  enable sandbox in a throwaway project, register a probe hook that allows a
  `touch ~/sandbox-escape-probe` call, confirm the file is NOT created on the host.
- [ ] **E2 (T4):** A `permissions.deny` rule blocks a command even when the gate
  hook returns `allow` for it (deny evaluated first). Method: deny a sentinel
  command, have the hook allow it, confirm it is still blocked.
- [ ] **E3 (T6, D2):** Determine whether a sandbox-auto-allowed command still fires
  the PermissionRequest census hook. Method: enable auto-allow, run a compound
  command that would normally prompt, inspect friction.jsonl for a new `shown`
  record.
- [ ] **E4 (T3):** A Bash call with `dangerouslyDisableSandbox: true` still prompts
  under auto-allow, and with `allowUnsandboxedCommands: false` the parameter is
  ignored (command stays sandboxed or fails, never silently escapes).
- [ ] **E5 (prereq):** With `failIfUnavailable: true` and `socat` absent, startup
  hard-fails (no silent unsandboxed fallback). Then install `socat` and confirm the
  sandbox actually activates on this kernel (`apparmor_restrict_unprivileged_userns=0`).
- [ ] **E6:** Confirm the native `sandbox.*` key names and defaults against the
  installed 2.1.175 `/sandbox` panel, since docs may lead the binary.

## Go / No-Go exit bar for Phase 1

Phase 1 (sandbox enablement, scoped trial) may begin once this ADR is accepted.
Phase 2 (the gate hook) is GATED and may begin only if:

- E1 passes (hook `allow` keeps the command sandboxed), AND
- E2 passes (deny still outranks hook allow), AND
- after the native `autoAllowBashIfSandboxed` is on, a measured replay of the
  recorded Step-1 command shapes still shows enough residual #43713 prompts to
  justify the hook's risk surface.

If E1 fails, Phase 2 is abandoned and the project ends at the native setting
(D4). If the residual prompt count after the native setting is negligible, the
hook is unnecessary. In both cases Phase 0's security-first framing has done its
job: it stopped us from scaffolding a hook that would either be a hole or be
redundant.

## Consequences

- Phase 1 acquires a hard prerequisite: install `socat`, then run E1-E6 in a
  scoped single-project trial before any user-level settings change.
- The issue plan is corrected: "PreToolUse gate hook" moves from "the mechanism"
  to "a conditional, empirically-gated workaround for a specific upstream bug".
- No production behaviour changes from this ADR. `~/.claude/settings.json` is
  untouched; the census hook is untouched; `make deploy` is unaffected.
- If the docs' key names prove wrong at E6, Phase 1 corrects them before rollout;
  nothing downstream has hard-coded them yet.

## References

- Issue #541 (this epic); anthropics/claude-code#43713 (auto-allow analyzer bug;
  Ten0 gate 2026-06-11, connorbrinton fail-closed warning 2026-04-09, residual
  patterns).
- https://code.claude.com/docs/en/sandboxing, .../permissions, .../hooks.
- CPP #482 / PR #490 (census hook), #519 (severity walk), #534 / PR #540 (Codex
  sandbox awareness - distinct).
- Ledger fingerprint `2711b88` (cd-prefix volume finding, deliberately personal).
- Box state at authoring: Claude Code 2.1.175, `bwrap` present, `socat` MISSING,
  `apparmor_restrict_unprivileged_userns=0`, `sandbox.*` unset.
