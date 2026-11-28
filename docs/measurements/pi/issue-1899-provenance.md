# Pi #1899 partial B0-B3 provenance

Status: PARTIAL. B0 and B2 are attributed host completions; B3 was owner-stopped
with gaps; B4 is draft-only and NOT RUN. This inventory identifies available
inputs and reviewed exports without inventing unavailable original artifacts.
It does not certify byte equality to private captures the author never opened.

## Input and observation bindings

| Batch | Executed input and observation source | Available publication | Missing binding or limit |
|---|---|---|---|
| B0 | Reviewed command commit 6b8cf44c34eb0e6a7bd0722bc49036a2e5493e39; host checkout only abbreviated d3484def; master 42350/42358, K738 completed 13:45:02Z | [B0 results](issue-1899-b0-results.md), command-file and amended-instruction digests there | Full host revision, amended collector bytes, command timings and raw output hashes were not supplied |
| B2 | Executed b18e207812f0ab5c8b1a62d3743cbe9848b548c6 plus master 42449 model-only footer ruling; completion 42465 at 14:35:48Z | [B2 results](issue-1899-b2-results.md), exact command/helper/fixture hashes there | Raw response/capture hashes and full listing/pin digests remain unavailable; prefixes are not full bindings |
| B3 | Executed d9c511c153f91371328d5e0a51f4bfb6bf68af87 plus disclosed host capture-driver amendments | [Stopped B3 results](issue-1899-b3-results.md), original command/probe/server SHA256 values there; driver archives below | No raw server event/capture tree supplied; some relays provide prefixes only; lost and unrun rows remain gaps |
| B4 | No host execution | [Draft](issue-1899-b4-draft.md), public-source premises and proposed budget | No collector, runtime identity, actual turn/history or receipt round trip |

pi version 1.6.0 and Node 22.23.4 are host-reported. Public-package inspection
is separately bound in [the source note](issue-1899-pi-1.6.0-source.md).
Version equality is not whole-binary equality. The reused CLI pin and exact
model-only footer selection do not establish authenticated runtime identity.
B2 fixture manifest SHA256 is
60d74753706d5c0796e3a63eeecd684a46183d6b02962a913897f19a621cb61f;
its six files are exact constructed inputs, not captured host responses.

## Sanitized driver exports independently inspected

All tar digests below were recomputed by the author. Member paths/types and
bytes were examined before retention; supplied member digests were checked.
These are sanitized helper/control exports, not raw session or capture exports.
No raw credential or persisted session file was opened. Python .py.txt files
are byte copies; shell .sh.b64 files are serialized data whose strict decoding
reproduces the originals. [SHELL-STORAGE.tsv](issue-1899-b3-driver/SHELL-STORAGE.tsv)
maps previous paths and both encoded/decoded hashes. No ShellCheck exclusion or
source-byte repair is used. Original member digests below name decoded bytes.

| Original export identifier | SHA256 | Reviewed repository derivative and mapping |
|---|---|---|
| drv2.tar | 0f89803dcfb8f6a9a36f52b14a3c0c38f06350761a8dde6c464e14fa0df2d040 | [exported/SHA256SUMS](issue-1899-b3-driver/exported/SHA256SUMS); all 22 original members retained, Python as .py.txt and shell as .sh.b64 data with original decoded hashes; account paths already replaced by exporter |
| xchk.tar | 8eaccfb9cc50947767c095f9a5b4b7d2254bbfc8d87fb731379b2630b4031574 | [xcheck/SHA256SUMS](issue-1899-b3-driver/xcheck/SHA256SUMS); all 19 original members retained with the decoded-byte mapping above |
| v3.tar | f677bc68b48e4012ff82b369364e35bd1da8702f77f22f49344758c319ef7d2f | [v3/SHA256SUMS](issue-1899-b3-driver/v3/SHA256SUMS); all 24 original members retained with the decoded-byte mapping above; neutral structural controls replace displayed commentary prose |
| v4.tar | 1d439f86729c9e81259e943fc8306a47f73f50c22745c240fd145510869d46fc | [v4/SHA256SUMS](issue-1899-b3-driver/v4/SHA256SUMS); all 34 original members retained with the decoded-byte mapping above |
| v4-wrappers.tar | 54f552e964efc2f46424fef6df221b664d41de198cc90f9c259e833f7e21059c | Both supplied wrapper bytes compared equal to locally derived decoded v4 run/session originals; no duplicate archive committed |
| final.tar | f3e1dde8baae9688698acaa8dcea137d5be102aa1fede05a061b45404ef12dc2 | [source digest list](issue-1899-b3-driver/final/SOURCE-SHA256SUMS.txt); all five source member hashes verified; manifest/ledger/two wrapper files retained, shell sources use .sh.b64 data; raw cleanup deliberately omitted |

