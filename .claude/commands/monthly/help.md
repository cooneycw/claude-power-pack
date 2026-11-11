---
description: Overview of monthly review commands
---

# Monthly Review Commands

Standing work that never finishes - emptying the Nit Store, the `evergreen`
issues, the friction retro, follow-ups that come due - gets one dated issue a
month, so it is visible, ranked and closable like any other work.

## Commands

| Command | Purpose |
|---------|---------|
| `/monthly:create` | Scan the repository and write this month's monitoring list as a `Monthly review: YYYY-MM` issue |
| `/monthly:review` | Work the open review item by item and record what was done |
| `/monthly:help` | This help page |

## How it is triggered

`/project:next` reports the review's state on every run: open (with its age and
how many items remain), done, or none for this month with the
`/monthly:create` route. Nothing runs on a timer. `/project:init` creates a new
project's first review.

## What the scan reads

- The open Nit Store: how many findings it holds and how old it is.
- Every open issue labelled `evergreen`. The label still means "never offer
  this as the next thing to start"; the monthly review is what visits it.
- The friction log on this host.
- Open issues labelled `follow-up` with a `Due: YYYY-MM-DD` line.

A source that cannot be read is listed as unread. It is never left out and
never reported as nothing due.

## The Nit Store is not the review

The Nit Store is the inbox findings go into all month. The monthly review is
the list that says, among other things, to empty it.
