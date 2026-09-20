# `bad-unknown-disagreement` - `unknown` as a REACHED state, not a documented one

The initial pid namespace (the general signal says `host`) on a machine with no
`/etc/machine-id` (the fleet signal says `container`). The gate must report
`unknown` (exit 4), because picking a winner between a general signal and a
fleet-specific one is exactly the guess this contract refuses.

This case exists because a three-state contract whose third state nothing
exercises is a two-state contract with a third word in its documentation. It is
registered BAD alongside `bad-container`: both are inputs the gate must report
on, and the vendored anchor must miss both - it answers `host` on this one too.

It is not a hypothetical shape. Several minimal Linux distributions ship no
`/etc/machine-id`, and a host that is one of them reaches this case on every
run.

## What each artifact is

| Path | Provenance |
|---|---|
| `ns-pid` | Symlink targeting `pid:[4026531836]`, the initial namespace measured on this host, harness 2.1.266, 2026-09-20. |
| `proc-mountinfo` | The same trimmed host capture as the sibling cases; read only by the anchor. |

`etc/machine-id` is absent, deliberately - see `bad-container/README.md` for why
absence rather than an empty file, and why the two are the same evidence.
