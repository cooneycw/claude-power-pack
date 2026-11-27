# Pi #1899 B3 local MCP handoff

Status: K769 ran d9c511c1 and stopped after T1-beta. See the scoped disposition
below; later documentation amendments are not silently claimed as executed code.
MAX MODEL TURNS: 32 response rounds; MAX USER PROMPTS: 16 (8 states x 2 repos).
One user prompt and at most one MCP call per session; no retries or follow-ups.
Stop on an extra tool attempt or a response round beyond tool-call plus final
response. Compatible-client protocol calls spend ZERO provider-model turns.
Owner go must state both budgets before routing. Reuse pi 1.6.0, the retained
disposable HOME and github-copilot/gpt-5.3-codex pin. Do not update or sign in again.
For EVERY tag record ACTUAL user prompts, model-response rounds, MCP attempts
and exit, then report aggregate actual usage against both caps, including any
stopped attempt. Count new observed response phases; do not infer actual rounds
from tool-call counts or report the maximum as usage. If round boundaries are
unexaminable, stop and route that limit before further turns; never read history.
Refs #1899; [B2 results](issue-1899-b2-results.md).

Live scoped disposition: [T1-beta capture was lost](issue-1899-b3-capture-stop.md).
It remains UNEXAMINABLE, not an absence pass. No retry. Continuation A starts at
T2 only after zero-model capture controls; two prompts and an actual round
interval 1-2 are already spent. Book upper bound 2 for admission, not as actual
usage. This named exception does not waive any future unexaminable-row STOP.

## Bind source and intervention boundaries

Master verifies the reviewed full commit and file SHA256 for this handoff,
[config/control helper](issue-1899-b3-probe.py), [server](issue-1899-b3-server.py),
and reused B2 model helper before running. Use a separate reviewed CPP clone
and retain it until every stdio child has stopped; do not change the owner's
CPP checkout. All relative commands below execute from that reviewed clone.
Each fenced command derives its own arguments without prior shell variables.
Record Python's version and verify the host pi package remains the measured
1.6.0 before routing model turns; the version check must use the same cleared
probe environment as B0. Any version change stops for a new plan, never updates.

Intervention pi-1899-B3 creates ONLY the PROBE agent/mcp.json, its atomic
.pi-1899-b3-mcp.pending sibling, and work/pi-1899-b3 evidence/state. Existing
mcp.json, aliases, changed bytes or interrupted journals stop without adoption,
overwrite or reset. The fixture file starts with a disabled synthetic foreign
entry and autoEnableCodemode=false. This is not the owner's real registration.
Each case changes only the two cpp-pi1899 fixture keys, preserves the synthetic
foreign entry exactly, and has a guarded set-foreign undo. Final undo removes
the synthetic-only file only when it matches the recorded owned baseline.
Unexpected added content is preserved/refused. No force flag or recursive delete.

The HTTP fixture binds ONLY 127.0.0.1 on an OS-assigned port. Stdio uses pipes.
No external MCP service, bearer token, credential copy, OAuth flow or direct
settings/auth/model-store/session read is part of the helper. Pi itself uses
the owner's already approved disposable sign-in normally. A fresh HOME is
configuration isolation, not a filesystem, credential or network boundary.
All helpers are pure stdlib; do not install packages. Keep an exclusive helper
window; these guards do not claim safety against hostile concurrent writers.

Use master's retained digest-only regular-agent collector before preparation,
after direct/default tests, after dead tests and after undo. Publish only
stable/changed/unexamined, never the real count/digest pairing. Matching sampled
names establish neither unchanged bytes nor absence of transient writes.

## 1. Prepare once (zero model turns)

Record Python and pi versions first; require pi 1.6.0, with no update:

```bash
python3 --version
```

