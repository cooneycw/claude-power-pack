# AGY packaging research and evidence provenance

This accompanies [the operational contract](spec.md). Architectural decisions
and rationale remain in
[ADR 0014](../../../docs/decisions/0014-antigravity-capability.md); this file
records what the #1887 author has actually read and what is still unavailable.

## Sources and isolation

The approved [B0-B4 handoff](https://github.com/cooneycw/claude-power-pack/issues/1876#issuecomment-7078771603)
requires a disposable configuration/home established when launching a new AGY
process, two unrelated scratch repositories, no production configuration
changes, no credential copies and no transcript reads. Batch 0 must establish
isolation before later mutations. Batch 4 is limited to fixture-only,
non-transcript runtime metadata. A disposable home isolates configuration, not
the rest of the filesystem. Never repurpose HOME in a running session.

The author read the published handoff, the seven batch/preservation relays below,
ADR 0014 and the
[2026-11-25 read-only sanitized manifest](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7168427969).
The manifest's reported SHA256 is
`65aaf96e9298e9eb4a3810aa4447a2d50e9b8cb6b08f3e4cd9207568c89d3417`.
It was exported from retained evidence without running a new probe or opening
configuration, credentials or transcripts. The raw private artifacts were not
supplied to this checkout. These remain **attributed observations**, now with
the manifest's file-level provenance, not newly reproduced tests or independent
inspection of originals. Missing commands and prompts have not been invented.

The manifest records AGY 1.5.14 in every batch and CPP checkout
`40d25173c8c09987fac851cffa565efdc0f11c72` (v13.0.0). CPP was present,
not executed by the probes. B1b/B1c and B2b lack their own CPP revision fields;
do not infer additional measurements from the unchanged checkout. Run IDs are
`batch0-20261122-0718`, `batch1-20261122-0738`, `batch2-20261122-0745`,
`batch3-20261122-0749` and `batch4-20261122-0753`; some sub-batches have
timestamps only. Per-file commands/exits and the 200-row inventory (plan plus
199 evidence files) remain in the linked manifest rather than being duplicated.

## Paired observations

| Batch/source | Reported positive | Reported negative/comparison | What remains unresolved here |
|---|---|---|---|
| [B0 initial pause](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7078877412) | Help/spec inspected on AGY 1.5.14 | No supported relocation flag found; later batches paused | Help/spec is not discovery, cap or transport behavior |
| [B0 isolation](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079256159) | Fresh disposable home; probe marker present, regular marker absent; MCP config edits confined to probe root | Absent markers exit 1 in both roots; absent plugin enable exit 1 | Manifest confirms regular-config listing/sizes/mtimes stayed unchanged; that is not a content-hash comparison or actual MCP tool execution |
| [B1 discovery/lifecycle](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079330832) | Loose skill resolved in two repos; v1-to-v2 removed B and loaded changed A after source moved aside; v2 source/installed manifests match four hashes and modes; sibling sentinel unchanged; reinstall repaired tampering | Fresh removal gave NOT_FOUND; concurrent disable lost one update in 1/10 with both exits 0; same-name race had nondeterministic complete winners in 10 trials; list/validate missed tampering; foreign internal file removed | Full print-mode argv, some prompts and exact enable/disable argv missing; why the earlier concurrency experiment needed correction is unknown; native plugin results do not prove CPP loose-copy behavior |
| [B2 rules/cap](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079368856) | Global GEMINI.md, global AGENTS.md and plugin rules loaded independent markers in fresh sessions in two repos; 23,800-byte global fixture loaded head and tail | Removal removed markers; 26,000-byte global/plugin cases lost tail with exit 0/empty stderr; diagnostic logs show truncation; oversized install accepted | Strict-validation exit is inconsistent between two logs (0 vs 1); plugin-under was validated only, no runtime pair; exact boundary and aggregate 20,000-token behavior unmeasured |
| [B3 MCP](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079419121) | Manifest identifies stdio and HTTP server-side tools/call records and matching responses; foreign global entry survived native plugin lifecycle | Dead/disabled/uninstalled cases gave TOOL_UNAVAILABLE despite print-mode exit 0; live SSE control succeeded before/after while AGY POST received 405 without GET | Real call evidence is now located by file/hash/line below; fixed nonce alone is not proof; prompts/full argv and dead-server CLI diagnostic remain unresolved |
| [B4 runtime](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079661668) | Hooks exposed session/model/turn fields; manifest identifies distinct default/explicit runtime models and lifecycle events | Spoofed prompt label did not replace runtime model; invalid-model run exit 1; stream-only/corrupt-hook derived exports report unknown | Missing prompts for CLI surface tests/invalid-model run, complete history and receipt round trip unresolved; derived export is not raw payload equality |

## B3 actual calls and remaining measurement gaps

The sanitized manifest identifies these server-side artifacts (paths relative
to the original evidence batch, not this repository):

| B3 file | SHA256 | Reported proof |
|---|---|---|
| `stdio-server.calls.log` | `d6160459db7c8cb24453544bf0c981039097a2943edcf3efa2006524b275041d` | Lines 10-11: RECV tools/call with argument `ping-stdio-alpha`, followed by its SEND result |
| `http-server.calls.log` | `0ecb84933e363fdc3e43b7b2b1711f47f655e33131190cc6e38a87fcd9a1c615` | Lines 23-24: POST /mcp tools/call with `ping-http-beta`, followed by its response |
| `sse-server.calls.log` | `acddac119887f13be7b639c48cadbe10630d88793df5b39617d53cc8aa00b8cb` | Compatible-client tools/call before/after; AGY requests received 405, no AGY call |

These are helper-inspected live-call records, not merely assistant prose or
successful CLI exits. The echoed nonces are fixed constants in fixture source;
their presence alone does not establish a call or secrecy from the model. The
claim rests on the server-side request/response record. The original files
remain private and have not been independently reopened by this author. This
upgrades the earlier relay's missing-call-artifact finding to located,
digest-bound reported evidence; it does not deliver #1891 live-health checks.

The following remain **UNRESOLVED**, with no guessed completion:

- Full print-mode argv across batches; exact B1 enable/disable argv and B3 MCP
  add flags; B2's inferred logging flag. Commands measured elsewhere must not
  fill these missing historical invocations.
- B1's truncated first prompt and equality of prompts in its paired runs;
  missing B1b/B1c and B3 prompts; missing B4 CLI-surface/invalid-model prompts.
- B1's initial concurrency-run correction rationale; a 10-trial complete
  same-name result does not prove native serialization or a universal absence
  of torn writes.
- B2 strict-validation exit disagreement between `2b-validate.log` (0) and
  `2b-boundary.log` (1). A pipe/status-capture error is only a hypothesis.
  Runtime plugin-under positive pair, exact rule boundary and aggregate token
  loading remain unmeasured. Greeting prompt: "Respond with a single-line
  plain greeting saying hello."
- B3 dead-server diagnostic behavior: retained failure signal is the model's
  TOOL_UNAVAILABLE reply, not a demonstrated per-server CLI diagnostic. B3's
  original print-mode prompts are unavailable, limiting prompt-contamination
  analysis even with actual call logs.
- Archive-to-live member byte equality, missing sanitized byte-copy derivatives,
  complete hook-history retention and a real AGY receipt round trip. B4's
  missing/corrupt inputs use a derived export, not a shipped adapter.

`agy plugin uninstall --help` reportedly wrote the probe manifest and returned 0
in B0. This hazard was already recorded in the Nit Store before this change;
it is not a newly discovered finding. Later adapters must validate operands and
verify side effects, without treating help-looking arguments as read-only.

## Preserved originals and derivative policy

The [preservation receipt](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079688513)
reports a 199-file private archive with SHA256
`56e8a3b3a932dc061450a5b6f620e4d582ddf245b10cc422e8bbf295bbb2dd9c`.
The helper reported directory mode 0700, file mode 0600, a credential scan with
zero detections and a planted-token negative control detected. This author has
not opened the archive or rerun that scan. Preservation is not validation. The
new manifest reports a fresh archive-hash match and 199 names/sizes matching the
live evidence tree. Member byte equality was not checked; the separate plan is
not an archive member. This distinction explains the manifest's 200 rows.

Any later committed sanitized derivatives must have a reviewed mapping that
records: batch/run, AGY version, full CPP revision, original member identifier
without a private path, original SHA256, derivative repository path and SHA256,
redactions/normalizations, fixture inputs, exact short commands/prompts, exits,
and relevant paired observations. Preserve source-to-derivative correspondence;
label synthetic fixtures as synthetic rather than archived measurements.
Do not publish credentials, private host/session names, storage paths or
unrelated session contents. Never read transcripts to complete the mapping.

The published manifest supplies original per-file digests, not sanitized byte
copies. Its only identified derived fixture-data export is B4
`4-evidence-export.json`, SHA256
`2ab4efc1969e262f008e45d6ef6ea3f557a4d3dbd146e32706886398fada3e49`,
which summarizes specified hook/stream/corrupt-fixture inputs. That file itself
is not included here. Every other original has no sanitized-copy digest. The
manifest reports personal identifiers/internal URLs in CLI logs and absolute
paths in 68 files; review/redaction remains necessary before exporting originals.
This document is a summary of the published manifest, not a claimed byte-equal
derivative of any raw file. Its source link/digest and selected original digests
retain the provenance available now. Missing inputs remain acceptance gaps.

## Measured tradeoffs and deferred delivery

Option B is the owner-selected design, not a new inference from this table.
Native plugins reportedly supplied useful copy and source-independent lifecycle
behavior, but their integrity checks missed tampering, concurrency lost updates
and reinstall removed unexpected internal files. CPP managed copies therefore
own deterministic bundling, explicit ownership, locking and actual installed
byte/mode inspection. They incur that implementation and maintenance cost; an
advisory CPP lock cannot repair direct native writers that ignore it.

Topic-first delivery permits portable canonical guidance without prematurely
claiming command/workflow parity. The driver first reaches Claude/Codex/AGY
only. pi, Qwen and Gemma/OpenCode adapters, command-derived AGY skills, real AGY
`cpp-update` invocation and runtime-receipt parity remain named follow-ups in
#1876/#1888/#1889/#1886. No native list, successful exit, archive receipt or
topic build closes those deliveries.

## #1887 acceptance accounting

| Acceptance | Draft disposition |
|---|---|
| B0-B4 within isolation/no-transcript boundaries | Attributed completed probe reports retained above; independent artifacts unresolved |
| Discovery, rules/cap, MCP, lifecycle/orphans, checkout independence, drift, foreign content, actual execution | Manifest now locates hash-bound B3 server-call logs; paired reported observations retained; missing argv/prompts, B2 exit discrepancy and raw/sanitized byte correspondence remain unresolved |
| Owner B/no-symlink/topic-first and partial scope | Recorded by reference to ADR; tradeoffs above |
| Canonical topics/bundles, ownership, lock, hashes and unchanged Codex | Defined in spec; implementation deferred to #1888/#1889 |
| Command-derived skills and real AGY update follow-up | Explicit in spec and #1876/#1888/#1889; undelivered |
| Revision/discovery/report/failure/adapter responsibilities; current checkout refresh | Defined in spec; implementation deferred to #1889 |
| Authoritative Tier-3 route, linked ADR, no duplicated decision authority | This directory; issue linkage at PR publication |

This draft does not yet justify closing #1887. The manifest improves provenance
but leaves the gaps above. Resolve material gaps or obtain an explicit acceptance
revision from the existing decision authority; document completion is not that
revision.
