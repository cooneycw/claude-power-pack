# Counter-model runtime evidence

New `ran` receipts use schema 5. Each role independently selects a runtime
evidence adapter: Codex thread or rollout, an exec stream resolving Codex,
Qwen Code or OpenCode evidence, or a Claude session transcript. The adapter
derives identities from the runtime records. A typed model name, assistant
prose, startup instruction provenance or a neighbouring session cannot supply
an identity. Runtime prefixes do not make the same model independent.

The reviewer must differ from every retained implementing model. Codex and
Claude implementing sessions retain their complete model set; an unreadable
turn is unknown, not an invitation to drop that turn. A reviewer must resolve
one unambiguous model. Model strings describe the runtime's recorded requested
model; this does not attest which model an external endpoint actually served,
or resolve aliases between different recorded names.

One thing is not an alias: a trailing context-window tag. `claude-opus-5-5[1m]`
is `claude-opus-5-5` with a larger window, so the tag (exactly `[`, digits, `k`
or `m`, `]` at the end of the name) is removed before a name is recorded or
compared. Without that, one model could review its own work under two
spellings (issue #1710).

Independence is also refused when the comparison keys differ only by one
leading `claude-`, after harness/provider and context-tag stripping (#1747).
For example, `claude/opus-5` versus `claude/claude-opus-5` may be the same
model; their equivalence is not established, so independence cannot be claimed.
The same rule applies to the Sonnet spellings and to every write-time and
validation comparison. It does not assert an alias or rewrite the recorded
names. No other prefix or fuzzy matching is applied; Opus versus Sonnet and a
different Codex model remain independent under this comparison.

The 28 short-name receipts dated 2026-09-15 through 2026-09-19 (27
`claude/opus-5`, one `claude/sonnet-5`) are caller-typed labels predating
implementer measurement. The [original writer and worked example at
ffc315ad](https://github.com/cooneycw/claude-power-pack/commit/ffc315ad)
accepted free-text `--implementer` and supplied literal `claude/opus-5`.
[727725eb](https://github.com/cooneycw/claude-power-pack/commit/727725eb)
removed that argument and derived the transcript model; [09a9d656](https://github.com/cooneycw/claude-power-pack/commit/09a9d656)
restricted the source to assistant `message.model` and recorded the first
derived long-name receipt. Those historical short labels have no retained
implementer evidence pointer and do not establish which model actually ran.
String comparison cannot turn them into measured identities.

A Codex review launched with `codex exec --ephemeral` writes no rollout, so
it cannot back a receipt: the reviewer's model is read from the rollout. When
the writer finds no rollout for a thread it says to check this first (issue
#1710).

## Bind the reviewed artifact

Commit an implementation checkpoint before requesting a receipt-bound review.
The patch producer refuses dirty work rather than silently omitting it:

```bash
python3 scripts/counter-model-receipt.py review-patch --base origin/main > /tmp/review.patch
```

For a full-scope review, the reviewer must execute exactly `git rev-parse HEAD`
as a separate runtime shell tool call before inspecting the change. Keep the
runtime tool call and successful result, not a pasted head or startup metadata.
The receipt writer compares the last successful probe between the preceding
report and the current runtime `## Findings` report to the target commit.
Each report requires fresh evidence in that interval, including a fresh input
patch for diff-only reviews. A later report cannot inherit an earlier review's
patch or HEAD probe. It checks recorded ordering, not
the point at which semantic inspection began. Retain that assistant report
alongside the input and tool evidence.

For a diff-only review, give the reviewer the exact producer output as stdin.
Codex CLI 0.164.0 can record stdin as unframed user text. The writer accepts
that Codex input only when its entire UTF-8 text equals the freshly recomputed,
nonempty canonical patch byte for byte. It does not strip text, select a
substring, or accept a prefix or superset. Empty diffs still require explicit
framing, so an empty/nontext user message cannot stand in for a captured patch.
Supported `<stdin>` framing remains valid. A Claude or Qwen user request may
instead frame the unchanged patch as
`<cpp-review-patch>` followed by a newline, the exact bytes, then
`</cpp-review-patch>`. The closing marker immediately follows the patch's own
last byte. Retain the reviewer's runtime transcript; a patch supplied only as
a receipt-writer argument is not evidence. Unsupported or ambiguous runtime
input framing is UNKNOWN, and the write refuses.
Each runtime user message supplies at most one frame, across all its text
parts and both supported delimiter types. Competing frames in one input are
UNKNOWN. Exact raw Codex captures and framed inputs retain their runtime
chronology; the latest eligible capture in the current review interval supplies
the artifact. A later wrong framed patch still refuses even when an earlier raw
input matched. Findings headings
inside backtick or tilde fences are examples, not completed reports.

At write time the helper resolves the current base ref and target commit,
computes their merge-base then recomputes the canonical binary Git diff. It
forces repository-wide paths and short submodule diffs, including gitlink
changes even when Git config would hide them. The checkpoint guard likewise
enumerates untracked files and submodule changes explicitly. It
compares exact bytes without whitespace or context normalization. A clean
update that preserves those bytes still binds; changed hunks or context need
a fresh review. The receipt records base SHA, target head, current merge-base,
patch SHA256 and the binding method. Scope `unverified` uses captured-patch
binding too; it does not acquire a full-tree claim.

**Trust boundary:** binding establishes which recorded artifact the reviewer
received or which commit its runtime probed, not how thoroughly it reviewed it.
Runtime transcripts and local Git are evidence sources, not tamper-proof
attestations. Snapshot digests identify the consumed evidence bytes; they do
not authenticate their author. `validate` checks stored receipt shape and
internal consistency without reopening host-local evidence. It does not
upgrade a historical record to an audited review.

## Pair roles independently

For example, a native Codex TUI implementation reviewed by Claude needs no
invented exec stream:

```bash
python3 scripts/counter-model-receipt.py write --issue 1584 --branch issue-1584 \
    --status ran --implementer-thread-id "$CODEX_THREAD_ID" \
    --reviewer-session-id "$REVIEWER_SESSION_ID" --review-base origin/main \
    --scope full --network unverified --local-credentials unknown
```

The reviewer in this example must have executed the HEAD probe in its own
session. Use `--scope diff-only` with captured input for a reviewer that cannot
open the repository. `--reviewer-thread-id` and `--reviewer-rollout` support
Codex reviewers without an exec stream. Each side accepts exactly one selector.
Explicit selectors resolve inherited environment ambiguity.

Codex exec reviewers retain sandbox scope remeasurement and its downgrades.
Other adapters cannot assert a Codex network or credential probe they did not
run: use `unverified` and `unknown`. Keep exec stdout as JSONL and stderr
separate; damaged or non-JSON evidence refuses attribution rather than being
silently discarded. OpenCode full-scope binding reads its completed shell tool
events; diff-only OpenCode input is not guessed from an assistant text event.

Schemas 1-4 still validate under their historical contracts, with no corpus
migration. Their absent evidence does not become verified by compatibility.
Skip receipts retain their reason contract. Enrolment still accepts reviewed
head ancestry; it does not claim that later commits were reviewed. The legacy
rollout-attribution audit examines only Codex reviewers; other schema-5
reviewers are explicitly outside that instrument's population.

## Escalated reviews: more than three passes (issue #1700)

The cap is two passes; a third is recordable with a reason. A review that
honestly needed more had no truthful receipt, so a finding accepted on the last
allowed pass left three bad choices: a false count, a false skip, or a gate left
red on purpose. By the owner's ruling of 2026-11-11 the cap stays the default,
and a named authority may raise it mid-run for that run.

- **The receipt.** `status` stays `ran`. `passes` holds the true count. An
  `escalation` object holds `ruled_by`, `reference` (where the ruling can be
  read) and `raised_cap`. `extra_passes_reason` is still required. Written with
  `--passes N --escalated-by ... --escalation-ref ... --raised-cap M
  --extra-pass-reason ...`.
- **The bounds.** `passes` may not exceed `raised_cap`, and `raised_cap` may not
  exceed `PASSES_OUTER_BOUND`, which is 10: a receipt already committed in kyle
  records 9 passes, and the bound should make every honest history
  expressible. The bound exists so that "raise the cap" cannot mean "no cap".
- **Recorded, not authenticated.** The writer requires the fields to be present
  and non-blank. It cannot check that the named authority exists or ruled. The
  reference is what lets a reader check it.
- **The gate does not read the count yet (issue #1765).** `flow-finish-gate.sh`
  prints `receipt:` for an escalated receipt and passes, as it does for any
  other `ran` receipt. Nothing on the gate's line says the review was
  escalated; read the receipt. For the same reason a HAND-MADE receipt above
  three passes with no ruling still passes the gate, though `validate` and the
  corpus check reject it.
- **Exactly three passes** keeps its earlier form: a reason and nothing more,
  and the line reads `receipt:`.
- **No new status value, deliberately.** A repository whose CI pins an OLDER
  gate reads an escalated receipt the same way (`receipt:`, passing). The
  older VALIDATOR does reject it (`passes is 5, beyond the hard ceiling of 3`),
  so a consumer that runs the corpus check must move its pin before committing
  an escalated receipt.

### Asking for a further pass, and what happens on a refusal

The first accepted fix earns one re-review. From then on, every further pass is
asked for before it is run. The approver is whoever approved the plan at Step
3: the user, or in a wave the orchestrator.

If the approver declines, the receipt is written for the LAST REVIEWED head
with its true count, and the approver chooses what happens to the fix made
after it:

1. It is backed out, and the finding goes to its own issue.
2. It stays as a commit after the receipt, and the PR names it, in words, as
   not reviewed by the second model.

A finding of medium severity or higher takes the first route unless the
approver reads the fix themselves and says so in the PR. There is never a
receipt for the unreviewed head, never a false count, and never silence.
