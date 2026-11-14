<!-- flow-run n=1 id=08b229d7233b45aba4a0ba269f84ad95 -->
## Run 1 - issue #1804 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1804
- Read at:      2026-11-14T16:40:25Z
- updatedAt:    2026-11-14T16:39:05Z   (context only - moves on comments and labels)
- Body digest:  f33610627b59382f41be36a6d14537bcad7509f3845c9453510fa229915f5f5d   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2326 of 2326 (cap 16384)

### Body as read
A released legacy wave role can regain its previous file lane and merge observation when the role is re-registered. This behavior is present on main `35c51d81424999849f496f325a51ecc7b7ea9367`; it was found during the second-model review of #1762 and is excluded from that change after measuring the same inputs on main.

A fix changes what a released role keeps on re-registration. That behavior is visible to wave sessions, so an owner ruling is required before implementation; no code change for this issue is authorized by #1762's three rulings.

Use an owned fixture registry containing a historical released row that retains `files: "a.py,b.py"`, issue `1710`, a repo, PR `55` / base `base-2` / diff `diff-1`, and `overtaken: 1`. The helper explicitly supports legacy released rows with retained lane fields; current `release` clears the active fields, so this concerns older retained rows.

Measured with the real helper, a fixture-owned repo/cwd and pinned fixture process liveness:

| Re-registration input | Main's resulting active work |
|---|---|
| identity omitted | old files, PR and count retained; released becomes false |
| same issue only | old files, PR and count retained; released becomes false |
| same issue and repo | old files, PR and count retained; released becomes false |
| different issue, same repo | files and observation cleared, count zero |

The omitted identity behavior changes under #1762, but reactivation of the old work occurs on both implementations. The re-registration skips the released row when reporting an active lane drop, so there is no work-transition notice explaining this restoration.

This can turn history into a current claim, producing false lane conflicts and an old PR/overtake baseline for a fresh session. Decide explicitly how retained released work is handled on role reuse, while preserving intentional restatements and normal release-history visibility. Add same/omitted-identity legacy cases alongside the different-issue control. All reproduction must stay within owned fixture registries; no live wave should be used.

Measurement is retained in `tests/test_flow_wave_reregister_review_regressions.py` on #1762's branch: it runs the same four transitions against a byte-verified main helper and the branch. No behavior fix for this issue is included there.


<!-- end of body -->
