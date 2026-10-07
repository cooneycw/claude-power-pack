"""Tests for `scripts/mutation-probe.py` (issue #970).

The committed control (`controls/mutation-probe`) covers the ONE property the
tool exists for: does a battery's verdict CHANGE when a declared protection is
removed. These tests cover the paths that control deliberately does not reach -
the refusals - and the safety property that makes the tool usable at all.

WHY THE REFUSALS LIVE HERE RATHER THAN IN A COMMITTED CASE. ADR 0008's carve-out:
a unit test whose failure the surrounding suite would catch does not need its own
committed input, because the suite's green is what is load-bearing. Each refusal
below is a branch in one file, exercised by a test in this file, and a regression
in any of them reddens `make test`. The control exists for the property no suite
can establish by reading, which is a different question.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "mutation-probe.py"

GATE = '''#!/usr/bin/env python3
"""A toy gate with one protection."""
import pathlib
import sys

TOKEN = "FORBIDDEN"


def main() -> int:
    root = pathlib.Path(sys.argv[sys.argv.index("--root") + 1])
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            if TOKEN not in line:
                continue
            if line.strip().startswith("#"):
                continue
            print("TOY-FINDING: " + path.name, file=sys.stderr)
            return 1
    print("toy-gate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

BATTERY = '''#!/usr/bin/env python3
"""A miniature battery: run each case, refuse when an observed verdict differs."""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "controls" / "toy" / "control.json").read_text())


def main() -> int:
    failed = 0
    for case in SPEC["cases"]:
        proc = subprocess.run(
            [sys.executable, str(ROOT / SPEC["gate"]), "--root",
             str(ROOT / "controls" / "toy" / case["input"])],
            capture_output=True, text=True, check=False)
        observed = "GOOD" if proc.returncode == 0 else "BAD"
        if observed != case["expect"]:
            failed += 1
            print("TOY-BATTERY-FAIL: " + case["name"], file=sys.stderr)
    if failed:
        return 1
    print("toy-battery: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _tree(tmp_path: Path, *, good_case: bool, mutations: list[dict]) -> Path:
    """A self-contained repository with a toy gate, a battery and a manifest."""
    root = tmp_path / "tree"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "toy-gate.py").write_text(GATE)
    (root / "scripts" / "toy-battery.py").write_text(BATTERY)
    cases = root / "controls" / "toy" / "cases"
    (cases / "bad").mkdir(parents=True)
    (cases / "bad" / "input.txt").write_text("    FORBIDDEN\n")
    registered = [{"name": "bad", "input": "cases/bad", "expect": "BAD"}]
    if good_case:
        (cases / "good").mkdir(parents=True)
        (cases / "good" / "input.txt").write_text("    # FORBIDDEN in a comment\n")
        registered.append({"name": "good", "input": "cases/good", "expect": "GOOD"})
    (root / "controls" / "toy" / "control.json").write_text(json.dumps({
        "gate": "scripts/toy-gate.py",
        "battery": ["{python}", "scripts/toy-battery.py"],
        "cases": registered,
        "mutations": mutations,
    }))
    return root


COMMENT_REJECTION = {
    "name": "comment-rejection",
    "protection": "a commented-out occurrence is not an occurrence",
    "find": r'if line\.strip\(\)\.startswith\("#"\):',
    "replace": "if False:",
    "count": 1,
}


def _probe(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROBE), "--root", str(root), *extra],
        capture_output=True, text=True, check=False, timeout=300)


def test_a_battery_that_exercises_the_protection_reports_caught(tmp_path: Path) -> None:
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    result = _probe(root, "--strict")
    assert "MUTATION-CAUGHT: controls/toy/control.json::comment-rejection" in result.stdout
    assert result.returncode == 0


def test_a_battery_that_does_not_exercise_the_protection_reports_uncaught(tmp_path: Path) -> None:
    """The decorative finding, and the whole of issue #970 in one assertion.

    The two trees differ by ONE registered case. The GATE is byte-identical in
    both, so no amount of reading it separates them.
    """
    root = _tree(tmp_path, good_case=False, mutations=[COMMENT_REJECTION])
    result = _probe(root, "--strict")
    assert "MUTATION-UNCAUGHT: controls/toy/control.json::comment-rejection" in result.stdout
    assert result.returncode == 1


def test_a_declaration_that_matches_nothing_is_inapplicable_not_uncaught(tmp_path: Path) -> None:
    """The distinction that keeps a broken DECLARATION from reading as a broken BATTERY.

    Both produce a green battery under mutation. They need opposite responses:
    one says fix the manifest, the other says fix the controls. Collapsing them
    is the UNRESOLVED-versus-BLIND failure one directory over.
    """
    mutation = dict(COMMENT_REJECTION, find=r"this text is nowhere in the gate")
    root = _tree(tmp_path, good_case=True, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-INAPPLICABLE: controls/toy/control.json::comment-rejection" in result.stdout
    assert "matched 0 time(s)" in result.stdout
    assert "MUTATION-UNCAUGHT" not in result.stdout
    assert result.returncode == 1


def test_a_declaration_that_matches_too_often_is_inapplicable(tmp_path: Path) -> None:
    """An anchor matching twice is as wrong as one matching nothing (#1013's rule).

    Two substitutions where one was declared means the edit is not the edit that
    was reviewed, and whichever verdict follows is about a different mutation.
    """
    mutation = dict(COMMENT_REJECTION, find=r"import", count=1)
    root = _tree(tmp_path, good_case=True, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-INAPPLICABLE" in result.stdout
    assert "the declaration requires 1" in result.stdout
    assert result.returncode == 1


def test_a_mutation_that_breaks_the_syntax_is_refused_not_scored(tmp_path: Path) -> None:
    """Without this, deleting the file is the cheapest way to certify a battery.

    Everything goes red, every mutation reads CAUGHT, and the proof rests on an
    edit that never produced an instrument.
    """
    mutation = dict(COMMENT_REJECTION, replace="if False")  # missing colon
    root = _tree(tmp_path, good_case=True, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-INAPPLICABLE" in result.stdout
    assert "does not parse" in result.stdout
    assert "MUTATION-CAUGHT" not in result.stdout
    assert result.returncode == 1


def test_an_already_red_battery_is_unresolved_not_caught(tmp_path: Path) -> None:
    """Named in controls/mutation-probe/control.json as the ACCEPTED gap's cover.

    A mutation scored against a battery that was already failing reads CAUGHT for
    free, and the tool would certify every declared protection of every broken
    instrument in the tree.
    """
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    # Break the battery BEFORE any mutation: the bad case stops being bad.
    (root / "controls" / "toy" / "cases" / "bad" / "input.txt").write_text("nothing here\n")
    result = _probe(root, "--strict")
    assert "MUTATION-UNRESOLVED" in result.stdout
    assert "already RED" in result.stdout
    assert "MUTATION-CAUGHT" not in result.stdout
    assert result.returncode == 1


def test_an_accepted_gap_needs_a_written_reason(tmp_path: Path) -> None:
    """`expect: uncaught` with no `why` is an oversight wearing an acceptance's name."""
    mutation = dict(COMMENT_REJECTION, expect="uncaught")
    root = _tree(tmp_path, good_case=False, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-INAPPLICABLE" in result.stdout
    assert "no `why`" in result.stdout
    assert result.returncode == 1


def test_an_accepted_gap_that_is_now_caught_reports_stale(tmp_path: Path) -> None:
    """The second direction, without which the acceptance field is a one-way fail-open.

    Every accepted entry would stay accepted forever, including the ones somebody
    has since closed - and the register would report a gap that no longer exists
    while nothing said so.
    """
    mutation = dict(COMMENT_REJECTION, expect="uncaught", why="no case reaches it",
                     blocked_by="input-cannot-be-committed")
    root = _tree(tmp_path, good_case=True, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-STALE: controls/toy/control.json::comment-rejection" in result.stdout
    assert result.returncode == 1


def test_an_accepted_gap_that_is_still_uncaught_is_not_a_failure(tmp_path: Path) -> None:
    """A STATED gap is the outcome this tool wants where no control can be written."""
    mutation = dict(COMMENT_REJECTION, expect="uncaught", why="no case can reach it",
                     blocked_by="input-cannot-be-committed")
    root = _tree(tmp_path, good_case=False, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-ACCEPTED: controls/toy/control.json::comment-rejection" in result.stdout
    assert result.returncode == 0


def test_an_absolute_gate_path_cannot_escape_the_sandbox(tmp_path: Path) -> None:
    """Counter-model review, HIGH, accepted (issue #970).

    `Path("/sandbox") / "/real/gate.py"` is `/real/gate.py` - pathlib treats an
    absolute right-hand side as a replacement, not a suffix. A manifest naming an
    absolute `gate` therefore had its mutation written into the REAL checkout
    while the battery ran against the sandbox copy: every verdict about a file
    the mutation never touched, and a weakened instrument left behind if the run
    is interrupted between write and restore.
    """
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "gate.py"
    victim.write_text(GATE)
    before = _witness(outside)

    manifest = root / "controls" / "toy" / "control.json"
    spec = json.loads(manifest.read_text())
    spec["gate"] = str(victim)
    manifest.write_text(json.dumps(spec))

    result = _probe(root, "--strict")
    # The safety claim FIRST: the refusal message is how it is refused, but the
    # property is that nothing outside the sandbox was written. Measured on the
    # pre-fix probe, this assertion is the one that fails.
    assert _witness(outside) == before, "a file outside the sandbox was written"
    assert "MUTATION-UNRESOLVED" in result.stdout
    assert "OUTSIDE the sandbox" in result.stdout
    assert result.returncode == 1


def test_a_dotdot_battery_cwd_cannot_escape_the_sandbox(tmp_path: Path) -> None:
    """The same escape through the other path the manifest supplies."""
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    manifest = root / "controls" / "toy" / "control.json"
    spec = json.loads(manifest.read_text())
    spec["battery_cwd"] = "../../.."
    manifest.write_text(json.dumps(spec))
    result = _probe(root, "--strict")
    assert "MUTATION-UNRESOLVED" in result.stdout
    assert "OUTSIDE this run's sandbox" in result.stdout
    assert result.returncode == 1


def test_a_battery_side_effect_cannot_certify_a_mutation(tmp_path: Path) -> None:
    """Counter-model review, MEDIUM, accepted (issue #970).

    With one sandbox shared across the baseline and every mutation, only the GATE
    was restored between runs. A battery that drops a marker on its first
    invocation and fails whenever that marker exists passes the baseline and then
    reports EVERY later mutation CAUGHT without the gate being consulted - a
    non-zero that cannot tell "this mutation" from "the previous run".

    The mutation declared here is one the battery genuinely does NOT cover, so
    the only thing that could turn it red is the contamination.
    """
    root = _tree(tmp_path, good_case=False, mutations=[COMMENT_REJECTION])
    (root / "scripts" / "toy-battery.py").write_text(
        "import pathlib\nimport sys\n"
        "marker = pathlib.Path(__file__).resolve().parents[1] / 'ran.marker'\n"
        "if marker.exists():\n"
        "    print('TOY-BATTERY-FAIL: a previous run was here', file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "marker.write_text('x')\n"
        "print('toy-battery: ok')\n"
    )
    result = _probe(root, "--strict")
    assert "MUTATION-UNCAUGHT" in result.stdout, result.stdout + result.stderr
    assert "MUTATION-CAUGHT" not in result.stdout


def test_a_battery_cwd_escaping_into_a_sibling_sandbox_is_refused(tmp_path: Path) -> None:
    """Counter-model review pass 2, accepted (issue #970).

    Checking containment once, against the BASELINE sandbox, let
    `battery_cwd: "../tree-1"` through - `tree-1/../tree-1` is `tree-1` - and
    every later mutation then ran its battery in the baseline's sandbox, against
    an UNMUTATED gate, while the probe reported verdicts about the mutation.
    """
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    manifest = root / "controls" / "toy" / "control.json"
    spec = json.loads(manifest.read_text())
    spec["battery_cwd"] = "../tree-1"
    manifest.write_text(json.dumps(spec))
    result = _probe(root, "--strict")
    assert "MUTATION-UNRESOLVED" in result.stdout
    assert "OUTSIDE this run's sandbox" in result.stdout
    assert "MUTATION-CAUGHT" not in result.stdout
    assert result.returncode == 1


def test_a_neighbouring_edit_after_the_baseline_cannot_change_a_verdict(tmp_path: Path) -> None:
    """Counter-model review pass 2, accepted (issue #970).

    Rebuilding each sandbox from the LIVE checkout makes every run a fresh
    sample of a tree other processes are editing. Here the battery itself edits
    the checkout on its first invocation, so a rebuilt sandbox would carry that
    edit alongside the mutation: the registered bad case stops being bad, the
    battery goes red because a NEIGHBOUR changed, and a mutation nothing caught
    is certified CAUGHT.

    The declared mutation is one this battery genuinely does NOT cover, so
    UNCAUGHT is the honest verdict and CAUGHT can only come from contamination.
    """
    root = _tree(tmp_path, good_case=False, mutations=[COMMENT_REJECTION])
    victim = root / "controls" / "toy" / "cases" / "bad" / "input.txt"
    # The battery still EVALUATES ITS CASES - it only also nudges the checkout on
    # the way past. A stand-in that merely wrote the file and exited 0 would
    # report UNCAUGHT whatever the probe did, which is a test that cannot fail:
    # measured, it passed against the unfixed probe too.
    (root / "scripts" / "toy-battery.py").write_text(
        "import pathlib\n"
        f"pathlib.Path({str(victim)!r}).write_text('no finding here\\n')\n"
        + BATTERY
    )
    result = _probe(root, "--strict")
    assert "MUTATION-UNCAUGHT" in result.stdout, result.stdout + result.stderr
    assert "MUTATION-CAUGHT" not in result.stdout


def test_a_zero_count_declaration_cannot_be_an_accepted_gap(tmp_path: Path) -> None:
    """Counter-model review, MEDIUM, accepted (issue #970).

    `count: 0` satisfied the count check against a pattern matching nothing, so a
    declaration naming a protection that does not exist ran the battery
    unchanged, reported ACCEPTED beside a written reason, and exited 0 under
    `--strict`. A mutation that removes no protection is not a mutation.
    """
    mutation = dict(COMMENT_REJECTION, find="NOT_PRESENT_ANYWHERE", count=0,
                    expect="uncaught", why="claims to be an accepted gap")
    root = _tree(tmp_path, good_case=True, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-ACCEPTED" not in result.stdout
    assert "MUTATION-INAPPLICABLE" in result.stdout
    assert "positive integer" in result.stdout
    assert result.returncode == 1


def test_a_replacement_that_changes_nothing_is_inapplicable(tmp_path: Path) -> None:
    """The count says the pattern MATCHED; only a byte comparison says it CHANGED.

    A `replace` equal to the text it matches substitutes the declared number of
    times and leaves the gate byte-identical, so the battery runs against an
    unmutated instrument and its green is read as a verdict about coverage.
    """
    mutation = dict(COMMENT_REJECTION,
                    replace='if line.strip().startswith("#"):')
    root = _tree(tmp_path, good_case=True, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-INAPPLICABLE" in result.stdout
    assert "BYTE-IDENTICAL" in result.stdout
    assert "MUTATION-CAUGHT" not in result.stdout
    assert result.returncode == 1


def test_no_manifest_at_all_is_unchecked_not_clean(tmp_path: Path) -> None:
    """A run that examined nothing must never exit 0 (the #952 rule)."""
    root = tmp_path / "empty"
    (root / "scripts").mkdir(parents=True)
    result = _probe(root)
    assert result.returncode == 1
    assert "UNCHECKED, not clean" in result.stderr


def test_a_named_manifest_that_is_absent_refuses(tmp_path: Path) -> None:
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    result = _probe(root, "--manifest", "controls/nope/control.json")
    assert result.returncode == 1
    assert "absent from this tree" in result.stderr


def test_a_manifest_with_no_mutations_is_counted_and_is_not_a_failure(tmp_path: Path) -> None:
    """"Nobody looked" is loud, visible and counted - never fatal (the #1060 rule).

    A gate that failed everything on day one is switched off inside a week, which
    is ADR 0009's oscillation arriving as the remedy rather than the problem.
    """
    root = _tree(tmp_path, good_case=True, mutations=[])
    result = _probe(root, "--strict")
    assert "MUTATION_PROBE_COVERAGE: 0 of 1 selected manifest(s) declare a mutation" in result.stdout
    assert result.returncode == 0


def _witness(root: Path) -> dict[str, tuple[str, int]]:
    """Content AND last-modification time, per file.

    The mtime is not decoration, and the first cut of this test omitted it. A
    probe that wrote the mutation into the REAL tree and then restored it in its
    `finally` leaves every byte identical - so a content-only witness reports a
    pristine tree about a tree that was weakened while a concurrent reader could
    see it, and about a run that leaves an instrument mutated if it is killed
    between the two writes. Measured: under a mutation redirecting the write
    from the sandbox to the tree, the content-only version of this test PASSED.
    """
    return {
        path.relative_to(root).as_posix():
            (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def test_the_working_tree_is_untouched_by_a_probe_run(tmp_path: Path) -> None:
    """THE SAFETY PROPERTY. This tool edits instrument source; if its sandboxing
    is wrong it is the most dangerous thing in the repository.

    Asserted over EVERY file of the tree, not just the mutated gate: a bug that
    wrote the mutation one directory across would leave the gate pristine and the
    assertion green.
    """
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    before = _witness(root)
    result = _probe(root, "--strict")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _witness(root) == before


def test_the_real_probe_reports_ok_on_its_covered_case_and_fails_on_its_decorative_one() -> None:
    """The committed pair, run directly rather than through the register.

    The register already runs this pair; running it here as well is the same
    second-opinion-from-a-different-process rule `controls/check-negative-controls`
    records about itself - a harness's own judgement of itself is not one.
    """
    covered = ROOT / "controls" / "mutation-probe" / "cases" / "covered"
    decorative = ROOT / "controls" / "mutation-probe" / "cases" / "decorative"
    good = _probe(covered, "--strict")
    bad = _probe(decorative, "--strict")
    assert good.returncode == 0, good.stdout + good.stderr
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert "MUTATION-UNCAUGHT" in bad.stdout
    assert "MUTATION-UNCAUGHT" not in good.stdout


def test_the_vendored_anchor_passes_the_decorative_tree_and_is_therefore_blind() -> None:
    """The anchor must MISS what the current probe catches, or it proves nothing."""
    anchor = ROOT / "controls" / "mutation-probe" / "anchors" / "0000000-ran-the-battery.py"
    decorative = ROOT / "controls" / "mutation-probe" / "cases" / "decorative"
    result = subprocess.run(
        [sys.executable, str(anchor), "--root", str(decorative), "--strict"],
        capture_output=True, text=True, check=False, timeout=300)
    assert result.returncode == 0, "the anchor caught the decorative tree, so it is not blind"
    assert "MUTATION-UNCAUGHT" not in result.stdout


def test_the_anchor_matches_its_recorded_digest() -> None:
    """A vendored artifact whose bytes are not pinned is a file, not evidence."""
    control = json.loads(
        (ROOT / "controls" / "mutation-probe" / "control.json").read_text())
    anchor = control["anchors"][0]
    path = ROOT / "controls" / "mutation-probe" / anchor["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == anchor["sha256"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_every_file_of_the_probes_control_is_tracked() -> None:
    """A control whose files are untracked discriminates here and is absent in a
    clean clone (issue #978). The green and the blindness look identical.

    `check=True` was wrong here and the probe found it: this module is COPIED
    into the probe's own sandbox and run there, and a tree that is not a git
    work tree makes `ls-files` exit 128 - an ERROR about the environment, raised
    from a test whose subject is tracking. The `which` guard does not cover it,
    because git being installed says nothing about this directory being a
    checkout. Unknown is reported as unknown.
    """
    inside = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True, check=False)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        pytest.skip(f"{ROOT} is not a git work tree, so tracking cannot be established")
    control_dir = ROOT / "controls" / "mutation-probe"
    on_disk = {
        path.relative_to(ROOT).as_posix()
        for path in control_dir.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    tracked = set(subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "controls/mutation-probe"],
        capture_output=True, text=True, check=False).stdout.split())
    assert on_disk - tracked == set()


def test_the_register_narrowing_selector_refuses_to_match_nothing() -> None:
    """`--control` is what lets the probe ask about ONE control, and a selector
    that silently selects nothing turns an empty run into a clean one."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-negative-controls.py"),
         "--root", str(ROOT), "--control", "controls/no-such-control", "--quiet"],
        capture_output=True, text=True, check=False, timeout=300)
    assert result.returncode == 1
    assert "matched no registration" in result.stderr
    assert "UNCHECKED, not clean" in result.stderr


def test_the_register_narrowing_selector_evaluates_only_the_named_control() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-negative-controls.py"),
         "--root", str(ROOT), "--control", "controls/mutation-probe", "--quiet"],
        capture_output=True, text=True, check=False, timeout=600)
    assert "NEGATIVE_CONTROL_REGISTERED: 1" in result.stdout
    gates = [line for line in result.stdout.splitlines()
             if line.startswith("NEGATIVE_CONTROL_GATE:")]
    assert gates == ["NEGATIVE_CONTROL_GATE: scripts/mutation-probe.py"]


# --------------------------------------------------------------------------- #
# The snapshot must carry a tracked SYMLINK, in both lanes (issue #959)
# --------------------------------------------------------------------------- #


def _build_sandbox(tmp_path: Path):
    """`build_sandbox` loaded from the probe, so the real function is exercised."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mutation_probe_under_test", PROBE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: the probe defines dataclasses under
    # `from __future__ import annotations`, and resolving those annotations
    # looks the module up in `sys.modules` by name. Without this the import
    # fails with a bare `AttributeError: 'NoneType' object has no attribute
    # '__dict__'` from dataclasses.py, which says nothing about the cause.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.build_sandbox


@pytest.mark.parametrize("git_lane", (True, False), ids=("git-lane", "wholesale-lane"))
def test_the_snapshot_preserves_a_tracked_dangling_symlink(
    tmp_path: Path, git_lane: bool
) -> None:
    """A DANGLING symlink is a legitimate tracked artifact, and both lanes lost it.

    `controls/flow-vantage` commits three on purpose: `readlink /proc/self/ns/pid`
    returns `pid:[4026531836]`, a string that is not a path, so the only faithful
    stand-in for that read is a symlink carrying that target. The probe's two
    snapshot lanes each mishandled it, in opposite and equally bad ways:

      * the GIT lane tested `src.is_file()`, which FOLLOWS the link - False for a
        dangling one - and skipped the path silently. The snapshot was missing a
        control's fixtures and the probe still reported `ok`. That is the
        "partial copy produces confident verdicts about a tree missing files
        nobody named" failure the OSError branch refuses, arriving through the
        branch that does not raise.
      * the WHOLESALE lane used `copytree` with the default `symlinks=False`,
        which DEREFERENCES: ENOENT, and the step dies. That lane is the one CI
        runs, because git is absent from the image by design - so the dev box
        never exercises it and the red arrived only after the push (measured:
        Woodpecker pipeline 2220, step `mutation-probe`).

    Both lanes are driven here, because a fix to one is invisible to the other.
    """
    if git_lane and shutil.which("git") is None:
        pytest.skip("requires git on PATH for the git-enumeration lane")

    source = tmp_path / "src"
    (source / "controls" / "case").mkdir(parents=True)
    (source / "controls" / "case" / "plain.txt").write_text("ordinary\n")
    link = source / "controls" / "case" / "ns-pid"
    link.symlink_to("pid:[4026531836]")
    # Precondition: the fixture really is the shape under test - a symlink whose
    # target does not resolve. Without this the test could pass over an
    # ordinary file and assert nothing about symlinks at all.
    assert link.is_symlink() and not link.exists(), "fixture must be a DANGLING symlink"

    if git_lane:
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "add", "-A"], check=True)
    else:
        # No repository, so `git ls-files` cannot enumerate and the probe falls
        # through to the wholesale copy - the CI lane, reproduced by absence
        # rather than by mocking.
        assert not (source / ".git").exists(), "fixture must NOT be a git repo"

    dest = tmp_path / "snapshot"
    ok, detail = _build_sandbox(tmp_path)(source, dest)
    assert ok, detail

    copied = dest / "controls" / "case" / "ns-pid"
    assert copied.is_symlink(), f"the snapshot lost the symlink ({detail})"
    import os

    assert os.readlink(copied) == "pid:[4026531836]"


# #1276 - one parser for control.json's `gate`, closed schema in this reader too


@pytest.mark.parametrize(
    ("gate", "why"),
    [
        ({"kind": "make-target", "file": "Makefile", "target": "t", "extra": 1}, "unknown key(s) extra"),
        ({"kind": "lib-module", "file": "Makefile", "target": "t"}, "not a known kind"),
        ({"kind": [], "file": "Makefile", "target": "t"}, "not a known kind"),
    ],
    ids=["unknown-key", "unknown-kind", "kind-list"],
)
def test_a_malformed_typed_gate_is_UNRESOLVED_not_a_path(tmp_path: Path, gate: object, why: str) -> None:
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    manifest = root / "controls" / "toy" / "control.json"
    spec = json.loads(manifest.read_text())
    spec["gate"] = gate
    manifest.write_text(json.dumps(spec))
    out = _probe(root)
    assert "UNRESOLVED" in out.stdout, out.stdout + out.stderr
    assert why in out.stdout, out.stdout


# ---------------------------------------------------------------------------
# Issue #1396: `blocked_by` is REQUIRED on every expect:uncaught entry, and
# combinations let several declared mutations be applied together so two
# protections that mask each other one at a time can finally be asked
# whether removing BOTH changes the verdict.
# ---------------------------------------------------------------------------


def test_blocked_by_missing_on_an_uncaught_entry_is_inapplicable(tmp_path: Path) -> None:
    mutation = dict(COMMENT_REJECTION, expect="uncaught", why="no case reaches it")
    root = _tree(tmp_path, good_case=False, mutations=[mutation])
    result = _probe(root)
    assert "MUTATION-INAPPLICABLE: controls/toy/control.json::comment-rejection" in result.stdout
    assert "blocked_by=None" in result.stdout
    assert "closed vocabulary" in result.stdout


def test_blocked_by_unrecognized_on_an_uncaught_entry_is_inapplicable(tmp_path: Path) -> None:
    mutation = dict(COMMENT_REJECTION, expect="uncaught", why="no case reaches it",
                     blocked_by="it-just-cannot-be-done")
    root = _tree(tmp_path, good_case=False, mutations=[mutation])
    result = _probe(root)
    assert "MUTATION-INAPPLICABLE: controls/toy/control.json::comment-rejection" in result.stdout
    assert "'it-just-cannot-be-done'" in result.stdout
    assert "closed vocabulary" in result.stdout


def test_blocked_by_is_not_required_on_an_expect_caught_entry(tmp_path: Path) -> None:
    """The field is scoped to expect:uncaught - a caught entry needs no reason

    for a gap that, per this run, does not exist.
    """
    root = _tree(tmp_path, good_case=True, mutations=[COMMENT_REJECTION])
    result = _probe(root, "--strict")
    assert "MUTATION-CAUGHT: controls/toy/control.json::comment-rejection" in result.stdout
    assert result.returncode == 0


#: A toy gate with TWO protections that MUTUALLY MASK each other on the one
#: input that reaches either - mirroring controls/shellcheck-gate's real
#: zero-matched-is-unknown / linter-crash-is-unknown pair (issue #1396).
#: Guard A refuses an empty directory outright; Guard B refuses a simulated
#: "tool" exit code outside {0, 1} - reached only when Guard A is bypassed,
#: and ALSO triggered by the same zero-file condition (`simulated_tool_rc =
#: 3`), exactly as shellcheck exits 3 when invoked with no file arguments.
#: Removing either ALONE changes nothing (the sibling still refuses); only
#: removing BOTH TOGETHER lets the gate fall through to a false "ok".
MASKED_GATE = '''#!/usr/bin/env python3
"""A toy gate with two protections that mask each other (issue #1396)."""
import pathlib
import sys


def main() -> int:
    root = pathlib.Path(sys.argv[sys.argv.index("--root") + 1])
    files = [p for p in sorted(root.rglob("*")) if p.is_file()]
    count = len(files)
    if count == 0:
        print("TOY-FINDING: no files matched", file=sys.stderr)
        return 1
    found = any(
        "FORBIDDEN" in line and not line.strip().startswith("#")
        for path in files for line in path.read_text().splitlines()
    )
    simulated_tool_rc = 3 if count == 0 else (1 if found else 0)
    if simulated_tool_rc not in (0, 1):
        print("TOY-FINDING: tool exited weird", file=sys.stderr)
        return 1
    if simulated_tool_rc == 1:
        print("TOY-FINDING: forbidden token", file=sys.stderr)
        return 1
    print("toy-gate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

MASKED_BATTERY = '''#!/usr/bin/env python3
"""A miniature battery for the masked-pair toy gate (issue #1396)."""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "controls" / "toy" / "control.json").read_text())


def main() -> int:
    failed = 0
    for case in SPEC["cases"]:
        proc = subprocess.run(
            [sys.executable, str(ROOT / SPEC["gate"]), "--root",
             str(ROOT / "controls" / "toy" / case["input"])],
            capture_output=True, text=True, check=False)
        observed = "GOOD" if proc.returncode == 0 else "BAD"
        if observed != case["expect"]:
            failed += 1
            print("TOY-BATTERY-FAIL: " + case["name"], file=sys.stderr)
    if failed:
        return 1
    print("toy-battery: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

#: Refuses an empty directory outright. Masked alone: Guard B (below) also
#: fires on the same zero-file input, reached only once Guard A is removed.
GUARD_A = {
    "name": "zero-count-refusal",
    "protection": "zero files matched must fail the battery, not pass silently",
    "find": (r'    if count == 0:\n        print\("TOY-FINDING: no files matched", '
              r'file=sys\.stderr\)\n        return 1\n'),
    "replace": "    if False:\n        pass\n",
    "count": 1,
    "expect": "uncaught",
    "why": "masked by the sibling tool-crash guard below, which also fires on count==0",
    "blocked_by": "masked-by-sibling",
}

#: Refuses a simulated tool exit outside {0, 1}. Masked alone: Guard A fires
#: FIRST on the only input that reaches this check at all (count==0).
GUARD_B = {
    "name": "tool-crash-refusal",
    "protection": "a simulated tool exit outside 0/1 must fail the battery, not pass silently",
    "find": (r'    if simulated_tool_rc not in \(0, 1\):\n        print\('
              r'"TOY-FINDING: tool exited weird", file=sys\.stderr\)\n        return 1\n'),
    "replace": "    if False:\n        pass\n",
    "count": 1,
    "expect": "uncaught",
    "why": "masked by the sibling zero-count guard above, which fires first on count==0",
    "blocked_by": "masked-by-sibling",
}

#: Genuinely decorative on its own: a comment no case can ever observe.
INERT_COMMENT = {
    "name": "comment-only-change",
    "protection": "a comment carries no behavior",
    "find": r'"""A toy gate with two protections that mask each other \(issue #1396\)\."""\n',
    "replace": '"""A toy gate with two protections that mask each other (issue #1396)."""\n# noop\n',
    "count": 1,
    "expect": "uncaught",
    "why": "a comment carries no behavior; no case can ever observe this change",
    "blocked_by": "input-cannot-be-committed",
}


def _masked_tree(tmp_path: Path, *, mutations: list[dict], combinations: Any) -> Path:
    """A self-contained repository with the masked-pair toy gate (issue #1396)."""
    root = tmp_path / "tree"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "toy-gate.py").write_text(MASKED_GATE)
    (root / "scripts" / "toy-battery.py").write_text(MASKED_BATTERY)
    cases = root / "controls" / "toy" / "cases"
    #: The BAD case is an EMPTY directory - zero files, triggering Guard A
    #: (and, if bypassed, the same condition drives Guard B's trigger too).
    (cases / "bad").mkdir(parents=True)
    (cases / "good").mkdir(parents=True)
    (cases / "good" / "input.txt").write_text("nothing forbidden here\n")
    registered = [
        {"name": "bad", "input": "cases/bad", "expect": "BAD"},
        {"name": "good", "input": "cases/good", "expect": "GOOD"},
    ]
    (root / "controls" / "toy" / "control.json").write_text(json.dumps({
        "gate": "scripts/toy-gate.py",
        "battery": ["{python}", "scripts/toy-battery.py"],
        "cases": registered,
        "mutations": mutations,
        "combinations": combinations,
    }))
    return root


def test_a_masked_pair_is_individually_uncaught_but_caught_in_combination(tmp_path: Path) -> None:
    """The motivating case (issue #1396): two protections, each ACCEPTED alone

    because its sibling masks it, but CAUGHT when removed together - the
    question single-mutation probing cannot even ask.
    """
    combo = {
        "name": "zero-count-and-crash-together",
        "protection": "removing both together must still fail",
        "mutations": ["zero-count-refusal", "tool-crash-refusal"],
        "expect": "caught",
        "why": "both guards removed lets the gate fall through to a false ok",
    }
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B], combinations=[combo])
    result = _probe(root, "--strict")
    assert "MUTATION-ACCEPTED: controls/toy/control.json::zero-count-refusal" in result.stdout
    assert "MUTATION-ACCEPTED: controls/toy/control.json::tool-crash-refusal" in result.stdout
    assert ("MUTATION-CAUGHT: controls/toy/control.json::zero-count-and-crash-together"
            in result.stdout)
    assert result.returncode == 0


def test_a_combination_the_battery_still_misses_reports_uncaught(tmp_path: Path) -> None:
    """A combination is not automatically CAUGHT just for existing: pairing one

    masked guard with a genuinely decorative mutation changes nothing, because
    the OTHER guard still independently covers the masked one's removal.
    """
    combo = {
        "name": "zero-count-and-inert-together",
        "protection": "pairing a masked guard with a no-op must still be missed",
        "mutations": ["zero-count-refusal", "comment-only-change"],
        "expect": "uncaught",
        "why": "tool-crash-refusal still independently catches zero-count-refusal's removal, "
               "and the comment changes nothing observable",
        "blocked_by": "masked-by-sibling",
    }
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B, INERT_COMMENT], combinations=[combo])
    result = _probe(root, "--strict")
    assert ("MUTATION-ACCEPTED: controls/toy/control.json::zero-count-and-inert-together"
            in result.stdout)
    assert result.returncode == 0


