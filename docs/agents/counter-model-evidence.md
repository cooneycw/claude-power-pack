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
Codex records that input in its own transcript inside `<stdin>` framing. A
Claude or Qwen user request may instead frame the unchanged patch as
`<cpp-review-patch>` followed by a newline, the exact bytes, then
`</cpp-review-patch>`. The closing marker immediately follows the patch's own
last byte. Retain the reviewer's runtime transcript; a patch supplied only as
a receipt-writer argument is not evidence. Unsupported or ambiguous runtime
input framing is UNKNOWN, and the write refuses.
Each runtime user message supplies at most one frame, across all its text
parts and both supported delimiter types. Competing frames in one input are
UNKNOWN. Separate inputs retain their runtime chronology; the latest captured
frame in the current review interval supplies the artifact. Findings headings
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
