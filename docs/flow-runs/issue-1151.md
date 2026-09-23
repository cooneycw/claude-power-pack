# Flow run record - issue #1151

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1151
- Base SHA:          e12b8e7
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          wave `claude-improvements` orchestrator, session
                     `claude-improvements-new`, mailbox rev 9, acked after the content
                     was held.
- Recorded at:       2026-09-23T15:00:00Z

## Section B evidence

- Commits touching the lane since filing (2026-09-20T17:27:37Z): #1201, #1195, #1183, #1156.
  All change what is bundled or generated; none adds an enumeration mode. `--help` at e12b8e7
  still offers only `--check | --write`, `--install`, and a families positional.
- #1136 (CLOSED) is the sibling - the re-sync trigger blind to bundled docs, two gate cycles in
  two hours. #1147 (CLOSED) is the same shape one layer up: an instrument read for a question it
  does not answer. Neither supersedes this.
- Searched "list-mirrors enumeration codex-skill-sync" across all states: only #1151 and the Nit
  Store.
- DEFECT REPRODUCED: `--check` on a clean tree exits 0 in 0.14s and prints exactly two lines
  mentioning `codex/skills` - the summary and a caveat - naming ZERO specific paths. That is the
  issue's own measurement.
- THE DERIVATION WAS VALIDATED AGAINST THREE INDEPENDENT OBSERVATIONS, not against itself.
  `expected_outputs()` already computes the whole set untouched - 74 skills, 271 mirror files.
  Asking which skills bundle a given source returns:
      scripts/gh-pr-merge.sh          -> 2 skills: flow-auto, flow-merge
      scripts/flow-finish-gate.sh     -> 4 skills: flow-auto, flow-check, flow-finish, flow-merge
      docs/agents/issue-contract.md   -> 5 skills
  The first two are exactly the mirrors observed drifting when those files were edited on #1191
  and #1192 earlier the same day, with matching names; the third is the number #1136's own
  header records from its incident.

## Section C - the approved plan

1. `scripts/codex-skill-sync.py` - add `--list-mirrors [SOURCE ...]`, non-mutating. With no
   SOURCE, print every `codex/skills/**` path the generator would produce, one per line. With
   SOURCEs, print only the mirrors those sources feed: a command document maps to its own
   skill's mirrors; a bundled script or doc maps to that path under every skill that bundles it.
   REUSES `expected_outputs()` rather than deriving a second population - a second reader is a
   second population to keep in step.
2. `tests/test_codex_skill_sync.py` - committed cases, two-sided. A bundled source names its
   mirrors and the count matches the generator; a NOT-bundled source prints zero lines AND says
   so BY NAME with a non-zero verdict, so "not bundled" is distinguishable from "bundled with no
   mirrors" - which cannot happen, and the output says so. The enumeration is pinned against
   `expected_outputs()` so the two cannot drift apart.
3. `docs/flow-runs/issue-1151.md` - this record.
4. `docs/flow-runs/issue-1151.as-read.md` - the as-read snapshot.

Scope: 4 files, approximately 130 lines net.

Risks: R1 a tool built to answer "what IS the mirror set" that returned SILENCE for an unknown
source would reproduce the defect it exists to remove - hence the by-name, non-zero unknown case.
R2 a second derivation would drift from the generator; mitigated by reusing `expected_outputs()`
and pinning the two together in a test. R3 this change edits a file that is ITSELF bundled.

PREDICTION BEFORE MUTATING, recorded here so the result can be checked rather than asserted:
editing `scripts/codex-skill-sync.py` will stale 2 mirrors - codex/skills/flow-auto and
codex/skills/flow-finish - which with their two `scripts/SHA256SUMS` is 4 drifted files. The
re-sync will be run BEFORE the gate rather than after, and the observed number reported whether
or not it matches. A miss is the more interesting result: it would mean the enumeration being
shipped here is wrong, discovered before shipping it.
