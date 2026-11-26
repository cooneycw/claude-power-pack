# pi-host-fixture

Run only against explicit disposable fixture paths, a clean pinned candidate
source, and an absolute reviewed pi/strace executable. `--lane rpc` requests
offline/no-session commands without a provider turn; `--lane syscalls` traces
the real copier separately from pi startup. `--source`, `--revision`, `--pi-bin`
or `--strace-bin` select those inputs. Missing prerequisites/evidence are UNKNOWN.
The returned JSON retains raw evidence, argv/lifecycle, hashes and cleanup.
Configuration separation is not a network or OS credential boundary.

`--read-rpc RECORD` classifies a supplied raw baseline/installed pair, checking
nonzero expected skills, correlated responses, source attribution and verbatim
diagnostics. `--self-test` runs committed opposite reader cases and claims no
host execution. Tool inventory is a separate field: published pi 1.6.0 RPC has
no documented built-in-tool inventory command, so actual host observations
leave that row unknown instead of borrowing skill discovery as evidence.
RPC stderr observes runtime/extension/provider/flag diagnostics only: pi 1.6.0
does not expose its skill-loader warning array there. Equal stderr cannot
establish absence of skill warnings. That row remains UNKNOWN pending a
separate supported observation channel and a firing malformed-skill control.

Children use a sanitized PATH containing the selected Git/interpreter parents
and system executable directories, fixture HOME/XDG/history, and no user-site.
Fixture Python commands additionally use `-I`. Before tracing, the dispatcher
records source Git/common directories with the copier's isolated Git flags
and derives interpreter paths from that same isolated interpreter. Only those
storage trees, exact runtime files and constrained native libraries are added
to the independent allowance; no main checkout or general HOME access follows.
Pretrace localtime binding records one exact regular target; bounded symlink
hops stay within the system zoneinfo root, with no tree allowance. Executable
prefix landmarks are metadata-only. Every trace observation reports
`audit_blockers` with distinct finding/UNKNOWN counts if its expected verdict
was missed, so zero-touch unresolved notes retain their actual causes.

Registered controls reject missing skills/changed diagnostics/tool changes and
retain malformed/ambiguous/unavailable inputs as unknown. The shape-only
constructed anchor misses the semantic bad cases. See the proposed
[host protocol](../measurements/pi/issue-1896-a2-host-fixture-plan.md) for remaining
live acceptance, paired negatives and attribution requirements. No owner install
or owner-session validation is performed.