```bash
(
set -eu
cd -- "$HOME/.cpp-pi-1899-probe/work/repo-alpha"
env -i PATH="$PATH" LANG=C.UTF-8 HOME="$HOME/.cpp-pi-1899-probe/home" \
  PI_CODING_AGENT_DIR="$HOME/.cpp-pi-1899-probe/agent" \
  XDG_CONFIG_HOME="$HOME/.cpp-pi-1899-probe/config" XDG_DATA_HOME="$HOME/.cpp-pi-1899-probe/data" \
  XDG_CACHE_HOME="$HOME/.cpp-pi-1899-probe/cache" TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" pi --version
)
```

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py prepare --root "$HOME/.cpp-pi-1899-probe"
```

This reuses B2's read-only check-t1 and exact model pin; it does not reprepare
B2. It requires both rule paths absent and the original stable/empty B2 journal.
It creates a new exclusive B3 directory, batch ID, reply directory and guarded
foreign-only config. If interrupted, preserve state and report; never retry.
Keep the batch ID, journal, expected config hash and foreign-entry hash private
until reviewed for the final sanitized manifest.

## 2. Start the HTTP fixture in a dedicated terminal

Execute from the same reviewed clone in a second host terminal, foreground:

```bash
(
set -eu
env -i PATH="$PATH" LANG=C.UTF-8 HOME="$HOME/.cpp-pi-1899-probe/home" \
  python3 docs/measurements/pi/issue-1899-b3-server.py http \
  --directory "$HOME/.cpp-pi-1899-probe/work/pi-1899-b3"
)
```

Wait for the printed HTTP PID and loopback port; record them and eventual exit.
endpoint.json contains fixture-only instance/teardown state; it is not published
or given to the model. Never print its shutdown token. Do not restart, kill an
unverified PID or substitute a different listener if the fixture stops. Teardown
below verifies the loopback instance and uses its scoped shutdown request.

Prove both fixture transports with the independent compatible client:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py control-stdio --root "$HOME/.cpp-pi-1899-probe"
```

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py control-http --root "$HOME/.cpp-pi-1899-probe"
```

Both must exit 0 with compatible_call=true. These clients perform initialize,
tools/list and a real tools/call; HTTP also closes its session. Their distinct
cpp-pi1899-control peer and control tags cannot count as pi evidence. Stdio
children record PID/start/stop and exit on stdin close. Controls use a cleared
probe environment; loopback HTTP ignores inherited proxies. A failed control
stops before model turns. This tests fixture compatibility, not actual pi.

## 3. Matrix, guarded writes and undo

T1 is the foreign-only state already created by prepare. T8 returns to that
state after T7's guarded undo. For EACH row use alpha and beta fresh launches
from section 4, then the exact row-bound prompts and evidence steps in section 5.
Do not add another prompt to repair a result. All observations start PENDING.

| Row | Case | Alpha tag | Beta tag | Comparison |
|---|---|---|---|---|
| T1 | foreign | T1-alpha | T1-beta | Probe tool absent baseline |
| T2 | stdio-direct | T2-alpha | T2-beta | Native stdio call and normalized tool ID |
| T3 | stdio-default | T3-alpha | T3-beta | Omitted exposure, restricted direct-call lane |
| T4 | http-direct | T4-alpha | T4-beta | Native Streamable HTTP call and normalized ID |
| T5 | http-default | T5-alpha | T5-beta | Omitted exposure, restricted direct-call lane |
| T6 | stdio-dead | T6-alpha | T6-beta | Known executable exits 23 before handshake |
| T7 | http-dead | T7-alpha | T7-beta | Same previously working endpoint, now stopped |
| T8 | foreign | T8-alpha | T8-beta | Removal/absence after demonstrated positive calls |

Before T2:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py set --case stdio-direct --root "$HOME/.cpp-pi-1899-probe"
```

After EVERY T2-T7 pair, audit then undo that case with these exact commands:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py audit --root "$HOME/.cpp-pi-1899-probe"
```

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py set --case foreign --root "$HOME/.cpp-pi-1899-probe"
```

The foreign-entry hash must equal preparation's hash after each transition and
both sessions. Byte/mode/content changes, foreign replacement or interrupted
state stop BEFORE further config mutation. This verifies this fixture's scoped
merge, not delivery of CPP's #1902 implementation or real-user preservation.

Before T3, after T2's foreign-only undo:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py set --case stdio-default --root "$HOME/.cpp-pi-1899-probe"
```

Before T4, after T3's undo:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py set --case http-direct --root "$HOME/.cpp-pi-1899-probe"
```

Before T5, after T4's undo:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py set --case http-default --root "$HOME/.cpp-pi-1899-probe"
```

For T2/T3 run control-stdio BEFORE and AFTER each pair. For T4/T5 run
control-http BEFORE and AFTER each pair. These zero-model-turn controls must
remain working before interpreting any native refusal. Record native MCP
connection/exposure/tool status if exposed by /mcp; do not change enablement,
exposure or login from that UI. Wait at most 15 seconds for a healthy-case
connection before its prompt; if unresolved, stop. Do not read mcp.log or stores.

After T5's undo, prove HTTP still works once, then stop that exact fixture:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py control-http --root "$HOME/.cpp-pi-1899-probe"
```

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py stop-http --root "$HOME/.cpp-pi-1899-probe"
```

Require http_stopped=true, the dedicated HTTP terminal exit 0 and its recorded
PID/instance. The helper first proves the listener is the recorded live instance,
requests shutdown, then requires its stop marker and closed port. It never
signals an arbitrary PID. The endpoint is retained solely for the dead row.

Before T6:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py control-dead-stdio --root "$HOME/.cpp-pi-1899-probe"
```

