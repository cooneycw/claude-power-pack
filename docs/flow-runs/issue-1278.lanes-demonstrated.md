

## v13 release draft - initial enumeration

<!-- lanes-demonstrated run=c6b0e02de89042b8a96abe51ad2a1d31 plan=da75cd3a5bd14628f8abab4a5b2efd415abdb5fb4ea7ae8b2434a6189668bbab -->

Initial base: 34c417f9, all 23 commits in git log 3ed25469..origin/main.
Release owner cp-orch mailbox 37242 agrees: 9 major / 6 minor / 8 patch.
The full table below is also in the draft PR body. Rows A/D/E are not yet in
this snapshot; refresh once after the last one lands, before final review/gate.
No tag, GitHub Release or completed-release claim is authorized.

| Commit | Class | Merged change |
|---|---|---|
| `c16af56e` | major | fix(delegated-drivers): drop --kind from the Step 3 escalation; gate doc flags against helpers (Closes #1835) (#1840) |
| `8f7d0e93` | minor | feat(charters): reserve charters/ and mirror CHARTER.md into codex skills (Closes #1838) (#1841) |
| `19e24318` | patch | fix(check-doc-helper-flags): one shell reader for every question the gate asks (Closes #1839) (#1843) |
| `f1253b45` | patch | fix(check-doc-helper-flags): read backtick substitutions, bounded to the simple shape (Closes #1842, Closes #1844) (#1845) |
| `06392d40` | minor | docs(issue-contract): let a valid finding end as an accepted limitation (Closes #1846) (#1852) |
| `62e928b9` | minor | refactor(codex-review): run the cross-model review through one helper (Closes #1847) (#1854) |
| `716b7c3f` | patch | docs(flow-auto): relay helper stop lines and state the missing-helper fallback once (Closes #1848) (#1855) |
| `2df9b1c6` | minor | feat(flow-plan-record): start / approve --plan / finish run verbs for /flow:auto (Closes #1849) (#1856) |
| `61d9c045` | major | docs(flow-auto): charter, proportional Tier 1 path, documentation out of the flow (Refs #1850) (#1858) |
| `2ff42c8d` | patch | fix(driver-parity): cite by unique text, not line number (Closes #1851) (#1859) |
| `de3fb38e` | patch | fix(oscillation): printable commit marker and drop orphaned C4 PNGs so API-only checkouts are byte-exact (Refs #1860) (#1861) |
| `2ad16992` | minor | feat(counter-model): a plan-record-only fix binds the reviewed head instead of forcing a re-review (Closes #1862) (#1866) |
| `5204ea06` | patch | fix(codex-review): drop the review question approve already enforces, with a parity test per clause (Refs #1863) (#1867) |
| `e32c06ed` | major | refactor(flow-auto): renumber to seven steps, retire Step 5, fold Verify CI and Deploy into Step 7 (Closes #1857) (#1868) |
| `25f5066a` | major | fix(drivers): finish published plan records (Refs #1811) (#1869) |
| `8c445b7b` | minor | feat(reports): review-yield and escaped-defect report (Closes #1865) (#1872) |
| `25407114` | major | fix(drivers): capture parent friction throughout lifecycle (Refs #1811) (#1873) |
| `cd6d2b48` | patch | refactor(review): drop duplicated delegated lane question (Refs #1863) (#1874) |
| `dbb485d4` | major | feat(codex-review): findings carry a kind from a closed list; parse counts by kind (Closes #1864) (#1870) |
| `78749847` | major | fix(drivers): check spec context before delegated planning (Refs #1811) (#1879) |
| `6dec8d52` | patch | test(secret-scan): control plan-record hash labels in the history scan (Closes #1871) (#1878) |
| `030f280c` | major | fix(drivers): guard pre-child ownership and stale bases (Refs #1811) (#1880) |
| `34c417f9` | major | feat(drivers): check child edits before checkpoint and shipping (Refs #1811) (#1881) |

All five metadata/notes files are updated together. uv lock changed only the
root virtual package version; dependency pins/hashes are unchanged. Existing
version-consistency check passes all five sites. Command/CLAUDE budgets,
Unicode and relative-link checks passed. No new instrument or test.

Old-version grep accounting, after editing all sites: 11 hits, every one below
is intentionally historical; none is an active version site. The grep already
finds known historical input, so an empty extractor is not its evidence.

| File:line | Why it remains |
|---|---|
| CHANGELOG.md:7 | New release describes its range since the previous release. |
| CHANGELOG.md:102 | Previous release heading. |
| README.md:229 | New notes describe the previous-release range. |
| README.md:243 | Previous release heading. |
| docs/flow-runs/issue-1278.as-read.md:281 | Immutable issue body as read for this run, before the release. |
| docs/flow-runs/issue-1278.md:98 | Prior run's owner approval. |
| docs/flow-runs/issue-1278.md:105 | Prior run's changelog plan. |
| docs/flow-runs/issue-1278.md:106 | Prior run's package version plan. |
| docs/flow-runs/issue-1278.md:108 | Prior run's README plan. |
| docs/flow-runs/issue-1278.md:109 | Prior run's CLAUDE version plan. |
| docs/flow-runs/issue-1278.md:111 | Prior run's post-merge/tag instructions. |

The draft push precedes final review/full gate only under explicit release-owner
mailbox 37236 timing. Draft CI/enrolment is not final release validation; the
release receipt and full gate follow the final refresh after rows A/D/E.


## Final release refresh - main ffc0aae9

Refreshed once after all remaining rows merged, cp-orch mailbox 37609.
Release date is 2026-11-22 UTC. All 26 commits from release base 3ed25469 to
ffc0aae9 are classified: 12 major, 6 minor, 8 patch (the final three add
mandatory driver obligations). Every feature and user-visible fix has a
changelog entry. The original five version sites changed together in e449b714;
re-locking after refresh made no additional lock change.

| Commit | Class | Merged change |
|---|---|---|
| `c16af56e` | major | fix(delegated-drivers): drop --kind from the Step 3 escalation; gate doc flags against helpers (Closes #1835) (#1840) |
| `8f7d0e93` | minor | feat(charters): reserve charters/ and mirror CHARTER.md into codex skills (Closes #1838) (#1841) |
| `19e24318` | patch | fix(check-doc-helper-flags): one shell reader for every question the gate asks (Closes #1839) (#1843) |
| `f1253b45` | patch | fix(check-doc-helper-flags): read backtick substitutions, bounded to the simple shape (Closes #1842, Closes #1844) (#1845) |
| `06392d40` | minor | docs(issue-contract): let a valid finding end as an accepted limitation (Closes #1846) (#1852) |
| `62e928b9` | minor | refactor(codex-review): run the cross-model review through one helper (Closes #1847) (#1854) |
| `716b7c3f` | patch | docs(flow-auto): relay helper stop lines and state the missing-helper fallback once (Closes #1848) (#1855) |
| `2df9b1c6` | minor | feat(flow-plan-record): start / approve --plan / finish run verbs for /flow:auto (Closes #1849) (#1856) |
| `61d9c045` | major | docs(flow-auto): charter, proportional Tier 1 path, documentation out of the flow (Refs #1850) (#1858) |
| `2ff42c8d` | patch | fix(driver-parity): cite by unique text, not line number (Closes #1851) (#1859) |
| `de3fb38e` | patch | fix(oscillation): printable commit marker and drop orphaned C4 PNGs so API-only checkouts are byte-exact (Refs #1860) (#1861) |
| `2ad16992` | minor | feat(counter-model): a plan-record-only fix binds the reviewed head instead of forcing a re-review (Closes #1862) (#1866) |
| `5204ea06` | patch | fix(codex-review): drop the review question approve already enforces, with a parity test per clause (Refs #1863) (#1867) |
| `e32c06ed` | major | refactor(flow-auto): renumber to seven steps, retire Step 5, fold Verify CI and Deploy into Step 7 (Closes #1857) (#1868) |
| `25f5066a` | major | fix(drivers): finish published plan records (Refs #1811) (#1869) |
| `8c445b7b` | minor | feat(reports): review-yield and escaped-defect report (Closes #1865) (#1872) |
| `25407114` | major | fix(drivers): capture parent friction throughout lifecycle (Refs #1811) (#1873) |
| `cd6d2b48` | patch | refactor(review): drop duplicated delegated lane question (Refs #1863) (#1874) |
| `dbb485d4` | major | feat(codex-review): findings carry a kind from a closed list; parse counts by kind (Closes #1864) (#1870) |
| `78749847` | major | fix(drivers): check spec context before delegated planning (Refs #1811) (#1879) |
| `6dec8d52` | patch | test(secret-scan): control plan-record hash labels in the history scan (Closes #1871) (#1878) |
| `030f280c` | major | fix(drivers): guard pre-child ownership and stale bases (Refs #1811) (#1880) |
| `34c417f9` | major | feat(drivers): check child edits before checkpoint and shipping (Refs #1811) (#1881) |
| `2ede561d` | major | fix(drivers): route supplemental findings through the parent (refs #1811) (#1883) |
| `bc7125e1` | major | feat(drivers): declare explicit parent salvage before approval (Refs #1811) (#1884) |
| `ffc0aae9` | major | fix: route delegated finish checks through the audited wrapper (#1885) |

### Live row cross-check

The live #1811 tracker is CLOSED. Read each merged PR's actual behavior and
merge status, then checked current driver-parity.json: all 36 pairs (12 rows
x three drivers) are run. This table maps the twelve actual rows, rather than
copying the old draft's incomplete list:

| Merged PR | Adopted gate/verb rows |
|---|---|
| #1869 | flow-plan-record.py drift; head-check |
| #1873 | friction-log.sh |
| #1879 | speckit-context.py |
| #1880 | flow-live-driver-guard.sh; flow-stale-check.sh; flow-worktree-claim.sh |
| #1881 | flow-worktree-guard.sh; check-ignored-additions.sh |
| #1883 | nit-store-resolve.sh |
| #1884 | flow-plan-record.py declare-salvage |
| #1885 | flow-finish-gate.sh |

Reviewed #1870's matching-helper/Kind/count/footer contract and #1878's
unchanged-scanner history control as separate release items; the latter is a
patch, not another driver row. Template regeneration reports zero changes;
current rendered counts/caps are codex 9789, qwen 11001, gemma 11610. Parity
checks 24 items / 72 pairs with zero missing; version check confirms five
active sites, command and CLAUDE budgets, Unicode and relative links passed.

Repeated old-version grep still has the same eleven historical hits. Updated
line positions for the original accounting: CHANGELOG.md:7 and :115;
README.md:229 and :245; issue-1278.as-read.md:281; issue-1278.md:98,105,106,108,109,111.
No active old-version site remains. Final review/receipt and the load-checked,
orchestrator-confirmed single full gate still follow this refresh. No tag.


Independent review pass 1 on f91737a1 used the audited helper and exact canonical
patch. Runtime reviewer codex/gpt-6.2-sol differs from implementer; scope
diff-only, network unverified, local repository credentials absent; reviewer
shell tools disabled. No instrument changed, so red cases proposed 0.

One LOW plan-bookkeeping finding was rejected with direct committed-source
evidence: reviewer claimed the two README hits were lines 230/246 rather than
229/245. Reading git show f91737a1:README.md confirms 229 contains the previous
release reference and 245 its heading; 230/246 are blank. Current file and
committed source agree, as does git grep. The existing accounting is correct;
no content fix or second review is warranted. Receipt records rejected 1,
accepted/deferred 0; no transcript was edited.
