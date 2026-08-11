# Flow: Register - Declare This Session's Wave Role

A worker session announces its own role to the wave orchestrator; the
orchestrator records the authoritative return address and addresses the worker
by that address forever after (issue #638, companion to the #637 wave loop).

## Why this exists

Session identity is unresolvable from the orchestrator's side, and the failure
is silent. `ListAgents` prints `projects-xx [ref]` display labels that do NOT
map to assigned roles; guessing misrouted three times in one four-worker wave
(2026-08-10), and those labels MUTATE mid-session - a send that succeeded
against a label failed minutes later after the label silently changed, same
session, same ref (#672). The only address that cannot be gotten wrong is the
one the messaging transport itself stamps on a delivered message: the `from=`
value. Two facts make guessing unrecoverable: GitHub authorship cannot
disambiguate sessions (every worker commits as the same user), and a `/clear`ed
worker cannot vouch for its own history. So identity is DECLARED going forward
and stored outside any session's transcript.

**The address is an OPAQUE, transport-stamped token** (issue #675). The registry
stores whatever the transport put in `from=` and never parses or validates it -
`verify` is a string comparison. `uds:/run/user/<uid>/cc-socks/<pid>.sock` is
one form; a Remote Control lane stamps `bridge:session_<id>`; a future transport
will stamp something else again, and all of them work unchanged. Treat the token
as an identifier to carry, never as a path to interpret. The one genuinely
socket-specific mechanism is SELF-DERIVATION at registration (below), which
guesses this session's own address before any message has been delivered.

## Arguments

- `ROLE` (required for register/get/release/verify): a short role label, e.g.
  `1`, `A`, `orchestrator`
- `--wave <name>`: wave namespace (default `default`) so concurrent waves on
  one host cannot collide
  - Omitting `--wave` is loud (#671): `register`/`get`/`verify` into the
    literal wave `default` without an explicit flag print an advisory stderr
    line (register also names the likely intended wave when exactly one other
    wave has a live orchestrator - suggestion only, never auto-join), and
    `list` appends a `note:` line for live entries parked in other waves, so
    a worker stranded in `default` shows up in the orchestrator's roster view
    instead of requiring a raw-JSON dig. Advisory only - verdicts and exit
    codes are unchanged.
- `--list`: orchestrator side - show the roster instead of registering
- `--release`: leave the wave
- `--force`: take over a role held by a live session (deliberate override only)
- `--socket <addr>`: register an address learned by some means other than
  self-derivation (harness env, user relay) - the manual bootstrap lane for a
  session that cannot derive its own (#672). Always wins over derivation.
  Despite the name it takes ANY transport's address verbatim - `bridge:...` is
  as valid as `uds:...` (#675). The name predates the transport-opaque contract
  and is kept because it is a published flag; the same applies to the
  `FLOW_WAVE_SOCKET_*` output keys below.

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
and is wiped by the OS at reboot - exactly when every session's address dies too.

### Worker side - `/flow:register <role> [--wave W]`

1. Register, passing what this session knows about its lane (literal values):

   ```bash
   ~/.claude/scripts/flow-wave-registry.sh register 1 --wave cpp --cwd /path/to/worktree --repo /path/to/repo --issue 42 --branch issue-42-slug
   ```

   The helper self-derives this session's address by walking ancestor pids
   against the socket dir. **This step is genuinely uds-specific** and is the
   only one that is (#675): it can produce a `uds:` address or nothing, because
   guessing an address before any message has been delivered means looking for a
   socket file on disk, and no other transport leaves one. Everything downstream
   - storing, verifying, addressing - is transport-opaque.

   That self-derived address is **bootstrap only** - an assertion, not an
   observation (see the trust model below). If it cannot be derived, the entry
   records `unknown` and registration still succeeds - but read
   `FLOW_WAVE_BOOTSTRAP` before assuming the address arrives later (see "When
   there is no address" below). On a transport that exposes no sockets this is
   the NORMAL path, not a fault: the address arrives from the first delivered
   message instead.

2. Act on the verdict line:
   - `FLOW_WAVE: registered` / `updated` - proceed.
   - `FLOW_WAVE: refused` (exit 1) - the role is held by a LIVE session. Two
     sessions both believing they are "worker 1" is the failure this command
     exists to prevent. **STOP** and report; only re-run with `--force` when
     the user confirms the other session is genuinely gone. A dead owner's
     entry is stale and taken over automatically - no `--force` needed.

3. Send the orchestrator a registration hello via `SendMessage`, stating the
   role, wave, cwd, repo, and current issue/branch. This message is what lets
   the orchestrator OBSERVE the real address. Pick the first branch that
   applies:
   - the orchestrator's address from `get orchestrator` - message it directly;
   - no usable address, but the orchestrator has messaged this session before -
     reply to its most recent message's `from=`;
   - `get orchestrator` says `free`, or its address is `unknown` - the
     orchestrator has not (usefully) registered yet. This is NORMAL, not an
     error (issue #670): registration already succeeded in step 2 and never
     depends on the hello landing. Report
     `registered; orchestrator not yet in roster; hello deferred` and carry
     on. The hello fires on FIRST CONTACT from either side: when the
     orchestrator arrives it initiates contact (see the orchestrator side),
     and this session's REPLY is the deferred hello - the reply carries the
     transport-stamped `from=` that `verify` needs.

4. Confirm back to the user which orchestrator was registered with once the
   ack arrives - or that the hello is deferred because no orchestrator has
   registered yet.

### When there is no address - the bootstrap lanes (issue #672)

`FLOW_WAVE_BOOTSTRAP=deadlock` on `register`, `get`, or `list` means the
address in question is `unknown`. **This is blocked, not pending.** `verify`
needs a transport-observed `from=`, which needs a delivered message, which
needs somebody to already hold an address - so when neither side has one, no
amount of waiting produces it. The 2026-08-11 wave lost ~2 hours to exactly
this, reading a healthy-looking verdict while both sessions stood by.

`FLOW_WAVE_SOCKET_REASON` names the cause, and the two causes differ:

- **`no-sock-dir`** - the socket dir does not exist on this host. It is created
  **lazily**, so this is a point-in-time answer, not a permanent verdict: on
  2026-08-11 the same host had no dir at 07:52 and self-derivation succeeded at
  10:27. Registration is idempotent and re-derives, so the first lane below
  usually just works.
- **`no-match`** - the dir exists but no ancestor pid of this session owns a
  socket in it. A retry alone will not change that; use lane 2 or 3.

**Order the lanes by the evidence in front of you** (#675). `no-sock-dir` does
not distinguish "not yet" from "not this transport", and the two want opposite
first moves. Let the OBSERVED traffic decide rather than a verdict about the
host: if messages are arriving stamped with a non-`uds:` scheme, that is
evidence this host's live transport is not uds, so retrying self-derivation is
unlikely to pay and lanes 2/3 are the better first move. With no such evidence,
`no-sock-dir` really may be the lazily-created dir and lane 1 is the cheap try.
Neither reading is a permanent claim about the host - a host with no dir at
07:52 had one at 10:27, and this wave ran on that host's later state.

Three lanes produce an address without self-derivation:

1. **Re-register.** Re-run the same `register` command. It re-derives and
   adopts a socket that has since appeared (`FLOW_WAVE_SOCKET_SOURCE=self`).
   Only this lane depends on a uds transport.
2. **`register --socket <addr>`** - the manual lane, and the one that works on
   any transport. Pass an address learned by any means (harness env, or the user
   relaying it from the other session), in whatever form that transport stamps;
   an explicit `--socket` always wins (`SOURCE=explicit`).
3. **User-relayed hello.** The user pastes this session's `FLOW_WAVE_*` block
   into the counterpart session; the counterpart's reply arrives over the real
   transport, and its `from=` is what `verify` needs.

**A failed derivation never downgrades a recorded address.** Re-registering as
the cheap re-brief is safe: if the walk comes back `unknown` while the roster
already holds an address, the recorded one is KEPT and reported as
`SOURCE=preserved`. A known address always outranks `unknown` - you cannot
message `unknown` - which is the #638 trust model read in its other direction.

### Orchestrator side

**Registration is order-independent (issue #670).** Workers registering before
the orchestrator is NORMAL practice - a user opens worker terminals first, or a
worker session outlives an orchestrator restart. On registering as
`orchestrator`, and on each `list`, treat every pre-existing unverified LIVE
worker as a PENDING HANDSHAKE (the roster's `[live, unverified]` entries are
exactly this list): initiate contact with each one at its recorded bootstrap
address. The worker's REPLY is its deferred hello, and the reply's
transport-stamped `from=` feeds `verify` below - so verification is reachable
from whichever side makes first contact. A worker whose address recorded as
`unknown` cannot be contacted orchestrator-first; that is the address-bootstrap
gap (#672), not an ordering problem - it waits until either side can produce a
usable address - see "When there is no address" above for the three lanes that
produce one, and pick the lane by the evidence described there.

**On receiving a worker's hello** (or its reply to your first contact),
reconcile the recorded address with the address the transport actually stamped
on that message:

```bash
~/.claude/scripts/flow-wave-registry.sh verify 1 --wave cpp --from <observed-address>
```

Pass the `from=` value VERBATIM, whatever its shape. Two forms seen in the field
(#675) - neither is privileged, and the registry stores either unchanged:

```
uds:/run/user/1000/cc-socks/12345.sock     # unix socket lane
bridge:session_01RLE...                    # Remote Control lane
```

**Trust model (gate condition, #638): the transport-observed `from=` is
authoritative.** Whatever `verify` observes REPLACES what was recorded and
becomes canonical - the reverse never happens, and "flagged but self-derived
kept" is not an outcome. That principle is transport-independent: it rests on
observation outranking assertion, never on which transport did the stamping.

`verify` reports which of two things happened, and the distinction is about
PROVENANCE, not trust: `address_filled` when the recorded value was `unknown`
and observation supplied one (the documented bootstrap fallback succeeding -
unflagged, and the only possible outcome on a transport where self-derivation
cannot run), `mismatch-corrected` when a recorded REAL address was contradicted
(loud, flagged, investigate it). Neither is a lesser grade than `verified`: the
address is transport-observed either way, and the word records how it was
established, never how much to trust it. The output contract below defines both
verdicts in full.

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
- **`FLOW_WAVE_BOOTSTRAP=deadlock`** counts LIVE roles with no address. Those
  are unreachable from either direction, so the orchestrator-first contact
  above has no target for them either - work the bootstrap lanes before
  assigning anything to those roles (#672).

**Addressing rule: registry-address-only.** Address workers exclusively by the
address the registry holds, in whatever form the transport stamped it, via
`SendMessage`. Never address by `ListAgents` display names (`projects-xx`) -
those labels do not map to roles AND they mutate mid-session, so a send that
worked once can silently reach the wrong session later; name-addressing is the
misrouting failure this command exists to remove. The rule was written as
"socket-only" (#675); the intent was always "not by display label", never a
claim that the address must be a socket.

### Release - `/flow:register --release`

```bash
~/.claude/scripts/flow-wave-registry.sh release 1 --wave cpp
```

Run on leaving the wave. Sessions that die without releasing are caught by
staleness detection; their entries persist as `stale`. Releasing a role owned by
another LIVE session refuses without `--force`.

**Liveness is two-factor only where sockets exist** (#675). The primary proof is
the recorded pid, signalled on the recorded host. A live socket FILE is a
SECOND, independent proof, covering a pid the helper cannot signal - but reading
it means stat-ing a path, so it can only ever apply to a `uds:` address. On a
transport that stamps something else there is no file to stat and liveness rests
on the pid alone. That is a property of the design, not an oversight: sockets
are what the second factor reads, so a transport without them has one factor.
(#689 makes the scheme test explicit rather than relying on a prefix-strip that
silently no-ops; it exposes the asymmetry, it does not remove it.)

## Output contract

Every verb ends with a machine-readable verdict:
`FLOW_WAVE: registered | updated | refused | released | listed | verified |
address_filled | mismatch-corrected | free | unknown | error`, preceded by
`FLOW_WAVE_*=` detail lines. Exit 1 = refused (live-owner conflict), exit 2 =
usage error, else 0.

`verify` splits its non-matching outcomes (#674). `address_filled` means the
recorded address was `unknown` and observation SUPPLIED one - the documented
bootstrap fallback succeeding: no warning, `address_mismatch` stays false, and
`list` renders `filled`. It is a fully verified state, not a lesser grade than
`verified` - the address is transport-observed either way, and the word records
how it was established, never how much to trust it. `mismatch-corrected` is
reserved for a recorded REAL address CONTRADICTED by the observed one, which
stays loud and flagged. Both keep the observed address as canonical (trust model
unchanged); neither changes the exit code, which stays 0.

Three detail lines describe the address itself (#672), so an unaddressed
session is never reported as a healthy pending handshake:

| Line | Values |
|------|--------|
| `FLOW_WAVE_SOCKET_SOURCE` | `explicit` (`--socket`) / `self` (derived) / `preserved` (derivation failed, recorded address kept) / `unknown` (no address) |
| `FLOW_WAVE_SOCKET_REASON` | `-` / `no-sock-dir` (no socket dir on this host - see the lane-ordering note above before assuming a retry helps) / `no-match` (dir exists, no ancestor socket) |

Both keys carry `SOCKET` for historical reasons and are published contract, so
they are not renamed (#675). `SOURCE` describes any address whatever its
transport - only the `self` value implies uds, since self-derivation is the one
uds-specific step. `REASON` is inherently uds-specific: it explains why a
socket-file guess failed, and is `-` when no guess was needed.
| `FLOW_WAVE_BOOTSTRAP` | `ok` / `deadlock` (the address is `unknown`, so `verify` cannot fire - blocked, not pending) |

## Notes

- This command is the address-exchange half carved out of #637; the assignment
  loop, gate judging, and lane-disjointness ENFORCEMENT live there. This
  command only records lanes and warns on overlap.
- Registration is idempotent for the owning session: re-running refreshes the
  entry (new issue/branch/cwd) without ceremony.
- Roles are free-form labels; `orchestrator` is just a role, so workers can
  `get orchestrator` to discover where to send their hello - or learn it is
  not there yet and defer the hello to first contact (#670).
- The helper needs `jq` (already a CPP bootstrap prerequisite).
