# Pi #1899 B2 exact model selection and footer ruling

Status: exact pin resolved per master; the subsequent
[B2 matrix results](issue-1899-b2-results.md) are now recorded separately.
Refs #1899. Source: master's mailbox message 42449 on 2026-11-27. This author
received the relay, did not run pi, and has not inspected the original listing
or pin artifact. All host observations below remain attributed.

## Executed source and zero-turn observations

The actual resume route was K751 job B at
b18e207812f0ab5c8b1a62d3743cbe9848b548c6. The earlier K749 route at 0edf44ca
was held by K750 before any step and supplies no execution evidence, per
master's correction in message 42430. Original preparation and T1's mutation
remain bound to e424a796 as recorded in the [pause evidence](issue-1899-b2-pause.md).

Master reported exactly one matching offline provider/id:
github-copilot/gpt-5.3-codex. Only abbreviated SHA256 prefixes were relayed:
listing 8ab5b84a and pin file 49e4d255. Full artifact digests remain pending
for the final provenance manifest; these prefixes are not full hash bindings.
No direct store inspection is substituted for the CLI listing.

At T1 alpha the launch printed Pinned model: github-copilot/gpt-5.3-codex.
Pi's footer displayed gpt-5.3-codex with medium thinking, without a provider,
even after the terminal was widened to 400 columns. The original handoff
stopped on that insufficient provider display before a prompt. Master reports
ZERO model turns used at that stop. The model selector was not opened.

## Master's scoped ruling

Master accepted the model-only footer when it shows exactly gpt-5.3-codex,
given the unique offline listing and matching provider-qualified --model pin.
Each launch must record "provider not displayed". A different or missing model
footer still stops the batch. The model selector is not opened. The batch
resumes from T1 alpha through K753; the total maximum stays 32 model turns with
no retries. No preparation or completed rule mutation is repeated.

This is a scoped amendment to the original handoff's provider-display STOP.
It does not make an absent provider field visible. The exact CLI/listing pin
is configuration evidence; the footer is a model-label observation. Neither
independently establishes resolved runtime provider/model identity or turn
provenance for B4. Thinking is recorded as displayed, without an inferred
runtime identity. Missing or unsupported evidence remains unknown in its
proper scope.

The [current command document](issue-1899-b2-commands.md) preserves the ruling
for review. That later documentation amendment must not be presented as the
commit executed by K751/K753. Final results must bind b18e2078 plus master's
explicit scoped ruling and actual run artifacts. No worker-side pi invocation
or independent verification is claimed by this note.
