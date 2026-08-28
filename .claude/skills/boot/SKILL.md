---
name: Boot
description: Menu-driven session identity registration for Kyle-compatible local-network discovery
trigger: boot, register, identity, session type, kyle
metadata:
  provenance:
    class: cpp-authored
---

<!--
Coexistence: Kyle ships its own /boot skill in its project directory
(.claude/skills/boot/SKILL.md within the kyle repo).  Kyle-spawned sessions
work inside the Kyle project context, so they use Kyle's project-scoped boot
(substrate briefing, token consumption, RC gating).  This CPP version is
installed globally and handles standalone sessions that want to be
discoverable by Kyle's local-network scanner without being spawned by the
substrate.
-->

# /boot - Session Registration

Register this session with a Kyle-compatible identity by renaming its tmux
session to `<prefix><group>-<role>-<name>`.  Kyle's local-network scanner
discovers sessions matching this pattern via `tmux list-sessions` (local and
over SSH on enrolled VMs).

## Step 1: Check prerequisites

Run:

```bash
tmux display-message -p '#S' 2>/dev/null || echo 'NO_TMUX'
```

If the output is `NO_TMUX` or the command fails, tell the user:

> `/boot` requires a tmux session.  Start Claude Code inside tmux to register.

Stop here.

Record the current tmux session name as `original_tmux`.

## Step 2: Check for Kyle substrate environment

Run:

```bash
env | grep '^KYLE_' | sort
```

If `KYLE_SESSION_ID`, `KYLE_BOOT_TOKEN`, and `KYLE_SUBSTRATE` are all set,
this session was spawned by the Kyle substrate.  Tell the user:

> This session was spawned by the Kyle substrate (KYLE_* env vars detected).
> Use the project-scoped `/boot` from the Kyle repo for substrate briefing.

Stop here.  Do not interfere with substrate-managed sessions.

## Step 3: Check for existing registration

If `original_tmux` already matches the Kyle prefix pattern
(`kyle-<something>` or `kyle-dev-<something>`), the session is already
registered.  Show:

> Already registered as: `<original_tmux>`

Ask whether to re-register or keep current identity.  If keep, stop here.

## Step 4: Load boot types

Read the configuration:

```bash
cat ~/.claude/boot-types.yml 2>/dev/null
```

If the file does not exist, tell the user:

> No boot types configured.  Create `~/.claude/boot-types.yml` with your
> available groups, roles, and names.  A template is at
> `claude-power-pack/templates/boot-types.yml`.

Stop here.

Parse the YAML.  Extract:
- `prefix` (default: `kyle-`)
- `groups` (list of `{slug, label}`)
- `roles` (list of `{slug, label}`)
- `names` (list of strings)

## Step 5: Present registration menu

Use `AskUserQuestion` to present the identity choices from the config.
Build the questions from the parsed lists:

1. **Group** (header: `Group`) - Show up to 4 groups.  Use `slug` as the
   option label and `label` as the description.  The user can type a custom
   group via "Other."  Warn if someone enters `core` - Kyle's scanner
   excludes `core-` sessions from external discovery.

2. **Role** (header: `Role`) - Show the roles from the config.  Never offer
   `master` even if it appears in the config - it is reserved for the Kyle
   singleton.  The user can type a custom role via "Other."

3. **Name** (header: `Name`) - Show up to 4 suggested names.  The user can
   type a custom name via "Other."

Present all three questions in a single `AskUserQuestion` call.

## Step 6: Build and apply identity

Slugify each selected value: lowercase, replace non-alphanumeric with
hyphens, collapse consecutive hyphens, strip leading/trailing hyphens.

Build the tmux session name:

```
<prefix><group>-<role>-<name>
```

Rename the tmux session:

```bash
tmux rename-session '<new-name>'
```

Verify the rename succeeded:

```bash
tmux display-message -p '#S'
```

If the rename failed (name collision, invalid characters), report the error
and stop.

## Step 7: Report

Reply with exactly one line:

```
BOOTED name=<name> role=<role> group=<group> tmux=<new-tmux-name> rc=off status=registered
```

`rc` is always `off` for CPP-registered sessions.  Remote Control is managed
by the Kyle substrate for substrate-spawned sessions only.

Do not do anything else after reporting the BOOTED line.
