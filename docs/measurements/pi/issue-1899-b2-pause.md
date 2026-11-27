# Pi #1899 B2 zero-turn pause and disclosed deviation

Status: B2 paused before its first model turn. Master-reported evidence, not
independently inspected host artifacts. Refs #1899. Source: master's mailbox
message 42399 (2026-11-27), followed by orchestrator message 42401 approving
resumption at the retained T1 state. K745 is the reported pre-hold receipt;
K744 was the original B2 routing. No turn is claimed for either label here.

## Input bindings and observed state

| Input or step | Master-reported observation |
|---|---|
| B2 command commit | e424a7962c6e8285e207f562fdbf7d212f05125a |
| Command-file SHA256 | 88396520f7d2fe80e690d3e5a1032c9fa2f8471732071d9a9f872564e9d7ec56 |
| Rule-helper SHA256 | 58d7679193e980b4cf08c18e1dff320fb924548ca76d4c1c112ef8a90a140220, matching |
| Fixture-manifest SHA256 | 60d74753706d5c0796e3a63eeecd684a46183d6b02962a913897f19a621cb61f |
| Regular-agent name summary before B2 | Stable; private count/digest pairing omitted |
| Preparation | Exit 0; ancestor preflight CLEAN; journal stable/rules {} |
| Transition 1 set absent | Exit 0; both rule paths absent |
| First alpha startup | No prompt sent; Ctrl+D exit 0 |
| Model turns consumed | ZERO |

No rules marker, precedence or size outcome was measured. The retained root
is already prepared at T1. The amended handoff must skip prepare and T1's
mutation, verify the retained state read-only, then perform the pinned-model
baseline turns. A different/blocked state stops for master review. The maximum
remains 32 model turns with no retries; this startup consumed none.

## Model labels and version

The helper reported that the B2 startup footer displayed claude-haiku-4.5 with
a truncated thinking label. It also relayed a B0-end footer label of
gpt-5.3-codex with minimal thinking. These are screen-label observations
supplied after the original B0 completion relay; they are not independent
runtime-model evidence or an explanation of why the selection differed.

The default selection therefore cannot be assumed constant for the B2 matrix.
The owner ruled to pin codex 5.3. The
[amended handoff](issue-1899-b2-commands.md) resolves exactly one provider/id
through the isolated offline CLI listing and passes that same pin to every
launch. An on-screen mismatch stops before any prompt. The informal owner
name and prior footer are not substituted for exact ID resolution.

Pi displayed an update-available notice for 1.6.1. Remain on the measured
1.6.0; no update command or package change is authorized by this measurement.

## Disclosed helper deviation

Master disclosed that, while checking the selection, the helper read the
PROBE agent/settings.json and printed only its model/provider/thinking keys.
The reported projection was {}: those keys were absent. This was an inspection
of the disposable probe, not the owner's regular HOME. Master reports that no
authentication or session file was touched. This author did not inspect that
settings file or independently audit the helper's access.

This is a deviation from the B2 instruction to take model selection only from
pi's UI/CLI and not directly inspect settings/model stores. It is retained as
part of the evidence, not concealed by the later pin amendment. The empty
projection does not identify the model, explain the default-selection change,
or authorize further store inspection. B4's runtime-identity boundary remains
separate, and transcript access is still unauthorized.

The resumed handoff adds no settings read and does not repeat this inspection.
Original per-step artifact hashes and exact timestamps still need to join the
final provenance manifest. This note is a sanitized summary of the master's
relay, not a byte-equal derivative of an inspected host log.
