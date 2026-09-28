<!-- flow-run n=1 id=4e1ee446f0c643f68c9ef627f8565fb4 -->
## Run 1 - issue #1278 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1278
- Read at:      2026-09-28T22:17:16Z
- updatedAt:    2026-09-28T18:25:49Z   (context only - moves on comments and labels)
- Body digest:  dccfca8876c8089adb0129bfebee82bd3b6e111f0481906d931aa05552227e89   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2691 of 2691 (cap 16384)

### Body as read
**Evergreen: stays open.** It's the standing checkpoint for cutting a CPP release, used again every time. A release PR references it with `Refs #<this>`, **never** `Closes`: GitHub honours closing keywords even when they're negated or incidental, and closing this loses the checkpoint.

## Why this exists

Individual PRs never bump the version. Releases happen in dedicated `chore(release)` PRs (v8.0.0 was #938 → PR #1003). Nothing prompted the next one, so as of 2026-09-26 (`main` at `8dad506`):

- **143 commits** since v8.0.0 (`41a7845`, 2026-09-15), **41** of them `feat(...)`.
- `CHANGELOG.md` `[Unreleased]` held **2 entries** covering all of that. The changelog had stopped being kept per PR, so the next release has to rebuild the history from `git log`.

Raised by the owner during #1264.

## When to cut one

Any time the owner asks. Otherwise, whoever notices one of these proposes a release in a comment here:

- `[Unreleased]` has entries **and** more than two weeks have passed since the last release, or
- a change alters how work is *accepted* (a gate, a default stage, a contract other repos build on). That's the kind of change that made 8.0 a major bump.

## Procedure (one PR, `Refs #<this>`)

1. **Pick the version from the evidence, not a habit.** Enumerate `git log <last-tag-commit>..origin/main` and classify it:
   - **major:** a contract or acceptance change a consumer must act on. Name each one.
   - **minor:** new commands, gates or capabilities with no required consumer action.
   - **patch:** fixes only.
   State the enumeration in the PR. "Looks minor" isn't a classification.
2. **Backfill `CHANGELOG.md`.** Move `[Unreleased]` under a `## [X.Y.Z] - YYYY-MM-DD` heading and fill the gaps from the enumeration: every `feat` and every user-visible `fix` gets an entry. Leave a fresh empty `[Unreleased]`.
3. **Version sites. All of them, in one commit:**
   - `pyproject.toml` `version =`
   - `uv.lock` (re-lock; the v8.0.0 release changed it)
   - `README.md` line 3 banner (`**vX.Y.Z**`, with a summary that names what the release is actually about)
   - `README.md` `### vX.Y.Z (date)` version-notes section
   - `CLAUDE.md` `Current version:`
   Grep for the old version string afterwards and account for every remaining hit. A missed site is how two version numbers end up shipping at once.
4. Go through `/flow:auto` like any change: ELI5 gate, counter-model review, `make verify`.
5. Comment here with the version, the PR, and the enumeration's counts, so the next release starts from a known point.

## Current state (update this line each release)

Last release: **v8.0.0** (2026-09-15, `41a7845`). Next: pending the enumeration in step 1.

