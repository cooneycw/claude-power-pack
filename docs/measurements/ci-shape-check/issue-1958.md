# Issue 1958 qualification and input attribution

The qualified runner/test checkpoint is `660e250e92f868f19fcce48cad3bf01bd89f0bf7`.
The local run completed in 430.601 seconds; host run K906 exercised the actual
`make ci-shape-ci` entry in the pinned validate image and completed in 411.9
seconds. The host script blob is `615543b37498c0875699a5303ad56a8459403ef3`;
its SHA256 is `6c104533b68a45412ea90037e6b4ec69ecde5a60c961d64123243f0833c3a091`.

| Tier | Each lane selected | Passed | Named skips | Real uid/euid |
|---|---:|---:|---:|---|
| Local | 315 | 309 | 6 | 1000/1000 |
| Pinned image | 315 | 313 | 2 | 0/0 |

Both clone lanes passed. The two exact historical-installer nodes are declared
expected omissions before fixture setup, with reasons bound in each receipt.
Their skips do not prove historical installation. Ordinary validation is unchanged.
The separate GC publication witness and all twelve cancellation cases executed
and passed in both lanes. Local GOOD retains an UNKNOWN root column; only the
actual image run supplies root qualification. No locale/TZ or earlier 79-case
code-review-shell coverage is claimed.

The byte-exact receipts are [local](issue-1958-local.json) and
[image](issue-1958-image.json); [host timing](issue-1958-host-time.txt) includes
Docker client CPU, not container workload CPU. Receipt SHA256 values:

- `issue-1958-local.json`: `74b94c0321c118df32d4cce5c136963064235113c1697fcb7e618550cb191806`
- `issue-1958-image.json`: `4b97c403dcd62346ba9dd94ed33b616e45f0d43c40150f62804381facb1b0ce6`

The GC fix is established separately by its committed behavioural red/green:
`f8b43876` adds the regression; `3aa9cba6` makes the owned shared source's default
automatic GC run in the foreground before publication. With the actual pinned
staged Git on PATH, run:

```sh
make test-ci-shape-review-entry CI_SHAPE_REVIEW_TESTS=tests/test_host_update_source_gc.py
```

Before the fix: one failure, GC parent exit event 122 precedes repack exit 156.
After the fix: the staged-Git focused battery passed 77 cases; an unchanged
real-source/default-maintenance probe changed from its second clone failing
with object-copy ENOENT to eight successful local clones. The trace, not a
readiness timeout, decides the regression. No retry, maintenance disablement,
or weaker installer assertion was introduced. K895's historical test failed
in fixture setup before its availability check; K902's later skip therefore
cannot establish the GC fix.

The collector's standalone regression `38779dea` failed with eleven failures
(including ten cancellation cases) before `0beaedaa` passed policy as data.
The controlled-population regression `568ed4a3` failed before `660e250e`
restricted declarations to selected nodes. No cancellation fixture/assertion
was changed. The complete affected family subsequently passed 396 tests with
three real-root-only skips, including all `test_ci_shape_*.py`, collector,
cancellation, review-helper, GC and general runner tests.

The source integration checkpoint is `af4f99dbc70d90c80bbde121d5791fda7b35865c`,
merging qualified runner source with main `c8fa44fc`. Its only conflict was the
attribution JSON. The approved structured union contains 22 attribution rows;
historical members and generator/parser pins remain unchanged. All 405 generated
members were measured using independent frozen/current transforms. Only the
existing `flow-auto/scripts/SHA256SUMS` candidate needed a combined value:

| Source | Bytes | Mode | SHA256 |
|---|---:|---|---|
| Main | 2742 | 0644 | `15d33c6b946fa6d53a384d9ea7d656616afb1f4e5fe02c6d412c59f0c1f59487` |
| Combined | 2742 | 0644 | `ccba9cba38a18a4a59191c6d2207c2dda327cfa424bd839553d07f5f642b5eb4` |

This existing-row refresh was approved by the orchestrator; the two new #1958
rows were owner-approved in [issue1958 comment7232680930](https://github.com/cooneycw/claude-power-pack/issues/1958#issuecomment-7232680930).
No new member or mode was added by the merge. The runner, collector, CLI,
selectors, shape controls and their tests remain byte-identical to the qualified
checkpoint. The host proof carries only for that unchanged runner scope; the
merged artifact still requires its direct finish gate and exact-head PR image
step on kyleci. This publication changes only the four named evidence files. Review, finish-gate and PR timing outcomes remain pending.

The PR pipeline must report ci-shape and validate start/end times. The new
step overlaps validate; a same-event pipeline or validate increase above about
120 seconds, or ci-shape finishing after validate, requires revisiting the
placement before merge. No actual PR critical-path improvement is claimed here.

The search-resolved [Nit Store follow-up](https://github.com/cooneycw/claude-power-pack/issues/1957#issuecomment-7233300929)
records delivery-pilot cloning of a live source and converting all clone errors
to skips. That occurrence is not independently reproduced and was not changed.