EXPECTED nonzero: the known dead child exits before initialization. This is an
intentional opposite verdict, not a retryable failure. Record its actual exit.

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py set --case stdio-dead --root "$HOME/.cpp-pi-1899-probe"
```

Before T7, after T6's undo, run control-http ONCE. It must now fail against
the same stopped endpoint. Record the actual nonzero exit, then configure:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py set --case http-dead --root "$HOME/.cpp-pi-1899-probe"
```

This refuses a still-listening endpoint or a mismatched teardown marker. After
T7's pair/audit/foreign undo, run T8's two final absence sessions without another
config write. Do not restart the HTTP server. A reported healthy dead endpoint
or an actual call in a dead row stops the batch and preserves the evidence.

## 4. Fresh pinned-model sessions

Read the retained pin, never re-resolve it or read settings/models/auth files.
Each launch must print github-copilot/gpt-5.3-codex, and the footer must show
exactly gpt-5.3-codex; record "provider not displayed" per master's B2 ruling.
Missing/different model or another tool attempt stops; do not open the selector.
Keep the same model throughout both repos. Record displayed thinking separately.

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
  XDG_CACHE_HOME="$HOME/.cpp-pi-1899-probe/cache" TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" \
  pi --no-session --model "$model_pin" --no-context-files --no-skills \
  --no-extensions -e builtin:mcp --no-builtin-tools --tools 'mcp__cpp_pi1899_*'
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
  XDG_CACHE_HOME="$HOME/.cpp-pi-1899-probe/cache" TMPDIR="$HOME/.cpp-pi-1899-probe/tmp" \
  pi --no-session --model "$model_pin" --no-context-files --no-skills \
  --no-extensions -e builtin:mcp --no-builtin-tools --tools 'mcp__cpp_pi1899_*'
)
```

The explicit builtin:mcp is necessary: --no-extensions alone also disables
native MCP. --no-tools/--no-mcp are deliberately absent. The plain MCP allowlist
leaves no read/bash/edit/write, codemode, tool_search, external extensions or
foreign tools available. An unexpected tool invalidates the controlled lane.
Do not infer bearer isolation from these selection flags.

## 5. Exact prompt and independent call evidence

Use the matrix's literal tag for each launch. The following is the complete
T2-alpha example; replace ONLY its tag with the exact matrix cell for other
sessions. The helper refuses a tag belonging to another configured case.

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py prompt --tag T2-alpha --root "$HOME/.cpp-pi-1899-probe"
```

Type its prompt VALUE once in pi. It names only the expected normalized tool
and fixed row tag, never a nonce. Return the text result verbatim or
TOOL_UNAVAILABLE if no such tool is declared. Each server response generates a
fresh random 128-bit nonce after receiving the call. Loggers retain the actual
tools/call request, response-send record, connection peer, instance, PID and tag.
They record no HTTP auth headers, environment or provider conversation.

Record the actual native tool-call identifier from pi's current tool event if
exposed. The expected stdio ID is mcp__cpp_pi1899_stdio__probe_echo and HTTP ID
mcp__cpp_pi1899_http__probe_echo. The received server tool name is probe-echo.
That comparison measures both server/tool hyphen normalization. A name written
in this prompt or assistant prose alone is not a native invocation record;
an unavailable call-identifier display leaves that part unresolved.

Exit pi after its one answer; record actual process exit and loader/connection
diagnostics that were exposed. Capture only the controlled new reply. Use the
literal row tag to create its exclusive reply file; T2-alpha example:

Wait for final/settled idle, not just any token-footer change. Preserve the
controlled per-launch capture until durable record-reply, verifier outcome and
artifact hashes exist; never delete it first. Empty, stale or unfinished capture
is unexaminable, not a model response or a successful absence observation.

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py record-reply --tag T2-alpha --root "$HOME/.cpp-pi-1899-probe"
```

Paste ONLY that new controlled reply into the helper's stdin and end with EOF.
Do not supply historical session files, transcripts, login output or unrelated
screens. Existing/empty reply files stop instead of overwriting evidence.

Verify against the same row/transport; T2-alpha example:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py verify --tag T2-alpha --transport stdio --root "$HOME/.cpp-pi-1899-probe"
```

