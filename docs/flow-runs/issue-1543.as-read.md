<!-- flow-run n=1 id=6df135253539434f8bbf8de26a581e1e -->
## Run 1 - issue #1543 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1543
- Read at:      2026-10-23T11:37:05Z
- updatedAt:    2026-10-23T11:28:21Z   (context only - moves on comments and labels)
- Body digest:  81c139580d0f1db5e64011ea06825124ae851d8d9f955450bd8cef48e95974a3   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3363 of 3363 (cap 16384)

### Body as read
## Problem

`/flow:auto` and `/flow:merge` merge through `~/.claude/scripts/gh-pr-merge.sh`. That
helper is the only thing that runs the issue-closing-keyword guards:
`guard_negated_close_keywords` (#726, #772, #1191, #1412) and the incidental-proximity
and commit-subject scan (#794). When the helper is missing (exit 127 / `! -x`), both
commands, and their generated Codex copies, fall back to an inline block that is a
**plain `gh pr merge --squash`**:

- `.claude/commands/flow/auto.md:1675` and `:1678`
- `.claude/commands/flow/merge.md:159` and `:162`
- `codex/skills/flow-auto/reference.md:1677` and `:1680`
- `codex/skills/flow-merge/reference.md:161` and `:164`

(line numbers at main `b318a14b`)

The fallback keeps the linked-worktree guard (#461) and the `MERGED` state check, but
**none of the close-keyword guards**. So when the helper isn't installed, a PR whose
body denies closing an issue still closes it, silently, and nothing fires. Example
wording: "Refs, not Closes: #N", or "Does not close #N". `merge.md` already says, about
this exact path, that "a plain `gh pr merge --squash` can compose it from the commits,
and there a stale closing reference still closes the issue". Yet the fallback block
itself adds no check.

The helper is most likely to be missing in Codex lanes and fresh hosts, before
`/flow-repair` has run.

The guard that pins the fallback, `tests/test_gh_pr_merge.py::test_flow_commands_wire_the_helper`,
only asserts the remote-branch delete and the `MERGED` check. It cannot fail when the
fallback lacks the keyword guards.

## Evidence

A real silent close of exactly this shape, on cooneycw/skillc:
- PR skillc#515's body said "That is why this says Refs, not Closes: #513 stays open";
- GitHub read `Closes: #513` as a closing keyword;
- skillc#513 closed 2 s after the squash (ClosedEvent, closer = PR #515; no ConnectedEvent);
- it stayed closed, unnoticed, for about 8 hours while its acceptance work continued.

Running CPP's current guard on that real body, through the test harness in
`tests/test_gh_pr_merge.py`, gives exit 5 and `CLEAN STOP: negated issue-closing keyword
detected`, with zero merge calls. So the helper would have prevented it, and any path
that skips the helper does not.

(How that particular merge reached GitHub is being confirmed with the session that made
it, a plain `gh pr merge` being the likely cause. It does not change this issue: the
documented fallback is one such path.)

## Acceptance

- [ ] The keyword guard is reachable without the helper. Either the inline fallback runs
  an equivalent check (for example a small standalone `close-keyword-guard` the fallback
  invokes, which also ships bundled in the generated Codex skills), OR the fallback is
  removed and a missing helper is a STOP that points at `/flow-repair`, never a silent
  unguarded merge.
- [ ] `test_flow_commands_wire_the_helper`, or a new test, FAILS on today's fallback
  blocks: the fallback contains no keyword guard. It passes once the guard is wired.
- [ ] A red using the skillc#515 shape, `Refs, not Closes: #N`, through the fallback path
  refuses before any squash.
- [ ] The generated Codex copies (`codex/skills/flow-auto`, `codex/skills/flow-merge`)
  carry the same behaviour.

Found while orchestrating skillc wave skillc-finish (skillc#513 early close). Related:
#726, #794, #1191, #1412.

