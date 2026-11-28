# Issue #1926: title populations and PR-body recovery census

This is a bounded observation, not adoption of PR-body provenance or capitalized
`Fix ...` titles. Part 1 admits only case-sensitive conventional `fix:` and
`fix!:` in addition to the existing scoped forms. Part 2 remains a count and
proposal pending #1877 and its preferred `--provenance-file` capture point.

## Observation boundary

- Source revision: `a0dbd0b7c42c9f95bef8cc9eeb7bd75c8eca014f`.
- Merged-PR period: 2026-11-01 through 2026-11-28T02:21:26Z, inclusive.
- PR-body/issue-body/comment observation completed: 2026-11-28T02:26:11.095391+00:00.
- Complete paginated GitHub search per repository:
  `repo:OWNER/NAME is:pr is:merged merged:2026-11-01..2026-11-28T02:21:26Z`.
- Search replies asserted `incomplete_results=false`, total at most 1,000,
  and collected row count equal to `total_count`. No failed read counted as zero.
- Title sample query: `repo:OWNER/NAME is:pr is:merged in:title Fix` with
  `merged:<=2026-11-28T02:21:26Z`; exact capital `^Fix\s` results below.
- Titles and PR/issue bodies remain editable after merge. The cutoff selects
  merge dates; these are current-body observations at the recorded read time,
  not a claim about the bodies at merge time.

## Old and expanded title populations

| Repository | All merged | Old scoped forms | Expanded forms | Added |
|---|---:|---:|---:|---:|
| cooneycw/kyle | 333 | 86 | 90 | 4 |
| cooneycw/skillc | 95 | 19 | 19 | 0 |
| cooneycw/claude-power-pack | 174 | 65 | 81 | 16 |
| Total | 602 | 170 | 190 | 20 |

No old members are removed. The 20 additions are all `fix:`; this historical
sample contains no added `fix!:`. Committed synthetic cases cover both forms,
scoped breaking/nonbreaking forms and near misses. The old/new fixture
freezes the predecessor populations and an unchanged report; tests exercise
both the real collector and renderer. Existing unchanged rows stay byte-identical.

Added PRs:

