# Pi #1899 B0 attributed host observations

Historical batch receipt; see the [partial provenance](issue-1899-provenance.md)
and [owner-stopped B3 results](issue-1899-b3-results.md) for current status.

Status: B0 reported complete by master on 2026-11-27. B2-B4 remain PENDING.
Refs #1899 and #1876. This author received the host relay, not the original
execution artifacts, and did not independently run pi or inspect credentials.

## Provenance

The owner authorized B0 through master. Host job K738 finished at 13:45:02Z.
Master's completion relay is mailbox message 42358; amended-collector provenance
and controls are in message 42350. These identify attributed reports rather than
independently inspected raw artifacts. Exact per-command timestamps, wrapper
bytes and original output-file digests were not supplied in the completion relay.

| Input | Binding supplied by master |
|---|---|
| Reviewed command commit | 6b8cf44c34eb0e6a7bd0722bc49036a2e5493e39 |
| [B0 command file](issue-1899-b0-commands.md) SHA256 | d1a489e798e0d461edf6e0ae28266603586747b8133f0aa69e9c75a43f80b1a5; reported matching |
| Master's amended instruction SHA256 | e0320528ccd222ac40e44533e545aa947f5dc33f374840a0c8e6c6716b112737 |
| Host CPP checkout | d3484def, abbreviated revision as relayed; distinct from the command-document commit |
| pi version | 1.6.0, version command exit 0 |
| Node version | v22.23.4 |

Block 2 was amended before execution: the regular agent's name list was
represented only by its count and digest; probe entry names remained visible.
The digest is the first 16 hex characters of SHA256 over UTF-8 sorted os.listdir
names joined with a newline, without a trailing newline. Missing directories
report null. No entry stat or content inspection is part of that algorithm.
The original command-file digest does not identify the amended collector;
retain both input bindings above. This author has not opened the amended file.

## Reported observations and intervention undo

Intervention pi-1899-B0 created one disposable HOME/agent and two scratch
repositories. All later comparisons will reuse that root with fresh pi sessions.

| Step | Master-reported result |
|---|---|
| Setup (block 1) | Exit 0 |
| Isolated version (block 3) | Exit 0; pi 1.6.0 |
| Owner login | Owner reported YES; pi exit 0 from a wrapper exit file; no login capture |
| Marker undo (block 5) | unlink exit 0 |
| Regular agent at observation points a/b/c/d | Name summary stable at all four points; both fixture markers absent |
| Probe at a/b | Isolation marker present; never-created marker absent |
| Probe at c | Isolation marker still present after pi initialization and login; never-created marker absent |
| Probe at d | Isolation marker absent after undo; never-created marker absent |

The probe gained pi's standard store entries during initialization. Their
contents were not supplied or inspected by this author. The disposable root
and owner login are retained for B2-B4; marker undo is not whole-root cleanup.
Final cleanup remains an owner/master action after evidence retention.

Per master's publication boundary, the regular count/digest pairing is private
and is deliberately omitted here. Its reported equality supports stable observed
name population at the four sampling points. It does not prove unchanged file
bytes, no transient writes, credential isolation, or a filesystem/network boundary.
The owner's login report does not establish a resolved runtime model identity.

## Opposite cases and their attribution

The actual host marker was observed present before scoped removal and absent
afterward. The never-created comparison remained absent. An absence-only reader
could not produce the reported positive marker observation.

Master separately ran the amended digest logic in its own scratch directory:

| Synthetic input | Reported count | Reported digest prefix |
|---|---|---|
| Names a and b | 2 | 7e18f737311b2dc3 |
| Add a synthetic name | 3 | 75bafb0e272a2d3c |
| Remove that name | 2 | 7e18f737311b2dc3 |
| Rename b to c | 2 | 9e58d7137c654f52 |
| Missing directory | null | null |

These controls demonstrate the master-reported logic can distinguish added,
removed and same-count renamed names, rather than returning a constant summary.
The exact added synthetic filename was not supplied; its digest is an attributed
observation, not a reproducible input specification here. No real-agent mutation
was part of those controls. This author did not rerun master's controls.

The original committed name collector was locally exercised before handoff in
a synthetic temporary HOME: marker present before unlink, absent afterward,
never-created marker absent, regular fixture names unchanged. That local check
did not exercise master's amended collector and does not replace its provenance.

## Disposition

The host relay supports proceeding from B0 to a separately reviewed B2 handoff
under the approved plan. It supplies no B2 rules/cap, B3 MCP or B4 runtime-identity
measurement. The [B2 draft](issue-1899-b2-commands.md) remains explicitly unready
for host execution until its exact mutations and size fixtures are finalized.
Original artifact bindings still need to join the final provenance manifest;
this summary is not a byte-equal derivative of an inspected host log.
