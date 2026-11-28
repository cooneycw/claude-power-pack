# Runner replay controls (#1973)

`make runner-replay-canary` constructs an owned Git source, real depth-1 clone,
private HOME/TMP/PATH and a real serial pytest child through the maintained
`run_lane`. Its 41 named functions are intentionally trivial canaries, not the
actual application tests. The production collector writes their outcomes and
the public CLI verifier classifies the resulting schema-1 receipt.

GOOD requires all committed names once. BAD partners remove a node, skip one,
duplicate collection or a call report, change or erase selectors, substitute a
neighbour, corrupt a terminal outcome, erase execution, mislabel a lane or claim
GOOD with errors. The duplicate-report fixture sends a real extra call report
and records that action independently of the collector's verdict.

The missing-Make case removes the actual executable from the private staged
tool tree and asserts its absence before probing. It is UNKNOWN, never GOOD.
The constructed anchor passes prerequisite UNKNOWN through, then always claims
GOOD without checking terminal evidence. It must miss every BAD case and agree
on the availability boundary; a crash is not accepted as discrimination.

These controls neither prove the real 41 tests executed nor attest an image.
Those claims require the committed real profile run and exact-head PR pipeline.
The verifier binds selection, commit, image and tier, without adding a separate
receipt format. The default shape profile keeps its independent two-lane policy.
