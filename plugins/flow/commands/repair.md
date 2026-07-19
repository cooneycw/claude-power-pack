---
description: Install the flow helper family into ~/.claude/scripts/ (fixes exit-127 on marketplace-only installs)
allowed-tools: Bash(~/.claude/scripts/flow-helpers-install.sh:*), Bash(scripts/flow-helpers-install.sh:*), Bash(test:*), Bash(ls:*), Bash(jq:*), Read
---

# Flow: Repair - Install the Helper Family

Put the flow helper scripts at the stable `~/.claude/scripts/` path the flow
commands invoke and the permission allowlist matches.

## Why this exists (issue #590)

The flow commands are only half the product: Step 1 of `/flow:start` and
`/flow:auto` runs `~/.claude/scripts/flow-start-resolve.sh`, `/flow:merge` runs
`gh-pr-merge.sh`, and so on. Historically only the repo-local `/cpp:init` /
`/cpp:update` installer put those there, so a user who installed flow from the
marketplace (`/plugin install flow@cpp` - the canonical path since ADR 0001
Phase B5) hit exit 127 with no clone to fall back to.

The plugin now bundles the helper family (`${CLAUDE_PLUGIN_ROOT}/scripts/`,
the same delivery mechanism the secrets plugin uses for its masking hook). This
command copies or links them to `~/.claude/scripts/`. That stable path matters:
the #581 allowlist rules in `templates/claude-settings-permissions.json` match
`Bash(~/.claude/scripts/flow-start-resolve.sh:*)` and friends, and a versioned
plugin-cache path would never match them - running the helpers in place would
trade exit-127 breakage for a permission prompt on every call.

Run this once after installing the plugin. It is idempotent - re-run it any
time, and after a plugin upgrade.

## Instructions

When the user invokes `/flow:repair`, resolve the installer through this chain
and run the FIRST one that exists. Invoke it bare, with no arguments (the #581
invocation discipline: a compound invocation defeats the allowlist prefix rule).

**1. Already installed** - the normal case for a repeat run:

```bash
~/.claude/scripts/flow-helpers-install.sh
```

**2. Plugin bundle** (exit 127 above - a marketplace-only install). The plugin
root is only defined when this command runs from an installed plugin:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/flow-helpers-install.sh
```

**3. CPP checkout** (exit 127 above - running from the repo itself, where
`CLAUDE_PLUGIN_ROOT` is unset):

```bash
scripts/flow-helpers-install.sh
```

If all three exit 127, neither a plugin nor a checkout is present: report that
flow is not installed from a source that carries the helpers, and point at
`/plugin install flow@cpp`.

The installer prints one line per helper and a verdict:

- `FLOW_HELPERS: installed` - helpers were placed (or refreshed). Report which.
- `FLOW_HELPERS: ok` - everything was already current; nothing changed.
- `FLOW_HELPERS: error` - report the message and stop.

It picks its own delivery: **symlink** when the source is a CPP checkout, so the
helpers follow `git pull` exactly as `/cpp:init` Tier 2 does; **copy** when the
source is a plugin bundle, because plugin cache paths are version-stamped and a
symlink into one dangles at the next upgrade.

### Then: check the allowlist

Installing the helpers fixes exit 127. The zero-prompt lane additionally needs
the flow allowlist merged into `~/.claude/settings.json`. Report its state:

```bash
jq '.permissions.allow | map(select(startswith("Bash(~/.claude/scripts/"))) | length' ~/.claude/settings.json
```

If the count is 0 (or the file is missing), tell the user the helpers will now
run but will prompt on each call, and that `/cpp:init` / `/cpp:update` merges the
rules - or they can copy them from
`templates/claude-settings-permissions.json` (bundled documentation:
`templates/claude-settings-permissions.md`).

## Report

```
Flow Repair

  Source:    plugin bundle (/home/user/.claude/plugins/cache/cpp/flow/1.0.0) | CPP checkout (~/Projects/claude-power-pack)
  Delivery:  copy | symlink
  Installed: 9 helpers to ~/.claude/scripts/ | already current
  Allowlist: 6 rules present | not merged (flow will prompt on each helper call)

  Verify with /flow:doctor.
```

## Notes

- Read-only alternative: `/flow:doctor` reports the same helper state without
  changing anything (it calls `flow-helpers-install.sh --check`).
- This is the only flow command that writes outside the repo. It touches exactly
  `~/.claude/scripts/`, and only the helper family listed in the installer.
- Clone users do not need this - `/cpp:init` Tier 2 and `/cpp:update` Step 5b
  already link every `scripts/*.sh`. Running it anyway is harmless and idempotent.
