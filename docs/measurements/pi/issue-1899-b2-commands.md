# Pi #1899 B2 rules host commands

Status: READY FOR ORCHESTRATOR/MASTER REVIEW; no B2 host execution claimed.
MAX MODEL TURNS: 32 (16 transitions x 2 scratch repositories); NO RETRIES.
First model-turn batch on the owner's disposable sign-in; requires owner's go.
Owner amendment: pin codex 5.3 using one exact, provider-qualified CLI-listed ID.
Refs #1899. B0's [attributed completion](issue-1899-b0-results.md) establishes
the retained disposable root and owner sign-in. One HOME and fresh pi processes
per comparison; no further sign-in is planned. No owner-pane questions.

## Bindings and intervention

Master verifies the full reviewed commit, this file, the adjacent
[mutation helper](issue-1899-b2-files.py), and
[fixture manifest](issue-1899-b2-fixtures/manifest.json) before execution.
All helper commands below run from THAT CPP checkout; they take no variables
from another fence. Record full revision, helper/manifest/file hashes, exact
commands/prompts, cwd label, exits and fixture-only responses. The host checkout
must contain the reviewed helper and all fixtures; the historical B0 checkout
alone does not contain them. Never pull or switch the owner's working checkout
implicitly; master chooses the reviewed source path.

Intervention pi-1899-B2's rule helper touches only the two named global rule
paths in the existing disposable agent and its work/pi-1899-b2-state.json journal. Fixtures
are read from the reviewed CPP checkout. The helper never starts pi, lists the
agent, reads settings/session history, or probes credential files. It checks
only named rule paths, its own journal/fixtures, and the bounded context paths
below. No regular-install rules are written. Use an exclusive helper window;
this is not protection against hostile or concurrent non-cooperating writers.

Master's digest-only B0 amendment remains the regular-install comparison lane:
report only stable/changed/unexamined, never the private regular count/digest
pairing. Matching names do not establish unchanged bytes or no transient writes.
Use the retained amended collector, not the original names-printing B0 block.
Run it before B2, after its rule matrix, after size samples and after final undo.
No credential file contents or metadata are inspected.

## 0. Resolve the owner's model choice with zero model turns

B2 was paused before its first turn for the owner's ruling to pin codex 5.3.
Before resuming, master records whether the paused job created a B2 journal or
rule files. Existing preparation is not automatically retried or adopted; a
preexisting-journal refusal goes to master for a scoped resume disposition.
The published 1.6.0 CLI supports --offline --list-models with optional search,
and --model provider/id. Exact syntax and list-table structure are bound in the
[source note](issue-1899-pi-1.6.0-source.md). Do not guess an ID from the informal
name or read any settings, auth or model-store file.

```bash
python3 docs/measurements/pi/issue-1899-b2-model.py resolve --root "$HOME/.cpp-pi-1899-probe"
```

The [model helper](issue-1899-b2-model.py) runs only pi's offline listing, with
env -i-equivalent explicit environment construction, probe HOME/agent, no stdin
or prompt, and all tools/MCP/extensions/skills/context discovery disabled. It
prints matching provider-qualified IDs from pi's available-model table. Only
one matching row may proceed; none, multiple, duplicate, malformed output,
diagnostics, nonzero exit or timeout stops before ANY model turn. Offline
listing may lack current cached availability; do not retry online or choose a
different provider implicitly. Route an unresolved exact ID to master/owner.
Record the listing as intervention pi-1899-B2-model-pin: its helper writes only
the pin evidence under work; pi may perform its normal disposable-root store
initialization. Keep that evidence until final retention/whole-root cleanup.

The match requires both codex and version 5.3 in the MODEL ID, not a guessed
display name; different variants such as a second codex 5.3 row remain ambiguous.
Availability is pi's CLI report under its configured provider, not independent
proof of authentication or runtime identity. No helper inspects store contents.
Only pi itself uses its normal isolated internal authentication machinery.
--offline disables startup network operations by documented intent; this is
not a network-confinement or zero-auth-access claim about pi.

