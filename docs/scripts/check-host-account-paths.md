# `check-host-account-paths` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `check-host-account-paths` (#1689)

- check-host-account-paths fails when a tracked file carries a home path that names an account: the plain form under the homes directory, or the encoded form Claude and Qwen use for a project's transcript directory. `make host-account-paths-check`; in `make verify` and CI.
- check-host-account-paths MATCHES THE SHAPE, NEVER THE RUNNING ACCOUNT. A check keyed on the running account sees nothing in CI, where the account differs, and reports clean over the files it exists to catch. That weaker check is the control's constructed anchor.
- check-host-account-paths HAS A PLACEHOLDER LIST THAT NARROWS IT ON PURPOSE (`user`, `clean`, `test` and similar). A new name fails until it is added to `PLACEHOLDERS` deliberately.
- check-host-account-paths READS `git ls-files` and prints `HOST_ACCOUNT_PATHS_EXAMINED:` on every verdict. No git, an unreadable tracked file, or zero text files is `UNKNOWN` (exit 2), not clean.
- check-host-account-paths found one occurrence a grep for the Linux form had missed while it was being written: a receipt recorded on macOS, under the other homes directory.
- The writers were changed in the same issue: `counter-model-receipt.py` redacts the home directory's encoding in a recorded evidence path, `lib/cicd/evidence.py` records home paths as `~/...`, and `skill-coverage-snapshot.py` records its command with `~`.
