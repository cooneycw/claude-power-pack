# ADR 0005: Retire plugin-marketplace distribution

- Status: Accepted
- Date: 2026-08-11
- Deciders: cooneycw (owner)
- Issue: #662
- Supersedes: ADR 0001 (Phase B distribution decision)
- Related: #663 (restore the tiered `/cpp:init` + `/cpp:update` symlink command surface), #622 (`install-drift.sh` detection)

## TL;DR

Retire CPP's plugin-marketplace distribution lane. Delete its marketplace
manifest, all 15 per-family plugin trees, and the plugin parity generator. The
tiered `/cpp:init` + `/cpp:update` symlink install returns as CPP's canonical
command surface through issue #663. Existing plugin installs migrate by running
`/plugin uninstall <family>@cpp` for each installed CPP family before the
restored symlink tier replaces them.

This decision applies only to CPP's own marketplace. Claude Code's native
`/plugin` surface and third-party marketplaces remain valid distribution paths
for third-party content such as `eli5-gate`.

## Context

### Empirical record

The issue #662 investigation opened with the executed CPP command surface 34
commits and 48 command files behind its checkout. `/plugin update` was run
twice. Both runs reported CPP as "already at latest (1.1.0)" and refreshed the
marketplace clone to the current repository state, but left the command cache
that Claude Code actually executed at its 2026-07-18 snapshot. A direct
`/plugin install <family>@cpp` then refused because the family was "already
installed" and changed nothing.

The resulting cache was not merely old in the abstract: the 2026-08-11
inspection found 24 of 98 command files stale and `flow/wave.md` absent. The
only working reconciliation was to uninstall and reinstall every affected
family individually - 12 or more interactive uninstall/reinstall sequences on
the observed host.

### Structural cause

This was not a faulty update invocation. CPP's marketplace plugin entries
carried no `version` field. The per-plugin package manifests carried a 1.1.0
stamp, but that stamp did not move as command files changed on every merge.
`/plugin update` compares version stamps, not the content behind them. It could
therefore update the marketplace clone and still correctly conclude that an
installed 1.1.0 cache was already the latest 1.1.0 cache.

`scripts/install-drift.sh`, added by issue #622, could report the gap between
the checkout and the executed cache. It could not reconcile it. No bulk or
content-aware reconciliation half exists in the marketplace model; only the
per-family interactive uninstall/reinstall path refreshes these snapshots.

## Decision

CPP retires the marketplace lane as a command-distribution path:

- `.claude-plugin/marketplace.json` and its directory are removed;
- all 15 `plugins/<family>/` trees are removed; and
- `scripts/plugin-sync.sh` and its command-parity tests are removed.

The source remains `.claude/commands/<family>/*.md`. Issue #663 restores the
tiered `/cpp:init` + `/cpp:update` symlink install as the canonical Claude Code
command surface. A symlinked `.claude/commands` tree follows the clone's
`git pull` atomically, so a clone-carrying host cannot split into a current
checkout and an older executed command snapshot.

### Why removal, not repair

The lighter repair considered was to make `plugin-sync.sh --write` bump a
per-plugin version whenever that plugin's content changed. That would give
`/plugin update` a moving stamp, but it would add release bookkeeping to every
command change and preserve two generated command surfaces plus their parity
gate.

CPP's fleet always carries the repository clone: the live installation was
already hybrid because helper scripts and infrastructure came from the clone
while command markdown came from plugin caches. The marketplace model's one
distinct advantage - a clone-less install - was unused. On these hosts the
symlink design is both smaller and structurally correct: the checkout and the
executed commands move together, with no version protocol to maintain and no
reconciliation operation to forget.

## Migration

Existing installations may retain marketplace metadata and versioned caches
after this repository stops publishing plugins. For each of the 15 CPP
families, run:

```text
/plugin uninstall <family>@cpp
```

The families are `browser`, `cicd`, `claude-md`, `codex`, `cpp`,
`documentation`, `evaluate`, `flow`, `github`, `project`, `qa`,
`second-opinion`, `secrets`, `security`, and `self-improvement`. Until issue
#663 lands, `scripts/install-drift.sh` reports a lingering cache as a retired,
non-failing surface rather than pretending it can reconcile it. Issue #663's
restored symlink tier replaces the uninstalled command surface.

## Consequences

- A clone is again required for CPP's own command surface.
- Command edits have one Claude Code source tree and no marketplace parity
  copies to regenerate.
- Existing plugin caches remain executable until the operator uninstalls them;
  the migration report names those families but does not mutate the host.
- Codex skills remain a separate generated harness surface, maintained by
  `scripts/codex-skill-sync.py`.
- External marketplaces and Claude Code's native `/plugin` support are out of
  scope and unchanged.