The raw final cleanup source SHA256 is
582680bbfd31d2ca3e0f71389063e28043ec314085c28512d3b7b31b5b6e3d4c.
It includes the private regular count/digest pair and incidental auth-file
modes. It is NOT committed. The results summarize only reviewed cleanup facts
and disclose the metadata-listing deviation. That narrative is not a byte-equal
copy of the raw receipt. Original digest lists identify source files, including
omitted files; they are not asserted to be complete local-directory manifests.

Operational hashes in MANIFEST.txt can differ from sanitized launch derivatives
because the exporter replaced helper paths; both roles are documented in the
[driver README](issue-1899-b3-driver/README.md). Tars themselves and original
private evidence remain host-owned, not included here. No credential-scan
zero-detection claim is made from this authoring pass.

## Derived collaborators and version boundaries

The driver README records complete SHA256 values and exact derivations for
session-v3, the historical first exact-target correction, corrected pane-target
collaborators, and run/session-v4. These are constructed script variants with
committed predecessor controls, not claimed historical host snapshots.

| Boundary | Reported application |
|---|---|
| V1 | T1; T2-alpha initially captured before native-header layout correction |
| V2 | T2-alpha final-only recovery onward; exact activation time not supplied |
| Bound xcheck v2 | Retained T2-alpha/T2-beta/T3-beta zero-model recheck; later recordable rows required AGREE alongside original verifier |
| V3 | 2026-11-27T16:28:19Z, T6; no historical default-exposure row used v3 |
| Corrected pane/session targets | 16:41:16Z; earlier session-only exact-target variants were never installed; T6-beta had launched before the hold on prefix scripts |
| V4 | 16:43:55Z; T6-beta saved-capture recovery, then T7; not the model-turn classifier for T6-beta |
| Cleanup | 16:52:41Z, guarded undo reported; owner B3 stop relayed at 17:16:57Z |

## Evidence readers and limits

Committed helper coverage: test_pi_rules_probe.py (16 cases),
test_pi_model_pin.py (9), test_pi_mcp_probe.py (17), and
test_pi_capture_driver.py (96 at v4 handoff). Tests exercise guarded mutations,
exclusive artifacts, unique model selection, real fixture transports, stale
positive refusal, process/request/nonce binding, capture/extraction, bound
count comparisons and actual private-socket tmux operations. Actual predecessor
red runs and committed opposite inputs are named in the results/driver record.
No real pi model or default tmux server is used by these focused tests.

The final row/negative wrappers are historical provenance, not approved new
gates. A dormant nocall/unknown-verifier defect is
[recorded in Nit Store](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7223818894).
A ROW OK or global zero count cannot reclassify a missing/capture-lost/provider-
blocked row as successful absence. Exact reported verifier 1 is retained where
available; no verifier outcome is invented for unrecordable rows.

This PR delivers observations and probe controls only. #1901 rules ownership,
adoption and unsupported-size policy; #1902 managed merge/native health; #1903
runtime receipts; B4 runtime identity; and final T8 native absence are separate
undelivered acceptance. #1899 and #1876 stay open.