def test_combinations_field_before_the_fix_was_silently_ignored(tmp_path: Path) -> None:
    """Names the fix's crux directly: a combination entry must produce its OWN

    probe line, under its own name - not be silently absent from the report.
    """
    combo = {
        "name": "zero-count-and-crash-together",
        "protection": "removing both together must still fail",
        "mutations": ["zero-count-refusal", "tool-crash-refusal"],
        "expect": "caught",
        "why": "both guards removed lets the gate fall through to a false ok",
    }
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B], combinations=[combo])
    result = _probe(root, "--strict")
    assert "zero-count-and-crash-together" in result.stdout, (
        "a declared combination must appear in the report under its own name")


def test_a_combination_name_colliding_with_a_mutation_name_is_inapplicable(tmp_path: Path) -> None:
    combo = {
        "name": "zero-count-refusal",  # collides with GUARD_A's own name
        "mutations": ["zero-count-refusal", "tool-crash-refusal"],
        "expect": "caught",
    }
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B], combinations=[combo])
    result = _probe(root)
    assert "MUTATION-INAPPLICABLE: controls/toy/control.json::zero-count-refusal" in result.stdout
    assert "collides" in result.stdout


def test_a_combination_naming_an_unknown_mutation_is_inapplicable(tmp_path: Path) -> None:
    combo = {
        "name": "combo-with-a-typo",
        "mutations": ["zero-count-refusal", "tool-crash-refusel"],  # typo
        "expect": "caught",
    }
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B], combinations=[combo])
    result = _probe(root)
    assert "MUTATION-INAPPLICABLE: controls/toy/control.json::combo-with-a-typo" in result.stdout
    assert "not declared in this manifest" in result.stdout


