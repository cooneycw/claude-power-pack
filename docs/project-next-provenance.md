# project-next: provenance

CPP owns `lib/project_next` outright. This file records where it came from,
because ownership transferred and authorship did not.

## Origin

The engine, its v1.3 contract, its golden fixture corpus and its configuration
schema were written in [cooneycw/codex-power-pack](https://github.com/cooneycw/codex-power-pack)
and vendored into CPP under `vendor/project_next/` from issue #723 until issue
#1069. The MIT license they were published under travels with the code at
`lib/project_next/LICENSE`; CPP's ownership is of the maintenance, not of the
authorship.

| | |
|---|---|
| Upstream repository | `cooneycw/codex-power-pack` |
| Transferred at | `1724e7d9` - the commit the vendoring manifest pinned |
| Transferred in | CPP issue #1069 |
| Contract version at transfer | 1.3 |

## Git history: a deliberate choice, not an accident

The code arrived as a **fresh copy and carries no upstream commit history**.
That was an owner decision (consolidation ledger, decision **Q8**), taken before
the move rather than by default afterwards.

What it costs is bounded and was measured before the ruling: the history in
question is five squash commits spanning two days - `9fe9b19`, `5961546`,
`8339534`, `1724e7d` and `f39bcf3`. Their messages reference codex-power-pack
issue numbers, which would render inside CPP as links to unrelated CPP issues.

It costs less than it would otherwise, because codex-power-pack is **not deleted
and not archived**. It goes private and dormant; history, issues, PRs and
attribution stay readable at their source. `git blame` for these files lives
there.

## What that does NOT cover

"Readable at their source" is true for a person and false for tooling. Nothing
automated in CPP can reach that repository once it is private: `lib/vendor.py`
carries no auth handling, and the fetch paths that used to reach it were removed
with the vendor gate. So the provenance above is durable as a reference and is
not a retrieval path - anything CPP needs from upstream had to come across in
the transfer, which is why the engine's own unit tests came with it rather than
being left behind as "still available upstream".

## One upstream change not adopted

`f39bcf3` (2026-09-06, docs-only) edited `docs/project-next-contract.md` after
the pinned `1724e7d`, adding a paragraph on the contract's relationship to CPP's
wave-lane grammar. The transfer took the recorded pin, per the issue's
acceptance. That paragraph is adopted separately as CPP's own edit rather than
silently dropped or silently folded into the transfer.

## Compatibility: what moved, and what to do about it

Every path that changed at #1069, and whether a consumer has to act. The import
path itself is the one most likely to be assumed broken and is not.

| Was | Is now | Action |
|---|---|---|
| `lib.project_next.*` (import) | `lib.project_next.*` | **none** - the dotted name is unchanged; only the sys.path root moved from `vendor/project_next` to the repo root |
| `vendor/project_next/lib/project_next/` | `lib/project_next/` | update a hardcoded FILE path; an import needs nothing |
| `vendor/project_next/tests/.../fixtures/` | `tests/project_next/fixtures/` | update a hardcoded fixture path |
| `vendor/project_next/docs/project-next-contract.md` | `docs/project-next-contract.md` | the pointer document that used to sit at this path is superseded by the contract itself |
| `.claude/project-next-vendor.json` | `.claude/project-next-ownership.json` | update the path; `contract_version` still means what it meant |
| `vendor/project_next/scripts/project-next.py` | **removed** | it was a 17-line shim that did `import_module("lib.project_next.cli").main`. Replace with `python -c "from lib.project_next.cli import main; main()"`, or use `scripts/project-next.py`, which is the supported entry point |
| `scripts/project-next-vendor.py` | `scripts/project-next-ownership.py` | different gate, different question - see `docs/scripts.md` |
| `make project-next-check` | `make project-next-check` | **none** - same target name, new recipe |
| `make project-next-drift` | **retired** | it fetched from codex-power-pack. There is no upstream to drift from |
| `make project-next-revendor` | `make project-next-repin` | re-pins locally instead of re-fetching |
| `decision policy: contract v1.3 (vendored engine)` | `... (project-next engine)` | a consumer matching that literal must update it |

## Rollback

The transfer is one squashed commit and reverting it restores the vendored
arrangement wholesale - `vendor/project_next/`, the vendor gate, its manifest and
its control - because nothing outside that commit depends on the new layout.

Two things that revert does NOT restore, and both are why a revert should be a
deliberate decision rather than a reflex:

- **The engine's unit tests stay useful only while they can be fetched.** The 726
  lines under `tests/project_next/` were never vendored; a revert deletes them
  from CPP, and re-obtaining them needs codex-power-pack, which is going private
  and dormant. Reverting after that point loses them.
- **`make project-next-drift` will not work again** even though the revert
  restores it. It fetches from a repository that has stopped being public, and
  `lib/vendor.py` carries no auth handling. It would fail open - exit 0 with a
  note - which looks exactly like "upstream is current".

So a revert is safe as a short-term undo and is not a durable arrangement. If the
ownership decision is being reversed rather than the code, re-derive the vendor
link deliberately rather than restoring a gate that can no longer reach its source.