The helper creates work/pi-1899-b2-model-pin.json exclusively. It records the
unique provider/id and a digest of the CLI listing. Failed resolution leaves
an invalid reservation for manual review; no retry or automatic replacement.
Record the first printed ID and pin-file hash as the one batch selection. Every
launch below rereads this probe-owned evidence, adds --model with that exact
ID, and prints it before starting pi. Compare it with the original selection
and record pi's on-screen selected provider/model ID BEFORE entering the prompt.
A changed pin or screen mismatch stops the batch. A shortened/friendly label
that cannot establish the exact selected provider/id stays unresolved: stop and
ask master, using only pi's UI/CLI, never settings or stores. No model cycling.
The same model must be used for every one of the maximum 32 turns. These are
configuration/display observations, not B4 resolved runtime-model evidence.

## 1. Prepare and refuse contamination

Pi 1.6.0 discovers context from cwd ancestors independently of HOME/trust. The
helper checks ONLY the five documented context names in each known scratch cwd
and its ancestors, using existence metadata without reading content. A present
file or symlink stops preparation for relocation review. Do not read, remove or
adopt it. This includes possible real-HOME ancestor rules; fresh HOME alone does
not exclude them. A missing/unreadable directory or other inspection error stops
the command. No arbitrary project scan is performed.

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py prepare --root "$HOME/.cpp-pi-1899-probe"
```

This refuses preexisting probe AGENTS.md/AGENTS.override.md and an existing B2
journal. It validates every source fixture against its manifest before creating
the journal. Initial state is both rules absent. Preparation is not retried
following partial failure; report the stopped step and preserve state.

## 2. Exact rule transitions and fresh-session matrix

Run the following transitions IN ORDER. After each command, launch alpha then
beta using section 3, enter the neutral prompt once, record the response and
exit the process. All outcomes start PENDING. There are 16 transitions and at
most 32 model turns, with no automatic retries or additional size search.
Unexpected baseline marker, failed guard, authentication prompt, unsupported
flag or ambiguous state stops the batch and goes to the orchestrator.

The helper preflights BOTH installed rules against its stable journal before
any mutation. Present rules must be non-symlink regular files, mode 0644, with
exact previous fixture bytes. Unexpected, missing, edited or mode-changed rules
are preserved and refused. Unchanged members remain in place, including BASE
when the override changes. It marks the journal blocked before writing; an
interruption requires manual review, never an automatic retry/adoption. New
files use exclusive no-follow creation. Journal publication is atomic; the
multi-file rule transition is not claimed to be atomic.

1. Baseline, no marker expected:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set absent --root "$HOME/.cpp-pi-1899-probe"
```

2. Base alone; test BASE loading independently:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set base --root "$HOME/.cpp-pi-1899-probe"
```

3. Base removed; test disappearance after demonstrated presence:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set absent --root "$HOME/.cpp-pi-1899-probe"
```

4. Override alone; test OVERRIDE independently:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set override --root "$HOME/.cpp-pi-1899-probe"
```

5. Override removed; test its disappearance:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set absent --root "$HOME/.cpp-pi-1899-probe"
```

6. Both; observe which marker(s) appear without assuming precedence:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set both --root "$HOME/.cpp-pi-1899-probe"
```

7. Zero-byte override, BASE unchanged; test suppression:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set empty --root "$HOME/.cpp-pi-1899-probe"
```

8. Override removed, BASE unchanged; test BASE reappearance:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set base --root "$HOME/.cpp-pi-1899-probe"
```

9. Both removed; neither marker expected:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set absent --root "$HOME/.cpp-pi-1899-probe"
```

Run the retained amended name collector now. The empty-override inference needs
BASE present before and after; absence without those positives is unresolved.
The fixture tokens are PI1899BASE7KQ and PI1899OVERRIDE9VX; neither is in the
neutral prompt. Unexpected output is an observation, not automatically a
loader diagnostic or evidence of failed byte loading.

## 3. Independent isolated launches

