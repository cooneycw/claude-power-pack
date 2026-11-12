<!-- flow-run n=1 id=a78066e3993c44d1b472bc436531b77e -->
## Run 1 - issue #1713 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1713
- Read at:      2026-11-12T00:41:31Z
- updatedAt:    2026-11-11T23:11:07Z   (context only - moves on comments and labels)
- Body digest:  7bede978b34690ec6d7bcfc0dc1263c98fd33040ea5049ad996b756633210a9e   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 6598 of 6598 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 12 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
Findings in the helpers that start a flow run and record its plan. `flow-plan-record.py compliance` leaves intent-to-add entries in the index that break a later merge, returns UNKNOWN on a colon-form Section C line that `approve` accepted, and covers only one commit on a salvage chain. `flow-start-resolve.sh` misses a newer branch spelling on pickup and accepts a pull request number as an issue. `flow-preflight`'s bash `missing` verdict is unreachable because its own bootstrap is bash. Plus command documents that call bundled helpers by a cwd-relative path, a partial-source installer that reports success, and a bare `wayfinder` label that the label rule misses.

## Findings (12)
- [seq 84](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5679613623), 2026-09-15, low (estimated): LANE_SERVE_STATUS value set (serving|dead|unreachable|unknown) is prose only; no test pins it. Status at origin/main `f63dc946`: tests/test_lane_serveability.py pins KEY sets exactly (:377-405) but no test derives or asserts the status VALUE set vs docs; unchanged since report.
- [seq 543](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6294768195), 2026-10-20, low (stated): wayfinder label rule misses a bare 'wayfinder' label in project-next and flow-start-resolve. Status at origin/main `f63dc946`: project-next.py:94 WAYFINDER_LABEL_PREFIX='wayfinder-' and normalize_label strips trailing '-', so label 'wayfinder:' normalizes to 'wayfinder' and is missed; flow-start-resolve.sh:505 mirrors it.
- [seq 563](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6365089634), 2026-10-23, low (estimated): Claude-side command docs run bundled helpers by cwd-relative scripts/<name> (wave.md, merge.md, c4.md, retro.md, permissions.md). Status at origin/main `f63dc946`: wave.md:892,1153,1163,1177 and merge.md:489 still use bare scripts/ paths. #1546 only fixed the Codex mirrors, stated as not the Claude side.
- [seq 575](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6390647727), 2026-10-24, low (estimated): flow-plan-record compliance returns UNKNOWN on colon-form 'path: gist' Section C lines. Status at origin/main `f63dc946`: parse_plan_paths (scripts/flow-plan-record.py:749-774) still accepts only a dash separator preceded by whitespace; colon form yields [] and compliance exits 4.
- [seq 584](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6396518069), 2026-10-25, low (estimated): flow-plan-record approve stamps baseline without validating Section C lines that compliance can later parse. Status at origin/main `f63dc946`: parse_plan_paths is called only from cmd_compliance (line 821); cmd_approve does not validate. Em dash separator is still unsupported.
- [seq 612](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6441014817), 2026-10-27, medium (estimated): flow-plan-record compliance leaves git add -N intent-to-add entries that break a later merge. Status at origin/main `f63dc946`: scripts/flow-plan-record.py:793-795 still runs git add -N on untracked files and never restores them; no temp-index path.
- [seq 629](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6496344952), 2026-10-29, low (stated): flow-plan-record.py approve commits issue body verbatim as as-read snapshot, which a repo leak gate can refuse. Status at origin/main `f63dc946`: No redaction or opt-out in flow-plan-record.py; as-read snapshot is verbatim (escape_markers only handles run markers).
- [seq 657](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6631438046), 2026-11-04, low (stated): flow-start-resolve.sh remote-pickup matches only origin/issue-N-*, missing newer issueN-... descendant branch. Status at origin/main `f63dc946`: Candidate listing at lines 733 and 756 is still 'issue-${ISSUE_NUM}-*' only.
- [seq 658](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6635311218), 2026-11-04, low (stated): flow-plan-record declare-salvage covers one commit; earlier chain commits show PLANNED BUT NOT TOUCHED; changes record after approve. Status at origin/main `f63dc946`: declare-salvage (flow-plan-record.py ~440-470) still takes one sha and refuses a second distinct one.
- [seq 659](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6637162103), 2026-11-04, low (estimated): flow-helpers-install.sh bundled in codex flow-repair/flow-doctor skips absent helpers yet prints FLOW_HELPERS: installed. Status at origin/main `f63dc946`: Install loop still prints 'skip name (not present in source)' and continues; only an all-absent source is unverifiable. Codex bundles are now generated, not tracked (#1679), so bundle content not checked.
- [seq 667](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6711969470), 2026-11-07, medium (stated): flow-preflight.py bash check 'missing' unreachable: flow-preflight.sh is bash and exits 127 before Python on PATH without bash. Status at origin/main `f63dc946`: flow-preflight.sh still #!/usr/bin/env bash; init.md:120 and update.md:331 only print 'not met or not verified (exit 127)', no install remedy or command -v bash.
- [seq 670](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6722958745), 2026-11-08, low (stated): flow-start-resolve.sh accepts a PR number as an issue (gh issue view resolves PRs) and creates a lane. Status at origin/main `f63dc946`: Lines 491-498 use gh issue view with --json state/title only; no PR-vs-issue check anywhere in the script.

## Acceptance
- `compliance` leaves the index as it found it; `approve` refuses a Section C line `compliance` cannot parse; the remaining items are fixed or declined here.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Constraint
Freeze (#1673): fixes only, no new feature under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/`. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is by default; a change to one needs a coordination issue in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before the PR merges.

Parent: #1690 (child of #1673)


<!-- end of body -->
