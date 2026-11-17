<!-- flow-run n=1 id=f9f08a92b206474696c5353719e9a90e -->
## Run 1 - issue #1860 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1860
- Read at:      2026-11-17T01:38:19Z
- updatedAt:    2026-11-17T01:38:05Z   (context only - moves on comments and labels)
- Body digest:  fe7c7b19d4fab009c97242037f0e74b9aeb3e62b3765832251935ac184067e38   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3483 of 3483 (cap 16384)

### Body as read
## Problem

On a network that blocks git smart-HTTP (the `upload-pack` POST) and raw-content fetches, `git clone` of this repository cannot run. The fallback is to build an API-only checkout: a depth-1 tree, with each file fetched through the GitHub GraphQL `Blob.text` field. Six tracked files cannot be reproduced that way, and the two fixtures below are the dangerous ones because they fail **silently**:

| File(s) | Content | What the API returns | Effect |
|---|---|---|---|
| `docs/architecture/c4-l{1-context,2-container,3-cicd,4-config-runner}.png` | binary PNG | `isBinary: true`, `text: null` | missing file (a loud failure) |
| `controls/check-oscillation/cases/{bad-reversed,good-monotonic}/history.log` | text containing NUL bytes (`--format=%x00%H%x00%s`) | `isBinary: false`, and each NUL comes back as the **literal two characters `^@`** | a wrong file with no error |

Verified on main @ 2ff42c8 by fetching `bad-reversed/history.log` through GraphQL: the raw JSON carries `^@`, and `cmp` against the real bytes differs at byte 1. A scan of all 4764 files in HEAD for NUL, non-UTF-8 and CR finds only these six.

### The PNGs are orphaned
Nothing in the repository references `c4-l*.png` (`git grep` is empty). They were committed once in 58f055aa (2026-03-08) as screenshots of the sibling `.html` files, never regenerated, and have drifted from them. `/documentation:c4` now emits Mermaid. Deleting them loses nothing: the HTML sources stay.

### The fixtures are NUL-delimited because the gate's capture format is
`scripts/check-oscillation.py` `GIT_LOG_ARGS` uses `--format=%x00%H%x00%s`, and `parse_log` recognises a commit header by `startswith("\x00")`. The control cases are captures made with those args, so they carry NULs.

## Fix

1. Delete the four orphaned PNGs.
2. Change the commit-header format to a printable marker line, for example `--format=OSCILLATION-COMMIT %H %s`. It stays unambiguous: every line of `git log -p --unified=0` output after the header is a diff header (`diff --git`, `index`, `---`, `+++`, `@@`, mode/rename/similarity lines, `Binary files`, `\ No newline`) or a `+`/`-`/space-prefixed content line, so no diff line can begin with the marker. Update `parse_log` with it, in ONE place shared by the live and `--from-log` paths.
3. Recapture both control cases with the new args. Update the constructed anchor (`anchors/constructed-single-commit-check-oscillation.py`), which carries its own copy of the format and parser, and re-pin its `sha256` in `control.json`.

## Acceptance

- [ ] `git ls-files` contains no file with a NUL byte or invalid UTF-8 (a one-off scan in the PR body, shown red on main and green on the branch).
- [ ] `controls/check-oscillation` still discriminates: `bad-reversed` scores BAD and `good-monotonic` scores GOOD through the framework, and the anchor still MISSES the bad case and AGREES on the good one.
- [ ] `test_a_captured_log_gives_the_SAME_answer_as_the_live_repo` passes (live and captured parsing agree on both verdicts).
- [ ] Both fixtures round-trip byte-exact through GraphQL `Blob.text` after merge (post-merge check).

## Out of scope / follow-ups
- A standing guard that refuses new NUL or non-UTF-8 tracked files (it would need its own negative control). Recorded as a possible follow-up, not built here.
- A full install and `/cpp:update` on such a network also need a non-git transport (for example a `git bundle` or source-tarball release asset). That is a separate question.


<!-- end of body -->
