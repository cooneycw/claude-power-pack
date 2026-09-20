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
    mutation = dict(COMMENT_REJECTION, expect="uncaught", why="no case reaches it")
    root = _tree(tmp_path, good_case=True, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-STALE: controls/toy/control.json::comment-rejection" in result.stdout
    assert result.returncode == 1


def test_an_accepted_gap_that_is_still_uncaught_is_not_a_failure(tmp_path: Path) -> None:
    """A STATED gap is the outcome this tool wants where no control can be written."""
    mutation = dict(COMMENT_REJECTION, expect="uncaught", why="no case can reach it")
    root = _tree(tmp_path, good_case=False, mutations=[mutation])
    result = _probe(root, "--strict")
    assert "MUTATION-ACCEPTED: controls/toy/control.json::comment-rejection" in result.stdout
    assert result.returncode == 0


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