def test_a_combination_of_fewer_than_two_mutations_is_inapplicable(tmp_path: Path) -> None:
    combo = {
        "name": "not-really-a-combination",
        "mutations": ["zero-count-refusal"],
        "expect": "caught",
    }
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B], combinations=[combo])
    result = _probe(root)
    assert ("MUTATION-INAPPLICABLE: controls/toy/control.json::not-really-a-combination"
            in result.stdout)
    assert "at least two" in result.stdout


def test_a_combinations_step_is_checked_against_the_already_mutated_text(tmp_path: Path) -> None:
    """Pins the declared-order semantics (issue #1396): each step's `find` is

    matched against the text AFTER the earlier steps' edits. A combination
    whose SECOND member's `find` only matches once the FIRST member's edit
    has already landed APPLIES in that order; declared in the opposite
    order, the second member's `find` never matches the original text and
    the combination is INAPPLICABLE instead.
    """
    # `tool-crash-refusal`'s find (`if simulated_tool_rc not in (0, 1):...`)
    # matches the ORIGINAL text unconditionally - it does not depend on
    # zero-count-refusal having run first. So to pin order-dependence
    # directly, declare a synthetic second step whose find text only exists
    # AFTER zero-count-refusal's replacement has landed.
    order_dependent = {
        "name": "depends-on-prior-step",
        "find": r"    if False:\n        pass\n    found = any",
        "replace": "    if False:\n        pass  # order-dependent\n    found = any",
        "count": 1,
        "expect": "caught",
    }
    combo_right_order = {
        "name": "right-order",
        "mutations": ["zero-count-refusal", "depends-on-prior-step"],
        "expect": "caught",
    }
    combo_wrong_order = {
        "name": "wrong-order",
        "mutations": ["depends-on-prior-step", "zero-count-refusal"],
        "expect": "caught",
    }
    root = _masked_tree(
        tmp_path, mutations=[GUARD_A, GUARD_B, order_dependent],
        combinations=[combo_right_order, combo_wrong_order])
    result = _probe(root)
    #: `depends-on-prior-step`'s own edit is cosmetic (a comment), so in the
    #: correct order this combination removes only Guard A - UNCAUGHT, same
    #: as Guard A alone (masked by Guard B, untouched here). The point is NOT
    #: this exact verdict; it is that the step APPLIED AT ALL only when Guard
    #: A's replacement landed first, which "wrong-order" below disproves.
    assert "MUTATION-INAPPLICABLE: controls/toy/control.json::right-order" not in result.stdout
    assert "MUTATION-UNCAUGHT: controls/toy/control.json::right-order" in result.stdout
    assert "MUTATION-INAPPLICABLE: controls/toy/control.json::wrong-order" in result.stdout
    assert ("step 1 of 2: `find` matched 0 time(s)" in result.stdout), (
        "wrong-order must fail at ITS FIRST step - depends-on-prior-step's find text "
        "does not exist in the ORIGINAL gate, only after zero-count-refusal has landed")


