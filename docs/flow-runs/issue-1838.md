# Flow run record - issue #1838

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=068669874b7848aa8245bc9842e2b48c -->
## Run 1

- Run-id:            068669874b7848aa8245bc9842e2b48c
- Run-start:         3ed254698f3e32fb99adf203c955308531729a75
- Issue:             #1838
- Base SHA:          3ed254698f3e32fb99adf203c955308531729a75
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session "approving your revised plan" after the revised Section C informed by discussion #1830
- Recorded at:       2026-11-15T11:37:20Z

### Section B evidence
- Commits since filing (2026-11-15T10:45:21Z): none on origin/main; none touching scripts/codex-skill-sync.py or charters/.
- Merged PRs since 2026-11-15: none.
- Issues searched ("charter"): #1838 only relevant; #956, #1014, #950, #864 unrelated and closed.
- Host sibling worktrees: none with unpushed commits touching the planned paths.
- External: skillc PR #746 (open) parses a CHARTER.md YAML block that must open the file and refuses unknown fields; `subject:` is added by skillc #726 PR A (owner decision comment on skillc #726, 2026-11-15).
- Discussion #1830 (Parts 2-5): enforce in a check rather than prose; test behaviour, not wording; no hand-made copy of skillc's format; no always-loaded additions.

### Section C - the approved plan
1. `charters/README.md` - new, ~20 lines: path mapping, why not beside the command or in codex/skills, `subject:` required and enforced by the generator, link to skillc docs/specs/contracts.md, skills keep CHARTER.md beside SKILL.md.
2. `scripts/codex-skill-sync.py` - CHARTERS_ROOT; generate_skill mirrors charters/<family>/<stem>/CHARTER.md with the GENERATED marker after the YAML block and links rewritten against the charter's real path; excluded from PROVENANCE.md; charter_errors() (orphan charter, stray file, missing/mismatched subject) feeds --check.
3. `tests/test_codex_skill_sync.py` - (a) mirrored with YAML block first and body unchanged, (b) no charter mirrors nothing, (c) planted charter changes no skill names with the .claude/commands/flow/CHARTER.md control producing flow-CHARTER, (d) each charter error reported and the clean case not, (e) drift on charter change, (f) wrong subject refused.
4. `tests/test_skills_check_charters.py` - new: a planted charters/ tree does not change skills-check.py's count; a planted .claude/skills/x/SKILL.md does.
5. `docs/scripts/codex-skill-sync.md` - #1838 history entry.
6. `codex/skills/README.md` - CHARTER.md in the per-skill layout, sourced from charters/.

Scope: 6 files (3 new), ~230 lines, mostly tests.
Risks: a landed charter changes the Codex skill's closure digest, so coverage-map and eval-enrollment evidence for that skill go stale (intended); the strict subject check reds CPP --check for a draft that omits or misspells subject; skillc PR #746 refuses the subject field until skillc #726 PR A merges (no charter lands here).

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test - main checkout: a temporary repository; linked worktree: not covered separately, the generator resolves paths from REPO_ROOT identically |
| Harness | will test - Codex install: the generated mirror carries CHARTER.md; Claude install: charters/ is not a command or a skill |
| Driver | not applicable - no driver procedure changes |
| Coordination | not applicable - no coordination path involved |
| CI provider | not applicable - no CI output is read |
| Project state | will test - a repository that has adopted a feature's file or record (charters/ present) and one that has not (no charter mirrors nothing, no error) |
| Toolchain version | not covered - CI's pinned image only |
| Clone shape | not applicable - the generator is git-free |
| Run location | not applicable - paths derive from the script's repository root |
| Gate target | not applicable - no consumer toolchain involved |
| Wave role state | not applicable - no wave state involved |
| Reader: Codex sessions reading the mirrored CHARTER.md | will test - test (a) reads the real generated copy |
| Reader: skillc contracts reading charters/ | not covered - no skillc code runs here; test (a) checks only the YAML-first rule |
