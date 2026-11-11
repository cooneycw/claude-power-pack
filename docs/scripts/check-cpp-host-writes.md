# `check-cpp-host-writes` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `check-cpp-host-writes` (#1132, #1198)

Enforces **two** properties over `.claude/commands/cpp/init.md` and
`update.md`, reported as two finding types and counted separately in the
verdict so one red never means two things:

| finding | property | issue |
|---|---|---|
| `INLINE-HOST-WRITE:` | the write goes THROUGH the seam | #1132 |
| `UNREAD-SEAM-VERDICT:` | the seam's ANSWER is read | #1198 |

Refuses an inline host write in either document. Every host write in those two
documents goes through `scripts/cpp-host-write.sh`, which declares the surface
and can be told to defer it; this gate keeps it that way.

**And refuses a seam call whose exit status is discarded** (#1198). Routing the
write through one door is half the guarantee: the seam answers `0` wrote, `3`
deferred-by-request, `1` failed, and `127` when it is not installed, and a
caller that reads none of them prints the same checkmark for all four. Measured
2026-09-22, all twenty call sites did exactly that - `/cpp:update` reported
`Flow allowlist merged (52 total allow rules)` having merged nothing.

**The rule is "always read the status", not "read it when a claim follows".**
Keying the finding on a nearby success message excuses the shape that actually
bit: a `link-into` loop calling the seam ninety times, claiming nothing, and
leaving 25 scripts unlinked in silence. There is no legitimate reason to write a
host surface and not care whether it happened, so the requirement has no
exceptions to enumerate - and a rule with no exceptions cannot be defeated by
phrasing a claim differently.

A status is "read" when the invocation is a condition (`if`/`while`/`until`), is
chained to a handler (`||`, `&&`), or is followed by a statement referencing
`$?`. Those are shell FORMS rather than a list of blessed handler names, which
would need widening for each new one. Two joins are load-bearing and both appear
in the scanned documents: backslash continuations (the line after
`json-merge-sections \` is that statement's own arguments, not its handler) and
heredoc bodies (a `$?` inside a `<<'JQ'` body is jq program text, not a check).

**Scans by write FORM, not by surface**, because every enumeration by surface
during #1132 missed something: a same-line redirect, an indirect one (target
assigned twenty lines above its use), embedded python inside a heredoc, and
`mkdir`/`ln` into a host directory.

**A line is a comment only when its first non-whitespace character is `#`.** A
filter that dropped any line containing a hash would excuse
`printf '# managed by cpp' >> "$RC"` - a real write whose line merely looks
like one, and the write such a filter is most likely to meet.

Its verdict names the two documents it scanned and claims nothing about the
other command families, which are not in its input.
