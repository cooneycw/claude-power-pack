---
description: Re-check a project's lane file against the repository and record that it was reviewed
allowed-tools: Bash(~/.claude/scripts/lane-file.py:*), Bash(gh:*), Bash(git:*), Bash(ls:*), Read, Grep, Glob, Edit
---

# Lane: Update - Review the Project's Lane File

A lane list goes out of date when the product gains a route nobody added to it,
and a stale list still produces a plan table that looks complete. This command
re-reads the repository against `.claude/lanes.md`, proposes changes, writes
only what the owner accepts, and records the review date. The rule is in
[the lanes reference](../../../docs/agents/lanes.md) (`docs/agents/lanes.md`).

## Arguments

- `PROJECT` (optional): a directory under `~/Projects`, resolved like
  `/project:next`. Default: the current repository.

**Resolve the target once and use it for every step.** With a PROJECT, every
helper call below takes the same `--root <path>`, the `gh` query runs against
that project's repository (`--repo`, read from its `origin`), and every read
and edit is in that directory - never the directory the session happens to be
in. Reviewing one project and stamping another records a review nobody did.

## Step 1: Read the file's state

Run the helper bare (with `--root <path>` for a PROJECT):

```bash
~/.claude/scripts/lane-file.py age
```

- `absent` - there is nothing to update. Route to `/lane:create`. **STOP.**
- `fresh`, `stale` - continue, and note the `LANE_FILE_REVIEWED:` date.
- `unknown` - continue if the file can be read and only its date is missing or
  wrong; this review will set it. `LANE_FILE_REVIEWED:` is then `-`: there is
  no last review to search from (Step 3 says what to do). If the file itself cannot be read, report the
  reason and **STOP**.

On exit 127 use `scripts/lane-file.py` from the CPP checkout and tell the user
to run `/cpp:update`.

## Step 2: Re-survey

Work through the same checklist `/lane:create` uses (its Step 2 table), reading
the repository as it is now. Then sort what you found into three lists, and for
every entry cite the evidence - the file or line it rests on:

1. **Missing** - lanes the repository shows that the file does not list.
2. **Evidence gone** - rows whose evidence is no longer in the repository.
   Propose removal; do not remove a row merely because you could not find it.
3. **Unchanged** - rows that still hold.

## Step 3: Read recent fixes for lanes nobody listed

A miss that turned out to be an unlisted lane is how the list grows. List the
fix issues closed since the last review date:

```bash
gh issue list --state closed --search "closed:>=<LANE_FILE_REVIEWED date> fix in:title" --limit 50 --json number,title,closedAt
```

**With no usable review date** (`LANE_FILE_REVIEWED: -`), search the last 90
days instead, and tell the owner that this period was chosen because the file
was undated - older fixes were not read.

**A full page is a truncated list.** If the query returns exactly as many
issues as its `--limit`, more were closed than it showed. Do not stamp over
that: re-run with a higher `--limit`, or split the period into shorter windows,
until a query returns fewer than its limit. If you cannot, tell the owner which
period went unread, and leave the review date where it was.

Scan the titles for work that failed in one route and worked in another, and
offer each as a candidate lane. If `gh` cannot be read, say so: the list was
not examined, which is not the same as no candidates.

## Step 4: Show, then write only what the owner accepts

Show the three lists and the candidates. Say what a survey cannot find: a lane
that leaves no trace in the repository. Edit `.claude/lanes.md` with only what
the owner accepts.

## Step 5: Stamp the review - even when nothing changed

```bash
~/.claude/scripts/lane-file.py stamp
```

With a PROJECT, the stamp takes the same `--root <path>` as Step 1. A review that changes no row is still a review, and the date records that a
person read the whole list today. On `refused`, report the reason; do not edit
the date by hand around it. Leave the file uncommitted for the owner unless
they ask for a commit.
