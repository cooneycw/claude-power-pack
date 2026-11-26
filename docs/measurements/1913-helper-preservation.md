# Helper collision preservation - #1913

Owner/master priority41078 and approved plan41087. B2a parked at25783187.
The actual current-main helper reproduced personal-byte loss with exit0.
Committed regressions ran against unmodified main helper/callers:5failed,
58passed. The failures were regular/directory/FIFO collisions and actual
init/update fences replacing a personal executable seam.

The fixed focused battery passed66 tests, including two injected destination
races, actual caller fences and local-tier failure-before-configuration.
The three-case preservation control passed: both BAD inputs refuse and preserve
whole byte/type trees; the GOOD matrix covers absent install, source advance
through an existing CPP link and unchanged foreign links. Exact historical
anchor b1cd1f16 misses both BADs and agrees on GOOD; its bytes compared with the
full original commit. No new native/model/setup command was run.

Actual make codex-skills produced80 skills, whose complete names/hashes/modes
matched the original baseline (zero deltas). cpp/init, cpp/status and cpp/update
are explicitly excluded by the current generator; there is no generated
cpp-update reader to claim exercised. Therefore no attribution/baseline/test
change is needed; those three historical inputs stay byte-for-byte unchanged. Full focused/static/parity/control evidence, exact-head independent
review, receipt and supervised finish gate remain required. No release or tag
authorization is inferred.
