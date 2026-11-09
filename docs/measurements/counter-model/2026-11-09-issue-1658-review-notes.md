# Issue 1658 review evidence disclosure

Three initial review attempts used `--ephemeral`. Their JSONL/final outputs are
retained under `/workspace/.work/cs-w3/1658-review{,-v2,-v3}.*` as unverified
model provenance. They are not included in the derived receipt's pass count.
The receipt writer rejected them:

```text
COUNTER_MODEL_EVIDENCE: UNKNOWN - expected one Codex rollout for '01a1bd96-f74a-7083-a179-8b8b96042415', found 0
```

Owner mailbox 19750 authorized one additional persisted diff-only run. It is
thread `01a1bd9a-5b5c-70c1-8b9c-df778a844c0e`, reviewing
`bd16cf38302c2b7eb91311befc5bb1fd95ac8dd9`. Its one P2 finding concerned
acknowledging an existing receipt after failed directory synchronization.
The repair is `4a9e7f1729bc1cc283f912e22a6320430b027020`; it receives owner
exact-head review, not another model review. No fifth pass occurred.

The report initially lacked the reader's required Findings heading. Owner
mailbox 19765 accepted a formatting-only continuation in the same thread,
provided it added, removed or changed no finding. Comparison confirms the same
P2, trigger, consequence, remedy and red-first case. No new review or tool
execution was requested. The instruction text is quoted verbatim:

> Formatting-only continuation of the same persisted review. Do not conduct another review, do not inspect the changed checkout, and do not use tools. Restate ONLY the one P2 finding you already issued, under the required exact heading "## Findings". Include the same scope (diff-only bd16cf38302c2b7eb91311befc5bb1fd95ac8dd9), consequence and proposed red-first case; do not add or remove findings. The exact already-reviewed patch bytes are repeated below solely with the receipt reader's transport framing; the author has verified they are byte-identical to the original input. This is not the later fix and is not a fifth review pass.

That instruction is followed by `<cpp-review-patch>` framing around the exact
already-reviewed canonical patch, ending with `</cpp-review-patch>`. The full
verbatim prompt is retained at
`/workspace/.work/cs-w3/1658-review-v4-format-prompt.txt`. Its SHA256 is
`c800eab86634792a5d781aa45b39e24c3903fd7cec707ae6f02597745add4b58`. Its patch payload was
byte-compared with the original pass-4 input before the continuation and is
reproducible using:

```bash
python3 scripts/counter-model-receipt.py review-patch --base 3223421a47e401285eaaba60843f8ba53b90708e --head bd16cf38302c2b7eb91311befc5bb1fd95ac8dd9
```

Owner mailbox 19763 defines `passes: 1` here as the one provenance-verified
run; it does not erase the three earlier attempts. The receipt's counts and
red-case count cover only that verified run's one finding. The previous
unverified attempts proposed four other findings that were repaired earlier;
those are disclosed in the PR body but are not certified by this receipt.
The gate's three-pass ceiling was not changed or bypassed.
