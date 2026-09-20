# `bad-container` - the known-BAD input the anchor must MISS

A process in a NON-initial pid namespace on an image that ships no
`/etc/machine-id` - the kyle-session image, measured 2026-09-13 (issue #947,
one container, kyle session 48). The real gate must report `container`
(exit 3); the vendored blind anchor reports `host`, which is the blindness this
control exists to demonstrate and the dangerous direction to be wrong in.

## What each artifact is, and where it came from

| Path | Provenance |
|---|---|
| `ns-pid` | A real symlink whose target is `pid:[4026533495]` - the inode measured inside the container on 2026-09-13. |
| `proc-mountinfo` | The SAME trimmed host capture as `good-host`, and that is deliberate rather than sloppy. The measured fact both cases rest on is that `~/.claude/sessions/` appears in NEITHER side's mount table (host: 0 matches, 2026-09-16 and 2026-09-20; container: no, 2026-09-13). The anchor's blindness is the ABSENCE of that line, and which side's capture carries the absence changes nothing. A fabricated "container mountinfo" would have been invented data standing where a measurement belongs. |

## What is deliberately absent

`etc/machine-id` - there is no `etc/` directory at all. The absence IS the
fixture: the kyle-session image ships no `/etc/machine-id`, so a container
session record's `pidDomain` reads `linux::pid:[...]` with an EMPTY machine-id
half. An absent file and an empty file are the same evidence to the gate, and
it treats them identically.
