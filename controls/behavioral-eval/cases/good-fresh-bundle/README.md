A coherent, minimal producer bundle (ledger, manifest, receipt, lifecycle,
result - one attempt), under `bundle-1/`: #1369's "one bundle per immediate
subdirectory" layout. Adapted from skillc `controls/ledger-binding/good/complete/`
at commit `2202603` (ids and digests unchanged); no `skill-evidence` record, so
this exercises `_validate_bundle`'s restated subset alone, not the R9/R14/R15
skill-evidence path (see `good-bundle-skill-evidence-matched` for that).
