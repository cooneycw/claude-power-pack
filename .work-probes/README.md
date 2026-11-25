# Disposable pi probes

Never merge this branch. No product implementation or pi acceptance is claimed.
Run only after the host's pi 1.6.0 help has been reviewed for the flags used.
Do not fetch branch-tip bytes: use the exact full commit supplied in the handoff.

Fetch each Python file with `git show COMMIT:.work-probes/FILE.py` into a fresh
temporary file on the host. Run with `env -i PATH="$PATH" python3 TEMP_FILE ...`.
The subprocess environment contains only fixture home/config/data/cache/history,
PATH, locale and (for the fixture TUI) TERM. No provider request is sent. This
environment selection is not filesystem credential isolation or a network fence.

Batch 1: run `pi-discovery.py --self-test` first, then, after help review,
`pi-discovery.py --help-reviewed`. Its private mktemp root is printed with undo
before any install, and removed in `finally` after child cleanup. Retain complete
fixture stdout/stderr. Collision cases record the actual winner and diagnostics;
do not infer precedence from list order. Hidden metadata placement is a measured
candidate only. Discovery does not establish model invocation or session-history
persistence precedence. The reader's committed good/empty/missing response cases
test the reader, not pi itself.

Batch 2 uses a helper-owned fresh fixture TUI, never the owner's existing session.
Run `pi-reload.py create` and retain its printed ROOT and undo before continuing.
Launch `pi-reload.py launch ROOT --help-reviewed` in a separate fixture terminal.
Type `/reload` and capture the fixture skill's presence. From another helper
shell run `pi-reload.py remove ROOT`, reload again and capture disappearance.
Run `pi-reload.py restore ROOT`, reload and capture reappearance. Exit the fixture
TUI, then execute `pi-reload.py cleanup ROOT`. The initial presence is required
before interpreting subsequent absence; no automatic UI verdict is emitted.

Keep the fetched probe file until cleanup completes. If a child is killed along
with its supervisor, use the printed exact fixture-root undo only after ensuring
that child has stopped. No cleanup command names the real owner installation.
