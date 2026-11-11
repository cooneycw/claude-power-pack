# Flow run record - issue #1671

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=29c599b037704e7889141765edf1d4b3 -->
## Run 1

- Run-id:            29c599b037704e7889141765edf1d4b3
- Run-start:         b3a8162700bce8a4208ef82db741d95d4689da61
- Issue:             #1671
- Base SHA:          b3a8162700bce8a4208ef82db741d95d4689da61
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the repository owner, in the interactive session ("approved", choosing the markdown `controls/census.md` home over JSON)
- Recorded at:       2026-11-11T20:30:00Z

### Section B evidence
- Commits since 2026-11-11T14:58:28Z on the census paths: none moving the census (abce5ab5 #1670 and b3a81627 #1677 inspected; neither relocates it).
- Merged PRs inspected: #1675, #1676, #1679, #1680, #1682 - none moves the census.
- Open PRs: #1681 (Refs #1669) edits census row 28 inside the ADR - a collision, not a duplicate.
- Duplicate/superseding issues: none (#1060, #1268, #1264, #1036 closed; they built the current gate).
- Sibling worktrees: no unpushed commits on these paths; one stale entry (t008/cpp-pin, directory gone) UNREADABLE, unexamined.

### Section C - the approved plan
1. `controls/census.md` - new; receives verbatim the Universe and derivation section, the Captured table and notes, the Excluded table, the external-subjects marker and prose, and the Retired table; row numbers unchanged.
2. `docs/decisions/0008-instrument-negative-control-bound.md` - enumeration data replaced by a pointer to controls/census.md; the rule, bound, rationale and rule sections stay; path unchanged.
3. `scripts/instrument-census-check.py` - shared resolver tries controls/census.md first, then the ADR path and the candidate globs; messages name the file read.
4. `scripts/check-negative-controls.py` - fallback path constant and comments follow the resolver.
5. `scripts/verify-coverage-check.py` - CENSUS_REL and comments point at the new home.
6. `controls/instrument-census/control.json` - registers the new cases and the updated anchor hash.
7. `controls/instrument-census/cases/bad-unaccounted-data-home/controls/census.md` - new known-bad tree at the new location (with its scripts/ files).
8. `controls/instrument-census/cases/good-accounted-data-home/controls/census.md` - new known-good tree at the new location (with its scripts/ files and Makefile).
9. `controls/instrument-census/anchors/constructed-loose-tokens-forward-only-instrument-census-check.py` - the blind anchor learns the new location so it misses the new bad case for its own reason.
10. `tests/test_instrument_census.py` - resolver precedence tests: new home wins, ADR fallback works, moved-out tables with no data file refuse as unread.
11. `tests/test_codex_consolidation_ledger.py` - the census-membership assertion reads the new file.
12. `CLAUDE.md` - Project Map lines for the census and the ADR.
13. `README.md` - sentences naming where the gate reads the census.
14. `docs/scripts.md` - the instrument-census-check entry names the new home.

Scope: 14 planned paths (plus fixture scripts beside items 7 and 8); ~450 ADR lines moved verbatim, ~250 new lines.
Risks: PR #1681 edits row 28 in the ADR (second merger must carry it); a tree holding both a data file and ADR tables has the ADR tables ignored; ADR prose cites rows by number in another file; skillc fixtures reading tables inside the ADR are unverified until grepped.
