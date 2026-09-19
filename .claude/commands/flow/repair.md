---
description: Install the flow helper family into ~/.claude/scripts/
allowed-tools: Bash(~/.claude/scripts/flow-helpers-install.sh:*), Bash(scripts/flow-helpers-install.sh:*), Bash(test:*), Bash(ls:*), Bash(jq:*), Read
---

# Flow: Repair - Install the Helper Family

Put the flow helper scripts at the stable `~/.claude/scripts/` path the flow
commands invoke and the permission allowlist matches.

## Why this exists (issue #590)

The flow commands are only half the product: Step 1 of `/flow:start` and
`/flow:auto` runs `~/.claude/scripts/flow-start-resolve.sh`, `/flow:merge` runs
`gh-pr-merge.sh`, and so on. Historically only the repo-local `/cpp:init` /
`/cpp:update` installer put those there. The retired marketplace lane could
leave commands without those host helpers, producing exit 127 (#590, #662).

The verify gate also arms the shared-stash guard, `scripts/stash-worktree-guard.sh`
(issue #1056), which the resolver calls as a sibling - so that script is bundled
alongside it here. Without the bundle the resolver finds no helper, reports
`STASH_GUARD=unknown`, and the advertised default protection is simply absent
(counter-model finding). It is advisory and fail-open, and it honours a
repository's recorded `cpp.stashGuard=false` opt-out.


Legacy caches may still bundle the helper family at
`${CLAUDE_PLUGIN_ROOT}/scripts/` until they are uninstalled. This command copies
or links helpers to `~/.claude/scripts/`. That stable path matters:
the #581 allowlist rules in `templates/claude-settings-permissions.json` match
`Bash(~/.claude/scripts/flow-start-resolve.sh:*)` and friends, and a versioned
plugin-cache path would never match them - running the helpers in place would
trade exit-127 breakage for a permission prompt on every call.

Run this after cloning CPP. It is idempotent and remains able to repair a legacy
cache while the #662 migration is in progress.

## Instructions

When the user invokes `/flow:repair`, resolve the installer through this chain
and run the FIRST one that exists. Invoke it bare, with no arguments (the #581
invocation discipline: a compound invocation defeats the allowlist prefix rule).

**A REPAIR MUST NOT PREFER THE ARTIFACT IT REPAIRS (issue #927).** The order
below puts a SOURCE OF TRUTH first and the installed copy last. It used to be
the reverse, and a stale installed installer then repaired from its own stale
allowlist: measured at 22 entries against main's 24, it installed 22 helpers,
reported `FLOW_HELPERS: installed`, and never CONSIDERED the two helpers whose
absence was the reason to run the repair. A name absent from the allowlist is
not reported missing, because the installer iterates that allowlist.

**1. CPP checkout** - a source of truth, preferred. `scripts/...` is
CWD-RELATIVE, so it only resolves when `/flow:repair` is invoked from inside the
CPP checkout itself. Run from any other repository it misses, the chain falls
through to the installed copy, and mechanism B recurs - the stale installer
finds the checkout by its own upstream search and then processes it with its own
shortened allowlist. So try the known locations too, first one that exists:

```bash
scripts/flow-helpers-install.sh
```

```bash
~/Projects/claude-power-pack/scripts/flow-helpers-install.sh
```

```bash
/opt/claude-power-pack/scripts/flow-helpers-install.sh
```

```bash
~/.claude-power-pack/scripts/flow-helpers-install.sh
```

These are the same locations the installer's own upstream search uses, so
a host where the installer can find a checkout is a host where this chain can
too. Running the CHECKOUT's installer is the point: it is the one whose
allowlist is current.

**2. Retired plugin cache** (exit 127 above). This compatibility fallback stays
until #663 migrates hosts; the plugin root exists only for a cached command:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/flow-helpers-install.sh
```

**3. Already installed** (exit 127 above) - the only path left when no source of
truth is reachable, which is the normal case inside a session container:

```bash
~/.claude/scripts/flow-helpers-install.sh
```

**Reordering helps only where a source of truth EXISTS, and that is worth
stating rather than implying.** On a host whose installed copy is a SYMLINK into
the checkout, entry 3 was already current and this changes nothing. Inside a
container, no checkout is reachable and this also changes nothing - entry 3 is
still the only one that resolves. The case it fixes is a host carrying a stale
COPY, which this fleet has recorded before. The container case is covered by the
verdict instead, below.

If all three exit 127, no CPP checkout or usable legacy cache is present. Report
that a CPP checkout is required; the canonical symlink surface returns in #663.

The installer prints one line per helper and a verdict:

- `FLOW_HELPERS: installed` - helpers were placed (or refreshed). Report which.
- `FLOW_HELPERS: ok` - a comparison happened and everything was already current.
- `FLOW_HELPERS: unverifiable` - **the helpers are installed and NOTHING WAS
  COMPARED** (issue #927). No source of truth was reachable, so this run cannot
  tell a current install from one several versions behind. It is not a lesser
  `ok`: `ok` asserts a comparison happened, `unverifiable` asserts one did not.
  **`/flow:repair` cannot fix this state** - there is nothing to repair FROM.
  Report it as unverified, and say that a CPP checkout must be brought within
  reach before any verdict about currency is possible.
- `FLOW_HELPERS: error` - report the message and stop.

Every verdict is now preceded by its own provenance, so a verdict can be read
against what produced it (issue #927, the #952 denominator convention applied
to this script):

```
FLOW_HELPERS_INSTALLER:   which installer actually ran
FLOW_HELPERS_ALLOWLIST:   how many helper names it knows about
FLOW_HELPERS_SOURCE_KIND: checkout | plugin
FLOW_HELPERS_SOURCE_DIR:  what it compared against
```

`FLOW_HELPERS: ok` from a 22-entry allowlist and the same line from a 24-entry
one were indistinguishable before this. Report the allowlist length whenever you
report the verdict.

It picks its own delivery: **symlink** when the source is a CPP checkout, so the
helpers follow `git pull`; **copy** for a legacy plugin cache, because a symlink
into a version-stamped cache can dangle when that cache is uninstalled.

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

  Source:    retired plugin cache (/home/user/.claude/plugins/cache/cpp/flow/1.0.0) | CPP checkout (~/Projects/claude-power-pack)
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
  already link every executable helper in `scripts/` (issue #669). Running it
  anyway is harmless and idempotent.
