---
description: Draft a project's lane file from what the repository shows, and write it once the owner has read it
allowed-tools: Bash(~/.claude/scripts/lane-file.py:*), Bash(git:*), Bash(ls:*), Read, Grep, Glob, Write
---

# Lane: Create - Draft the Project's Lane File

A lane is one of the routes the same behaviour travels: main checkout or linked
worktree, dev or prod, small fixture or real-size data. A project lists its
lanes in `.claude/lanes.md` so a plan has to say which ones it tested. The
format and the rule are in
[the lanes reference](../../../docs/agents/lanes.md) (`docs/agents/lanes.md`).

Only `.claude/lanes.md` is read; lane lists kept at other paths are not read.

This command drafts that file. It never writes a lane the owner has not seen.

## Arguments

- `PROJECT` (optional): a directory under `~/Projects`, resolved like
  `/project:next`. Default: the current repository.

**Resolve the target once and use it for every step.** With a PROJECT, every
helper call below takes the same `--root <path>`, and every read and write is
in that directory - never the directory the session happens to be in.

## Step 1: Check there is nothing to overwrite

Run the helper bare (with `--root <path>` for a PROJECT):

```bash
~/.claude/scripts/lane-file.py age
```

Act on the `LANE_FILE_AGE:` line:

- `absent` - continue.
- `fresh` or `stale` - a lane file exists. Do not overwrite it: report it and
  route to `/lane:update`. **STOP.**
- `unknown` - something is in the lane file's place and cannot be read. Report
  the reason and **STOP**; the owner decides what to do with it.

On exit 127 use `scripts/lane-file.py` from the CPP checkout and tell the user
to run `/cpp:update`.

## Step 2: Survey the repository

Survey the repository using this checklist; record what you found and where.

| Kind of lane | Evidence to look for |
|---|---|
| Checkout | worktree use in scripts or docs; per-checkout files that are git-ignored |
| Environment | deploy config, environment files or names (dev, staging, prod), feature flags that differ by environment |
| Placement | Dockerfiles, compose files, container entry points beside host scripts |
| CI provider | `.woodpecker.yml`, `.github/workflows/`, other pipeline files |
| Harness or driver | more than one agent or model the project runs under; generated copies of commands |
| Install target | more than one way the project is installed or packaged |
| Version or generation | migrations, upgrade paths, long-running sessions or data created by an older build |
| Client | supported widths, browsers or devices; more than one user persona or role |
| Data size | fixtures much smaller than real use; documented size or message limits |

A kind with no evidence gets no row. A project with one route everywhere gets a
one-row file, not a skipped step.

## Step 3: Show the draft before writing

Draft the file in the reference's format: one row per lane, with `Values`
naming the routes and `How it is exercised` saying how the project tests the
lane, or that it has no way to today. Under the draft, list for each row the
file or line it came from - every row cites its evidence.

**Show the draft and the evidence to the owner before writing anything.** Then
say plainly what a survey cannot find: a lane that leaves no trace in the
repository, such as a setting that exists only in production. Ask the owner
what is missing, and what is wrong.

## Step 4: Write and stamp

Write `.claude/lanes.md` with only the rows the owner accepted, then record the
review date:

```bash
~/.claude/scripts/lane-file.py stamp
```

With a PROJECT, the stamp takes the same `--root <path>` as Step 1.
`LANE_FILE_STAMP: stamped <date>` is success. On `refused`, report the reason;
do not edit the date by hand around it. Leave the file uncommitted for the
owner unless they ask for a commit.
