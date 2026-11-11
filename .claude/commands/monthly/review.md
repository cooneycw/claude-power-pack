---
description: Work through the open monthly review issue item by item and record what was done
allowed-tools: Bash(~/.claude/scripts/monthly-review.py:*), Bash(~/.claude/scripts/nit-store-resolve.sh:*), Bash(gh:*), Bash(git:*), Read
---

# Monthly: Review - Work This Month's Monitoring List

Work the open `Monthly review: YYYY-MM` issue one item at a time. Each item
ends ticked with a one-line record, or left open with the reason it is carried.

## Arguments

- `PROJECT` (optional): a directory under `~/Projects`, resolved like
  `/project:next`. Default: the current repository.

## Step 1: Find the review

```bash
~/.claude/scripts/monthly-review.py status
```

- `open #N` - read it: `gh issue view N`. An `OVERDUE` review is still the one
  to work; finish it before creating this month's.
- `none for YYYY-MM` - there is nothing to review yet. Route to
  `/monthly:create` and **STOP.**
- `done for YYYY-MM` - report it and **STOP.**
- `unknown` (exit 3) - **STOP** and report the reason.

## Step 2: Work each unticked item

Take the items in order. An item is a pointer to work, not the work itself:

| Item | What to do |
|---|---|
| Roll over the Nit Store | Follow `docs/agents/nit-store-rollover.md` in the CPP checkout. It is a large read with its own owner checkpoint; when it will not fit in this session, file or link an issue for it and record that issue as the item's outcome. |
| Standing item #N | Read issue #N and do the check it describes for this month. Record what you found as a comment on #N. Leave #N open: it is standing work. |
| Run `/self-improvement:retro` | Run it. The count is this host's log only. |
| Follow-up due DATE - #N | Do what #N asks, then close #N if it is finished. |
| UNREAD - ... | Read that source by hand, then do whatever it turns out to need. |

Ask the user before anything hard to reverse: closing a Nit Store, closing an
issue you did not open, or filing more than a handful of issues.

## Step 3: Record each outcome on the review issue

Edit the issue body so each item reads one of:

```
- [x] Standing item #871: ... - checked 2026-12-03, no change (comment link)
- [ ] Roll over the Nit Store ... - CARRIED to 2027-01: waiting on owner read of #1690
```

Fetch the body, change only the lines you worked, and write it back with
`gh issue edit N --body-file <file>`. Never tick an item you did not do, and
never delete one.

## Step 4: Close only when nothing is left open

Re-run `status`. It reports `X of Y item(s) open`.

- `0 of Y` - close the review: `gh issue close N --comment "<one-line summary>"`.
- Anything else - leave it open and report what remains. An item marked
  `CARRIED` is still unticked on purpose: before closing, copy each carried
  line into a comment so `/monthly:create` next month is not the only memory
  of it, then tick it with `carried to YYYY-MM`.

## Report

Lead with what needs the owner, then what was done per item, then the links.
