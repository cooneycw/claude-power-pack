<!-- flow-run n=1 id=cec17c1df5d84556af7b80f67613d13e -->
## Run 1 - issue #1441 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1441
- Read at:      2026-10-12T14:18:39Z
- updatedAt:    2026-10-12T14:17:56Z   (context only - moves on comments and labels)
- Body digest:  9bd45c1df382313ffe175ac03f012cb598fb65295aae4e13648fbba9de0ed6df   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6363 of 6363 (cap 16384)

### Body as read
# Host-level instructions for Claude and Codex have no shared source, and already contradict each other

## Summary

At repository level, CPP solved "Claude and Codex read different instruction files"
in #1071: `AGENTS.md` is a thin pointer to `CLAUDE.md`, so the two cannot disagree.
At **host** level nothing does that. Each tool has its own global file, written by
hand, unchecked, and they have already drifted:

| Host file | Read by | Measured |
|---|---|---|
| `~/.claude/CLAUDE.md` | Claude Code, every directory | Nit Store + Negative Control directives |
| `~/.codex/AGENTS.md` | Codex, every directory | Nit Store only, different rules |
| `~/Projects/AGENTS.md` (added 2026-10-11) | **uneven** - see below | GitHub-access rules |

CPP's own docs place `~/.claude/CLAUDE.md` "outside this repo" (ADR 0009:201,
ADR 0008:38/685), yet ADR 0008 depends on its Negative Control text. No instrument
looks at either global file.

## Evidence

Probe: a no-tools prompt asked each tool whether six exact phrases appear in its
loaded instructions, run in four directories. A decoy phrase in no file
(`Purple Walrus Protocol`) returned NO in all 8 runs. Claude in `kyle` was run
twice with the same answer. Single-model self-reports: read as strong signal,
not as a spec of each tool's loader.

| Phrase (source) | Claude ~/Projects | Claude kyle | Claude skillc | Claude CPP | Codex ~/Projects | Codex kyle | Codex skillc |
|---|---|---|---|---|---|---|---|
| "Do not use the GitHub connector" (`~/Projects/AGENTS.md`) | YES | NO | YES | NO | YES | NO | NO |
| "## Negative Control" (`~/.claude/CLAUDE.md`) | YES | YES | YES | YES | NO | NO | NO |
| "One finding per comment" (`~/.claude/CLAUDE.md`) | YES | YES | YES | YES | NO | NO | NO |
| "Group related findings ... concise comment" (`~/.codex/AGENTS.md`) | NO | NO | NO | NO | YES | YES | YES |

Codex 0.162.1. Claude Code, sonnet, `claude -p`.

## Defects

1. **Direct contradiction on Nit Store format.** Claude: "One finding per comment."
   Codex: "Group related findings from a review into a concise comment." Sessions
   working in tandem write the same store (#864) in incompatible shapes; triage
   passes read one-per-comment as the unit.
2. **Codex sessions never receive the Negative Control directive.** ADR 0008's
   bound is consumed by Claude sessions only. A Codex session that adds or widens a
   gate is not told a committed red case is required. (Mitigated, not removed, when
   Codex runs under a Claude `/codex:auto` orchestrator that applies CPP gates.)
3. **Store list drift.** `~/.codex/AGENTS.md` lacks `cooneycw/skillc` #20 (falls
   back to search, so low harm) and has no update path when stores change.
4. **`~/Projects/AGENTS.md` reaches neither tool evenly.** Codex reads it only when
   started in `~/Projects` itself (it stops at the git root), so in every repo a
   Codex session misses it. Claude reads it in `~/Projects` and in repos with no
   `CLAUDE.md` of their own (skillc, sage, codex-power-pack) but not in kyle or CPP.
   Today its content agrees with existing practice, so nothing breaks. But a rule
   placed there "for the whole workspace" silently applies to a different subset per
   tool and per repo.

## Proposed change (owner-approved direction, 2026-10-12)

**Generate `~/.codex/AGENTS.md` from `~/.claude/CLAUDE.md`, and guard it with a drift check.**

1. **Generator.** A CPP script (alongside `make codex-install`, which already owns
   `~/.codex/`) writes `~/.codex/AGENTS.md` as: a header saying the file is
   generated and naming its source, the full text of `~/.claude/CLAUDE.md` copied
   in verbatim, then a short hand-maintained **Codex-only deltas** section (e.g. the
   existing standing authorization to post routine Nit Store comments without
   asking). The deltas live in a CPP-tracked source, not in the generated file.
2. **Copy, not pointer.** A one-line "read `~/.claude/CLAUDE.md`" pointer is
   rejected: it works only if Codex chooses to open the file, and #1071 already
   found Codex sessions stop at a thin `AGENTS.md` unless told to follow the
   pointer (`scripts/codex-skill-sync.py:173-184`). A skipped read is
   indistinguishable from compliance.
3. **Drift check.** Report-only, wired into `/cpp:status` (the files are
   host-local, so not `make verify`). It reports DRIFT when the generated body no
   longer matches the current `~/.claude/CLAUDE.md`, or when `~/.codex/AGENTS.md`
   was hand-edited. It also lists any `AGENTS.md` above a repo root (e.g.
   `~/Projects/AGENTS.md`) with the reach caveat above.
   **Negative control (committed):** a fixture pair where the source gains a
   directive the generated file lacks → DRIFT; a hand edit to the generated file →
   DRIFT; a freshly generated pair → clean.

**Behaviour shift (accepted by owner):**
- Claude Code: none.
- Codex: begins following Negative Control (a committed red case for any gate it
  adds or changes, which costs more per `/codex:auto` run); posts Nit Store
  findings one per comment instead of grouped; gains skillc #20 in its store list.
- Going forward, anything added to `~/.claude/CLAUDE.md` also reaches Codex. A
  Claude-only rule must go outside the copied file or carry an explicit exclusion
  the generator honours.

**Alternatives considered:** report-only check alone (no behaviour change, but
leaves the live contradiction); hand-fixing only the Nit Store contradiction in
`~/.codex/AGENTS.md` (fixes today, drifts again tomorrow); pointer file (rejected,
see 2).

Out of scope: kyle session containers do not mount `~/.claude/CLAUDE.md`
(ADR 0008:709), a third surface; and where `~/Projects/AGENTS.md` should live.

## Related (all FIXED per the 2026-10-06 Nit Store triage)

- #864 comment 5751638070 - repo `AGENTS.md` facts lacked a fixture → `tests/test_agents_md_facts.py`
- #864 comment 5805176605 - concurrent pull in shared checkout → #1263 / PR #1287
- #864 comment 5680393259 - worktrees share `refs/remotes/` → `scripts/deletion-accounting.sh` (#1031)
- #864 comment 5740510212 - PR mid-finish invisible → `gh-pr-merge.sh` `check_local_divergence()` (#1262)
- #1071 - thin repo `AGENTS.md` pointer (the repo-level precedent)

Found while answering an owner question about Claude and Codex sessions running in
tandem (2026-10-12).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

