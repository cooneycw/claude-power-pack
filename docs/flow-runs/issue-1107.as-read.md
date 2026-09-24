# Issue #1107 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1107
- Read at:      2026-09-24T17:36:34Z
- updatedAt:    2026-09-23T21:42:37Z   (context only - moves on comments and labels)
- Body digest:  8ab2de1292c4b2feae4a7e7416b9496bb49874967a64ce664bf1529acae38488   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3202 of 3202 (cap 16384)

## Body as read
## Background

Split from #1095 during implementation, per orchestrator direction (message
1085: "your recommendation - a real mechanism like `--registry-required`
rather than an inferred default, because inference is what breaks it - is
right; file it as its own issue").

#1095 added a check so `flow-wave-mailbox.sh`'s `__supervise_daemon` exits
once every role registered in its wave has ended. The issue that opened
#1095 also named a second, broader case: a supervisor whose `--wave` was
never registered at all (a typo, a misconfiguration, or a registry that
never recorded anything) should also exit, with a distinct reason.

## Why #1095 does not (and should not, by default) cover this

`flow-wave-mailbox.sh` has a ratified, explicitly-documented boundary
(#814): a role that reads `free` (never registered) is a **legitimate,
independent way to use `supervise`** - the registry is an optional
companion, not a dependency. From inside the daemon, "this session
deliberately never uses the registry" and "this session's `--wave` is a
typo" are **observationally identical** - both produce a free role and an
empty wave. There is no default the daemon can infer here without
guessing which of those two the operator meant, and #814 already settled
that ambiguity in favor of NOT exiting.

Measured directly during #1095: wiring an unconditional "empty wave ->
exit" check into the daemon broke 6 existing tests that use `supervise`
purely for its mailbox behavior (message surfacing, SIGKILL/backoff
handling) and never touch the registry at all.

## Proposed scope

An explicit, opt-in flag on `supervise` - e.g. `--registry-required` - that
a caller passes when it KNOWS this wave/role is supposed to be tracked by
the registry (for example, an orchestrator that always registers its
workers before supervising them). With the flag set, an empty wave (no
roles registered at all, ever) is treated as the misconfiguration signal
the original issue wanted, and the daemon exits with a reason distinct from
"every role ended" (#1095's `no-roles-ended`) - something like
`no-roles-registered-and-required`.

Without the flag (the default, unchanged from #1095), the current #814-safe
behavior stands: a wave with zero registered roles is read as legitimate
registry-optional usage and the daemon keeps supervising.

## Negative control

- `supervise` with `--registry-required` against a wave that was never
  registered must exit, with a log reason distinct from the roles-ended
  case.
- `supervise` WITHOUT the flag, against the identical never-registered
  wave, must NOT exit (the current #1095/#814-safe behavior) -
  `tests/test_flow_wave_mailbox.py::TestSupervise::test_a_role_that_was_never_registered_at_all_keeps_supervising`
  already pins this and must stay green.
- A wave that HAS at least one ended-but-once-registered role, with
  `--registry-required` set, must read as `no-roles-ended` (the #1095
  case), not the new required-and-missing case - the two reasons must not
  collapse into each other now that both exist.

## Provenance

Filed by cpp-w2 while delivering #1095 (PR #1106), per orchestrator
direction to split this out rather than build it on an inferred default.
