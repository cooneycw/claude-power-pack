# Historical anchor retention (#1797)

The full main clone could not compare the branch-protection anchor's recorded
commit `1a13bc6e184aebfaa1a3ddb8d492f2b6a80d78ce`. A full all-branch clone
found it only under `origin/feat/1604-app-identity`, from squash-merged PR #1661.
Its bytes have SHA256 `074a28aa67e2ec15d46a9b6c031e480ac3363d20649416f16a71801c3f79c820`.

Main has three versions of `scripts/branch-protection.sh`; none has those bytes.
The search's positive control found the current main artifact, so the empty
exact-byte match was established by a search that could find an artifact.
The real main predecessor `bbba536c9ea9027e03dfc23c9642a0f26a11ab78` has
SHA256 `6088fcfabfe79e1de10433b019f24239857a16aab73b942f415f32155868e78c`.
Its actual bytes miss both null and omitted app-ID cases, agree on explicit
`app_id: -1`, and the current gate rejects both bad cases. This replaces the
registration without constructing or editing historical evidence. No feature
reference was deleted or changed.

## Readers and lanes

The changed output's readers are strict `make negative-controls`, PR CI's
negative-controls step, unit tests that parse the provenance/count protocol,
and operators reading stdout. The tests feed the real emitted protocol to its
assertions; the registered control runs the real checker. CI tests execute the
actual extracted shell block using owned git/sleep stubs for retry failures.
Real Git integration also runs that block over a local bare origin with a
shallow detached checkout and PR-only fetch refspec, then checks both retained
and side-only historical records using the actual emitted flag. They do not run a live Woodpecker pipeline.
Kyle's default caller omits provenance verification; the frozen baseline pins
that call's stdout/exit compatibility. Skillc has no registered controls and is
outside the changed historical population.

Exercised locally: Python 3.11 runner, full and depth-1 Checkout, detached HEAD,
local main fallback, explicit origin/main, absent main, non-main remote default,
and a side-branch commit with matching bytes. The original #1797 record is also
refused in a fixture where its object is absent. A shallow clone whose anchor
object is visible still yields unknown retention. No live remote branch or
protection setting was mutated. PR checkout's previous ref inventory was not
established (CI log API returned 403); the new explicit fetch supplies the ref
rather than relying on that inventory. Main push behavior is unchanged.

## Regression and controls

The pre-fix harness accepts matching side-branch provenance, has no retention
counts, and accepts missing main. The new regressions are run against its actual
bytes before restoring the fixed script. The frozen no-flag stdout comes from
main `34c99e4cc5ebec35f0db2d885d3bb012cdb76372`, independently of the implementation.
Only synthetic fixture commit IDs are normalized. Committed cases cover
`OFF_MAIN`, missing-main unknown, and detached origin/main success.


## Lanes for this change

| Lane | Decision and evidence |
| --- | --- |
| Checkout | Will test full/shallow clones, detached HEAD, explicit origin/main and local-main fallback through real Git. Linked worktree traversal is unchanged and existing checkout/control tests remain readers. |
| Harness | Claude/Codex installs do not change this repository-local Python checker. No command or generated skill changes. |
| Driver | Driver independent; both invoke the same strict checker. No live delegated workflow claim. |
| Coordination | Kyle does not participate in the checker or its Git probes; CI runs without Kyle. |
| CI provider | Will test actual Woodpecker PR/push shell block with local real Git and owned git/sleep failure stubs; live pipeline untested before PR. No GitHub Actions wiring changed. |
| Project state | Will test historical, constructed/no historical, missing main, absent object and non-main remote default. No controls keeps the previous protocol. |

| Reader | Output fed to reader | Evidence |
| --- | --- | --- |
| make negative-controls / make verify | Strict checker exit and provenance | Registered known-bad/known-good cases run the real checker; full gate requires a slot. |
| Woodpecker PR step | Flag file, strict checker exit | Actual extracted shell block fetches local bare origin from a shallow detached PR-only checkout; real checker consumes emitted flag. Retained record passes, off-main fails. Retry failures use owned stubs. |
| Woodpecker push step | Empty flag file and stdout | Actual block tested: no fetch and explicit no-verification diagnostic. |
| Unit-test protocol parsers | Real provenance/count lines | Tests assert full stdout without the flag against frozen original bytes, and parse real retention/byte counts with the flag. |
| Operator | Ref/reason and summary | Real cases assert OFF_MAIN versus UNCOMPARED, named ref and remedy; neither is summarized as clean. |
| Kyle no-flag caller | Previous stdout/exit protocol | Three full-output compatibility cases; no live Kyle caller executed. |


Independent first-pass review (`gpt-6-astra`, diff-only, network proxy unverified,
repository-local credentials absent) identified missing real-Git fetch coverage.
Accepted: the local-origin integration adds both retained and off-main cases.
Both fail with the original CI block lacking the explicit main fetch, and pass
with the new block. No live network or cloud service is involved.


## Final preflight corrections and cost

The first 45-record preflight at `f695a32c` had 44 exit-zero records (including
1,386 tests in 26 referencing files) and one binary-guard failure. The new nested
Git helper's definition was lexically outside its caller's `try/OSError` scope;
the static scanner charged 148 no-flag tests with a hard Git dependency. Moving
the definition inside the existing try preserves runtime handling and makes the
existing scanner recognize it. Standalone binary-guard and 62 provenance tests
then passed. No scan exception or gate policy was changed.

Orchestrator review requested explicit non-strict exit/summary tests and an
Upgrading note: verification failures remain advisory exit 0 without strict,
but print their named failure instead of an ok summary. Strict exits 1 on the
same input. Repositories with a non-main default now get unknown retention;
the supported policy and consumer options are stated in Upgrading.

The ancestry set is cached for one run by resolved root and main tip. Failed
reads never enter the cache; a changed root or tip causes another enumeration.
A focused test forces read failure, retry, reuse, second root, and changed tip.
It fails on the pre-cache instrument.

Five consecutive measurements of the provenance phase over all 49 actual
historical registrations (same clone, Python 3.11, each run's cache empty) give:

| Version | Median seconds | Range seconds | rev-list calls per run |
| --- | --- | --- | --- |
| Before cache, f695a32c | 1.719 | 1.709-1.739 | 49 |
| After cache | 0.652 | 0.640-0.658 | 1 |

Every run returned ok for all 49 anchors. These times measure the byte/history
verification performed by `--verify-provenance`, excluding unrelated execution
of the 127 controls; they are not whole-command timings or a remote CI estimate.
