# Counter-model review fixtures (issue #934)

**These are RECORDED transcripts from a real reviewer, not hand-written
imitations.** `defect-present` and `defect-removed` are the same nine-line file
reviewed twice by `codex exec` on 2026-09-15 (first recorded as gpt-5.5; the run is attributed to gpt-6-astra by `docs/measurements/counter-model-reviewer-attribution.md`, #1272) - once with a seeded
defect and once without. The reviewer named the exact seeded bug in the first
and returned the prescribed clean statement in the second. That pair is
acceptance item 1 of #934: a stage wedged at "findings" and a stage wedged at
"clean" each pass one half of it, and only the pair separates them.

`real-multi-finding.review.md` is the genuine first-pass review of PR #1000
(issue #936), kept because it exercises several severities and a much longer
body than a constructed sample would.

**Why recorded and not live.** Neither `codex` nor `git` is in the CI image
(`CI_IMAGE_BINARIES` in `scripts/check-test-binary-guards.py`), a live call
costs the user's quota, and the reviewer is not deterministic across runs. What
CI can and does check is the STAGE's handling of a reviewer's output; the
reviewer's own judgement is exercised here once, recorded, and re-read. That
limit is real and is stated in ADR 0007 rather than implied.

The degenerate three are the cases that must NOT read as clean:

| fixture | what it is | required verdict |
|---|---|---|
| `absent.review.md` | the reviewer produced nothing | `unparseable` |
| `truncated.review.md` | cut off mid-finding | `unparseable` |
| `prose-only.review.md` | replied, but not in the contract's shape | `unparseable` |

`bullet-shape.review.md` is the fourth outcome (issue #1259): a review that
HAPPENED, with real severity-bearing findings, written as `- **MEDIUM - file:line**`
bullets instead of `### [SEVERITY] title` headings. Required verdict:
`format-mismatch` - never `unparseable`, which step 1c records as a skip.
**It is RECONSTRUCTED, not recorded:** the #1056 transcripts were not kept, so it
restates that run's four findings in the bullet shape the Nit Store report
(#864, comment 5741945325) quoted. It pins the SHAPE, not a reviewer's judgement.

All three contain zero finding headings, which is byte-identical - to anything
counting headings - to a review that found nothing wrong. They are the reason
`parse_review` has three outcomes instead of two.

`codex-unframed-user.constructed.json` is constructed from the #1600 measured
shape, not a captured runtime record. The issue's native Codex CLI 0.164.0
reproducer measured one raw input_text part: 71,153 bytes, SHA256
`cdd5ce4e8e05457e6edbcf57b5f4daa22b4c22e6b284ebb7761e343c55869c5e`.
The fixture substitutes an owned test repository's canonical patch. It pins
whole-input matching, strict negative cases and input chronology; it does not
claim that the constructed session is a live review.


`native-codex-head.json` is a sanitized actual Codex CLI 0.164.0 native event,
captured during #1584 through `functions.exec` calling `tools.exec_command`.
Its command, argv, successful exit code, output, event envelope and parsed
command are preserved. Timestamp was removed; command id, process id, cwd and
duration were normalized. It is execution-format evidence, not a review.
Source thread: `01a17ccf-39dc-7a52-b013-482c0a8cbc5c`, record line 12687;
original record SHA256:
`1c800ddd7d017a57f7cac13998f9c115eb7429f163059f4ce201c3942f3944a7`.
A bounded prefix of that own rollout (32991633 bytes, SHA256
`f9db7dca77df14c9a6223d55afdec52af5e22b48780e5a287cd46040578d2454`)
contained 1190 CommandExecution events and 1159 custom `exec` calls, including
two successful exact HEAD probes. The retained shell event is already supported;
this observation does not establish every installed runtime's serialization.

The paired controls require extraction of the captured successful result and
refusal when its exit is failed, missing or textual. The writer integration
adapts only the captured output SHA to an owned temporary Git repository,
combines it with explicitly synthetic identity/model/report evidence, and
requires successful write versus refusal on an exit-code mutation. No textual
shell-result parser or wrapper-JavaScript parser was added on speculation.
