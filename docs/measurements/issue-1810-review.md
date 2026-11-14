# Issue 1810 review record

Implementation checkpoint: `1bd18ba5da603daaf9e9e9dfc52c7002b351a68a`.
Dependency: normal merge of #1809 at `6cd64ec7410bb0f86df92162907043df7c05924b`;
#1810 gates wait for #1809 to merge. Closes #1810; #1811 remains open.

| Pass | Reviewed head | Scope | Result and disposition |
| --- | --- | --- | --- |
| 1 | `8a874166a8ab6739d7099939b68a83d8f05cf0a6` | Full, base `65921ba3` | Four P1 accepted and fixed. |
| 2 | `a9dfa9464c73f59ca5df2607be41cdbd3e7c64d6` | Full, base `65921ba3` | Two P1 accepted and fixed under owner-ruled closed grammar A-G. |
| 3 | `b1cce978b9919783f5a111bd905cd3662fd9175f` | Full, base `65921ba3` | P1 alias-fallback substitution masking and P2 globbed probe operands accepted; fixed at `1bd18ba5`. |
| 4 | `1bd18ba5da603daaf9e9e9dfc52c7002b351a68a` | Fix delta only, base `b1cce978` | New P2 fail-closed quoting rejection; master ruled ship unchanged and defer. |

The pass-4 P2 is recorded once in the [Nit Store comment](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-6871320513).
It produces UNKNOWN for two valid nested-quoting inputs. It cannot let a hidden
helper through; no current command document contains such a line. Pass 4 requested
changes; this record does not relabel the reviewer verdict as approval.

cr-orch relayed master approval for pass 4 in mailbox 25904, raising the cap to
four, reason: "pass 3 found alias-fallback substitution masking and glob test
operands". Mailbox 25909 relayed master's ship/defer ruling. No fifth pass ran.
Cumulative findings: eight accepted/fixed, none rejected, one deferred with the
Nit Store link above. The accepted findings have eleven concrete red-first test
variants (five from pass 1, four from pass 2, two from pass 3); none was already
covered before its fix. Pass 4 adds two deferred reproduction inputs.

## Receipt boundary and framing refusal

The [unmodified writer's receipt](counter-model/2026-11-14T035818Z-issue-1810.json)
records pass 3 truthfully: three passes, full scope, exact runtime-observed
`b1cce978` head, base `65921ba3`, and eight accepted findings. It is evidence that
the review ran, not a claim of a clean verdict. It does not claim to bind pass 4
or to review the later fix delta in full scope.

A write attempt for pass 4 with `--scope diff-only`, base `b1cce978`, head
`1bd18ba5`, passes 4 and the escalation was refused: "captured reviewer patch
differs from the target head's current merge-base diff; re-review the exact
patch". The prompt generator accidentally put one extra newline after the
canonical patch, before the closing frame. An audit of the original persisted
reviewer input proves the captured frame is exactly canonical bytes plus one
trailing newline; diff content is unchanged.

- Canonical patch: 8848 bytes, SHA256 `b046b0d11770744babcf376d825a6016cf6a6b2cc349baea31cbf1edb7039697`.
- Captured frame: 8849 bytes, SHA256 `cd11fa1ccba5f2cd12ef3d7cf3c9006d81e02efeb23853015394c24ec49aec0a`.
- Pass-4 reviewer thread: `01a1d831-433f-7cc0-81e3-51149fbf65e5`.

The writer has no flag to use runtime-HEAD binding while retaining diff-only
scope: runtime-HEAD is selected only by full scope. Per cr-orch ruling in mailbox
25911, the pass-3 receipt is therefore retained and this refusal documented;
the coordinator is taking the limitation to master. No receipt JSON, runtime
input, captured patch, or checker was edited to bypass refusal. No review was
re-framed or re-run. Raw runtime evidence and receipt-bound byte prefixes are
preserved under `/workspace/.work/receipts/1810/review/`, with the archival hash
manifest in `runtime-evidence/manifest.json`.

## Pass-4 report

## Findings

1. **P2 - Valid non-helper substitutions can now block the gate** at [scripts/check-driver-parity.py](/workspace/.work/cpp-1810/scripts/check-driver-parity.py:271). The new fallback parsing sends every original line containing `||` through `shlex.split`, including `||` inside a command substitution. `shlex` does not parse nested shell quoting correctly.

   Owned reproduction: put either line in an Instructions bash fence:

   ```bash
   echo "scripts/probe.sh $(printf '%s' '||"')"
   /d/scripts/probe.sh "$(printf '%s' '||"')"
   ```

   `bash -n` accepts both. On `b1cce978`, the first is classified as non-executing output and the second inventories `probe.sh`. At `1bd18ba5`, both produce `UNKNOWN: No closing quotation`. This breaks the stated compatibility for pure quoted output and non-helper substitutions in ordinary helper-call arguments.

**Verdict: Changes requested.**

## Verification limits

The final implementation has 201 focused tests passing, live 23-item/69-pair
parity green, strict controls distinguishing 14 BAD/11 UNKNOWN/7 GOOD, and
lint/type checks passing. Both pass-3 exact reproductions failed on `b1cce978`
before their fix. The controls include unsupported cases that deliberately
return UNKNOWN rather than mislabeling UNKNOWN as BAD detection. The fixed-list
anchor remains blind, explicitly declared for UNKNOWN cases. Earlier full
wiring/fixture/document checks also passed; no full finish gate has run.

The gate establishes static helper/plan-record-verb membership, not argument
correctness, phase/order, live execution, or semantic equivalence. The deferred
case limits supported input grammar and remains visible in the Nit Store.
