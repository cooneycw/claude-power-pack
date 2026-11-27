# Pi #1899 B2 rules command draft

Status: DRAFT, NOT READY FOR HOST EXECUTION. Refs #1899. Prepared while B0
queues behind R2. No command below has been executed by the author. Review
this file and finalize the size fixtures before routing any B2 host step.

## Preconditions and intervention

Use the single disposable HOME/agent created by the
[B0 handoff](issue-1899-b0-commands.md), with the owner's one direct sign-in.
Master must first return B0's actual version, isolation observations and owner
agreement to reuse that root. Stop if B0 is unresolved pending isolation review.
If the owner skipped regular-agent name observations, record that lane as
unexamined; probe markers and env -i do not establish an unchanged regular
installation. Do not silently lower #1899's acceptance requirement.

Intervention pi-1899-B2: create only the two named rule files in the disposable
agent and fixture files under its disposable work area. No regular-install
mutation. Never read/stat/copy auth.json, mcp-auth.json or any session history.
Each matrix row gets a new pi process with --no-session and no prior turn.
No second login or second HOME is planned. Unexpected rules from B0 or any
changed fixture stop this batch; preserve them and report instead of adopting.

The commands below assume the version measured by B0 is pi 1.6.0. Master must
confirm --no-session behavior before routing model turns. Unsupported syntax
stops the row; no fallback that reads session history is authorized.

## 1. Baseline and fixture preparation (draft)

From the reviewed CPP checkout, record full git revision and command-file hash.
Run the approved B0 name comparison, with its owner-selected listing lane.
The following preparation refuses existing rule files (including symlinks)
and an existing B2 fixture directory. It never inventories agent neighbors.
The top-level fixture directory is deliberately exclusive; do not retry after
partial setup without reporting it. File digests are local fixture provenance,
not proof of runtime loading.

```bash
python3 - <<'PY'
import hashlib
import os
from pathlib import Path

root = Path.home() / '.cpp-pi-1899-probe'
agent = root / 'agent'
for name in ['AGENTS.md', 'AGENTS.override.md']:
    if os.path.lexists(agent / name):
        raise SystemExit('STOP: unexpected preexisting probe rule: ' + name)
fixtures = root / 'work' / 'b2-fixtures'
fixtures.mkdir(mode=0o700)
inputs = {
    'base.md': b'For every response, include the exact token PI1899BASE7KQ.\n',
    'override.md': b'For every response, include the exact token PI1899OVERRIDE9VX.\n',
    'empty.md': b'',
}
for name, content in inputs.items():
    with (fixtures / name).open('xb') as output:
        output.write(content)
    print(name, len(content), hashlib.sha256(content).hexdigest())
PY
```

Before first model turn, master records that the two scratch repositories have
no project rule files, skills or MCP fixtures from another batch. Restrict that
inspection to known fixture repositories; no arbitrary project scans.

## 2. Independent fresh-session launch commands (draft)

Launch from the ordinary host shell, not from a shell already using the probe
HOME. Each command derives the same isolated environment independently.
Copy only the controlled fixture response for the row and the process exit;
never capture login, existing conversation, session files or unrelated output.
Do not use /reload as a substitute for a fresh process in these comparisons.

