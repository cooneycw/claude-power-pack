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
- Role-level facts (#699), all optional and all flag-answerable:
  `--model <name>`, `--permission-mode <mode>`, `--files <a,b,c>` (this
  session's file lane), `--capacity <text>`
- Wave-level policy (#699), on the `policy set` verb only: `--driver`,
  `--authority`, `--authority-model`, `--gate`, `--ledger`,
  `--merge-authority`, `--deploy-policy`, `--repo`

## The wave policy: two tiers of declared state (issue #699)

The registry used to record a role, an address and a lane. Everything else a
wave RUNS ON - whether it may write code at all, where a worker stops for
approval, who judges, what a completion report looks like, which files each
worker owns - lived in prose the orchestrator retyped into every message. Three
consequences, all observed in the 2026-08-11 wave:

- **It does not survive a `/clear`.** The registry's stated purpose is
  surviving one. The protocol was the half that did not.
- **Retyping is where the errors were.** One message fenced a worker's file
  lane out of `flow-helpers-install.sh` and, three paragraphs later, assigned it
  the issue whose fix lives in that file. The worker refused to start and asked
  which was right. The cause was not carelessness - the lane existed only as
  hand-typed text, with nothing to read it back from.
- **The most consequential fact of all was established out of band.** Whether
  the wave writes code or files issues - against CPP's standing "file issues,
  don't implement" rule - took a user round-trip and then had to be restated in
  every brief. Both workers correctly refused to infer authority from being
  handed an issue number, because nothing in the registry could tell them.

So policy is DECLARED DATA, in two tiers.

**Tier 1 - wave-level, declared ONCE by the orchestrator, inherited by every
role:**

| Field | Flag | Why it is here |
|---|---|---|
| repo / project | `--repo` | a worker registered with `repo=""` |
| wave name | `--wave` | was INFERRED by a worker once, correctly, by luck (#671) |
| driver | `--driver` | `flow:auto` vs `codex:auto` determines the gate shape |
| **implementation authority** | `--authority` | `implement` or `file-issues-only`. The out-of-band fact above |
| gate policy | `--gate` | which step, who judges, whether `--yes` is forbidden |
| **authority model** | `--authority-model` | `orchestrator-only` or `user-and-orchestrator`. Two required signatures is how a wave deadlocks (#676) |
| ledger format | `--ledger` | the one structured element that already worked - both workers produced comparable output all day |
| merge authority | `--merge-authority` | who authorises the merge |
| deploy policy | `--deploy-policy` | Woodpecker-only, #469 no-op, etc. |

**Tier 2 - role-level, declared per session on `register`:**

| Field | Flag | Why it is here |
|---|---|---|
| role, wave | positional / `--wave` | already recorded |
| model | `--model` | routing: do not hand the hardest issue to the smallest model |
| **permission mode** | `--permission-mode` | a session that will hit permission prompts cannot take unattended work; routing it there wastes a cycle. Previously visible only in message metadata |
| cwd, repo, issue, branch | `--cwd` etc. | already recorded |
| **file lane** | `--files` | the largest gap. `list` warned on repo/issue/branch/worktree overlap; every real collision in the reference wave was file-level |
| capacity | `--capacity` | whether this session can take a second issue |

**Four anti-patterns this deliberately designs against**, because a template
that violates them trains people to paste anything:

1. **Nothing derivable is asked for.** Repo comes from the cwd's git root,
   the address from the pid walk, the model from the session. Every field
   above changes a downstream decision.
2. **Nothing that goes stale instantly is required.** Issue and branch before a
   worktree exists is the #683 trap; re-registration is normal instead.
3. **Everything is flag-answerable, never interactive-only.** An
   interactive-only path strands scripted startup - #677's lesson one layer up.
4. **A declared policy nobody checks is decoration.** This is the one that
   would make the whole feature worthless, so four things read it back:
   `register` reprints the policy (below); an undeclared policy is reported as
   `absent` rather than passing silently; a role briefed on a superseded rev
   reads `brief=STALE`; and declared file lanes participate in overlap
   detection like branches do.

### Declaring the policy (orchestrator, once)

```bash
~/.claude/scripts/flow-wave-registry.sh policy set --wave cpp \
  --repo /home/user/Projects/claude-power-pack \
  --driver flow:auto \
  --authority implement \
  --authority-model orchestrator-only \
  --gate "stop at /flow:auto Step 3; orchestrator judges; --yes forbidden" \
  --ledger "delivered / in-scope / residual" \
  --merge-authority worker \
  --deploy-policy "woodpecker-only, never a manual deploy"
```

`policy set` MERGES: fields not given are left alone, so amending one field is
a one-flag call rather than a restatement of the whole policy (restating it is
how a field gets silently dropped). Every set bumps `rev`, and the helper names
any live role still carrying the older rev - an amendment nobody re-read is
exactly the drift a declared-but-unread field would hide.

`--authority` and `--authority-model` are validated against their enums (a typo
is exit 2, not a stored value nobody can act on). The rest are free text: they
are read by humans and the wording is the content. Read it back any time with
`policy show --wave cpp` (`--json` for the object).

### The re-brief: what makes this more than a JSON file

`register` REPRINTS the wave policy on every registration. That is the whole
mechanic. `register.md` already called re-registering "the cheap re-brief" for
addressing; a `/clear`ed or compacted worker now recovers the PROTOCOL the same
way, by re-registering, instead of waiting for an orchestrator to retype it.

A worker reading `FLOW_WAVE_POLICY=absent` should say so rather than infer:
nothing in the wave has declared whether it may write code, and being handed an
issue number is not that declaration.

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

1. Register, passing what this session knows about its lane and itself
   (literal values):

   ```bash
   ~/.claude/scripts/flow-wave-registry.sh register 1 --wave cpp --cwd /path/to/worktree --repo /path/to/repo --issue 42 --branch issue-42-slug --model opus --permission-mode bypassPermissions --files scripts/flow-wave-registry.sh,tests/test_flow_wave_registry.py
   ```

   The role-level facts are optional and each answers a routing question the
   orchestrator otherwise had to ask (#699). They are PRESERVED across a
   re-register that omits them - unlike cwd/issue/branch, which a re-register
   rewrites because they describe a lane that genuinely goes stale. Pass an
   empty value (`--files ""`) to clear one deliberately.

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

2. Act on the verdict line, and READ THE POLICY BLOCK it prints (#699). The
   registration output carries the wave's declared protocol - implementation
   authority, gate policy, ledger format, merge authority - which is the
   compaction-proof re-brief. Two states matter:
   - `FLOW_WAVE_POLICY=declared` - those are this wave's rules; follow them,
     and check `FLOW_WAVE_BRIEF` (`current` means nothing has changed under you).
     `FLOW_WAVE_POLICY_LEDGER` is the one line here this session must PRODUCE
     rather than merely obey - see "What a worker EMITS" below for the block
     shape the validator enforces against it.
   - `FLOW_WAVE_POLICY=absent` - the wave has declared nothing. Do NOT infer
     implementation authority from having been handed an issue number: say the
     policy is undeclared and ask the orchestrator to `policy set` it. This is
     the failure the field exists to remove.
   Then the address verdicts:
   - `FLOW_WAVE: registered` / `updated` - proceed.
   - `FLOW_WAVE: refused` (exit 1) - the role is held by a LIVE session. Two
     sessions both believing they are "worker 1" is the failure this command
     exists to prevent. **STOP** and report; only re-run with `--force` when
     the user confirms the other session is genuinely gone. A dead owner's
     entry is stale and taken over automatically - no `--force` needed.

3. Send the orchestrator a registration hello stating the role, wave, cwd,
   repo, and current issue/branch, following the DELIVERY PREFERENCE ORDER
   below. A hello delivered by `SendMessage` is what lets the orchestrator
   OBSERVE the real address; a hello delivered by mailbox does not carry a
   `from=`, so say so in the message and let the orchestrator's own first
   contact supply the observation. Pick the first branch that applies:
   - the orchestrator's address from `get orchestrator` - `SendMessage` it
     directly;
   - no usable address, but the orchestrator has messaged this session before -
     reply to its most recent message's `from=`;
   - `get orchestrator` says `free`, or its address is `unknown` - the
     orchestrator has not (usefully) registered yet. This is NORMAL, not an
     error (issue #670): registration already succeeded in step 2 and never
     depends on the hello landing. **Write the hello to the mailbox anyway**
     (lane 2 below) - the orchestrator's inbox watch delivers it whenever that
     session arrives, so the hello waits in a place that WAKES someone instead
     of waiting on a human. Report
     `registered; orchestrator not yet in roster; hello left in the mailbox`
     and carry on. The address handshake still fires on FIRST CONTACT from
     either side: when the orchestrator arrives it initiates contact (see the
     orchestrator side), and this session's REPLY carries the
     transport-stamped `from=` that `verify` needs.

4. **ARM THE WATCH before standing by (issue #676).** This is not optional and
   not a nicety: a registered worker with no watch is exactly the 2026-08-11
   failure - it stands by correctly, forever, while a written assignment sits
   undelivered, because an idle session polls nothing. Launch the watch as a
   BACKGROUND Bash call (`run_in_background: true`) so the harness re-invokes
   this session the moment mail lands:

   ```bash
   ~/.claude/scripts/flow-wave-mailbox.sh watch --role 1 --wave cpp --timeout 1800
   ```

   On wake it prints the messages and exits 0; re-arm it after handling them,
   for as long as this session is in the wave. Exit 5 is a plain timeout, NOT
   evidence the orchestrator is gone - re-arm and check the roster before
   concluding anything. Release by simply not re-arming (the watch is bounded,
   so a wave can never leave one spinning after it ends).

5. Confirm back to the user which orchestrator was registered with once the
   ack arrives - or that the hello is waiting in the mailbox because no
   orchestrator has registered yet - and that the watch is armed.

### What a worker EMITS - the two transition tokens (issue #701)

Everything above is how a worker JOINS a wave. This is what it SAYS once it is
in one, and it is the half that is already enforced. #701 gave the wave a
reserved vocabulary for the speech acts that are state transitions with a
wrong-answer cost, and two of those tokens are emitted by the WORKER. The rest
(`GATE:`, `LANE:`, `MERGE:`, `STATE:`, `RATIFY`/`OVERRULE`) are the
orchestrator's and are documented in `wave.md`.

**Both are refused at SEND, not at read.** `flow-wave-mailbox.sh send` validates
every body: a malformed reserved token exits 6 with `FLOW_WAVE_MAILBOX: refused`
and the box is left untouched, so the message does not arrive late and wrong -
it does not arrive at all. That is why the shapes belong here rather than only
in the orchestrator's file: the guard fires correctly, and until it was written
down it fired at a reader who had never been told the rule. Reserved lines are
LINE-ANCHORED (the token opens the line, leading whitespace allowed), so a
mention inside a sentence is never mistaken for a declaration, and a message
carrying NO reserved token always delivers - prose is not the target.

**`PUSHBACK <argument>` - refuting an assignment's premise.** The orchestrator
side of this file already states the rule ("pushback is structural, not
polite"); this is its shape. The argument is MANDATORY - a bare `PUSHBACK` is
refused - because the token exists precisely so that a refutation cannot be
skimmed past as agreement. Put the argument on the same line, or on the lines
beneath it: continuation lines belong to the token and run to the next reserved
line or EOF, so a multi-paragraph refutation needs no terminator.

<!-- lexicon-example: pushback -->

```
PUSHBACK the assignment fences my lane out of scripts/flow-wave-registry.sh,
but the fix for the assigned issue lives in that file - the lane and the issue
contradict each other. Verified against the tree: `policy set` is defined in
that script and nowhere else, so I cannot close the issue without writing to
the fenced path. Which of the two is authoritative?
```

**`LEDGER` - the completeness ledger.** A block carrying `delivered:`,
`in-scope:` and `residual:`. All three sections are REQUIRED and a missing one
is refused BY NAME, because this is the one structured element that already
worked in the reference wave - formalised rather than invented. It is the same
format the wave declared once with `policy set --ledger` (#699) and that this
session reads back as `FLOW_WAVE_POLICY_LEDGER` on every register: the policy
line is what the wave expects to RECEIVE, this block is how a worker PRODUCES
it. The orchestrator takes it when verifying the PR, and accepting it is what
releases the next issue - so it is the report itself, not a courtesy summary.

<!-- lexicon-example: ledger -->

```
LEDGER
delivered: PUSHBACK and LEDGER shapes documented in the worker-side section,
  with the pre-send check that verifies a draft before the mailbox sees it
in-scope: nothing further - the assignment named two tokens and both are
  covered, including the enforcement each one carries
residual: none. The other reserved tokens are orchestrator-emitted and were
  already documented in wave.md when the lexicon shipped
```

State `residual: none` explicitly rather than omitting the section: an empty
residual is a recorded JUDGMENT, and this line is where every narrowing gets
declared BEFORE approval.

**Declaring a residual is mandatory; FILING it is a severity call (#714).** File
an issue - and name its number on this line - when the residual names a
consequence someone would notice: a user-visible behavior, a correctness or
security risk, a cost or data-loss exposure, or work another issue is already
blocked on. Otherwise this line plus the PR description is the whole of its
record. Not issue-worthy on their own: "measure X", "annotate the files we
excluded", "tighten a coupling we just introduced", "consider whether Y is still
needed". Filing those anyway is what bred the third-generation residual that
proposed a compose-dependency change which, as written, would have deadlocked the
stack on every cold start (aws-learn#838) - a residual reasoning about the
previous agent's work product rather than about the system. So: a residual
proposing a change to a system you have not run carries its verification, or is
worded as a QUESTION rather than a directive, and one descended from another
residual carries its generation - that is the signal to write it down instead of
filing it.

**Validate a draft BEFORE sending it.** `validate` is read-only and runs the
same parser `send` runs, so a report can be checked without spending a delivery
attempt. Invoke it BARE at the stable path (#581 discipline):

```bash
~/.claude/scripts/flow-wave-lexicon.sh validate --body-file /tmp/report.md
```

It prints one `FLOW_LEXICON_TRANSITION=` line per recognized token and ends in
`FLOW_LEXICON: ok | invalid | none`. `invalid` (exit 1) names the offending
line number and what is missing. `none` (exit 0) means the body declares no
transition at all - correct for ordinary prose, and worth a second look on a
message you MEANT to carry a token, since a token mis-typed out of
line-anchored position reads as prose rather than as a broken block.

(Exit 127 - helper not installed: fall back to
`${CLAUDE_PLUGIN_ROOT}/scripts/flow-wave-lexicon.sh`, else the CPP-checkout
copy; tell the user to run `/flow:repair`. The validator FAILS OPEN by design -
`send` delivers unvalidated rather than blocking when the helper is missing or
itself broken, since a wave stalling on its own linter is the #676 failure in a
different hat. A missing validator is therefore not permission to skip the
shape; it only means nothing will tell you.) If a prose line legitimately opens
with a reserved word, `send --no-lexicon` is the per-message escape.

### The delivery lane - mailbox + wake (issue #676)

Everything above is the ADDRESS BOOK: who a role is, where it lives, whether
the address can be trusted. None of it delivers anything, and on 2026-08-11
that gap cost ~2 hours - the harness rejected every orchestrator->worker
`SendMessage` (it routes only to subagents the calling session spawned), so a
fully-written assignment sat undelivered while both sessions correctly stood
by. The only transport that moved a message was the user typing a pointer into
the worker's terminal by hand.

**Delivery preference order. Follow it in order; do not skip to the end.**

1. **Direct session messaging** (`SendMessage` to the registry address) - use
   it wherever the harness supports it. Worker->orchestrator has been reliable
   in the field; orchestrator->worker has not.
2. **Mailbox + watch** - the host-local lane below. This is the fallback for
   every direction the harness cannot route, and it is a REAL lane: it wakes
   the counterpart.
3. **User relay** - the DOCUMENTED LAST RESORT. On 2026-08-11 it was the first
   resort, which is the bug. Reaching for a human means lanes 1 and 2 both
   failed, and that is worth saying out loud rather than doing quietly.

**The lane.** Beside the registry, same lifetime, same host-local scope
(`$XDG_RUNTIME_DIR/cc-flow-wave/<wave>/`), one audited helper invoked BARE
(#581 discipline):

```bash
~/.claude/scripts/flow-wave-mailbox.sh send  --to 1 --wave cpp --body-file /tmp/brief.md
~/.claude/scripts/flow-wave-mailbox.sh send  --to orchestrator --from 1 --wave cpp --body "..."
~/.claude/scripts/flow-wave-mailbox.sh read  --role 1 --wave cpp
~/.claude/scripts/flow-wave-mailbox.sh watch --role 1 --wave cpp --timeout 1800
~/.claude/scripts/flow-wave-mailbox.sh list  --wave cpp
```

(Exit 127 - helper not installed: fall back to
`${CLAUDE_PLUGIN_ROOT}/scripts/flow-wave-mailbox.sh`, else the CPP-checkout
copy; tell the user to run `/flow:repair`.)

- Orchestrator writes to a worker: `outbox-<role>.md`. Worker writes back:
  `inbox-<role>.md` - one file per WRITER, so two workers reporting at the same
  moment never contend, and the orchestrator watches all of them at once with
  `--role orchestrator`.
- Sends APPEND a rev-stamped block; nothing already unread is ever overwritten.
  (`--replace` exists for a box that holds current state rather than a log, and
  still bumps the rev so a replace can never read as already-consumed.)
- `read` prints only what is newer than this role's cursor, then advances it;
  `--all` re-reads history (useful after a compaction), `--peek` reads without
  consuming so an armed watch still fires.
- **A mailbox with no watch is not a lane.** The wake is the half that makes
  this different from the ad-hoc 2026-08-11 workaround, which still needed a
  human to say "go read your outbox". Arm the watch (worker step 4 above;
  orchestrator side below) as a background call and let the harness re-invoke
  the session on exit. Where a harness Monitor-style tool is available it works
  equally well - the contract is "something blocks on this box and wakes the
  session", not one specific tool.

The lane is HOST-LOCAL, exactly like the registry. Two sessions on different
machines still have no transport between them; that is out of scope here.

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

Four lanes produce an address without self-derivation:

1. **Re-register.** Re-run the same `register` command. It re-derives and
   adopts a socket that has since appeared (`FLOW_WAVE_SOCKET_SOURCE=self`).
   Only this lane depends on a uds transport.
2. **`register --socket <addr>`** - the manual lane, and the one that works on
   any transport. Pass an address learned by any means (harness env, or the user
   relaying it from the other session), in whatever form that transport stamps;
   an explicit `--socket` always wins (`SOURCE=explicit`).
3. **Mailbox hello (issue #676).** Write the hello to the wave mailbox and arm
   the watch. This does not itself produce an address - a mailbox write carries
   no `from=` - but it is the lane that reaches a counterpart with no address at
   all, and the counterpart's REPLY over the real transport is what `verify`
   needs. Prefer it over lane 4: it needs no human, and it wakes the other side.
4. **User-relayed hello.** The DOCUMENTED LAST RESORT. The user pastes this
   session's `FLOW_WAVE_*` block into the counterpart session; the counterpart's
   reply arrives over the real transport, and its `from=` is what `verify`
   needs. Reaching for this means lanes 1-3 all failed - say so rather than
   quietly making the human the transport, which is how ~2h were lost on
   2026-08-11.

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

**Arm the inbox watch (issue #676).** Before assigning anything, arm the
orchestrator's own watch as a BACKGROUND Bash call, so a worker's hello or
report wakes this session instead of waiting for the next time a human looks:

```bash
~/.claude/scripts/flow-wave-mailbox.sh watch --role orchestrator --wave cpp --timeout 1800
```

It covers every `inbox-*.md` at once. Re-arm after handling each wake.

**Declare the wave policy before assigning anything (#699).** Run `policy set`
once (see "Declaring the policy" above). It is what makes the ack below a
POINTER to durable state rather than the only copy of it: the gate points, the
ledger format, the authority model and the merge authority live in the registry,
and a worker re-reads them by re-registering. Without it, every brief is a
retype and a `/clear` erases the protocol.

**Ack with the protocol.** The registration ack is the handshake: send the
worker its wave brief so the rules survive its compaction - the gate points
(stop at `/flow:auto` Step 3, no `--yes`), the completeness-ledger format
(delivered / in-scope / residual), its file lane, and the pushback rule,
stated verbatim. With a declared policy the first three are already recorded, so
the ack states the worker's LANE and any issue-specific conditions and points at
the policy rev for the rest; grant the file lane with `--files` on the worker's
next register (or tell it to), so the lane is data the roster can check rather
than a sentence only the orchestrator remembers. Deliver it by the preference
order above: `SendMessage` when
the harness routes it, otherwise the mailbox (`send --to <role>`), and only
then a human. An ack that cannot be delivered is not an ack - if it lands in
the mailbox, say so, because the worker sees it on its next watch wake rather
than immediately:

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

- Shows `role -> address`, liveness, verification state, and current issue -
  plus any declared role-level facts (`files=`, `model=`, `perm=`,
  `capacity=`), rendered only when declared so a wave that uses none reads
  exactly as before (#699).
- **The wave policy is the roster's header** (#699), or an explicit
  `NONE DECLARED` line. A live role carrying a superseded policy rev is marked
  `brief=STALE` and summarized in a `BRIEF:` line - it is running on older
  rules until it re-registers, and re-registering is the whole fix.
- Dead entries read `stale` and are kept, not deleted - a dead worker mid-issue
  is information, and its worktree claim outlives it.
- **Unregistered `flow-claim` locks are reconciled in (#687).** Registration is
  opt-in and orthogonal to `/flow:auto`, so a session doing ordinary
  single-issue work holds a real worktree lock while appearing nowhere on the
  roster - in #673 an issue read as free while a live session was minutes from
  a PR on it. `list` now also reads `git worktree list --porcelain`, and any
  LIVE `flow-claim` lock that no live registry entry accounts for is rendered
  as a claim-derived row (issue, branch, worktree, pid) and **participates in
  lane-overlap detection**. Claim rows are contactable but are NOT roles: they
  are never `verify`/`release` targets, and in `--json` they appear under a
  separate `unregistered_claims` key rather than in the roles map.
  - Their address is **observed, never derived**: a socket actually present for
    that pid is reported; otherwise the row says it has no address. Computing
    one from the pid would re-introduce the uds assumption this file dropped.
  - **Coverage bound, stated so it is not mistaken for completeness:** repos to
    scan come from the wave's own LIVE entries, plus an explicit `--repo <path>`.
    A host where nothing is registered has nothing to scan and stays invisible.
    #673 WOULD have been caught, because the orchestrator was registered with a
    repo - that is the shape of the coverage, and the reader should not have to
    guess it.
- **Lane overlap warnings fire on the useful signal only**: same repo + same
  issue, same branch, same/nested worktree paths, or overlapping declared FILE
  LANES between LIVE entries. Sharing a repo alone is the NORMAL wave shape (all
  workers, one repo, separate worktrees) and prints as info, never a warning - a
  warning that fires on the normal case trains everyone to ignore it. Roles that
  have DECLARED NO LANE are exempt from the pairwise checks entirely (#683): the
  `orchestrator`, which never implements and so cannot collide with a lane
  whatever its cwd, and any live role with no issue, no branch, no file lane,
  and a shared-parent cwd. The exemption is announced in the roster rather than
  silent - a skipped check nobody can see is a blind spot, not a quiet win -
  and it lapses the moment the role declares a lane. It is narrow on purpose:
  a declared branch, a genuinely nested worktree, or a granted file lane is a
  lane even with no issue number yet.
- **File-lane overlap is EXACT-MATCH on declared paths** (#699), not glob
  expansion, prefix containment, or realpath resolution. Two lanes that mean the
  same directory but spell it differently do not collide here - declare the same
  string on both sides. The narrow rule is deliberate: a comparison that guesses
  invents collisions nobody declared, and this warning has to be believed to be
  worth having. Every real collision in the reference wave was file-level (two
  workers in `register.md`, two PRs regenerating `codex/skills/**`, one issue
  whose fix lived in another worker's file), and all of it was managed by the
  orchestrator holding paths in prose and checking by hand.
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

The mailbox lane (#676) does not weaken this rule - it obeys it from the other
end. A mailbox is addressed by ROLE, the same declared identity the registry
keys on, so `send --to 1` reaches whoever holds role 1 in this wave and cannot
be misrouted by a label that changed since the last send. It is the registry's
addressing model with a delivery mechanism attached, not a second addressing
scheme.

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
address_filled | mismatch-corrected | free | unknown | policy_set |
policy_shown | policy_absent | error`, preceded by `FLOW_WAVE_*=` detail lines.
Exit 1 = refused (live-owner conflict), exit 2 = usage error, else 0.

`policy_absent` is a STATE, not a failure, and exits 0 (#699) - a wave that has
not declared its policy yet is a normal early condition, and the point is that
it is visible rather than implicit. A new verdict must never become a new exit
code, or a `set -euo pipefail` caller aborts on it; that is the #674 rule, kept.

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

Wave-policy detail lines (#699), emitted by `register`, `get`, `list` and
`policy` - present or absent, so a consumer can always tell "no policy declared"
from "this call does not report policy":

| Line | Values |
|------|--------|
| `FLOW_WAVE_POLICY` | `declared` / `absent` |
| `FLOW_WAVE_POLICY_REV` | current revision (`0` when absent); every `policy set` bumps it |
| `FLOW_WAVE_POLICY_AUTHORITY` | `implement` / `file-issues-only` |
| `FLOW_WAVE_POLICY_AUTHORITY_MODEL` | `orchestrator-only` / `user-and-orchestrator` |
| `FLOW_WAVE_POLICY_DRIVER` / `_GATE` / `_LEDGER` / `_MERGE_AUTHORITY` / `_DEPLOY` / `_REPO` / `_TS` | free text as declared |
| `FLOW_WAVE_BRIEFED_REV` | the rev THIS role was briefed on (`register` / `get`) |
| `FLOW_WAVE_BRIEF` | `current` / `stale` / `none`. `stale` = the policy was amended after this role registered; re-register to take the re-brief |

`list --json` gains a `wave_policy` sibling key when a policy is declared -
alongside `unregistered_claims` and for the same reason: roles are top-level
keys, so policy is hung beside them rather than nested, and the key appears only
when there is something to report, so a wave without a policy emits
byte-identical JSON to before. The same caveat the #687 precedent accepted
applies: a role literally named `wave_policy` would collide.

## Notes

- This command is the address-exchange half carved out of #637; the assignment
  loop, gate judging, and lane-disjointness ENFORCEMENT live there. This
  command only records lanes and warns on overlap.
- Registration is idempotent for the owning session: re-running refreshes the
  entry (new issue/branch/cwd) without ceremony.
- Roles are free-form labels; `orchestrator` is just a role, so workers can
  `get orchestrator` to discover where to send their hello - or learn it is
  not there yet and defer the hello to first contact (#670).
- The wave policy covers declared STATE (#699). Its companion #701 covers state
  TRANSITIONS - gate verdicts, lane grants, merge authorizations - and the two
  carry the same load-bearing caveat: a declared policy or a reserved token that
  nothing reads back is decoration, and its broken version is indistinguishable
  from its working one. Which is why every field here has a named reader. The
  two WORKER-emitted tokens, `PUSHBACK` and `LEDGER`, are documented above under
  "What a worker EMITS"; the orchestrator-emitted rest live in `wave.md`.
- The helper needs `jq` (already a CPP bootstrap prerequisite).
