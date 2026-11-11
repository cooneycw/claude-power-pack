# Nit Store rollover

The Nit Store is an inbox: one open issue titled exactly `Nit Store`, one
finding per comment. An inbox nobody empties stops being read (#864 reached 731
comments), so it rolls over monthly (issue #1673).

Nothing in this repository names the store's number for routing.
`scripts/nit-store-resolve.sh` finds the one open issue with that exact title,
so a rollover needs no code change and no document edit.

## Monthly procedure

1. **Aggregate.** Read every comment in the open store. Give each one exactly
   one disposition, recorded as a list in the rollover's own issue:
   - `filed #N` - it became, or joined, a real issue. Group related findings
     into one issue; do not file one issue per comment.
   - `fixed by #N` - a merged change already resolved it. Cite the change.
   - `obsolete` - the thing it describes no longer exists. Say what removed it.
   - `declined` - true, and not worth doing. Say why in one line.
   A finding of medium severity or higher, or any live correctness, security or
   data-loss problem, is always `filed`.
2. **Have the owner read the disposition list** before anything is closed.
3. **Close the old store**, with a comment linking the disposition list.
4. **Open the successor immediately after**, titled exactly `Nit Store`, with
   the `evergreen` label and a body linking its predecessor.
5. **Check the route:** run `scripts/nit-store-resolve.sh` and confirm it prints
   the successor's number with `NIT_STORE_STATUS: ok`.

## Why close before opening

The resolver requires exactly one open store. In the wrong order there are two,
and it answers `unknown`: findings are posted nowhere until one is closed. In
the right order there is a short gap with none, and it answers `none`: a
finding found in that gap is filed as a normal issue, which loses nothing.

GitHub's search index can lag a newly opened issue by a short while, which
extends that gap. Step 5 is how you learn it has ended; do not assume it.

## Reading a closed store

Citations of the form `Nit Store #864, comment N` across the code and documents
are history and stay valid: a closed issue's comments still resolve.
`scripts/maintain-loop-indicator.py --capture out.json --nit-store 864` reads a
closed store's findings; without `--nit-store` it reads the current one.

## Other places that name a store

- The owner's global directives list a number per repository for repositories
  that are not this one. This repository is deliberately absent from that list
  and falls under its "any other repo - search" line.
- A harness that bakes those directives into an image or a generated file (the
  Codex global `AGENTS.md` is generated from them) must be regenerated when the
  directives change, before the store it used to name is closed.
