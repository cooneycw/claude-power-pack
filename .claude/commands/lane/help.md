---
description: Overview of lane file commands
---

# Lane Commands

A lane is one of the routes the same behaviour travels - main checkout or
linked worktree, dev or prod, small fixture or real-size data. A project lists
its lanes in `.claude/lanes.md`, and every plan then says which lanes it will
test and which it will not. The rule is in `docs/agents/lanes.md`.

## Commands

| Command | Purpose |
|---------|---------|
| `/lane:create` | Draft the lane file from what the repository shows; the owner reads the draft before anything is written |
| `/lane:update` | Re-check the lane file against the repository and recent fixes, and record that it was reviewed |
| `/lane:help` | This help page |

## When they run

- `/project:init` runs `/lane:create` for a new project.
- The plan step (`/flow:eli5`) reads the lane file's review date and says so
  when it is more than 60 days old, or cannot be read. That notice is advisory:
  it never stops a plan. `/lane:update` is the remedy it names.
- A project with no lane file is asked nothing.

## What the commands cannot do

They survey the repository. A lane that leaves no trace there - a setting that
exists only in production, for example - is found only by the owner reading
the draft. And a freshly reviewed list can still be incomplete: the review date
says somebody read it, not that it is right.
