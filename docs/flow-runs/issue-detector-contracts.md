# Flow run record - the command-substitution class note

HISTORICAL RECORD of what was agreed BEFORE the text was written, at the base SHA
below. It does not graduate.

- Issue:             none. The wave orchestrator's brief is the contract; it
                     ruled that filing is its call and none was asked for.
- Base SHA:          658d971
- Necessity verdict: Still needed
- Approval:          granted - GO, scoped to prose
- Approver:          CPP-improvements-orch (wave claude-improvements, rev 4)
- Recorded at:       2026-09-22T16:10:00Z

## Section B evidence

- The class was found during #1206 and is not hypothetical. Measured on this
  host, both halves independently:
    `V=$(printf 'a\000b')` captures as `ab` - the NUL is stripped;
    `V=$(printf 'x\n\n\n')` captures as `x` - trailing newlines are stripped;
    bash prints `ignored null byte in input` while doing it.
- The live consequence, before #1206: `hook-mask-output.sh` declined to match
  `pass<NUL>word=VALUE` - correctly, it is not `password` - and the capture then
  reassembled it into `password=VALUE`, emitted with exit 0. The filter
  reconstructed the secret it exists to remove.
- The document already carries the two questions and the anti-control question,
  and its instance index says "Link new instances here", so both the section and
  the row have a home that predates this change.

## Section C - the approved plan

1. `docs/agents/detector-contracts.md` - one prose section, "The channel can
   rewrite the verdict": the SHAPE first, `hook-mask-output.sh` as the worked
   example, the bash warning nobody consumed, and the question a reviewer should
   ask. No code, no new gate.
2. The same file's instance index - link #1206 as a row and move the heading
   count from twenty-nine to thirty, because the index says to and because
   `test_the_index_heading_matches_its_population` pins the two together.

### What this deliberately does not do

No gate, no test, no script. The contribution is the sentence, not a patch: an
instrument that pipes a payload through command substitution is subject to a
silent rewrite, harmless in most, and in a FILTER capable of manufacturing
exactly the thing being filtered for.

### Named risks

1. A prose-only change cannot be enforced, and this document says so about
   itself elsewhere. The mitigation is that the class is now WRITTEN where a
   reviewer of the next filter will meet it, which is the same standing this
   document's other sections have.
2. Over-indexing on the instance rather than the shape would make it read as one
   script's bug. The section leads with the shape and uses the example to prove
   it, in that order.

## Correction to Section B, appended after the counter-model review

This record does not graduate, so the evidence above is left exactly as it was
when the plan was approved - including the part of it that was wrong. The
correction is appended instead, because what a plan was approved ON is the thing
a later reader is trying to recover, and silently repairing it destroys that.

**Section B's second bullet misattributes the worked example.** It says the
reconstruction was the behaviour "before #1206". Measured against the frozen
pre-#1206 anchor, that implementation emits a bare newline and exit 0 and never
reconstructs the secret: it interpolated stdin into Python SOURCE, so the JSON
NUL escape decoded before the JSON was parsed and parsing then failed. That is a
different fail-open - the one #1206 was filed about.

The reconstruction belongs to the INTERMEDIATE implementation, after the input
handling was repaired and before the output capture was removed. The chain is
real and was measured; it existed only inside the fix.

Section B's FIRST bullet - the two shell measurements - stands, now scoped to
`bash`: `zsh` can hold NULs in parameters, and the "ignored null byte in input"
warning is bash 4.4 and newer.

The approved plan is unaffected: the section still leads with the shape and uses
the example to prove it. Only the example's attribution moved, and the landed
prose now says which implementation it is measuring.
