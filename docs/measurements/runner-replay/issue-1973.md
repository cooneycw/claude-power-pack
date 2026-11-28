# Issue 1973 local qualification

The executable/test/configuration checkpoint is `6f271f926cf7dd9d82ee5a975ca31164668714d9`.
Both maintained entries completed under one native full-suite coordination
lease. These are actual local runs, not the tiny control fixtures.

| Profile | Lanes | Selected per lane | Passed per lane | Skips per lane | Entry wall time |
|---|---:|---:|---:|---:|---:|
| Default ci-shape | 2 | 322 | 316 | 6 named expected skips | 483.220 s |
| Runner replay | 1 depth-1 | 41 | 41 | 0 | 9.535 s |

The required default `codex-review-run.sh --qualify-only` stage reported GOOD
at that checkpoint. The replay used the maintained Make/CLI profile at `-n0`.
All 41 actual application node IDs have a PASS in the receipt and exactly one
`RUNNER_REPLAY_NODE: ... PASS` line in its log. Public CLI verification passed
for both receipts. Both root columns remain UNKNOWN; this is not image proof.
Local timing does not establish any saving in CI.

Byte-exact receipts:

- [Default local](issue-1973-default-local.json), SHA256 `ef88a9b1ece5737cd09379c5019a76e6ea46a689d0a68e3da854298cdc2260ef`.
- [Replay local](issue-1973-replay-local.json), SHA256 `92c98d62b0074b2df2417bcce523ddf2a89e23c41d1e0f89daed0bab3a1ec925`.

The retained raw log SHA256 values are
`55f036e69a6fdb556b14ee4e9b31aff48ea1e98202195ea51441ee5593066169`
(default) and `ce946d33f51bb61d234028c6de0332b927854bd2319bd5025c038741fa3a78e9`
(replay). Logs remain in the author evidence store. Historical root-only and
installer skips in the default lane establish neither root execution nor
historical installation. Replay permits no skip.

The exact 41-node manifest was discovered independently from the existing CI
keyword and both explicit classes at main `dbcc728a`. Both collections selected
the same 41 unique names with empty outcomes; collect-only was never called
execution evidence. The committed contract red at `5e7a8f7d` had 14 failures
before the profile, duplicate-call guard and CI sibling existed. Profile units
now pass 24 cases; the affected default family passed 166 with three root-only
skips. Four registered shape control sets discriminate, including the new
physical-clone/collector canaries and their availability-only, always-green
terminal producer. The canaries are deliberately trivial, not the real tests.

The full 405-member independent-generator measurement at the executable
checkpoint has no attribution delta. Historical pins and approved attribution
rows are unchanged. This publication adds only the two raw receipts and this
report; no executable, test or configuration input changes.

Review, the direct finish gate and real-image PR acceptance are pending.
The PR must quote replay/validate intervals and compare validate against
1332 seconds and the total pipeline against 1503 seconds, without assuming
that overlap proves a net saving or increasing worker counts.