Use http for T4/T5/T7 and stdio otherwise. A verified call needs ONE matching
pi-labelled request in THIS batch/tag/transport, bound start/initialize evidence,
one matching response-send record, and its fresh nonce/tag in the reply. The
pi client label is not authenticated identity: correlation relies on the
exclusive fixture window, actual native tool event and controlled reply too.
Compatible-client records and old positive row tags cannot substitute.
The structured logs retain controlled request/response fields and version
metadata, not a byte-for-byte wire capture; omitted client metadata/headers are
not reconstructed later. Preserve original log bytes and their full digests.

Exit 0 means that bounded live call round trip was evidenced. Exit 1 means no
verified call; exit 4 means evidence is missing/unreadable/incomplete. A pi
exit 0, model statement or static current config cannot establish health.
T2/T4 must prove actual calls; failure stays unresolved rather than retried.
If either direct positive is unexaminable or fails, stop the remaining matrix
and report its paired controls. Perform only the reviewed guarded config undo
and fixture teardown when their preconditions still hold; never reset evidence.
T6/T7 MUST fail the call verdict even if pi exits 0. Empty/invalid logs are
UNKNOWN, not an absence proof. T1/T8 supply paired absence after actual positives.

Omitted exposure defaults to codemode. T3/T5 test only this deliberately
restricted direct-call lane, with indirect mechanisms unavailable. Record the
actual verdict, including an unexpected successful call; do not force the
expected answer. No call does not by itself mean an unhealthy server: working
compatible-client controls and native connection/exposure status remain separate.
Do not report direct exposure globally required for all pi MCP usage.

## 6. Final guarded undo and retained evidence

After T8, the recorded config must be foreign-only and all pi sessions exited.
All logged stdio instances need matching stop records; the HTTP instance needs
its recorded shutdown/closed-port proof and terminal exit. Then:

```bash
python3 docs/measurements/pi/issue-1899-b3-probe.py undo --root "$HOME/.cpp-pi-1899-probe"
```

This refuses changed config, non-baseline content, missing stop evidence or a
mismatched HTTP instance. On success the owned synthetic-only mcp.json is absent;
the disabled foreign sentinel was preserved through every case and is removed
only as part of its explicitly owned fixture undo. No real foreign entry is
deleted. Retain B3 logs, response files, journal, endpoint and model pin for the
final provenance manifest and B4. Whole-root cleanup remains a later master act.
If any process/state is unexaminable, stop and report rather than claiming cleanup.

Run the retained regular-agent name collector after undo. Master supplies actual
version/revision/commands/prompts/exits, controlled replies, native call labels,
raw fixture artifact identifiers/full hashes, nonce-bound request/send records,
foreign/config hashes, PID/teardown records, per-tag and aggregate ACTUAL prompt/
model-round/attempt counts (including stopped attempts), and the display/isolation lane.
Publish only reviewed sanitized derivatives, not private paths or teardown state.
No full B4 identity, receipt validity, SSE behavior, production merge behavior
or all-harness parity is claimed by these fixtures.

## Local controls before host routing

Final local verification: 42 focused cases passed (17 B3 and 25 retained B2),
lint passed, and all committed shell blocks were syntax-checked without execution.
The focused suite exercises the actual stdio/HTTP fixture processes, independent
compatible clients, live listener shutdown and dead controls, config preservation,
mode-change refusal, actual CLI calls from outside CPP, and synthetic call-log
readers. None starts pi or accesses owner paths. Pure synthetic pi-labelled
records test the reader; actual local compatible-client calls cannot count as pi.

Committed opposite inputs include a stale positive tag with simulated pi exit 0,
wrong client label, missing response-send record, empty/malformed evidence,
changed config bytes/mode and preexisting config. The dead-row refusal test ran
red with tests/fixtures/pi-mcp-blind.py (DID NOT RAISE ValueError), then green
with the real reader. The changed-mode case ran red on the initial draft before
its mode guard, then green after the guard. These new instruments have no
preexisting production implementation; the blind anchor is deliberately synthetic.
Local verification is not host acceptance. No full suite or PR CI is requested
by this draft, and fixture basetemps are removed after each run.
The reader also ran red on the initial draft with PID, instance or request-ID
bindings removed from every record; each now reports UNKNOWN instead of green.

Reproduce the blind-reader red only in synthetic local fixtures:

```bash
CPP_PI_MCP_BLIND_CONTROL=1 make test-pi-mcp-probe 'PI_MCP_PROBE_TESTS=tests/test_pi_mcp_probe.py::test_dead_server_exit_zero_cannot_reuse_old_call'
```
