# Pi #1899 measurement plan

Status: plan approved by the orchestrator on 2026-11-27; B0 subsequently
[reported complete by master](issue-1899-b0-results.md), followed by
[B2's attributed rule measurements](issue-1899-b2-results.md). B3/B4 remain PENDING.
Refs #1899 and #1876. The plan itself is not execution evidence.

## Scope and authority

Add measured pi rows to the existing
[shared contract](../../../.specify/specs/antigravity-host-update/spec.md)
and [research record](../../../.specify/specs/antigravity-host-update/research.md).
[ADR 0014](../../decisions/0014-antigravity-capability.md) remains the decision
authority. There is one discover -> refresh -> verify -> report contract.
Option B managed copies, no symlinks, ownership, installed byte/hash/mode
inspection, foreign-content preservation and CPP locking remain obligations.
File fidelity, contextual effectiveness, MCP health and runtime identity are
separate claims.

The [revision 6.1 plan](../../plans/pi-topic-skills/plan.md), #1898, #1887,
#1916 and the [Part 1 sign-off](issue-1897-owner-signoff.md) are prior sources.
The [discovery/reload observations](2026-11-25-discovery-reload.md) are attributed
fixture evidence. They do not measure global rules, MCP or runtime identity.
The #1896 built-in-tool inventory and skill-loader diagnostics remain UNKNOWN.

No adapter, rules installer, MCP merger, capability enrollment, receipt writer
or Kyle runtime implementation is in scope. Consumers are #1900 through #1903;
their implementation acceptance stays separate.

## Host boundary and sequencing

Master routes host steps behind R2 work. No pi command, including version/help,
runs in the owner's regular HOME. B0 creates one disposable HOME and explicit
PI_CODING_AGENT_DIR. Subject to owner agreement, the owner signs in there once;
B2-B4 reuse that root with fresh pi sessions per comparison. No planned batch
needs a second HOME. Stop and explain to the orchestrator if a later observation
requires one. Never change HOME inside an already running pi process.

Never read, stat or copy pi credential files, including auth.json and
mcp-auth.json. Helpers may list directory entry names without inspecting their
metadata; they must not recursively inventory the agent root. Owner login is
interactive, without recording its screen, browser traffic or authentication
output. No credentials or provider environment variables are carried into the
new process. The owner enters credentials directly through pi's login flow.

Each batch records an intervention and its scoped undo. Teardown of the whole
disposable installation follows evidence retention at the end, through master;
B0 does not remove the signed-in root. Each later batch removes its own rule or
MCP fixtures before the next baseline. Fresh HOME separates configuration, not
the filesystem, network, bearer access or container runtime.

## Measurement rows

| Batch | Status | Positive input | Opposite or unexaminable input |
|---|---|---|---|
| B0 isolation | Attributed host completion; see results | Unique marker reported only in probe; regular name summary stable | Never-created marker absent; marker absent after undo; digest reader's changed-name controls reported by master |
| B2 rules | Attributed host completion; see results | Independent global rule markers in two repositories; override selected with both present | Removal removed markers; zero-byte override suppressed base; removing it restored base |
| B2 size | Bounded samples attributed; exact cap UNKNOWN | Head/middle/tail markers reported present at 8192/32768/65536 bytes in both rule names | No loss observed at sampled positions; no above-limit pair or every-byte/full-cap claim |
| B3 stdio/HTTP | PENDING | Actual pi-originated tools/call and response retained at fixture server | Dead stdio and HTTP servers; CLI exit 0 cannot establish health |
| B3 exposure/names | PENDING | Record direct exposure and hyphenated registration's actual tool name | Omitted/alternate exposure and non-normalized candidate; observed behavior, not plan assertions |
| B3 preservation | PENDING | Synthetic foreign entry survives bounded fixture add/remove | Diff identifies any changed foreign value; this is not a delivered CPP merge test |
| B4 identity | PENDING | Non-transcript metadata binds session, turn and resolved provider/model | Spoofed user label, missing/corrupt/unreadable metadata, incomplete history all remain distinct from runtime identity |

B0 uses the [committed command handoff](issue-1899-b0-commands.md).
B2-B4 command files and fixture inputs are committed and reviewed individually
before their host execution. All batches retain exact argv, cwd, prompts, exit
codes, pi/Node versions, full CPP revision and input hashes. Two unrelated scratch
repositories live inside the disposable work area. Fresh sessions prevent prior
marker responses from contaminating removal comparisons. Neutral prompts do not
contain rule marker values or MCP response nonces.

Do not borrow AGY's size limit. Bound the size search and record only tested
sizes if no limit is found. Absence of warnings does not prove full loading.
Before interpreting a transport refusal, use a working server and a compatible
client before and after the pi attempt. Echo listeners bind loopback; retain
server request/response records and tear down exact recorded processes. Use
fresh response nonces; assistant prose and successful exits are insufficient.

B4 first examines documented RPC/hook metadata. Persisted v3 message records
and streamed message_end/agent_settled have different schemas; their names do
not authorize reading message bodies. Never open an existing transcript or dump
JSONL. Any candidate that requires transcript access stops that row, stays
UNKNOWN, and goes to the orchestrator for an authorization decision. A metadata
source alone does not establish complete history or a #1903 receipt round trip.

## Evidence and controls

Each published row names its input, paired comparison, observed outcome and
remaining limit. Retain private originals; publish only reviewed sanitized
derivatives. The provenance manifest maps original member identifier and digest
to derivative path/digest, run/version/revision, normalization and redaction.
No private host names, paths, credentials or unrelated conversation are published.
Missing originals, prompts or hashes remain unresolved rather than reconstructed.

Every new or changed load-bearing result reader must ship committed good, bad
and unexaminable inputs before anyone relies on its verdict. Assert bad-input
preconditions. Demonstrate that a blind reader fails the cases; any regression
also runs red against the actual pre-change reader. Named bad inputs include
absent marker, removed rule, truncated tail, dead server with CLI exit 0, spoofed
identity, incomplete history and empty-success/missing artifact. A sanitization
scan's zero-detection claim needs a synthetic planted-token detection control.
B0's manual marker comparisons have both committed input states in its handoff;
they establish only marker visibility, not whole-host isolation.

## Files, readers and lanes

Deliver this plan, per-batch command handoffs and fixture inputs under
docs/measurements/pi/. Results and the provenance manifest join measured pi
rows in the existing shared research/spec in one final PR. No second contract
or ADR change is planned. Implementers and ch-rev consume the actual observations;
synthetic reader fixtures remain explicitly synthetic.

| Repository lane | Planned treatment |
|---|---|
| Checkout | Author in linked worktree; host checkout revision recorded. Any Git-dependent helper must cover main and linked layouts |
| Harness | Actual isolated pi host is product evidence; native Codex authoring supplies no Claude/AGY effectiveness claim |
| Driver | No flow/delegated-driver parity claim or changed command output |
| Coordination | With-Kyle host handoff; any local reader fixtures run without host authority |
| CI provider | PR CI only after final handoff; no GitHub Actions parity claim |
| Project state | Absent and present rules/config fixtures in two unrelated scratch repositories |
| Toolchain | Record host pi/Node and local/CI Python separately; no version matrix claim |
| Clone shape | Host commands must not depend on historical objects; test shallow/full if later helpers depend on Git shape |
| Run location | Resolve CPP explicitly; run actual sessions from both external scratch repositories |
| Gate target | CPP fixtures only; no consumer interpreter/PATH claim |
| Wave role state | Unaffected; no fresh/released-role claim |

## Delivery and stop points

Use one branch, issue-1899-pi-measurements. Push committed host files without a
PR and send master through the orchestrator the full commit SHA, file SHA256
and exact short commands. One final results PR follows all batches. Master
arranges B0 and owner login; no owner questions go through the worker pane.
R2 #1927 then #1917 merge first; run the #1917 CI-shape check before review once
available. ch-rev supplies counter-model review with master's host rollout copy.

No heavy run is needed for this documentation handoff. Later heavy suites use
the coordination lock client, at least 25G free and basetemp cleanup. The finish
gate runs directly with CPP_KYLE_LOCK_BIN set to the lock client, never wrapped
and never with CPP_KYLE_FULL_SUITE_ACTIVE. No host execution or acceptance is
claimed by committing these documents.
