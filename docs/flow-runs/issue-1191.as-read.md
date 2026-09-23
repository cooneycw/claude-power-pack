# Issue #1191 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1191
- Read at:      2026-09-23T13:10:28Z
- updatedAt:    2026-09-21T20:57:47Z   (context only - moves on comments and labels)
- Body digest:  10cc475fead3a77c775df5add9560af3bbd37d20a652aa83415ffcd0b8176d9a   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3380 of 3380 (cap 16384)

## Body as read
`gh-pr-merge.sh`'s close-keyword guards (lines 176-200, issues #726, #772, #794) exist so an author-time disclaimer cannot be defeated by GitHub's parser. A PR that says `Refs #N`, never `Closes`, closed its issue anyway and the guard did not fire.

## What happened

cooneycw/kyle PR #1313 used `Refs #1267`, stated so in its first line, and merged as `0376aa2`. GitHub closed #1267. The issue timeline attributes the close to the commit, not to a person.

The trigger is in the PR body, which became the squash body verbatim:

```
## What this does NOT close

#1267's remaining criteria are **observations**, and they are consolidated as ...
```

GitHub matches `close` + `#N` by proximity, **ignoring grammar and ignoring negation**. The heading ends on the word "close"; the next token in the document is `#1267`.

**The sentence whose entire purpose was to disclaim the close is what performed it.**

## Why the guard should have caught it, from its own header

Two documented branches both apply and neither matched:

- Lines 188-197 describe flagging *"when #N is immediately followed by a possessive or a slash-compound modifier"*, citing a real near-miss of exactly that shape. The referent here is `#1267's` — the possessive case, named.
- Lines 177-186 describe the negated-keyword guard, which recognises *"only an adjacent negation with at most two intervening words"*. The negation here ("does NOT close") **is** adjacent to the keyword — but the keyword and `#N` are separated by a newline, a blank line and a paragraph boundary, so a window measured in words cannot reach.

So both of the guard's own shapes are present in one construction, and the distance between keyword and referent is a *paragraph* rather than words.

## Why this placement is the highest-risk one

A markdown heading is the most likely place an author will put it, because `## What this does NOT close` is the natural way to write a section disclaiming a closure. The guard exists precisely to stop an author-time disclaimer being defeated by the parser, and **the disclaimer's most idiomatic form is the one that slips through.**

The failure is also silent at merge time: the issue closes, the PR says `Refs`, and nothing in the merge output mentions it. The worker found it only by checking the issue state afterwards, could not identify the trigger from the squash body, correctly declined to invent one, and reopened with the anomaly recorded as unknown. The cause was identified afterwards by someone holding the #726/#772 prior.

## Suggested disposition

Treat a `close|fix|resolve` keyword as in-scope for the whole of the next markdown block rather than a word window — a heading governs the paragraph beneath it, which is how a reader parses it and, empirically, how GitHub does too.

Alternatively: flag any close-keyword occurrence that is not a clause-initial `Closes #N` directive and is followed by an issue reference anywhere before the next heading.

Cheapest variant: warn whenever a close keyword appears in a markdown heading at all, since a heading is never a legitimate place for a closing directive.

## Provenance

Nit-store record: #864 comment [5765879691](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5765879691). Found by a worker in wave `kyle-improvements`; cause identified by the orchestrator. Filed at the owner's direction.

