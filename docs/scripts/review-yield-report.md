# review-yield-report.py

An informational report reached from `/monthly:create` (#1865). It never
allows or refuses monthly creation. No GitHub writes are performed.

```bash
python3 scripts/review-yield-report.py --since 2026-11-11 --until 2026-11-20
python3 scripts/review-yield-report.py --since 2026-11-11 --until 2026-11-20 \
  --fixture tests/fixtures/review-yield-report/provenance.json
```

Dates are inclusive. Live mode defaults to cooneycw/kyle, cooneycw/skillc and
cooneycw/claude-power-pack; repeat `--repo owner/name` to choose others. GitHub
CLI authentication is required only for live mode. Output is Markdown, with
source failures labelled UNKNOWN. Even an unreadable source exits zero: this
is an observation, never a gate. Invalid CLI arguments exit 2.

Merged `fix(scope):` and `fix(scope)!:` pull requests are listed. The report
follows GitHub's closing-issue references, including references across repos,
and reads the issue body and all comments for exact `Origin:` and
`Missed because:` lines. Missing links, missing lines, unrecognised answers
and conflicting answers are visible. It reads the answer lists from the marked
sections in [the canonical contract](../agents/closing-report-contract.md).
Missing sections produce UNKNOWN, never empty tallies.

An earlier-work observation requires a delivering issue/PR origin and a
missed-test answer other than the contract's new-requirement answer. It is
what the fixing session recorded, not independent proof that review caused or
could have prevented the defect. Missing provenance is not an escaped defect
count. Tallies count linked issue records, so a PR closing multiple issues
can contribute multiple records and two fixes closing the same issue can
repeat an observation. The report does not deduplicate underlying defects.

Review yield reads the JSON receipt blobs from one pinned main commit per
repository. It uses `recorded_at` dates and the latest cumulative receipt per
issue within the period, summing accepted/rejected/deferred counts and showing
passes per issue. Older snapshots and skipped receipts are counted separately.
Receipts from outside the period do not contribute yield. These are review
recording dates, not merge dates; the two populations are deliberately shown
separately. Historical schema shapes are read without claiming fresh validation
or authenticated identities. The report does not reinterpret accepted
limitations or infer optional finding kinds.

PR and receipt readable/total denominators expose incomplete observations.
A failed listing has an unknown denominator; partial individual reads retain
readable observations with UNKNOWN. Search truncation beyond 1,000 merged PRs,
GitHub rate limits, malformed records, truncated trees and missing receipt
adoption produce UNKNOWN. Narrow the period when the search bound is reached.
A readable empty PR listing says there were no merged fix PRs; an unreadable
listing cannot say that. Receipt source absence is UNKNOWN, not zero yield.

Fixture input is an object with `repos` mapping repository names to `prs`,
`receipts` and `errors`. Null sources are unreadable; empty lists are readable
empty sources. PRs carry `number`, `title`, `merged_at` and `issues`; issues
carry `repo`, `number`, `body` and string `comments`. Receipt objects retain
committed fields (`issue`, `status`, `recorded_at`, `counts`, `passes`).
Fixture mode never invokes GitHub. `make review-yield-test` exercises the
committed missing/present negative pair and the unreadable case.

The instrument census's existing reporter exclusion applies: this report
provides observations for a human, not a decision that lets work through.
No registered gate control is added. The issue nevertheless requires the
committed fixture control pair above, which stays in the test suite.
