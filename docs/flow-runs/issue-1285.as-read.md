# Issue #1285 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1285
- Read at:      2026-09-27T11:49:36Z
- updatedAt:    2026-09-27T11:49:29Z   (context only - moves on comments and labels)
- Body digest:  5200377a3c5613dfd08f53f3b7bba9e39506c03f2032befdc832495a7813b3bc   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2398 of 2398 (cap 16384)

## Body as read
## Defect

`/codex:auto` hard-codes `--sandbox workspace-write` at Step 4 (`.claude/commands/codex/auto.md:408`) and in the fix loop (`:669`, rendered from `templates/delegated-driver-core.md`). Inside a Kyle session container that sandbox cannot start, so codex exits **0**, answers in prose, and changes nothing. A command-line `--sandbox` overrides `~/.codex/config.toml`, so Kyle's #1174 entrypoint setting (`sandbox_mode = "danger-full-access"`) cannot reach this lane.

Tracked from cooneycw/kyle#1396, where the owner chose this route (option 2) on 2026-09-27.

## Measured (kyle-session:release-fc7559a, `--security-opt no-new-privileges`, codex-cli 0.157.1)

| configuration | nonce file written? |
|---|---|
| no `--sandbox` flag (config: danger-full-access) | yes |
| `--sandbox workspace-write` | **no**, exit 0 ("sandbox requires `bwrap`, which is unavailable") |
| + `features.use_legacy_landlock=true` | no (still routes through bwrap) |
| codex's bundled `codex-resources/bwrap` mounted | no: "No permissions to create a new namespace" (default seccomp) |
| + `seccomp=unconfined` | no: "Failed to make / slave: Permission denied" (docker-default AppArmor) |
| + `apparmor=unconfined` | `uid_map` write refused (host `kernel.apparmor_restrict_unprivileged_userns=1`) |

So "install bubblewrap in the image" is not a fix without a broad relaxation of container hardening.

## Change

Both invocations read `${CODEX_AUTO_SANDBOX:-workspace-write}` and accept only `workspace-write` or `danger-full-access`. Any other value is refused loudly, never silently defaulted. CPP does not detect its caller: Kyle supplies the value as data, and only for containers it starts (the #1139 / kyle#1296 `CPP_DEFER_SURFACES` contract shape). Unset keeps today's behaviour and #735's fence exactly. The #735 post-execution overrun verification is unchanged and still runs.

## Cost, stated

When a caller sets `danger-full-access`, the mechanical network fence from #735 does not apply to that run. The textual execution fence and the overrun verification remain. The capability table and Notes say so.

## Acceptance

- [ ] Unset: both invocations still pass `--sandbox workspace-write`
- [ ] `CODEX_AUTO_SANDBOX=danger-full-access`: both pass that value
- [ ] Any other value refuses the run with a message naming the variable
- [ ] Codex skill mirrors and the delegated-core render stay in sync

