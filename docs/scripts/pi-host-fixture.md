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

Registered controls reject missing skills/changed diagnostics/tool changes and
retain malformed/ambiguous/unavailable inputs as unknown. The shape-only
constructed anchor misses the semantic bad cases. See the proposed
[host protocol](../measurements/pi/issue-1896-a2-host-fixture-plan.md) for remaining
live acceptance, paired negatives and attribution requirements. No owner install
or owner-session validation is performed.
