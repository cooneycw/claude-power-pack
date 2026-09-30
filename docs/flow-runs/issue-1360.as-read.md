<!-- flow-run n=1 id=6973febd668a470780e861fb3359f051 -->
## Run 1 - issue #1360 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1360
- Read at:      2026-09-30T16:23:26Z
- updatedAt:    2026-09-30T15:25:45Z   (context only - moves on comments and labels)
- Body digest:  5457f3f56d5c91e51254464322422a9f843d98d7f7ab039e982f71185e80691c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1776 of 1776 (cap 16384)

### Body as read
## Problem

`dependency-audit` now fails on main: push pipeline #2973 (restart of #2972, merge `785d7daa` of PR #1359) is red at step `dependency-audit`, which also stops `validate`, `negative-controls` and `mutation-probe` from running. Every push to main will be red until this is fixed.

```
DEP-AUDIT-FINDING: uv.lock urllib3 2.7.0 CVE-2026-97687 - no allowlist entry accounts for it.
DEP-AUDIT-FINDING: uv.lock urllib3 2.7.0 CVE-2026-97688 - no allowlist entry accounts for it.
DEP-AUDIT-FINDING: uv.lock urllib3 2.7.0 CVE-2026-97689 - no allowlist entry accounts for it.
```

The advisories are new in the feed. PR pipeline #2970 passed `dependency-audit` on the identical tree (`9eef8c20`) earlier the same day, and `uv.lock` was not touched by #1359.

| CVE | Summary (OSV) |
|---|---|
| CVE-2026-97687 | HTTPS proxy TLS configuration may be ignored or overridden |
| CVE-2026-97688 | Chunked Deflate streaming can enter an infinite loop |
| CVE-2026-97689 | HTTPResponse.stream()/read_chunked() buffers an unbounded chunk-size line into memory |

OSV query by version (2026-09-30): `urllib3 2.7.0` -> GHSA-8988-9cw3-xx77, GHSA-gh4c-6fx4-qh6g, GHSA-vxq7-64xx-v4gw; `urllib3 2.8.0` (on PyPI since 2026-09-15) -> none.

## Proposed fix

`uv lock --upgrade-package urllib3` to 2.8.0 (transitive; no direct pin in pyproject.toml), then `make verify`. Exposure assessment: identify which locked packages pull urllib3 (`types-requests` sits beside it in the lock) and whether any shipped code path uses the streaming/proxy surfaces, for the PR description.

## Acceptance

- `python3 scripts/dependency-audit.py` reports 0 gating findings on the bumped lock, and reports the 3 findings on the pre-bump lock (the red case).
- Push pipeline on main green through `validate`.

