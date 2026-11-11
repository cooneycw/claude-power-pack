# `qa-regression-export` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `qa-regression-export`

- qa-regression-export - `/qa:test` Step 7b's handoff (#1291): `export` turns a confirmed bug's repro spec (`cpp.qa-regression/1`, a CLOSED schema with no field for cookies, storage state or headers; relative paths only; a literal into a password-like field refused in favour of `value_env`) into a test in the CONSUMER's own Playwright setup - opt-in via `.claude/qa.yml` `regression_export.enabled`, written to `regression_export.test_dir` or the config's `testDir`. With no runner it names the missing prerequisite and installs nothing. `run` executes one exported test with the consumer's runner and classifies `passed`/`reproduced`/`unavailable`/`error`: the generated test loads its start page inside a step that re-throws with a fixed marker, so an unreachable app is never read as the bug coming back, and zero executed tests is `error`, never a pass
