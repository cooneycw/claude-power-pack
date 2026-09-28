# Issue #1014 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1014
- Read at:      2026-09-28T15:18:46Z
- updatedAt:    2026-09-20T14:34:33Z   (context only - moves on comments and labels)
- Body digest:  1c78805692ae97a2f2c9fb26f1fb835cc2187d73054db51d0760806451bdbc80   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2597 of 2597 (cap 16384)

## Body as read
Measured on `863f0ae`. Part of the 2026-09-16 architecture review set.

## Problem

Two scripts independently reached the same rule about undeterminable answers, and each states it in its own vocabulary with no shared home.

- `scripts/flow-wave-registry.sh:416,434-438` — `pid_state` returns `alive | gone | unknown`. Comment: *"`unknown` is a real third answer, not a polite `gone` … Never checked and checked-but-undecidable are different facts."*
- `scripts/flow-wave-mailbox.sh:510-535` — watch state is `armed | stale | dead | absent | unknown`. Comment: *"`unknown` is the #800 convention in this helper: an unknowable answer is never rendered as a clean one."*

`flow-wave-registry.sh:436` cites its sibling by name rather than sharing code with it: *"rounding that down to 'dead' is the mistake the sibling mailbox refused when it moved off pid liveness (#814)."*

## Proposal

A shared result carrying `known(value)` / `undeterminable(reason)`, with one name for the third state. Each script keeps its own probe behind it.

## HARD CONSTRAINT — do not merge the probes

The two probes answer **different questions** and are deliberately different implementations:

- #814 moved the mailbox **off** pid liveness because pid liveness was the defect — #821, argv collision and pid reuse. `flow-wave-mailbox.sh:223-228` records that the obvious PID guard "reintroduces #821 one layer up".
- `flow-wave-mailbox.sh:532-535` records that its two consumers treat `unknown` in **deliberately opposite directions**: the duplicate-arm guard (#792 item 4) treats it as 0 so a wave is never blocked by an unavailable guard; reporting treats it as `unknown`.

Collapsing the probes would erase a distinction two incidents paid for. Only the convention above them is unshared. Scope this issue to the convention.

## Negative control (ADR 0008)

Whichever consumer reads the shared result, commit an input that forces `undeterminable` and show each consumer still fails in its documented direction — the guard permissive, the report honest. This is a change to two live instruments, so both current behaviours must be shown preserved, not assumed.



---

**Architecture review set (2026-09-16):** #1011 vendor the delegated-driver core · #1012 one vendor module for the two external-repo cores · #1013 derive the docs/scripts.md population · #1014 one home for the determinacy convention.

These four are independent — none is an input to another, and they touch disjoint files. #1011 is the recommended first: it is the only one where the duplication has already been shown to fail.
