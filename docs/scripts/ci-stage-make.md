# `ci-stage-make` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `ci-stage-make` (#1165)

- ci-stage-make - a pinned GNU make for the CI steps that need it (#1165) - asking make requires make, and the pipeline image has none (measured). Without it the derivation answers "cannot ask" everywhere in CI, `controls/flow-finish-gate-derivation` measures make's ABSENCE instead of its subject, and `TestSubsumedGates` SKIPS in validate on its `shutil.which` guard - the issue's own red case untested where a reviewer can re-derive it. Same shape and same reason as `ci-stage-jq` (#1017), staged for `validate` AND `negative-controls`. THE SOURCE IS A DEBIAN .deb because there is no canonical static make release to pin: the bytes come from the distribution the image is built from, so its only shared-library dependency (libc6) is present by construction, and it is extracted with the stdlib - a `.deb` is an `ar` archive whose `data.tar.xz` carries `./usr/bin/make`, and `ar` is a 60-byte-header format simple enough to read directly. TWO PINS: the archive, and the BINARY INSIDE IT, because an archive can be repacked around different contents and it is the binary that executes. AND IT RUNS WHAT IT STAGED - `make --version` before reporting success, because a copy that lands is not a tool that runs (#1168)
