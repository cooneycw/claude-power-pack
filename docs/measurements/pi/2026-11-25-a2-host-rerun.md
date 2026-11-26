# A2 reviewed rerun: residual gaps, not accepted

The host operator ran the reviewed relay once at
`ea9ba93434a5a11b19fbb176a1e1c0475b09cacd`, during
2026-11-25T23:02:56Z through 23:03:45Z. Versions remained Python 3.12.3,
pi 1.6.0 and strace 6.8. This author decoded the two forwarded parts, verified
the supplied sanitized record and compared both returned script-hash sets
against the frozen candidate's Git blobs. This author did not observe host
execution or replay omitted full traces. No new host execution was performed
while analyzing these records.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| Forwarded sanitized rerun summary, independently verified | 233613 | `65a1c4ed1a2ae1ffdc698901c887e4b43542c06e2227d8de25719a1f63d68b93` |
| Full stdout retained on host; host-reported digest only | 288523928 | `54e38b79e660b0d1bbc5ebee79e6dce6856ec6d471f3a08e7c8d33dce81a9737` |

Frozen script SHA256 values: fixture
`68a299e18d0d801bb4f595e330a2c1535b7c2e5ddf26b74509c4d3908b12ea6a`, audit
`d8f2d7dfbe6c6e23f1920f1e4f255f4fe409059e81ff4751bed66c3c59625bae`, and relay
`8cd09f051e214b0937f3e48b6bde81367d3cd93ced6c8fe7d59d49af1be6ddbb`.
Reader self-tests reported 9 RPC and 41 syscall cases. Both fixture cleanup
records were true, and the operator reported the temporary worktree removed.

## Result

RPC exited 4 with zero findings and the two expected UNKNOWN rows: no supported
tool-inventory command and no skill-loader warning channel in RPC stderr.
Install/verify reported all 18 packages and 36 members current. The hidden
management layout and non-topic commands were unchanged; removal/restoration
and bounded project shadow observations remained present. Equal paired stderr
still contains the known no-model warning and establishes no skill-warning
absence. See the [initial record](2026-11-25-a2-host-initial.md) for that channel
disposition; neither row is waived or closed.

Syscalls exited 1, with 270 aggregate findings in five distinct classes.
Independently comparing all returned per-case audit arrays shows that every
one of the 29 normal observations has the SAME nine findings and no observer
syntax/provenance UNKNOWNs:

| Distinct finding | Count per normal observation |
|---|---:|
| Metadata for `<exe-dir>/lib/python3.12/os.py` | 1 |
| Metadata for `<exe-dir>/lib/python3.12/os.pyc` | 1 |
| Metadata for `<exe-dir>/lib/python3.12/lib-dynload` | 1 |
| Read of the exact `/etc/localtime` symlink target | 3 |
| Metadata of that exact timezone target | 3 |

The executable directory was `/usr/bin`. The public record replaces the
timezone location with `Region/City`; this is not the literal host target.
The 270 count includes the already-recorded duplicate initial-install
aggregation (30 sets of nine, rather than 29 distinct normal observations).
The synthetic auth-stat case has those nine plus one authentication finding;
the transient trusted-write case has those nine plus eight scoped findings.
All 31 child exits matched expectations, without forced stops.

The aggregate's 28 unresolved notes correspond to the other normal rows after
initial install: verify, legal build, trusted/history refusals, record-only,
payload and foreign/adoption checks all require a matching observer result.
Their per-row audits contain the same five baseline classes only. This
supports a cascade diagnosis in the supplied records, but does not establish
that a corrected full run passes. The full raw trace bodies are omitted from
the forwarded JSON; no reconstructed fixture is a replay of them.

## Narrow correction and pending evidence

Bind `/etc/localtime` before tracing via bounded readlink resolution to one
regular system-zoneinfo file (or a regular `/etc/localtime`). Record that exact
target. Every symlink hop stays within zoneinfo; escape, cycle, missing or
ambiguous target refuses. No zoneinfo directory read permission follows.
Derive executable-parent/version landmark candidates for each executable and
its resolved path, granting metadata only. Open/read/getdents/write of these
paths and read of a sibling/non-landmark file remain findings.

The landmark producer regression, metadata GOOD descriptor and exact-timezone
binding regression failed before the fixes. Committed constructed cases cover
the opposite verdicts; producer tests use disposable timezone files and check
that alias escapes are rejected before touching outside metadata. Each future
trace observation includes `audit_blockers`, with distinct findings/UNKNOWNs
and counts when its expected verdict is missed. This identifies what blocks
zero-touch checks while preserving their verdict rules.

Review pass 4 requires the owner's cap ruling before it is requested. No A2
receipt exists and no PR has been opened. Another reviewed host run must show
normal matches and seeded findings before syscall acceptance; fewer findings
alone do not satisfy it. Production adapter/core behavior is unchanged.

The operator reported owner-agent metadata listings unchanged, including root
mtime, and no subject finding naming real credential paths. These are
attributed observations, not content hashes or this author's full-trace scan.
All pi calls used fixture HOME/agent/history/XDG. Configuration separation is
not an OS credential or network boundary.
