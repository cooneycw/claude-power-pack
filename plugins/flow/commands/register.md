# Flow: Register - Declare This Session's Wave Role

A worker session announces its own role to the wave orchestrator; the
orchestrator records the authoritative return address and addresses the worker
by socket forever after (issue #638, companion to the #637 wave loop).

## Why this exists

Session identity is unresolvable from the orchestrator's side, and the failure
is silent. `ListAgents` prints `projects-xx [ref]` display labels that do NOT
map to assigned roles; guessing misrouted three times in one four-worker wave
(2026-08-10), twice handing two workers each other's issue. The only address
that cannot be gotten wrong is the one the messaging transport itself stamps on
a delivered message - the `uds:/run/user/<uid>/cc-socks/<pid>.sock` value in
`from=`. Two facts make guessing unrecoverable: GitHub authorship cannot
disambiguate sessions (every worker commits as the same user), and a `/clear`ed
worker cannot vouch for its own history. So identity is DECLARED going forward
and stored outside any session's transcript.

## Arguments

- `ROLE` (required for register/get/release/verify): a short role label, e.g.
  `1`, `A`, `orchestrator`
- `--wave <name>`: wave namespace (default `default`) so concurrent waves on
  one host cannot collide
- `--list`: orchestrator side - show the roster instead of registering
- `--release`: leave the wave
- `--force`: take over a role held by a live session (deliberate override only)

## Instructions

All state lives in the wave registry, managed by ONE audited helper invoked
BARE at its stable path (#581 invocation discipline - never wrapped, chained,
or followed by `echo $?`):

```bash
~/.claude/scripts/flow-wave-registry.sh <verb> ...
```

(Exit 127 - helper not installed: fall back to
`${CLAUDE_PLUGIN_ROOT}/scripts/flow-wave-registry.sh`, else the CPP-checkout
copy; tell the user to run `/flow:repair` to restore the prompt-free lane.)

The registry is a host-level file OUTSIDE any repo and outside transcripts
(`$XDG_RUNTIME_DIR/cc-flow-wave/registry.json`): it survives a worker's
`/clear`, can never become shared mutable repo state (the #635 hazard class),
and is wiped by the OS at reboot - exactly when every session socket dies too.

### Worker side - `/flow:register <role> [--wave W]`

1. Register, passing what this session knows about its lane (literal values):

   ```bash
   ~/.claude/scripts/flow-wave-registry.sh register 1 --wave cpp --cwd /path/to/worktree --repo /path/to/repo --issue 42 --branch issue-42-slug
   ```

   The helper self-derives this session's socket by walking ancestor pids
   against the socket dir. That self-derived address is **bootstrap only** - an
   assertion, not an observation (see the trust model below). If it cannot be
   derived, the entry records `unknown` and the orchestrator's verify step
   supplies the address; registration still succeeds.

2. Act on the verdict line:
   - `FLOW_WAVE: registered` / `updated` - proceed.
   - `FLOW_WAVE: refused` (exit 1) - the role is held by a LIVE session. Two
     sessions both believing they are "worker 1" is the failure this command
     exists to prevent. **STOP** and report; only re-run with `--force` when
     the user confirms the other session is genuinely gone. A dead owner's
     entry is stale and taken over automatically - no `--force` needed.

3. Send the orchestrator a registration hello via `SendMessage` (to the
   orchestrator's socket from `get orchestrator`, or reply to its most recent
   message's `from=`), stating the role, wave, cwd, repo, and current
   issue/branch. This message is what lets the orchestrator OBSERVE the real
   address.

4. Confirm back to the user which orchestrator was registered with once the
   ack arrives.

### Orchestrator side

**On receiving a worker's hello**, reconcile the recorded address with the
address the transport actually stamped on that message:

```bash
~/.claude/scripts/flow-wave-registry.sh verify 1 --wave cpp --from uds:/run/user/1000/cc-socks/12345.sock
```

**Trust model (gate condition, #638): the transport-observed `from=` is
authoritative.** On `FLOW_WAVE: mismatch-corrected`, the observed address has
REPLACED the self-derived one as canonical and the entry is flagged
(`address_mismatch`); investigate the discrepancy, but keep addressing the
observed socket. The reverse never happens - a self-derived address never
survives a mismatch, and "flagged but self-derived kept" is not an outcome.

**Ack with the protocol.** The registration ack is the handshake: send the
worker its wave brief so the rules survive its compaction - the gate points
(stop at `/flow:auto` Step 3, no `--yes`), the completeness-ledger format
(delivered / in-scope / residual), its file lane, and the pushback rule,
stated verbatim:

> Workers verify assignments against the tree; "the orchestrator said so" is
> not evidence - pushback is structural, not polite.

The orchestrator has been the unreliable component in practice (three
orchestrator errors in the 2026-08-10 wave, all caught by workers). Treat "that
isn't me" or "that contradicts the tree" from a worker as an addressing or
orchestration bug, never as a confused peer. A re-register is also the cheap
re-brief for a worker whose compaction dropped more detail than expected.

**Roster** - `/flow:register --list [--wave W]`:

```bash
~/.claude/scripts/flow-wave-registry.sh list --wave cpp
```

- Shows `role -> address`, liveness, verification state, and current issue.
- Dead entries read `stale` and are kept, not deleted - a dead worker mid-issue
  is information, and its worktree claim outlives it.
- **Lane overlap warnings fire on the useful signal only**: same repo + same
  issue, same branch, or same/nested worktree paths between LIVE entries.
  Sharing a repo alone is the NORMAL wave shape (all workers, one repo,
  separate worktrees) and prints as info, never a warning - a warning that
  fires on the normal case trains everyone to ignore it.

**Addressing rule: socket-only.** Address workers exclusively by the registry's
`uds:` socket via `SendMessage`. Never address by `ListAgents` display names
(`projects-xx`) - those labels do not map to roles, and name-addressing is the
misrouting failure this command exists to remove.

### Release - `/flow:register --release`

```bash
~/.claude/scripts/flow-wave-registry.sh release 1 --wave cpp
```

Run on leaving the wave. Sessions that die without releasing are caught by
staleness detection (socket gone + pid dead); their entries persist as `stale`.
Releasing a role owned by another LIVE session refuses without `--force`.

## Output contract

Every verb ends with a machine-readable verdict:
`FLOW_WAVE: registered | updated | refused | released | listed | verified |
mismatch-corrected | free | unknown | error`, preceded by
`FLOW_WAVE_*=` detail lines. Exit 1 = refused (live-owner conflict), exit 2 =
usage error, else 0.

## Notes

- This command is the address-exchange half carved out of #637; the assignment
  loop, gate judging, and lane-disjointness ENFORCEMENT live there. This
  command only records lanes and warns on overlap.
- Registration is idempotent for the owning session: re-running refreshes the
  entry (new issue/branch/cwd) without ceremony.
- Roles are free-form labels; `orchestrator` is just a role, so workers can
  `get orchestrator` to discover where to send their hello.
- The helper needs `jq` (already a CPP bootstrap prerequisite).
