# Pi #1899 B0 host commands

Status: PENDING, for master review and owner agreement after R2 host steps.
Refs #1899. These are manual commands, not an automatic acceptance gate.
Run only in the owner-approved host shell. No command here has been run on the
owner host by the author. Keep the disposable root for B2-B4 and one owner login.

Master records the exact CPP checkout and this file's reviewed commit/hash
before running anything. Execute setup from that checkout. Each fenced block
is independent: no shell variables from another block are required. The fixed
probe name below is private host-local state, not a published artifact path.
If it already exists, stop and route the collision to the orchestrator; never
reuse or delete an unknown prior root.

## 1. Prepare (intervention pi-1899-B0)

This creates only the named disposable tree. Record stdout and the shell exit
without a pipeline masking it. mkdir without -p on the top directory deliberately
refuses an existing tree. No recursive inventory or credential metadata access.

```bash
(
set -eu
umask 077
git rev-parse HEAD
command -v pi
node --version
mkdir -- "$HOME/.cpp-pi-1899-probe"
mkdir -p -- "$HOME/.cpp-pi-1899-probe"/{home,agent,config,data,cache,tmp,evidence,work/repo-alpha,work/repo-beta}
git -C "$HOME/.cpp-pi-1899-probe/work/repo-alpha" init -q
git -C "$HOME/.cpp-pi-1899-probe/work/repo-beta" init -q
printf '%s\n' 'pi-1899-B0-marker' > "$HOME/.cpp-pi-1899-probe/agent/cpp-1899-isolation-marker"
)
```

Undo for partial setup: stop, retain the partial root and report exactly which
command failed. Do not retry setup or recursively delete the tree. Master
reviews cleanup; this avoids removing unexamined signed-in or foreign state.

## 2. Name-only regular-agent baseline and marker pair

Run before and after each batch. Keep stdout private. The two exact marker
names are non-credential fixture paths. Directory names are observed with
os.listdir only, never stat or content reads of entries. A missing regular agent
is recorded as such; permission or other errors propagate rather than becoming
an unchanged claim. No listing of session subdirectories is permitted.

```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

regular = Path.home() / '.pi' / 'agent'
probe = Path.home() / '.cpp-pi-1899-probe' / 'agent'
for label, root in [('regular', regular), ('probe', probe)]:
    try:
        names = sorted(os.listdir(root))
    except FileNotFoundError:
        names = None
    print(json.dumps({'root': label, 'names': names}))
    for marker in ['cpp-1899-isolation-marker', 'cpp-1899-never-created-marker']:
        print(json.dumps({'root': label, 'marker': marker,
                          'present': None if names is None else marker in names}))
PY
```

Committed paired inputs: setup creates cpp-1899-isolation-marker only in the
probe. No command creates cpp-1899-never-created-marker. Expected observations
are present/absent in the probe and both absent in a readable regular agent.
For a nonexistent regular agent, retain names=null and establish only that
the directory was missing. An unexpected marker or changed regular listing
stops the batch. A reader that always prints absent fails the positive case;
one that always prints present fails the never-created case. Compare the actual
outputs; a command exit alone is not evidence of isolation. This names-only
comparison establishes neither unchanged bytes nor no transient host writes.

## 3. Version in the disposable environment

Run from the approved CPP checkout; the subprocess cwd is scratch-repo-alpha.
The login shell must provide an installed pi on PATH. The environment is rebuilt
without inherited provider tokens, pi settings or session-directory overrides.
Do not infer model identity from version/help output. No help command is needed.

```bash
(
set -eu
cd -- "$HOME/.cpp-pi-1899-probe/work/repo-alpha"
env -i PATH="$PATH" TERM="${TERM:-xterm-256color}" LANG=C.UTF-8 \
  HOME="$HOME/.cpp-pi-1899-probe/home" \
  PI_CODING_AGENT_DIR="$HOME/.cpp-pi-1899-probe/agent" \
  XDG_CONFIG_HOME="$HOME/.cpp-pi-1899-probe/config" \
  XDG_DATA_HOME="$HOME/.cpp-pi-1899-probe/data" \
  XDG_CACHE_HOME="$HOME/.cpp-pi-1899-probe/cache" \
  TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" pi --version
)
```

Stop if the measured package/version differs from the planned pi 1.6.0; report
it for a plan adjustment. Run the name-only comparison again before login.

## 4. Owner launch and sign-in (no capture)

Only after the owner agrees to this disposable HOME, master launches this
command in an interactive terminal. The owner uses pi's own login flow once
and exits without making a model turn. No helper reads credentials and no screen,
terminal, transcript or authentication traffic is captured. Record only whether
the owner reports login completed, plus final process exit. A reported login is
not a model-identity measurement. If login needs a missing environment value,
stop and route to the orchestrator rather than importing the owner's environment.

```bash
(
set -eu
cd -- "$HOME/.cpp-pi-1899-probe/work/repo-alpha"
env -i PATH="$PATH" TERM="${TERM:-xterm-256color}" LANG=C.UTF-8 \
  HOME="$HOME/.cpp-pi-1899-probe/home" \
  PI_CODING_AGENT_DIR="$HOME/.cpp-pi-1899-probe/agent" \
  XDG_CONFIG_HOME="$HOME/.cpp-pi-1899-probe/config" \
  XDG_DATA_HOME="$HOME/.cpp-pi-1899-probe/data" \
  XDG_CACHE_HOME="$HOME/.cpp-pi-1899-probe/cache" \
  TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" pi
)
```

Repeat section 2 after exit; compare the regular listing to its baseline.
Record probe marker present and never-created marker absent. Pi may initialize
store entries inside the disposable root; do not inspect those entries.
B0 is PENDING until master supplies actual paired observations and versions.
An isolation problem stops later batches. Login or version failure is not a
completed B0, even if marker comparisons match.

## 5. Scoped undo and handoff

Keep HOME/agent and scratch repositories for B2-B4. After the final B0 comparison,
remove only the known marker created in section 1, then repeat section 2 to
observe its absence (and regular listing stability). This is the marker's undo,
not cleanup of pi's own initialization or owner login.

```bash
unlink -- "$HOME/.cpp-pi-1899-probe/agent/cpp-1899-isolation-marker"
```

The marker's post-undo absence must be preceded by its observed presence. Retain
only command/exit/version and name-only comparison evidence, with private paths
redacted from the eventual publication. No scan of authentication/session files
is authorized. Final whole-root removal is an owner/master action arranged after
B2-B4 and evidence retention, not an automatic recursive command in this handoff.
