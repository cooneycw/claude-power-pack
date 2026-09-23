# Flow run record - issue #1185

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1185
- Base SHA:          5a4d7fc
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          CPP-improvements-orch (wave claude-improvements orchestrator,
                     policy rev 3, authority-model orchestrator-only) - verdict
                     GO-WITH-CONDITIONS, 2026-09-22
- Recorded at:       2026-09-22T11:20:00Z

## Section B evidence

- commits since 2026-09-21T18:49:42Z touching scripts/flow-helpers-install.sh,
  scripts/install-drift.sh, scripts/codex-skill-sync.py: exactly one, `e9a58b6`
  (#1195, the gate-lib migration). It adds no integrity verification.
- merged PRs since: #1197 #1196 #1195 #1194 #1193 #1188 #1187 #1186 #1184 #1183
  #1181 #1179 #1177 #1176 #1174. None touches integrity.
- duplicate / superseding issues: none. `gh issue list --state all --search
  "integrity tamper digest sha256"` returns only #1185 and #864 (the nit store).
- the issue's own 0/0/0 claim RE-MEASURED at this base rather than inherited,
  because it was filed before #1195 landed: sha256/hashlib/digest occurrences are
  still 0/0/0 in all three scripts and 0 in both bundled copies of the installer.
- the defect REPRODUCED at this base, not argued from the code:
  codex/skills/flow-doctor/scripts/worktree-remove.sh, canonical d57ee08d00f1
  (the digest the issue names), tampered 5136d74a767903e6 -> installs with
  `FLOW_HELPERS: installed` exit 0, injected line reaches the installed copy, and
  a subsequent `--check` reports `FLOW_HELPERS: ok`.

## Section C - the approved plan

Two commits, kept separate under a pre-committed stopping rule: if the orphan
axis needs anything beyond install-drift.sh, its test and its control, STOP and
return to the orchestrator rather than growing the commit.

### Commit 1 - #1185, integrity verification of a bundled helper

1. `scripts/codex-skill-sync.py` - when writing a skill bundle, also write
   `<skill>/scripts/SHA256SUMS` covering every script bundled into it.
2. `scripts/flow-helpers-install.sh` - verify each source file against that
   manifest before installing or comparing. TWO DISTINCT verdicts, never
   collapsed into one word, distinct through to the exit code: `tampered`
   (manifest present, bytes disagree) and `unverifiable-source` (a manifest is
   expected but unreadable, or no digest tool exists). Both refuse the whole run.
   Provenance gains `FLOW_HELPERS_MANIFEST:` so "no manifest" is REPORTED rather
   than silently read as verified.
3. `tests/test_flow_helpers_install.py` - a tampered source is refused; a bundle
   with its manifest deleted is refused; a checkout source with no manifest
   behaves as it does today.
4. `tests/test_codex_skill_sync.py` - the manifest exists per bundle, covers every
   bundled script, and changes when a bundled script changes.
5. `controls/flow-helpers-install` - the committed negative control. GOOD: an
   intact bundle installs. BAD: the issue's own tampered worktree-remove.sh case.
   BAD: manifest deleted from a bundle.

### Commit 2 - the orphan axis in install-drift.sh

6. `scripts/install-drift.sh` - add the orphan pass on its own reported line. The
   defect is at :245, NOT :240. A DIFFERENT PREDICATE PER SIDE: installed side
   `[ -f "$i" ] || [ -L "$i" ]` (a shape question), source side `[ -e "$src" ]`
   (an existence question).
7. `tests/test_install_drift.py` - the dangling symlink is reported; `__pycache__`
   is not, including on a fresh-clone-shaped checkout where only the install side
   has one. Assert MEMBERS, never counts.
8. `controls/install-drift` - GOOD and BAD cases for the orphan axis.

Scope: 6 tracked files + 2 new control directories, ~400-550 lines, plus generated
`SHA256SUMS` under `codex/skills/**` (lane-exempt wave-wide, not declared).

### Named risks

1. **The manifest ships inside the bundle it certifies.** It detects accidental
   corruption, partial tampering, and post-build modification. It does NOT detect
   a coherently regenerated bundle, and it says nothing about ARRIVAL - that needs
   a signature checked against a key outside the bundle. ACCEPTED as a declared
   limit, to be stated in the code, in the control's `limits`, and in the PR body.
2. **Fail-closed could refuse a legitimate legacy cache.** Requiring a manifest
   for every `SOURCE_KIND=plugin` source would also refuse the `CLAUDE_PLUGIN_ROOT`
   migration path. Scoped instead to an actual bundle, detected by a sibling
   `SKILL.md` beside `scripts/`.
3. **`sha256sum` may be absent.** Its absence lands in `unverifiable-source`, never
   in a silent pass: a guard that is absent must not look like a guard that passed.

### Declared dependency, deliberately NOT in either commit

Two shared inventory files hold declarations this change falsifies:
`.claude/verify-coverage.json:127` (`flow-helpers-install.sh` as
`"class": "not-a-checker"`, `"it issues no verdict"` - already false at HEAD) and
`docs/decisions/0008-instrument-negative-control-bound.md:543` (the exemption
justified by "the state they produce is re-derived by the drift and parity
checks", which is the sentence #1185 refutes). Both are held exclusively by
worker-A under its #1180 grant.

Census non-membership is NAMED, not FAILED - `failing` keys only on
`verdict != PASS`, `tracking == UNTRACKED`, `provenance == MISMATCH` - so the code
lands green either way and this is a correctness-of-record question rather than a
blocker. The correction is a THIRD step gated on the orchestrator's
`inventory-window`, to be requested when commits 1 and 2 are ready. Not folded
into either commit, and not raised with worker-A directly.
