# Flow run record - issue #1263

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1263
- Base SHA:          4deccd2
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          owner (cooneycw), interactive reply "approved"
- Recorded at:       2026-09-27T00:00:00Z

## Section B evidence

- Commits on the named paths since filing: 2ae3c47 (#1279), bdd2d14 (#1283) - neither touches the live items.
- Merged PRs since filing: #1284, #1283, #1280, #1279, #1275, #1274, #1270, #1255 - none addresses items 1, 3, 5, 6/7, 11.
- Prior delivery: 250d56f (#1218) unconditional codex re-sync (item 4); 4c58496 (#828) missing-helper axis and
  cbd7dcf (#1201) orphan axis in install-drift (items 2, 9); measured 93 executables / 93 links / 0 missing.
- Duplicate: #1256 owns item 8 (conflicting scopes), with owner decisions pending.
- Item 1 is design-blocked (candidate "skipped>0 and marked=0" fires permanently on this host: 0 marked, 13 skipped) - returned to the nit store.
- Item 10 largely superseded by #1218; residual is hand edits outside a flow run.

## Section C - the approved plan

1. `scripts/cpp-host-write.sh` - new `unlink-orphan <dir> <name>` subcommand: removes only a dangling, install-shaped symlink; refuses live links, plain files, non-install shapes; honours the defer-set; exits 0/3/1.
2. `.claude/commands/cpp/update.md` - Step 5b prune half driven by `install-drift.sh --json` orphaned_helpers, user-confirmed; Tier 6/7 model check gated on reachability; Step 3.5 compares against the literal pre-pull SHA, not ORIG_HEAD; Step 10 re-reads HEAD and reports the finishing SHA.
3. `.claude/commands/cpp/init.md` - same Tier 6/7 reachability gating so init and update give the identical diagnosis.
4. `lib/vendor.py` - MarkerSectionLayout.remote() fetches at the resolved revision via source.repo + source.path.
5. `tests/test_cpp_host_writes.py` - negative control: an upstream-deleted script's installed symlink is named by install-drift AND pruned; live/host-owned/neighbour entries survive.
6. `tests/test_vendor_module.py` - two-read hazard: moving URL returns B, SHA URL returns A; the vendored core must be A.
7. `tests/test_model_presence_check.py` - executed Tier 6/7 blocks against an unreachable endpoint report no "missing" line.
8. `CHANGELOG.md` - [Unreleased] entry.

Scope: ~8 hand-edited files, ~300-400 lines, plus regenerated codex/skills mirrors.
Risks: prune is a host delete (narrowed to dangling install-shaped links, user-confirmed);
existing text-pinning tests may need adjustment; eli5-drift advisory fetch URL changes.
