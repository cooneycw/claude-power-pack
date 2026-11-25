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

The author read the published handoff, the seven batch/preservation relays below
and ADR 0014's adoption text. The raw private artifacts were not supplied to this
checkout. The following are **attributed observations**, not newly reproduced
tests or independent live acceptance. No commands, nonces, exact versions or
per-file hashes have been reconstructed from memory or invented to fill gaps.

## Paired observations

| Batch/source | Reported positive | Reported negative/comparison | What remains unresolved here |
|---|---|---|---|
| [B0 initial pause](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7078877412) | Help/spec inspected on reported AGY 1.5.14 | No supported relocation flag found; later batches paused | Help/spec is not discovery, cap or transport behavior; this version is not automatically the version of every later batch |
| [B0 isolation](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079256159) | Reported run `batch0-20261122-0718`, CPP `40d25173`; fresh disposable home; MCP config edits confined to probe root; helper rechecked regular config unchanged | Absent markers exit 1 in both roots; absent plugin enable exit 1 | Full CPP commit, exact launch/help/marker commands, CLI version artifact and root comparisons need sanitized export; config edits are not actual MCP execution |
| [B1 discovery/lifecycle](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079330832) | Loose skill resolved across repositories; native plugin v1-to-v2 removed B and loaded changed A; installed hashes/modes matched; source moved aside; sibling skill preserved; reinstall repaired tampering | Fresh-session skill removal gave NOT_FOUND; concurrent disable lost one update in 1/10; same-plugin install last-writer-wins; list/validate missed tampering; native reinstall removed foreign internal files | Raw invocation/reference nonce, commands, membership/hash/mode records and concurrency schedule unavailable; native plugin results do not prove CPP loose-copy installer behavior |
| [B2 rules/cap](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079368856) | Global GEMINI.md, global AGENTS.md and plugin rules each loaded independent markers in fresh sessions in two repos; 23,800-byte fixture loaded completely | Removing tested location removed its marker; 26,000 bytes silently lost tail, exit 0/empty stderr; diagnostic log showed truncation; strict validation exit 1 but install accepted | Exact boundary around documented 24,000 bytes and aggregate 20,000-token behavior unmeasured; need raw byte counts/tail observations; no production target selected by this result |
| [B3 MCP](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079419121) | Stdio handshake (reported protocol 2025-11-25); HTTP via `mcp add --type http`, DELETE teardown; foreign global entry survived native plugin lifecycle | Dead stdio/HTTP and disabled/uninstalled plugin gave TOOL_UNAVAILABLE; broken -p invocation still exit 0; working SSE server got POST/405 instead of GET, compatible client succeeded before/after | Actual tool/server response nonce and call artifact absent from relay, so no independent live-call acceptance; exact commands/config/versions and compatible-client artifacts need export |
| [B4 runtime](https://github.com/cooneycw/claude-power-pack/issues/1887#issuecomment-7079661668) | Native lifecycle hooks exposed session ID, resolved modelName and turn provenance without transcript reads | Spoofed user label did not override identity; absent/unreadable identity stayed unknown; JSON/stream-json stdout lacked identity | Sanitized raw hook payloads/config, schema/version/event ordering and complete implementing-model history unavailable; no delivered adapter or receipt round trip |

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
not opened the archive or rerun that scan. Preservation is not validation.

Any later committed sanitized derivatives must have a reviewed mapping that
records: batch/run, AGY version, full CPP revision, original member identifier
without a private path, original SHA256, derivative repository path and SHA256,
redactions/normalizations, fixture inputs, exact short commands/prompts, exits,
and relevant paired observations. Preserve source-to-derivative correspondence;
label synthetic fixtures as synthetic rather than archived measurements.
Do not publish credentials, private host/session names, storage paths or
unrelated session contents. Never read transcripts to complete the mapping.

No derivative fixtures or original-to-sanitized per-member digests are included
in this draft because none have been inspected. The archive digest and public
relays are the available provenance pointers, not substitutes for those missing
artifacts. The requested helper export is an open #1887 acceptance item.

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
| Discovery, rules/cap, MCP, lifecycle/orphans, checkout independence, drift, foreign content, actual execution | Reported paired observations and exact evidence limits above; B3 live-call proof unresolved |
| Owner B/no-symlink/topic-first and partial scope | Recorded by reference to ADR; tradeoffs above |
| Canonical topics/bundles, ownership, lock, hashes and unchanged Codex | Defined in spec; implementation deferred to #1888/#1889 |
| Command-derived skills and real AGY update follow-up | Explicit in spec and #1876/#1888/#1889; undelivered |
| Revision/discovery/report/failure/adapter responsibilities; current checkout refresh | Defined in spec; implementation deferred to #1889 |
| Authoritative Tier-3 route, linked ADR, no duplicated decision authority | This directory; issue linkage at PR publication |

This draft does not yet justify closing #1887. Supply and review the sanitized
evidence, or obtain an explicit acceptance revision from the existing decision
authority; elapsed time or document completion is not that revision.