#: Each half of this pair is, on its own, a real one-step mutation (its
#: `replace` differs from its `find`'s text). Combined in declared order,
#: the second step exactly undoes the first - counter-model review, #1396.
FLIP_TO_UPPER = {
    "name": "flip-ok-marker-upper",
    "protection": "the toy gate's own success marker, flipped to uppercase",
    "find": r'print\("toy-gate: ok"\)',
    "replace": 'print("toy-gate: OK")',
    "count": 1,
    "expect": "caught",
}
FLIP_BACK_TO_LOWER = {
    "name": "flip-ok-marker-back",
    "protection": "undoes flip-ok-marker-upper - reaches the UPPERCASE text that step produces",
    "find": r'print\("toy-gate: OK"\)',
    "replace": 'print("toy-gate: ok")',
    "count": 1,
    "expect": "caught",
}


def test_a_combination_whose_steps_cancel_out_is_inapplicable_not_accepted(tmp_path: Path) -> None:
    """Two steps that each change the text can still net to NO edit at all if

    the second undoes the first (issue #1396, counter-model review). Scoring
    that as CAUGHT/ACCEPTED/UNCAUGHT would be a verdict about the UNMUTATED
    gate reported as if a protection had been removed.
    """
    combo = {
        "name": "flip-and-flip-back",
        "mutations": ["flip-ok-marker-upper", "flip-ok-marker-back"],
        "expect": "caught",
    }
    root = _masked_tree(
        tmp_path, mutations=[GUARD_A, GUARD_B, FLIP_TO_UPPER, FLIP_BACK_TO_LOWER],
        combinations=[combo])
    result = _probe(root)
    assert "MUTATION-INAPPLICABLE: controls/toy/control.json::flip-and-flip-back" in result.stdout
    assert "COMBINED result is BYTE-IDENTICAL to the original" in result.stdout


