"""No run-closing surface removes a worktree by hand (issues #899, #973).

WHAT THIS PINS AND WHY THE SHAPE
---------------------------------------------------------------------------
#899 made `/flow:merge` refuse when `worktree-remove.sh` is absent, because a
raw `git worktree remove --force` bypasses the claim check, the occupancy
check, the uncommitted-work check and the unpushed-commits check in one line -
and a guard that is absent is indistinguishable from a guard that passed.

The fix landed in `merge.md` only. `/flow:auto` - the lane almost every run
actually takes - still carried the raw form until #973.

MEMBERSHIP IS DERIVED, THE UNIVERSE IS PINNED. The invoker set is discovered
from the tree rather than listed, so a TENTH command document that starts
calling the helper is covered the day it lands. `test_the_invoker_set_is_not_
vacuous` pins the known nine separately, so a glob that silently stops matching
goes RED instead of making every assertion below vacuously true.

THE CONTROL IS EXECUTED, NOT ASSERTED. These are prompt documents, so the
honest thing to check is what the instruction DOES. The refusal block is
extracted from the shipped markdown and run twice against a fake HOME - helper
present, helper absent - and both verdicts are required. Asserting only the
absent case cannot tell a correct refusal from a block that always refuses.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
COMMANDS = REPO / ".claude" / "commands"
HELPER_REL = ".claude/scripts/worktree-remove.sh"

# A raw removal instruction: `git worktree remove ... --force` that is NOT a
# call to the guarded helper. This is the defect, in the form it actually took.
# A raw removal instruction. Anchored at the start of the line, so the guarded
# helper invocation (`~/.claude/scripts/worktree-remove.sh ... --force`) never
# matches - it does not begin with `git`.
#
# The first cut carried a negative lookahead for "worktree-remove.sh" ANYWHERE
# on the line, which Codex showed let `git worktree remove "$WT" --force  #
# worktree-remove.sh missing` through: the verdict depended on neighbouring
# comment text rather than on the command being executed. Removed.
RAW_REMOVAL = re.compile(r"^\s*git\s+worktree\s+remove\b[^\n]*--force", re.M)

# THE UNIVERSE. Derived membership is checked against this floor.
KNOWN_INVOKERS = {
    Path(".claude/commands/cpp/init.md"),
    Path(".claude/commands/cpp/status.md"),
    Path(".claude/commands/cpp/update.md"),
    Path(".claude/commands/flow/auto.md"),
    Path(".claude/commands/flow/cleanup.md"),
    Path(".claude/commands/flow/doctor.md"),
    Path(".claude/commands/flow/merge.md"),
    Path(".claude/commands/flow/start.md"),
    Path(".claude/commands/flow/wave.md"),
}

# The two surfaces that must carry the refusal, because they are the two that
# REMOVE a worktree as part of closing a run.
REFUSING_SURFACES = (
    Path(".claude/commands/flow/auto.md"),
    Path(".claude/commands/flow/merge.md"),
)

# EXCLUSIONS CARRIED AS DATA, WITH THEIR REASON (#973 gate condition).
# Each entry is a string that must still be present, and why it is NOT an
# instance of this class. If one of these stops matching, the exclusion has
# gone stale and someone must re-derive it rather than trusting a comment in a
# closed PR. This is the difference between an audited exclusion and a silent
# one.
JUSTIFIED_EXCLUSIONS = (
    (
        Path(".claude/commands/flow/merge.md"),
        "# Inline fallback (helper not installed): same linked-worktree guard.",
        "This fallback is for gh-pr-merge.sh, not worktree removal. It runs "
        "`gh pr merge` and `git push origin --delete` and touches no local work.",
    ),
    (
        Path(".claude/commands/flow/merge.md"),
        'git branch -D "$BRANCH" 2>/dev/null || true',
        "The no-worktree case, AFTER a merge. #899 deliberately kept it: with "
        "no worktree there is nothing for the helper to guard and no "
        "uncommitted work to destroy.",
    ),
    (
        Path(".claude/commands/flow/cleanup.md"),
        "declines\nto pass `--force` or `--steal`",
        "cleanup.md delegates every removal to the helper and explicitly "
        "forbids the override flags. No raw fallback exists to fix.",
    ),
    (
        Path(".claude/commands/flow/wave.md"),
        "Never clear it with `--force` or `--steal`",
        "Same as cleanup.md: delegation plus an explicit prohibition, at wave "
        "scale where a loop over every worktree is #889's path reopened.",
    ),
)


def discover_helper_invokers(root: Path = COMMANDS) -> list[Path]:
    """Command documents that invoke the worktree-removal helper.

    Takes a root so the negative control can actually EXERCISE it. The first
    cut hard-coded COMMANDS and its "negative control" asserted a literal
    string it had just written did not contain the helper name - a tautology
    that never called this function, so a matcher returning every file would
    have passed it.
    """
    found: list[Path] = []
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*.md")):
        try:
            if "worktree-remove.sh" in path.read_text(encoding="utf-8"):
                found.append(path)
        except (OSError, UnicodeDecodeError):
            continue
    return found


def all_command_documents(root: Path = COMMANDS) -> list[Path]:
    """EVERY command document, independent of whether it mentions the helper.

    The raw-removal assertion runs over THIS set, not over the invoker set.
    Codex found that scanning only helper-mentioning documents meant a NEW
    command carrying nothing but `git worktree remove --force` was never
    examined, while all nine membership assertions stayed satisfied - the scan
    depended on the presence of the safe alternative to notice the unsafe one.
    """
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.md"))


def refusal_block(surface: Path) -> str:
    """The shipped bash block, lifted verbatim from the markdown."""
    text = (REPO / surface).read_text(encoding="utf-8")
    for match in re.finditer(r"```bash\n(.*?)```", text, re.S):
        if "cleanup_refused=0" in match.group(1):
            return match.group(1)
    return ""


INVOKERS = [p.relative_to(REPO) for p in discover_helper_invokers()]
ALL_DOCS = [p.relative_to(REPO) for p in all_command_documents()]


def test_the_scanned_document_set_is_not_vacuous() -> None:
    """Floor for the set the RAW-REMOVAL check runs over.

    Codex found the raw scan parametrized over ALL_DOCS while only the invoker
    set had a floor: if `all_command_documents()` returned [], pytest would
    silently generate ZERO raw-removal cases and the suite would stay green
    having checked nothing. A parametrized test over an empty list does not
    fail - it disappears.
    """
    found = set(ALL_DOCS)
    assert found, "no command document discovered - the raw-removal scan checks nothing"
    missing = KNOWN_INVOKERS - found
    assert not missing, f"known command documents not scanned: {sorted(map(str, missing))}"


def test_the_raw_removal_pattern_detects_and_discriminates(tmp_path: Path) -> None:
    """POSITIVE control on the pattern itself, both forms, plus a safe counter-case.

    Without this, replacing RAW_REMOVAL with a never-matching regex passes
    every raw-removal assertion in this file - the trailing-comment fix would
    be unprotected by anything. Asserting only that clean documents pass cannot
    tell a working detector from one that detects nothing.
    """
    bare = 'git worktree remove "$WORKTREE_PATH" --force'
    commented = 'git worktree remove "$WORKTREE_PATH" --force  # worktree-remove.sh missing'
    indented = '   git worktree remove "$WT" --force --quiet'
    for bad in (bare, commented, indented):
        assert RAW_REMOVAL.search(bad), f"pattern misses a raw removal: {bad!r}"

    safe = '~/.claude/scripts/worktree-remove.sh "$WORKTREE_PATH" --force --delete-branch'
    prose = 'It used to run `git worktree remove --force` plus `git branch -D` directly.'
    for good in (safe, prose):
        assert not RAW_REMOVAL.search(good), f"pattern fires on a safe line: {good!r}"


def test_the_invoker_set_is_not_vacuous() -> None:
    """Membership floor: non-empty AND complete.

    A zero here makes every per-surface assertion below vacuously true, which
    is the defect `docs/agents/detector-contracts.md` exists to name.
    """
    found = set(INVOKERS)
    assert found, "no helper invoker discovered - the scan has stopped matching"
    missing = KNOWN_INVOKERS - found
    assert not missing, f"known invokers no longer discovered: {sorted(map(str, missing))}"


def test_the_scan_reaches_where_a_new_invoker_would_land() -> None:
    """Aimed where a new command document actually appears, proved by planting one."""
    probe_dir = COMMANDS / "_worktree_refusal_probe_"
    probe = probe_dir / "probe.md"
    probe_dir.mkdir(parents=True, exist_ok=False)
    try:
        probe.write_text("# probe\n\nCalls worktree-remove.sh somewhere.\n", encoding="utf-8")
        assert probe in discover_helper_invokers(), (
            "a new command document invoking the helper would not be discovered"
        )
    finally:
        probe.unlink(missing_ok=True)
        probe_dir.rmdir()


def test_discovery_separates_a_helper_document_from_an_unrelated_one(tmp_path: Path) -> None:
    """Negative control, EXECUTED against discovery on both kinds of input."""
    (tmp_path / "unrelated.md").write_text("# Notes\n\nNo helper here.\n", encoding="utf-8")
    assert discover_helper_invokers(tmp_path) == [], "the matcher matches everything"

    (tmp_path / "invoker.md").write_text(
        "# Doc\n\nCalls ~/.claude/scripts/worktree-remove.sh here.\n", encoding="utf-8")
    assert discover_helper_invokers(tmp_path) == [tmp_path / "invoker.md"], (
        "the matcher does not find a document that genuinely invokes the helper"
    )


@pytest.mark.parametrize("surface", ALL_DOCS, ids=str)
def test_no_command_document_instructs_a_raw_forced_removal(surface: Path) -> None:
    """THE ASSERTION #973 EXISTS FOR.

    Derived from the tree, so a tenth document that adds a raw fallback fails
    this on the day it lands rather than being found by the next downstream
    repo to import it - which is how #973 itself surfaced.
    """
    text = (REPO / surface).read_text(encoding="utf-8")
    hits = [m.group(0).strip() for m in RAW_REMOVAL.finditer(text)]
    assert not hits, (
        f"{surface} instructs a raw forced worktree removal, bypassing every "
        f"guard in worktree-remove.sh: {hits}"
    )


@pytest.mark.parametrize("surface", REFUSING_SURFACES, ids=str)
def test_the_refusal_sets_state_the_report_can_read(surface: Path) -> None:
    """A refusal that only prints is an owner item nobody receives (#965, #973)."""
    block = refusal_block(surface)
    assert block, f"{surface} carries no refusal block"
    assert "cleanup_refused=1" in block, (
        f"{surface}'s refusal sets no state the closing report can consume - "
        f"stderr is not a channel the report block reads"
    )
    assert "|| cleanup_refused=1" in block, (
        f"{surface}'s non-zero status is not EXPLICITLY tolerated at the call "
        f"site; a block that continues only because no `set -e` is in scope is "
        f"one `set -e` away from silently becoming an abort"
    )


def test_both_surfaces_ship_the_same_form() -> None:
    """Two refusal forms in a generated-mirror family read as a generator bug."""
    blocks = {s: refusal_block(s) for s in REFUSING_SURFACES}
    first, *rest = blocks.values()
    assert all(b == first for b in rest), (
        "the refusal forms have diverged between "
        f"{', '.join(str(s) for s in blocks)}"
    )


def test_doctor_states_the_consequence_rather_than_a_fallback() -> None:
    """The diagnostic must say what is TRUE, not merely stop saying what is false.

    doctor.md claimed an inline fallback "covers cleanup". That stopped being
    true for merge at #899 and for auto at #973; deleting the clause would
    leave a WARN with no account of what a missing helper now costs.
    """
    text = (REPO / ".claude/commands/flow/doctor.md").read_text(encoding="utf-8")
    assert "fallback covers cleanup" not in text, "doctor.md still claims a fallback covers cleanup"
    assert "REFUSE" in text, "doctor.md does not say what actually happens when the helper is absent"


@pytest.mark.parametrize(
    "surface,marker,reason",
    JUSTIFIED_EXCLUSIONS,
    ids=[f"{s.name}:{r[:28]}" for s, _, r in JUSTIFIED_EXCLUSIONS],
)
def test_each_justified_exclusion_still_holds(surface: Path, marker: str, reason: str) -> None:
    """An exclusion nobody can re-check is indistinguishable from an oversight."""
    text = (REPO / surface).read_text(encoding="utf-8")
    assert marker in text, (
        f"the justified exclusion in {surface} no longer matches, so its reason "
        f"may have gone stale and must be re-derived. Recorded reason: {reason}"
    )


def report_block(surface: Path) -> str:
    """The closing-report reader, lifted from the same markdown."""
    text = (REPO / surface).read_text(encoding="utf-8")
    for match in re.finditer(r"```bash\n(.*?)```", text, re.S):
        if "flow-cleanup-refused.d" in match.group(1) and "for m in" in match.group(1):
            return match.group(1)
    return ""


def _fake_repo(tmp_path: Path) -> Path:
    main_repo = tmp_path / "main"
    main_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main_repo, check=True,
                   capture_output=True)
    return main_repo


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="bash and git are required to execute the shipped block",
)
@pytest.mark.parametrize("surface", REFUSING_SURFACES, ids=str)
@pytest.mark.parametrize("helper_present", [True, False], ids=["helper-present", "helper-absent"])
def test_the_shipped_block_behaves_both_ways(
    surface: Path, helper_present: bool, tmp_path: Path
) -> None:
    """TWO-SIDED, EXECUTED, and across TWO SEPARATE SHELLS.

    The cleanup block and the report block are lifted from the shipped markdown
    and run as independent processes with NO inherited variables - which is how
    the real run invokes them. An earlier cut set MAIN_REPO and WORKTREE_PATH
    immediately before executing and read the marker from Python, which hid the
    fact that the block depended on state no later call would have.

    Asserting only the absent case cannot tell a correct refusal from a block
    that refuses unconditionally, so both verdicts are required.
    """
    block = refusal_block(surface)
    assert block, f"{surface} carries no refusal block"

    home = tmp_path / "home"
    (home / ".claude" / "scripts").mkdir(parents=True)
    main_repo = _fake_repo(tmp_path)
    worktree = tmp_path / "repo-issue-42-slug"
    invoked = tmp_path / "invoked.log"

    if helper_present:
        helper = home / HELPER_REL
        helper.write_text(
            f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{invoked}"\nexit 0\n',
            encoding="utf-8")
        helper.chmod(0o755)

    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    # The absence this test rests on (#933). The block under test must locate
    # the helper through HOME; if `worktree-remove.sh` were also resolvable on
    # the constructed PATH, the block could find it there and this would pass
    # without ever exercising the HOME derivation it exists to prove.
    # Keyed on env["PATH"] rather than the literal so the check follows the
    # value actually used.
    assert shutil.which(Path(HELPER_REL).name, path=env["PATH"]) is None, (
        "the helper must not be reachable via PATH, or the HOME lookup is untested"
    )

    # --- SHELL 1: cleanup. Only WORKTREE_PATH is supplied; MAIN_REPO must be
    # derived by the block itself from the cwd.
    cleanup = subprocess.run(
        ["bash", "-c", f'WORKTREE_PATH="{worktree}"\n{block}\necho "REFUSED=$cleanup_refused"'],
        capture_output=True, text=True, cwd=main_repo, env=env,
    )
    out = cleanup.stdout + cleanup.stderr
    marker_dir = main_repo / ".git" / "flow-cleanup-refused.d"

    if helper_present:
        assert "REFUSED=0" in out, f"helper present but the block refused: {out}"
        assert "REFUSING" not in out, f"helper present but the refusal fired: {out}"
        calls = invoked.read_text(encoding="utf-8").splitlines() if invoked.exists() else []
        assert len(calls) == 1, f"expected exactly one helper invocation, got {calls}"
        assert "--force" in calls[0] and "--delete-branch" in calls[0], (
            f"the helper ran without the flags this step relies on: {calls[0]}")
        assert not list(marker_dir.glob("*")) if marker_dir.exists() else True, (
            "a successful removal left a refusal marker behind")
        return

    assert "REFUSED=1" in out, f"helper absent but no refusal recorded: {out}"
    assert "REFUSING" in out, f"helper absent but nothing was reported: {out}"
    markers = sorted(marker_dir.glob("*")) if marker_dir.exists() else []
    assert len(markers) == 1, f"expected exactly one marker, got {markers}"
    assert markers[0].name == worktree.name, (
        f"marker is not scoped to this worktree: {markers[0].name}")

    # --- SHELL 2: the report. A NEW process, nothing inherited. This is the
    # handoff the owner item actually depends on.
    report = report_block(surface)
    assert report, f"{surface} documents no report-side reader"
    reported = subprocess.run(
        ["bash", "-c", report], capture_output=True, text=True, cwd=main_repo, env=env,
    )
    assert str(worktree) in reported.stdout, (
        f"the report did not name the worktree it must hand the owner; it can "
        f"only know it from the marker's CONTENTS: {reported.stdout!r}")
    assert not list(marker_dir.glob("*")), "the report did not consume the marker"


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="bash and git are required to execute the shipped block",
)
def test_a_concurrent_run_does_not_erase_a_pending_refusal(tmp_path: Path) -> None:
    """Two runs, interleaved. A shared marker path made this a race (#973).

    Run A refuses and its owner item is still pending. Run B then starts
    cleanup on a DIFFERENT worktree. B's `rm -f` must clear only B's entry: a
    single shared marker file meant B silently destroyed A's pending item
    before anyone read it.
    """
    block = refusal_block(REFUSING_SURFACES[0])
    home = tmp_path / "home"
    (home / ".claude" / "scripts").mkdir(parents=True)
    main_repo = _fake_repo(tmp_path)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LC_ALL": "C"}
    # The absence this test rests on (#933). The block under test must locate
    # the helper through HOME; if `worktree-remove.sh` were also resolvable on
    # the constructed PATH, the block could find it there and this would pass
    # without ever exercising the HOME derivation it exists to prove.
    # Keyed on env["PATH"] rather than the literal so the check follows the
    # value actually used.
    assert shutil.which(Path(HELPER_REL).name, path=env["PATH"]) is None, (
        "the helper must not be reachable via PATH, or the HOME lookup is untested"
    )
    marker_dir = main_repo / ".git" / "flow-cleanup-refused.d"

    for name in ("repo-issue-1-a", "repo-issue-2-b"):
        subprocess.run(
            ["bash", "-c", f'WORKTREE_PATH="{tmp_path / name}"\n{block}'],
            capture_output=True, text=True, cwd=main_repo, env=env,
        )

    names = sorted(m.name for m in marker_dir.glob("*"))
    assert names == ["repo-issue-1-a", "repo-issue-2-b"], (
        f"a concurrent run destroyed a pending owner item: {names}")
