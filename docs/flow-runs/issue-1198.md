# Flow run record - issue #1198

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1198
- Base SHA:          5a4d7fcd35d252420e5e69151db6c1ba5946de08
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the session owner (replied "approved" to the Step 3 gate)
- Recorded at:       2026-09-22T10:56:04Z

## Section B evidence

- Commits since the issue was filed (2026-09-22T10:50:40Z) touching
  `.claude/commands/cpp/`, `scripts/cpp-host-write.sh` or
  `scripts/check-cpp-host-writes.py`: **none**.
- PRs merged since filing: **none**.
- Related issues inspected: #1132 (closed, created the seam), #1139 (closed,
  made it deferrable), #1150 (closed, certified declarations by observation),
  #1142 (closed, a different init.md write bug). No duplicate; none addresses
  whether the seam's VERDICT is read.

Reframing accepted at the gate: the filed title names one cause (exit 127) of
three - exit 3 (deferred) and exit 1 (failed) produce the same false checkmark,
measured - and one document of two (init.md has 14 sites to update.md's 6).

## Section C - the approved plan

1. `.claude/commands/cpp/init.md` - bootstrap the seam through itself via the
   checkout path before first use; read the verdict at all 14 sites and report
   wrote/deferred/failed/unreachable distinctly.
2. `.claude/commands/cpp/update.md` - same at its 6 sites.
3. `scripts/check-cpp-host-writes.py` - add a second check: a seam invocation
   whose verdict is never read, followed by an unconditional success claim, is
   a red.
4. `controls/cpp-host-writes/cases/bad-unguarded-seam-call` - committed red
   case: calls the seam, claims success unconditionally.
5. `controls/cpp-host-writes/cases/good-guarded-seam-call` - committed green
   case: same call, verdict read.
6. `controls/cpp-host-writes/anchors` - an anchor proving the existing
   form-scan does NOT already catch case 4.
7. `controls/cpp-host-writes/control.json` - register the new cases and why.
8. `tests/test_cpp_host_writes.py` - control runner plus a regression test that
   FAILS against the pre-fix documents.
9. `CHANGELOG.md` - [Unreleased] entry.
10. `codex/skills` - regenerated mirrors via codex-skill-resync.sh, never
    hand-edited.

Scope: Medium - two large documents, ~20 edit sites, one gate, one control, one test.

Risks:
- Allowlist friction (#581): the bootstrap line will not match a permission
  prefix rule and may prompt once per run. Bootstrap-once-then-keep-bare-calls
  was chosen so the other 19 sites keep their prompt-free lane.
- The bootstrap is a write that installs the writer; it must satisfy
  check-cpp-host-writes.py's form scan without a carve-out. To be verified, not
  assumed.
- Mirror parity: both documents are mirrored into codex/skills/; an unsynced
  mirror reds the parity gates.