#: Deliberately missing `blocked_by` despite `expect: "uncaught"`, so this
#: entry is rejected during the single-mutation pass and never enters
#: `steps_by_name` - but it still CLAIMS its name in the manifest.
REJECTED_MUTATION_WITH_A_NAME = {
    "name": "shares-a-name",
    "protection": "deliberately invalid - missing blocked_by - to test name collision",
    "find": r'print\("toy-gate: ok"\)',
    "replace": 'print("toy-gate: OK")',
    "count": 1,
    "expect": "uncaught",
    "why": "deliberately missing blocked_by",
}


def test_a_combination_colliding_with_a_rejected_mutations_name_is_inapplicable(
        tmp_path: Path) -> None:
    """A mutation rejected for its OWN reasons (here, a missing `blocked_by`)

    never reaches `steps_by_name` - but it still claims its name, and a
    combination reusing that name must still be refused as a collision
    (counter-model review, issue #1396), not silently run under a name that
    is already ambiguous in the report.
    """
    combo = {
        "name": "shares-a-name",
        "mutations": ["zero-count-refusal", "tool-crash-refusal"],
        "expect": "caught",
    }
    root = _masked_tree(
        tmp_path, mutations=[GUARD_A, GUARD_B, REJECTED_MUTATION_WITH_A_NAME],
        combinations=[combo])
    result = _probe(root)
    lines = [
        line for line in result.stdout.splitlines()
        if line.startswith("MUTATION-") and "controls/toy/control.json::shares-a-name" in line]
    assert len(lines) == 2, (
        "both the rejected mutation and the colliding combination must report under this "
        f"name, distinctly: {lines}")
    assert all(line.startswith("MUTATION-INAPPLICABLE:") for line in lines)
    assert "collides" in result.stdout


def test_a_combinations_entry_that_is_not_an_object_is_inapplicable_not_a_crash(
        tmp_path: Path) -> None:
    """A malformed `combinations` member must not crash the probe (issue

    #1396, counter-model review) - `check-negative-controls.py`'s own schema
    check only refuses an unknown TOP-LEVEL key, it does not validate shape.
    """
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B], combinations=["not-an-object"])
    result = _probe(root)
    assert "combination entry is not an object" in result.stdout


def test_a_combinations_field_that_is_not_a_list_is_inapplicable_not_a_crash(
        tmp_path: Path) -> None:
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B], combinations={"oops": True})
    result = _probe(root)
    assert "`combinations` must be a list of objects" in result.stdout


def test_a_null_combinations_field_is_treated_as_no_combinations(tmp_path: Path) -> None:
    """`"combinations": null` must not crash, and is treated the same as the

    key's absence - the same convention this file already applies to a null
    `mutations` field.
    """
    root = _masked_tree(tmp_path, mutations=[GUARD_A, GUARD_B], combinations=None)
    result = _probe(root, "--strict")
    assert result.returncode == 0
    assert "MUTATION-ACCEPTED: controls/toy/control.json::zero-count-refusal" in result.stdout
