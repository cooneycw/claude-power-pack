# `good-host` - the known-GOOD input

A process in the INITIAL pid namespace, on a machine that ships an
`/etc/machine-id`. The real gate must report `host` (exit 0, nothing to report)
and so must the anchor - that agreement is the anchor-sanity half of the
control, and it is what separates "blind in the one way under test" from
"different for unrelated reasons".

## What each artifact is, and where it came from

| Path | Provenance |
|---|---|
| `ns-pid` | A real symlink whose TARGET is the namespace string, so `readlink` reads it exactly as it reads `/proc/self/ns/pid`. Target `pid:[4026531836]`, the value measured on this host, harness 2.1.266, 2026-09-20. |
| `etc/machine-id` | 32 hex characters plus a newline - the SHAPE measured on the host (33 bytes, 2026-09-20). The VALUE is a placeholder: a machine-id identifies a machine, and committing this host's real one would publish an identifier for no gain. Nothing reads the value; the signal is presence, not content. |
| `proc-mountinfo` | The first 12 lines of this host's real `/proc/self/mountinfo`, 2026-09-20, with any `claude/sessions` line filtered out - of which there were none to filter (measured: 0 matches, the #958 row). Read only by the anchor. |

## What is deliberately NOT here

No `sessions/` directory. Neither the gate nor the anchor opens one, and a
fixture carrying inputs nothing reads is a reassuring artifact: it makes the
case look like it exercises a signal it does not. The record-count signal is
exercised where it can actually be varied - `tests/test_flow_vantage.py`, which
builds record pairs (`<pid>.json` and `<pid>.<hash>.key`) in a tmp directory.
The `.key` half cannot be committed here in any event: `.gitignore` carries a
blanket `*.key` rule, so a committed record pair would arrive half-present and
the fixture would quietly stop being one.
