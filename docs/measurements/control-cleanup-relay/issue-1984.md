# #1984: cleanup-before-relay qualification

The pre-fix survey is pinned to `db63a7ec4e659b083230ca7327248f6ca983f1bb`.
The earlier inventory had 12 wrappers / 16 sites; merged #1958 adds
`ci-shape-review-entry:32`, making 13 wrappers / 17 sites.

Each invocation used the real wrapper, subject or anchor, and harness
`_invoke`/`_observe`. A trace recorded the executed print line. An owned
TemporaryDirectory subclass performed genuine cleanup, then planted ENOTEMPTY
only in the context that reached the selected site. Normal partners verified
the original registered outcome first. The unmodified aggregate evaluator
then replayed those captured results, changing one case at a time in a
representative registered GOOD/BAD/UNKNOWN plus selected-site population.
Every aggregate baseline was PASS. This was a focused survey, not a full
registered battery.

| Control / line | Planted result | Disposition before fixes |
| --- | --- | --- |
| `antigravity-skill-build:113` | BAD, UNKNOWN crash -> PASS | confirmed acceptance hole |
| `ci-shape-check:248` | BAD crash -> PASS | confirmed acceptance hole |
| `ci-shape-check:258` | UNKNOWN crash -> PASS | confirmed acceptance hole |
| `ci-shape-check:270` | BAD, UNKNOWN crash -> PASS | confirmed acceptance hole |
| `ci-shape-review-entry:32` | not reached by registered cases | UNKNOWN; no safety claim |
| `claude-host-links:101` | BAD, UNKNOWN crash -> PASS | confirmed acceptance hole |
| `cpp-host-install-receipt:91` | BAD crash -> PASS | confirmed acceptance hole |
| `cpp-host-link-preservation:59` | BAD crash -> PASS | confirmed acceptance hole |
| `cpp-host-link-preservation:80` | GOOD crash -> UNSIGNALLED | GOOD-only branch; no BAD/UNKNOWN reaches this site |
| `cpp-install-receipt:106` | BAD crash -> PASS | confirmed acceptance hole |
| `cpp-update-host-refresh:140` | BAD crash -> PASS | same affected context as final relay193; UID diagnostic not an independent verdict relay |
| `cpp-update-host-refresh:193` | BAD, UNKNOWN crash -> PASS | confirmed acceptance hole |
| `driver-parity:195` | BAD, UNKNOWN crash -> PASS | confirmed acceptance hole |
| `flow-finish-coordination:70` | not reached by registered cases | UNKNOWN; no safety claim |
| `flow-plan-record-lanes-verdict:112` | not reached by registered cases | UNKNOWN; no safety claim |
| `pi-skill-build:110` | BAD, UNKNOWN crash -> PASS | confirmed acceptance hole |
| `pi-skill-install:218` | BAD, UNKNOWN crash -> PASS | confirmed acceptance hole |

Ten wrappers have confirmed acceptance holes across twelve final relays. The
UID diagnostic shares the context of the confirmed final relay at line 193;
it is not a separate finding marker. Reached GOOD crashes were UNSIGNALLED,
and reached blind-anchor crashes were UNRESOLVED.

The three unreached sites and the GOOD-only site are **fixed for uniformity;
exploitability not demonstrated**. Separate cheap probes added an invalid
argument to the actual subject CLI and reached all three fallback sites;
both normal and cleanup-crashed protocol-error paths were UNAVAILABLE. That
qualifies only those error paths and does not prove general safety.

The coordinator selected uniform staging of all 17 sites, including the UID
diagnostic, to require zero AST-guard exemptions. All original assertions are
retained. The committed regression population has 39 real gate/anchor cases:
35 fail and 4 already-fail-safe partners pass on tests-only commit `19a137a4`;
all 39 pass after the fix. Normal positive partners precede each planted crash.
UNKNOWN manifests do not all pin an exact exit; the fix instead withholds the
load-bearing marker when cleanup fails, without changing subject protocols.

`make control-cleanup-relay-check` examines the real implementation population.
Its registered control commits old-shape, concatenation, non-first-argument and
alias BAD inputs, outside-context GOOD, and empty/parse UNKNOWN inputs. The
always-clean anchor misses all BAD inputs. Fixture cases/anchors/history are
explicitly outside this lexical population, not exempt implementation sites.

Reproduce with `make test-antigravity-skills
AGY_SKILL_TESTS='tests/test_control_relay_regressions.py
tests/test_control_cleanup_relay_check.py -o addopts='`, then
`make control-cleanup-relay-controls`. The full finish gate owns the full
registered battery. The guard runs in the existing negative-controls CI step;
no concurrent CI step or worker-count change is added.

Before/after generated Codex builds at the pinned base and the changed tree
have identical 405-member paths, hashes and modes. No attribution update is
needed. See #1983 for the original two-wrapper planted proof and #1984 for the
follow-up scope and uniformity decision.
