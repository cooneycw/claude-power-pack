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
change is needed; those three historical inputs stay byte-for-byte unchanged.

Broader CPP tests passed894 (77.23s); builder/CLI/independent parity passed33
(31.29s). The entire bare-caller negative-control batch passed147 registrations
with55 historical anchors byte-compared, before formal review. Ruff,559-file
typecheck, shellcheck, host-write/capability gates, binary/precondition checks,
command budgets, doc flags, census and derived coverage passed.

Fresh full and depth1 file-transport clones at source checkpointc0fc4ead each
passed66 focused tests. Full-clone preservation control/provenance passed.
Shallow-clone actual probes discriminated, but strict historical main-ancestry
verification correctly remained UNKNOWN (existing #1797 bound), not PASS.
The first full fixture advertised the worker's issue branch and stale local
main; strict provenance refused both. The corrected fixture explicitly models
actual origin/main without moving the shared local deployment branch or
relaxing the checker. Failed fixture logs are retained separately.

Every owned suite/clone temporary root was deleted immediately after its run.
Small logs remain outside the worktree under `/workspace/.cpp-validation/1913`.
Exact-head independent review, receipt and supervised finish gate remain required. No release or tag
authorization is inferred.