Each launch derives its own environment in the ordinary approved host shell.
All tools, MCP, extensions and skills are disabled so tool reads cannot supply
rule markers. Context-file loading stays enabled. Flags are bound to the
published 1.6.0 args source in the [source note](issue-1899-pi-1.6.0-source.md).
There is no session reuse or persisted-transcript read. If the owner encounters
an authentication issue, stop and route it rather than copying credentials.

Alpha:

```bash
(
set -eu
model_pin=$(python3 docs/measurements/pi/issue-1899-b2-model.py read --root "$HOME/.cpp-pi-1899-probe")
printf 'Pinned model: %s\n' "$model_pin"
cd -- "$HOME/.cpp-pi-1899-probe/work/repo-alpha"
env -i PATH="$PATH" TERM="${TERM:-xterm-256color}" LANG=C.UTF-8 \
  HOME="$HOME/.cpp-pi-1899-probe/home" \
  PI_CODING_AGENT_DIR="$HOME/.cpp-pi-1899-probe/agent" \
  XDG_CONFIG_HOME="$HOME/.cpp-pi-1899-probe/config" \
  XDG_DATA_HOME="$HOME/.cpp-pi-1899-probe/data" \
  XDG_CACHE_HOME="$HOME/.cpp-pi-1899-probe/cache" \
  TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" \
  pi --no-session --no-tools --no-mcp --no-extensions --no-skills --model "$model_pin"
)
```

Beta:

```bash
(
set -eu
model_pin=$(python3 docs/measurements/pi/issue-1899-b2-model.py read --root "$HOME/.cpp-pi-1899-probe")
printf 'Pinned model: %s\n' "$model_pin"
cd -- "$HOME/.cpp-pi-1899-probe/work/repo-beta"
env -i PATH="$PATH" TERM="${TERM:-xterm-256color}" LANG=C.UTF-8 \
  HOME="$HOME/.cpp-pi-1899-probe/home" \
  PI_CODING_AGENT_DIR="$HOME/.cpp-pi-1899-probe/agent" \
  XDG_CONFIG_HOME="$HOME/.cpp-pi-1899-probe/config" \
  XDG_DATA_HOME="$HOME/.cpp-pi-1899-probe/data" \
  XDG_CACHE_HOME="$HOME/.cpp-pi-1899-probe/cache" \
  TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" \
  pi --no-session --no-tools --no-mcp --no-extensions --no-skills --model "$model_pin"
)
```

Identical prompt for every turn:
`Respond with a single-line plain greeting saying hello.`
Exit after the single answer. Copy only the new controlled fixture response,
actual loader diagnostics if exposed, and process exit; no login capture,
unrelated output, historical transcript or session files. The model's statement
that a file loaded is not independent evidence. Do not include tokens, expected
outputs or fixture paths in prompts. Any tool call invalidates that row's
startup-loading claim even if tokens appear.

## 4. Exact bounded size samples (transitions 10-15)

The published 1.6.0 configuration docs and inspected loader/render functions
state no numeric per-file cap. Source inspection is not runtime measurement or
proof that no other limit exists. Use these exact committed samples in EACH
file independently; do not borrow AGY's limit or call these under/over a known
boundary. A later threshold search needs a separate reviewed budget.

After EACH command below, run both section 3 launches and the same prompt.
For size N, the independent expected markers are PI1899SNHEAD,
PI1899SNMIDDLE and PI1899SNTAIL, replacing N with the decimal byte size.

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set base-8192 --root "$HOME/.cpp-pi-1899-probe"
```

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set base-32768 --root "$HOME/.cpp-pi-1899-probe"
```

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set base-65536 --root "$HOME/.cpp-pi-1899-probe"
```

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set override-8192 --root "$HOME/.cpp-pi-1899-probe"
```

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set override-32768 --root "$HOME/.cpp-pi-1899-probe"
```

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set override-65536 --root "$HOME/.cpp-pi-1899-probe"
```