Alpha:

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
  TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" pi --no-session
)
```

Beta:

```bash
(
set -eu
cd -- "$HOME/.cpp-pi-1899-probe/work/repo-beta"
env -i PATH="$PATH" TERM="${TERM:-xterm-256color}" LANG=C.UTF-8 \
  HOME="$HOME/.cpp-pi-1899-probe/home" \
  PI_CODING_AGENT_DIR="$HOME/.cpp-pi-1899-probe/agent" \
  XDG_CONFIG_HOME="$HOME/.cpp-pi-1899-probe/config" \
  XDG_DATA_HOME="$HOME/.cpp-pi-1899-probe/data" \
  XDG_CACHE_HOME="$HOME/.cpp-pi-1899-probe/cache" \
  TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" pi --no-session
)
```

Type the identical neutral prompt once per process:
`Respond with a single-line plain greeting saying hello.`
Exit that process after its answer. Marker tokens must never be included in
the prompt or earlier turns. Do not count a model's explanation of rule loading
as an independent loader diagnostic. Record the exact observed tokens and any
actual diagnostic separately; unexpected output leaves the row unresolved.

## 3. Rule matrix and mutations to finalize before routing

Every row runs in BOTH alpha and beta, with the launch blocks above. Record
file byte counts/hashes, exact intervention and undo, prompt, response and exit
for each. Start and finish each independent sequence without either rule file.
All observations are PENDING. Expected tokens below are hypotheses under test.

| Sequence | Probe-agent input | Comparison question |
|---|---|---|
| Baseline | Both rule files absent | Neither marker should appear; otherwise find contamination before proceeding |
| Base present | base.md copied to AGENTS.md; override absent | Does BASE appear in both unrelated repositories? |
| Base removal | Both absent after scoped undo | Does BASE disappear in fresh processes after demonstrated presence? |
| Override present | override.md copied to AGENTS.override.md; base absent | Does OVERRIDE load independently? |
| Override removal | Both absent after scoped undo | Does OVERRIDE disappear after demonstrated presence? |
| Both present | base.md and override.md at their respective paths | Which marker(s) load? Do not assume override precedence |
| Empty override | base.md present; override is exactly empty.md (0 bytes) | Does an existing empty override suppress BASE? |
| Empty override removed | Base unchanged; override absent | Does BASE reappear with the identical prompt? |
| Final removal | Both absent | Neither marker; regular listing comparison only if that lane was approved |

Final host command revision must include exact exclusive creation and guarded
undo commands for these mutations. Never blindly cp over a destination or use
rm -f. A rule created by this intervention may be removed only after its bytes
match the recorded fixture and its type remains a regular non-symlink file.
Changing from nonempty to empty override requires that same guarded removal,
then exclusive creation. A failed guard preserves the file and stops the batch.
No mutation commands are routed from this draft.

The empty-override result needs the paired BASE-present observation on either
side: a baseline that never loads BASE cannot establish suppression. If both
markers appear, record it; do not reinterpret it as the planned precedence.
If removal does not remove a marker, stop before further size measurements.

## 4. Size fixtures: deliberately pending

First obtain version-specific non-secret documentation or source identifying
any pi per-file size boundary. This is not authorization to run help in the
owner's real HOME or inspect credentials. Do not use AGY's 24,000-byte value.

Before host execution, commit exact UTF-8 fixture bytes with independent head,
middle and tail tokens, lengths and hashes. Use the measured supported rule
target, with the other file absent. If a documented boundary exists, test
below/at/above it with fresh sessions in both repositories. If no boundary is
documented, propose a bounded byte-size sample and turn budget to the
orchestrator before routing commands. No unbounded search or unlimited-size
claim is authorized. Aggregate-token behavior remains separately unmeasured.

The size row's neutral prompt asks for a greeting and must not contain any
token. All expected markers must appear to support complete fixture loading;
an absent tail, even with exit 0 and no diagnostic, cannot pass that claim.
Retain the actual diagnostic or its observed absence separately. Head/tail
output is bounded behavioral evidence, not proof of every intermediate byte.
If model behavior cannot distinguish loading from failure to follow a rule,
leave that distinction unresolved rather than inventing a truncation boundary.

## 5. Undo, controls and evidence handoff

Guarded removal returns both disposable rule paths to the observed absent
baseline. Retain inputs/results outside the agent, keep the signed-in HOME for
B3/B4, and perform the approved regular-name comparison if permitted. Record
actual undo outcome; retained fixture directories are not a whole-root cleanup.

The committed marker cases provide the opposite inputs: absent, present,
removed, and empty-vs-nonempty override. Before any automated reader or gate is
introduced, it needs committed good/bad/unexaminable materialized inputs and a
demonstrated blind-reader failure. No result parser or acceptance gate is shipped
in this draft. No red/green runtime outcome is claimed.

Master returns sanitized fixture-only observations, full revision and version,
exact argv/prompts/exits, original artifact identifiers/hashes, intervention/undo
records and the selected isolation lane. Missing diagnostics or skipped regular
listing stay unexamined. Do not publish real host names, absolute private paths,
credentials or session contents. B2 cannot authorize transcript access for B4.
