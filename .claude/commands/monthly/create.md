---
description: Scan the repository and write this month's monitoring list as a monthly review issue
allowed-tools: Bash(~/.claude/scripts/monthly-review.py:*), Bash(~/.claude/scripts/review-yield-report.py:*), Bash(gh:*), Bash(git:*), Read
---

# Monthly: Create - Write This Month's Monitoring List

Write standing work as one issue titled `Monthly review: YYYY-MM`, labelled `monthly-review`.
`/project:next` triggers this when a month lacks a review; there is no scheduler.

## Arguments

- `PROJECT` (optional): directory under `~/Projects`; defaults to this repository.

## Step 1: See what exists

Run the helper bare, from the repository (pass `--root <path>` for a PROJECT):

```bash
~/.claude/scripts/monthly-review.py status
```

Act on the `MONTHLY_REVIEW:` line:

- `open #N` - a review is already open, this month's or an overdue one. Do not
  create another: report it and route to `/monthly:review`. **STOP.**
- `done for YYYY-MM` - this month is finished. Report it and **STOP.**
- `none for YYYY-MM` - continue.
- `unknown` (exit 3) - GitHub could not be read. **STOP** and report the
  reason. Unknown is not none: creating now could make a second review.

On exit 127 use `scripts/monthly-review.py` from the CPP checkout and tell the
user to run `/cpp:update`.

## Step 2: Show the list before writing it

```bash
~/.claude/scripts/monthly-review.py create --dry-run
```

Also show the previous calendar month's review yield and fix provenance:

```bash
~/.claude/scripts/review-yield-report.py --since YYYY-MM-01 --until YYYY-MM-DD
```

The report reads kind-field shape through its sibling
`scripts/counter-model-receipt.py`; keep both helpers together.

Use that month's first and last dates. On exit 127 use the CPP checkout copy.
Keep UNKNOWN visible; this observation never blocks creation.
Answers come from the [canonical contract](../../../docs/agents/closing-report-contract.md).

Show the dry-run title, body and three groups:

- **Checklist** - what the scan found due: the Nit Store rollover, each open
  `evergreen` issue, command documents over their word budget, friction signals waiting for a retro on this host, and
  each `follow-up` issue whose `Due: YYYY-MM-DD` falls in or before the month.
- **Could not be read** - a source the scan could not examine. It is written
  into the issue as an item to resolve by hand. Never drop one, and never
  describe one as clear.
- **Read, nothing due** - what was examined and needs nothing.

An empty checklist is ordinary.

## Step 3: Create it

```bash
~/.claude/scripts/monthly-review.py create
```

- `MONTHLY_REVIEW_CREATE: created <url>` - report the URL.
- `MONTHLY_REVIEW_CREATE: exists #N` - someone created it between Steps 1 and
  3. Nothing was written; report #N.
- `MONTHLY_REVIEW_CREATE: refused` (exit 3) - nothing was established. Report
  the reason. If it says the issue could not be created, check for a
  half-created issue before retrying.

The helper re-reads state and creates a missing `monthly-review` label.

## Declaring a dated follow-up

To make something appear in a future month's list, open an issue labelled
`follow-up` (and `not-startable`, so `/project:next` does not offer it early)
with a line `Due: YYYY-MM-DD` in its body. A `follow-up` issue with no readable
date is listed under "Could not be read", because nothing says when it is owed.

## Report

End with the review's URL and the count of due, unread and clear lines, then
route to `/monthly:review`.
