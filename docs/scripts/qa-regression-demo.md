# `qa-regression-demo` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `qa-regression-demo`

- qa-regression-demo - three-arm demonstration of `qa-regression-export` against `tests/fixtures/qa_regression/consumer` (#1291): buggy=`reproduced`, fixed=`passed`, no app=`unavailable`, plus `--negative-control`, which must report the buggy arm red when it is served the fixed app. `make qa-regression-demo` locally; the `qa-regression-demo` CI step in `mcr.microsoft.com/playwright` pinned to the lockfile's version is the load-bearing run. Deliberately outside `make verify`