- [cooneycw/kyle#2776](https://github.com/cooneycw/kyle/pull/2776): fix: align installer answers guidance, bind waiver and Docker preflight
- [cooneycw/kyle#2737](https://github.com/cooneycw/kyle/pull/2737): fix: acquire pinned CPP and reject releases without it
- [cooneycw/kyle#2736](https://github.com/cooneycw/kyle/pull/2736): fix: handle pre-boot assignments in the startup turn
- [cooneycw/kyle#2332](https://github.com/cooneycw/kyle/pull/2332): fix: stage offline CPP runner for Claude container gates
- [cooneycw/claude-power-pack#1971](https://github.com/cooneycw/claude-power-pack/pull/1971): fix: honor the verify timeout override in the task manifest
- [cooneycw/claude-power-pack#1885](https://github.com/cooneycw/claude-power-pack/pull/1885): fix: route delegated finish checks through the audited wrapper
- [cooneycw/claude-power-pack#1806](https://github.com/cooneycw/claude-power-pack/pull/1806): fix: align CI status fallback and recorded boundaries
- [cooneycw/claude-power-pack#1805](https://github.com/cooneycw/claude-power-pack/pull/1805): fix: require consent before wave re-registration drops active work
- [cooneycw/claude-power-pack#1799](https://github.com/cooneycw/claude-power-pack/pull/1799): fix: decide counter-model enrolment in Python
- [cooneycw/claude-power-pack#1655](https://github.com/cooneycw/claude-power-pack/pull/1655): fix: retire cpp:init Makefile generation (R3)
- [cooneycw/claude-power-pack#1647](https://github.com/cooneycw/claude-power-pack/pull/1647): fix: share cpp:init MCP registration per client (R2)
- [cooneycw/claude-power-pack#1643](https://github.com/cooneycw/claude-power-pack/pull/1643): fix: serialize live control tracking scans with probe writers (Closes #1641)
- [cooneycw/claude-power-pack#1640](https://github.com/cooneycw/claude-power-pack/pull/1640): fix: require an issue-visible handoff for preserved WIP (Closes #1614)
- [cooneycw/claude-power-pack#1638](https://github.com/cooneycw/claude-power-pack/pull/1638): fix: install project-next engine entry point with flow helpers (#1619)
- [cooneycw/claude-power-pack#1637](https://github.com/cooneycw/claude-power-pack/pull/1637): fix: name Git 2.36 floor for partial worktree removal (#1621)
- [cooneycw/claude-power-pack#1636](https://github.com/cooneycw/claude-power-pack/pull/1636): fix: report unparsed ADRs in premise-staleness coverage (Refs #1614)
- [cooneycw/claude-power-pack#1635](https://github.com/cooneycw/claude-power-pack/pull/1635): fix: release zombie-owned claims and wave roles
- [cooneycw/claude-power-pack#1634](https://github.com/cooneycw/claude-power-pack/pull/1634): fix: keep interrupted pytest populations failed after partial retries (#1617)
- [cooneycw/claude-power-pack#1633](https://github.com/cooneycw/claude-power-pack/pull/1633): fix: recognize Codex custom exec HEAD probes in full receipts
- [cooneycw/claude-power-pack#1632](https://github.com/cooneycw/claude-power-pack/pull/1632): fix: complete drift reports without Docker (#1629)

## Existing capitalized Fix-space sample

These are all exact capital `Fix ` titles returned by the bounded all-history
title queries (Kyle search 500 results, skillc 123, CPP 464). They look like
repairs, but inclusion would widen the stated conventional-title population.
They stay excluded; a later adoption decision must address that boundary.

- [cooneycw/kyle#2786](https://github.com/cooneycw/kyle/pull/2786): Fix main-only recipe preparation after squash merge
- [cooneycw/kyle#2739](https://github.com/cooneycw/kyle/pull/2739): Fix candidate executor scroll and exited-container grants
- [cooneycw/kyle#2789](https://github.com/cooneycw/kyle/pull/2789): Fix attach FD leak checks for unrelated descriptor closure
- [cooneycw/kyle#2782](https://github.com/cooneycw/kyle/pull/2782): Fix candidate approved commit identity documentation assertion (Rule C)
- [cooneycw/kyle#2699](https://github.com/cooneycw/kyle/pull/2699): Fix J01 identity oracle to read only its tagged fenced result
- [cooneycw/kyle#2429](https://github.com/cooneycw/kyle/pull/2429): Fix tmux no-leak assertions to inspect variable entries
- [cooneycw/kyle#1943](https://github.com/cooneycw/kyle/pull/1943): Fix copy-mode exit tests triggering tmux paste detection (Closes #1719)
- [cooneycw/kyle#675](https://github.com/cooneycw/kyle/pull/675): Fix retry_member race: atomic claim, parent-launch-status check
- [cooneycw/kyle#683](https://github.com/cooneycw/kyle/pull/683): Fix tool_abort_launch and tool_retry_member: always 403 in production
- [cooneycw/skillc#602](https://github.com/cooneycw/skillc/pull/602): Fix description optimizer ranking of valid zero scores
- [cooneycw/claude-power-pack#1928](https://github.com/cooneycw/claude-power-pack/pull/1928): Fix Pi install control under symlinked TMPDIR
- [cooneycw/claude-power-pack#1921](https://github.com/cooneycw/claude-power-pack/pull/1921): Fix parity fixture race with transient closing-report probes
- [cooneycw/claude-power-pack#1813](https://github.com/cooneycw/claude-power-pack/pull/1813): Fix bootstrap checker launch outside the CPP checkout
- [cooneycw/claude-power-pack#50](https://github.com/cooneycw/claude-power-pack/pull/50): Fix hardcoded absolute paths in commands and skills

## PR-body recovery count only

The same 190 expanded conventional-fix PRs were read through GraphQL, with
closing-issue links and each issue body/comments. Connections were checked
for complete pagination. Parsing uses the unchanged report `provenance()`
and canonical answer lists, including exact punctuation and conflicting-value
refusal. None of these observations changes production collection or tallies.

| Repository | Fix PRs | PRs with labels | Valid PR pairs | One closing issue | No closing issue | Multiple closing issues |
|---|---:|---:|---:|---:|---:|---:|
| cooneycw/kyle | 90 | 0 | 0 | 39 | 47 | 4 |
| cooneycw/skillc | 19 | 0 | 0 | 9 | 10 | 0 |
| cooneycw/claude-power-pack | 81 | 3 | 1 | 62 | 17 | 2 |

Only CPP #1730 has a valid complete PR-body pair that its sole closing issue
#1723 lacks: `Origin: #1696` and `Missed because: no test covered it`. This
would recover one complete linked-issue provenance record. All three
label-bearing PRs are in the old 170-member population too; expanding titles
adds no PR-body provenance in this period.

Two other PRs demonstrate why finding a label is insufficient:

- CPP #1819 has valid `Origin: #1515`, but `Missed because: no test covered it.`
  has an extra period and is invalid under the canonical vocabulary. Its
  linked issue #1818 has an invalid prose Origin rather than a missing value.
  A naive per-field fallback could count a second Origin category; the
  proposed missing-only/no-conflict rule must refuse this replacement.
- CPP #1915 has a prose Origin outside the vocabulary and no Missed-because
  field. It recovers no canonical category.

The parser found all three known label-bearing observations in this history
and distinguished the valid pair from invalid/prose values. Committed fixture
snapshots retain only the relevant label values, categories and issue links;
they do not invent missing history. No-link and multi-issue PRs remain separate
populations rather than guessed issue attributions.

## Proposed attribution rule, not adopted

1. Prefer #1877 capture to the explicitly selected delivering issue: if its
   validated file writes the canonical lines where the report already reads,
   preserve that issue-based record and do not add a duplicate PR observation.
2. Any future PR-body fallback should require exactly one GitHub closing-issue
   reference, retaining its full repository and issue identity. No closing
   reference is unlinked; multiple references are ambiguous without an
   explicit validated issue binding. Never infer a binding from arbitrary
   issue mentions or a title.
3. Require a complete valid canonical pair. Fill only an issue record whose
   two labels are missing; never overwrite an invalid, conflicting or different
   existing answer. A matching issue pair is already measured and adds zero.
4. Attribute at the existing linked-issue-record granularity and record the
   PR source if fallback is later approved. Do not claim unique underlying
   defects or deduplicate independent fixes without another contract.

Wait for #1877 to land before choosing an adoption. This change neither parses
PR bodies in production nor changes `provenance()` precedence. Issue #1926
therefore remains open.

## Verification and supplemental finding

Before changing the implementation, the new collector test observed only
`[201, 202]` instead of `[201, 202, 203, 204]`, and the independent renderer
test failed its expanded `4/12` expectation. The frozen unchanged report
passed. The report source SHA256 was identical to the pinned predecessor
(`dfb779bacfd4d829a3ac64c8ee28a30d7f17abcc053654f7183261324200f8e3`).

The managed-host start preflight selected a missing installed Codex engine
despite using checkout-local scripts with colocated library sources. The
orchestrator supplied the explicit managed-worker start procedure; no host
preflight success is claimed and installed skills were not modified. The
[Nit Store finding](https://github.com/cooneycw/claude-power-pack/issues/1957#issuecomment-7232396017)
records its misleading repair guidance separately from this change.
