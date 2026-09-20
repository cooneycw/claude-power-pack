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