The manifest binds exact UTF-8 bytes/hashes. Each sample has an instruction at
its head, halfway byte position and tail, separated by inert padding. Absence
of a tail cannot establish full loading even if pi exits 0 with no diagnostic.
All three output tokens support only behavioral marker retention at those
positions, not proof of every intervening byte. Model instruction-following
failure cannot alone establish a truncation boundary; record that distinction
as unresolved unless actual loader metadata settles it. No aggregate-token or
unlimited-size claim. Run the amended name collector after these samples.

## 5. Final undo and negative controls

Transition 16, return both rule paths to the observed absent baseline:

```bash
python3 docs/measurements/pi/issue-1899-b2-files.py set absent --root "$HOME/.cpp-pi-1899-probe"
```

Run both fresh sessions once more, then the amended name collector. If a rule's
bytes/type/mode changed or recorded output vanished, undo refuses without
removing either rule. Preserve the blocked state and report. Keep the journal,
source fixtures, scratch repositories and signed-in root for B3/B4; this undo
removes only B2 rules. Master arranges whole-root cleanup after final retention.

The helper's committed opposite cases are in tests/test_pi_rules_probe.py:
foreign, edited, symlink, mode-changed, missing, directory, ancestor context and
blocked/interrupted state. The real nonzero case matrix installs exact fixture
bytes/modes and returns to absent while preserving a personal neighbor. A
committed deliberately blind guard in tests/fixtures/pi-rule-probe-blind.py
accepts/deletes an edited rule; the actual refusal case must run red with that
guard and green with the real guard before routing. This is a new helper;
there is no preexisting implementation or fabricated pre-fix regression claim.
Run only local fixture tests with make test-pi-rules-probe; never substitute
those results for actual pi model observations. No runtime B2 result is claimed.

Master returns version/revision, exact commands/prompts/exits, fixture identities,
actual responses/diagnostics, intervention and observed undo, selected isolation
lane, and original artifact hashes for the final sanitized manifest. No regular
count/digest pairing, private host names, credentials, or session contents are
published. B2 supplies no B4 transcript-access authorization.

## Local handoff verification (not host B2 evidence)

The rule-guard fixture suite passed 12 cases; the model-pin amendment brings
the combined focused suite to 21 passing cases; lint passed. The edited-rule
refusal case ran red with the committed blind guard (DID NOT RAISE ValueError)
and green with the real guard. An unavailable-ancestor-metadata case ran red on
the original draft's lexists implementation (DID NOT RAISE PermissionError),
then passed after replacing it with lstat that propagates inspection errors.
No pi process or owner path was accessed by these local fixtures. Shell blocks
are syntax-checked only; actual version-specific flag enforcement remains a
host observation. No full suite or PR CI has been requested for this handoff.

To reproduce the deliberate red ONLY in local synthetic pytest fixtures:

```bash
CPP_PI_RULE_PROBE_BLIND_CONTROL=1 make test-pi-rules-probe 'PI_RULE_PROBE_TESTS=tests/test_pi_rules_probe.py::test_bad_input_preserved_and_refused[edited]'
```

Expected: test failure, because the blind guard deletes an edited synthetic
rule instead of refusing. Do not enable that test-only control during a normal
test run; the production mutation helper has no environment bypass.

The model parser uses committed synthetic one/two/none/malformed CLI tables
under tests/fixtures/pi-model-list. Its ambiguity-refusal case ran red with
the committed blind selector (DID NOT RAISE ValueError) and passed with the real
selector. Tests stub pi execution and check explicit probe environment, no
prompt, exclusive pin creation, diagnostics/exit refusal and symlink refusal.
The production model helper has no test-control environment bypass. The
synthetic provider/model IDs are fixtures, not a host availability claim.

Reproduce the model selector's deliberate red ONLY in local synthetic fixtures:

```bash
CPP_PI_MODEL_PIN_BLIND_CONTROL=1 make test-pi-rules-probe 'PI_RULE_PROBE_TESTS=tests/test_pi_model_pin.py::test_ambiguous_listing_refused'
```
