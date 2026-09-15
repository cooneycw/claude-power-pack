# Counter-model review fixtures (issue #934)

**These are RECORDED transcripts from a real reviewer, not hand-written
imitations.** `defect-present` and `defect-removed` are the same nine-line file
reviewed twice by `codex exec` (gpt-5.5) on 2026-09-15 - once with a seeded
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

All three contain zero finding headings, which is byte-identical - to anything
counting headings - to a review that found nothing wrong. They are the reason
`parse_review` has three outcomes instead of two.
