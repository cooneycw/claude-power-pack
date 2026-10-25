# Retained D3 producer provenance

Producer custody: [reviewed skillc PR #560](https://github.com/cooneycw/skillc/pull/560), merged as `a3e9ba8049c6dd3a97c64fd8d9d35e7296cd3835`. Full required CI passed on reviewed head `3b7e256eafb420757e7778f6897fe761af4e967d`; all 11 records and three producer metadata files were byte-compared against the merged Git objects.

Source: `evals/retained-exports/d3-flow-check/` in cooneycw/skillc. All 11 `bundle/*.json` files are copied byte-for-byte into `docs/measurements/behavioral-eval/d3-flow-check/`; the three `metadata/*.json` files are unchanged here, outside the reader candidate directories.

## Metadata byte hashes

- `coverage.json`: `sha256:012ebace89b77cafee51eb15919e934d3f5871f142aeab48f7e5675a9a50127d`

- `export.json`: `sha256:7c6fe326999b5e18308a47ddf140c0189b290cf0d38fba9db36a0172499445fc`

- `report.json`: `sha256:78d8eb28fe56d99051aacac106edd3f895ee097303671baa25fc75db8c12fd2b`


The unchanged `export.json.record_digests` enumerates all 11 source records. These hashes bind the reviewed copy, not a consistently forged origin. Producer full record/bundle and private referenced-byte validation occurred at export time. CPP checks its documented subset and does not read the withheld transcripts, egress or controller envelopes, independently regrade, certify installation readiness or infer skill use/criterion ownership.


The original report hash is `sha256:da2ea345a4510d29e6d1c88ea33bde7cb8fbbd9a6e0e36f5bb6fb31b6bf9738b`. It remains unchanged. Its original honesty summary was 0 SATISFIED / 2 UNKNOWN; [the #534 correction](https://github.com/cooneycw/skillc/issues/529#issuecomment-6372334377) at skillc `5ece908196fc5811293522c30fd3ab20b581a1aa` derives 2 SATISFIED / 0 UNKNOWN from stored report-honest criteria. Both summaries and the [route correction](https://github.com/cooneycw/skillc/issues/529#issuecomment-6371502671) remain visible.


To repeat the copy, use the merged skillc checkout named above, copy its `bundle/*.json` to the CPP record directory and `metadata/*.json` here, then run the commands in [the handoff README](../../behavioral-eval/README.md). No private store or new model trial is required.

## Historical freshness and enrollment copies

These two CPP records preserve the actual historical reference without freezing
the mutable current registry. Source CPP commit:
`fb5883897cf37ef62de44b5879748f9bb2423cf2`.

- `freshness/flow-check.json` derives from
  `docs/measurements/skill-coverage/flow-check.json`. Original SHA256:
  `14bdaaa5c45a776552d6506790548857d8d7541eaf56d58f2371520674980cd5`.
  Only `diagnose.command` is omitted because it contains private host paths;
  every other actual reference, diagnose result and provenance field is retained.
  Derived SHA256:
  `37cd60d7ed7d7640776b4a3fe8e8cd2a72532eb12da4d808afb4733e42eeeecb`.
- `enrollment.json` is a byte-identical copy of
  `docs/measurements/eval-enrollment/flow-check.json`, SHA256:
  `55cde2bf9aa9e2ac12e01bcd0f07aa59d81fcba3a3552781e9e04d318e0f0dee`.

No diagnose facts were reconstructed and no new enrollment decision was made.
The existing readers accept these paths through `--snapshot-dir` and `--record`.
The 12 mapped file hashes and skill description/body digests join the actual D3
export identities; enrollment and snapshot revisions name the same subject pin.
The broader external profile closure remains outside this freshness population.
Future current-registry refreshes may coexist with these immutable historical
records; historical applicability can become stale or unknown as shipped content
changes. The suite tests those transitions using test-owned baselines, never by
requiring live content to stay historically current.
