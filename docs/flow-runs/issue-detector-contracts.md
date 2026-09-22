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
