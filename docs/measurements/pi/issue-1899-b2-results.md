# Pi #1899 B2 attributed rule-loading observations

Status: B2 reported complete by master on 2026-11-27; B3/B4 remain PENDING.
Refs #1899 and #1876. Source: master's mailbox message 42465, relaying the
host helper's completion for K751 job B / K753 item 1 at 14:35:48Z. This author
did not run pi or independently inspect the original response artifacts.

## Provenance and accepted comparison lane

The reported executed source is the reviewed commit
b18e207812f0ab5c8b1a62d3743cbe9848b548c6, plus master's scoped footer ruling
in message 42449. Later documentation commits are not host execution evidence.
Original preparation and T1's mutation were already applied at e424a796;
the [zero-turn pause](issue-1899-b2-pause.md) and
[exact model selection](issue-1899-b2-model-selection.md) retain that history.
K749/0edf44ca was held before any step and supplies no execution evidence.

| Executed input | SHA256, reported matching by master |
|---|---|
| Command document at b18e2078 | 4d5925d8e05ec8922a8964bb6184c6b451e2a3411ecd57aca0489dd398a40d72 |
| Rule helper with read-only check-t1 | 07aed1fd8cfdb3090217549e2aebad3cdd7fe910cae7a436b3e2b8b9b601c9cb |
| Pause evidence document | 4f83cdbfc34ba2ec74d3b4380573de4c6cc36141106e5e46949d20c23c3be3df |
| Offline model helper | d6b7f2fe7f633252d711162670f55dfb8b17cc9176ab553e7776288ff4981890 |

The [fixture manifest](issue-1899-b2-fixtures/manifest.json), bound during the
preceding handoff, has SHA256
60d74753706d5c0796e3a63eeecd684a46183d6b02962a913897f19a621cb61f.
The helper identifies six exact fixture inputs; each transition runs in two
unrelated scratch repositories. Host pi remains 1.6.0; no update is part of B2.

Every launch reportedly printed the same CLI pin,
github-copilot/gpt-5.3-codex, and displayed the model footer gpt-5.3-codex with
medium thinking. EVERY launch records "provider not displayed". Master accepted
the exact model-only footer given the unique provider-qualified offline listing
and --model pin. This supports consistent observed selection configuration,
not independent runtime provider/model identity. The unique listing was not
re-resolved during the matrix. Only listing/pin hash prefixes were supplied
(8ab5b84a and 49e4d255); full artifact digests remain pending.

The original no-prompt startup and footer-display stop consumed ZERO turns.
The resumed matrix used exactly 32/32 model turns, no retries and no further
STOP. check-t1 exited 0 with stable/rules {}. Master reports every pi exit and
every set command exit 0, no loader diagnostic, and no tool call. These are
reported observations, not an independently audited exhaustiveness claim.
No diagnostic alone is used as proof of loading. The identical neutral prompt
was defined in the executed handoff and contained no fixture tokens:
"Respond with a single-line plain greeting saying hello."

## Marker presence, removal and override comparisons

The following response text is quoted from master's relay. No unreported output
or punctuation is reconstructed. Each alpha/beta comparison used a fresh pi
process in the same disposable HOME, with tools/MCP/extensions/skills disabled.

| Transition | Rule input | Alpha response | Beta response |
|---|---|---|---|
| T1 | Both absent | Hello! | Hello! |
| T2 | Base alone | Hello PI1899BASE7KQ | Hello PI1899BASE7KQ |
| T3 | Base removed | hello | Hello! |
| T4 | Override alone | Hello PI1899OVERRIDE9VX | Hello, PI1899OVERRIDE9VX |
| T5 | Override removed | Hello! | Hello! |
| T6 | Both present | Hello PI1899OVERRIDE9VX | Hello. PI1899OVERRIDE9VX |
| T7 | Base plus zero-byte override | Hello! | Hello! |
| T8 | Override removed, base retained | Hello PI1899BASE7KQ | Reported same as alpha |
| T9 | Both absent | Hello! | Hello! |
| T16 | Final undo, both absent | Hello! | Hello! |

These pairs support user-global discovery of each tested rule filename across
both repositories. T6 retained only the override marker, with no base marker.
T7 suppressed the base marker while the existing override was zero bytes;
T8 restored the base marker after removing only that override. T2/T3 and T4/T5
show that the marker reader first observed presence and then absence, rather
than reporting absence for every input. This measures the tested rule-loading
behavior; it is not a delivered CPP rules installer or adoption/ownership test.

## Exact bounded size samples

Only the three token-presence results, not full size-case response lines, were
provided in the relay. For decimal N, tokens are exactly PI1899SNHEAD,
PI1899SNMIDDLE and PI1899SNTAIL with N substituted. Their exact fixture positions,
bytes and hashes are committed beside the manifest.

| Transition | Filename under test | Exact bytes | Alpha | Beta |
|---|---|---:|---|---|
| T10 | AGENTS.md | 8192 | All three tokens reported present | All three tokens reported present |
| T11 | AGENTS.md | 32768 | All three present | All three present |
| T12 | AGENTS.md | 65536 | All three present | All three present |
| T13 | AGENTS.override.md | 8192 | All three present | All three present |
| T14 | AGENTS.override.md | 32768 | All three present | All three present |
| T15 | AGENTS.override.md | 65536 | All three present | All three present |

The sampled head/middle/tail instructions remained behaviorally visible through
65,536 bytes in BOTH filenames. This does not prove every intervening byte was
read or retained, an exact per-file size ceiling, unlimited loading, aggregate
token capacity, or truncation behavior beyond these samples. There is no tested
above-limit failure pair because no boundary was established. The prior source
inspection's absence of a stated numeric cap does not resolve those limits.

## Undo, isolation scope and disclosed deviation

T16 set absent exited 0; master reports the journal stable/rules {} and both
probe rule paths absent. The final two fresh responses contain no rule marker.
The regular agent's digest-only name summary was stable at all FIVE reported
sampling points. Private counts/digest pairings are omitted. Stable sampled
names do not establish unchanged bytes, absence of transient writes or a full
filesystem/network/credential boundary.

The disposable root, journal and model pin remain for B3/B4 and evidence
retention. Undo removed B2's rules, not pi's own initialized state or owner
login. Whole-root cleanup remains a later owner/master action.

The pre-hold helper's direct read of the PROBE settings.json, limited to
model/provider/thinking keys with reported projection {}, remains an explicit
deviation from the UI/CLI-only model-observation instruction. Master reports
that no auth or session file was touched. This author did not independently
audit the access. See the pause evidence; the completed matrix does not erase
that deviation or authorize further settings/store/transcript inspection.

## Remaining acceptance and evidence limits

B3 MCP transport/health/preservation and B4 non-transcript runtime identity are
unmeasured here. The Part 1 #1896 built-in-tool inventory and skill-loader
diagnostic UNKNOWNs remain separate; this TUI report does not retroactively
resolve those RPC-interface measurements. The exact rule-size cap and aggregate
loading budget remain unknown. No implementation issue or #1899 is closed.

The final provenance manifest still needs original response/diagnostic artifact
identifiers and full hashes, full listing/pin hashes, command-specific timing
and exits where retained, and reviewed source-to-sanitized-derivative mappings.
This note faithfully summarizes the master's relay and commits the available
paired observations; it is not a byte-equal derivative of an inspected host log.
