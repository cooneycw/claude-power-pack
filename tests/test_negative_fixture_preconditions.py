"""Tests for scripts/check-negative-fixture-preconditions.py - the #697 gate.

Contract:
- Fires on the #695 shape: a fixture that replaces ``PATH`` wholesale to create
  an absence, with no assertion that the absence is the one it intended.
- Stays silent on all three shapes issue #697 explicitly names as safe - a
  ``PATH`` prepend, ``monkeypatch.delenv``, and outcome assertions - so the
  convention cannot be over-applied.
- Honours the ``# negative-fixture: allow <reason>`` escape.
- Runs clean on CPP's real ``tests/`` tree.

The load-bearing test in this module is
``test_gate_fires_when_the_real_precondition_is_stripped``: it MUTATES the one
real instance in the suite (``test_cpp_commands_link.py``, whose precondition
landed in PR #695) and proves the gate goes red. Without it, this gate would be
one more measurement whose broken version is indistinguishable from its working
version - the exact defect class #697 belongs to (#673, #674, #677, #685, #698),
and the reason a green run over a one-line population proves nothing on its own.

This module deliberately shells out to NOTHING: the checker is pure source
analysis, so its own test drives it in-process over sources written to
``tmp_path``. That is what lets it run in the CI ``validate`` image.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-negative-fixture-preconditions.py"


def _load_checker():
    """Import the hyphenated CLI script as a module."""
    spec = importlib.util.spec_from_file_location("check_negative_fixture_preconditions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

PREAMBLE = """\
import os
import shutil

"""


def _findings(tmp_path: Path, source: str) -> list:
    path = tmp_path / "test_sample.py"
    path.write_text(PREAMBLE + source, encoding="utf-8")
    return checker.check_paths([path])


# --------------------------------------------------------------------------- #
# The mutation proof - this gate's own falsifiability
# --------------------------------------------------------------------------- #
def test_gate_fires_when_the_real_precondition_is_stripped(tmp_path: Path) -> None:
    """Remove the shipped assertion from the real fixture; the gate must go red.

    The detectable population in this repo is currently ONE line and it is
    already compliant, so a passing run over the real tree is equally consistent
    with a gate that cannot fire at all. This test is what distinguishes them:
    it deletes the ``fixture must lack git`` assertion from a copy of the real
    ``test_cpp_commands_link.py`` and requires a finding.

    A failure here means the guard has stopped guarding, whatever the real-tree
    run says.
    """
    real = ROOT / "tests" / "test_cpp_commands_link.py"
    source = real.read_text(encoding="utf-8")
    assert "fixture must lack git" in source, (
        "the #695 precondition is gone from the real fixture - either it was "
        "removed (a #697 regression) or renamed, and this mutation proof is "
        "no longer measuring anything"
    )

    mutated = "".join(
        line for line in source.splitlines(keepends=True) if "fixture must lack git" not in line
    )
    target = tmp_path / "test_cpp_commands_link.py"
    target.write_text(mutated, encoding="utf-8")

    findings = checker.check_paths([target])
    assert len(findings) == 1, f"stripped precondition not caught: {findings}"
    assert findings[0].func == "test_fail_open_when_git_is_absent"


def test_real_tests_tree_is_clean() -> None:
    """CPP's own suite satisfies the directive.

    This is what runs the gate in CI (the ``validate`` step runs pytest), the
    same wiring ``check-test-binary-guards.py`` relies on.
    """
    findings = checker.check_tree(ROOT / "tests")
    assert not findings, "\n".join(f.render(ROOT) for f in findings)


# --------------------------------------------------------------------------- #
# Fires: constructed absences with no precondition
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            'def test_thing(tmp_path):\n    env = dict(os.environ)\n    env["PATH"] = ""\n',
            id="empty-path-the-695-shape",
        ),
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    env = dict(os.environ)\n'
            '    env["PATH"] = str(tmp_path / "stub")\n',
            id="wholesale-replacement",
        ),
        pytest.param(
            'def test_thing(monkeypatch, tmp_path):\n'
            '    monkeypatch.setenv("PATH", str(tmp_path))\n',
            id="setenv-wholesale",
        ),
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    os.environ["PATH"] = str(tmp_path)\n',
            id="os-environ-direct",
        ),
    ],
)
def test_fires_on_constructed_absence(tmp_path: Path, body: str) -> None:
    findings = _findings(tmp_path, body)
    assert len(findings) == 1, f"expected one finding, got {findings}"


def test_finding_names_the_function_and_assignment_line(tmp_path: Path) -> None:
    findings = _findings(
        tmp_path,
        'def test_fail_open(tmp_path):\n    env = dict(os.environ)\n    env["PATH"] = ""\n',
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.func == "test_fail_open"
    rendered = finding.render(tmp_path)
    assert "test_fail_open" in rendered
    assert "PATH" in rendered


# --------------------------------------------------------------------------- #
# Stays silent: the shapes #697 names as safe (over-application guard)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    env = dict(os.environ)\n'
            '    env["PATH"] = f"{tmp_path}:{env[\'PATH\']}"\n',
            id="prepend-is-additive",
        ),
        pytest.param(
            'def test_thing(monkeypatch):\n'
            '    monkeypatch.setenv("PATH", f"/stub:{os.environ[\'PATH\']}")\n',
            id="setenv-prepend",
        ),
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    env = dict(os.environ)\n'
            '    env["PATH"] = os.pathsep.join([str(tmp_path), os.environ.get("PATH", "")])\n',
            id="derived-via-environ-get",
        ),
        pytest.param(
            'def test_thing(monkeypatch):\n'
            '    monkeypatch.delenv("CPP_HARNESS", raising=False)\n',
            id="delenv-is-a-named-removal",
        ),
        pytest.param(
            'def test_thing(tmp_path):\n'
            '    produced = tmp_path / "out"\n'
            '    assert not produced.exists()\n',
            id="outcome-assertion-not-a-precondition",
        ),
    ],
)
def test_silent_on_sanctioned_shapes(tmp_path: Path, body: str) -> None:
    assert not _findings(tmp_path, body)


def test_precondition_assertion_clears_the_finding(tmp_path: Path) -> None:
    """The shipped #695 shape - the whole point of the convention."""
    assert not _findings(
        tmp_path,
        'def test_thing(tmp_path):\n'
        '    stub = tmp_path / "nogitbin"\n'
        '    stub.mkdir()\n'
        '    assert shutil.which("git", path=str(stub)) is None, "fixture must lack git"\n'
        '    env = dict(os.environ)\n'
        '    env["PATH"] = str(stub)\n',
    )


# --------------------------------------------------------------------------- #
# Escape hatch + structural edge cases
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("anchor", ["same-line", "line-above"], ids=["same-line", "line-above"])
def test_allow_escape_suppresses(tmp_path: Path, anchor: str) -> None:
    comment = "# negative-fixture: allow deliberate total-absence probe"
    if anchor == "same-line":
        assignment = f'    env["PATH"] = ""  {comment}\n'
    else:
        assignment = f'    {comment}\n    env["PATH"] = ""\n'
    assert not _findings(
        tmp_path,
        "def test_thing(tmp_path):\n    env = dict(os.environ)\n" + assignment,
    )


def test_nested_helper_is_reported_once(tmp_path: Path) -> None:
    """A replacement inside a nested function is attributed to that function only."""
    findings = _findings(
        tmp_path,
        'def test_thing(tmp_path):\n'
        '    def _build():\n'
        '        env = dict(os.environ)\n'
        '        env["PATH"] = ""\n'
        '        return env\n'
        '    return _build()\n',
    )
    assert len(findings) == 1, f"expected exactly one finding, got {findings}"
    assert findings[0].func == "_build"


# --------------------------------------------------------------------------- #
# CLI contract
# --------------------------------------------------------------------------- #
def test_cli_reports_and_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_bad.py").write_text(
        PREAMBLE + 'def test_thing(tmp_path):\n    env = dict(os.environ)\n    env["PATH"] = ""\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "precondition assertion" in out
    assert "fixture must lack git" in out, "the remedy must name the shape to copy"
    # The failure line carries its denominator too (#933), not just a count of
    # findings. "6 unasserted" says nothing about whether 6 is most of the
    # population or a corner of it; "6 of 8" does. Asserted here rather than only
    # on the success path because a reader triaging a RED needs the scale most.
    assert "1 of 1 wholesale PATH replacement(s)" in out, out
    assert "test file(s) scanned" in out, out


def test_cli_is_silent_success_on_a_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(
        PREAMBLE + 'def test_thing(tmp_path):\n    assert tmp_path.exists()\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 0
    assert "ok" in capsys.readouterr().out


def test_cli_fails_when_the_root_has_no_tests_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """#840: a missing tests/ must not read the same as a clean scan - the
    exit code is what `make verify` reads, and the message alone (already
    present, previously on stderr) was a silent pass through that gate."""
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "no tests/ directory" in out


def test_cli_fails_when_tests_directory_has_no_test_files(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """#840: a present-but-empty tests/ is worse than a missing one - the old
    code printed a clean "ok" for a population of zero, a false positive
    rather than a missed report."""
    (tmp_path / "tests").mkdir()
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "no test files" in out


# --------------------------------------------------------------------------- #
# The dict-literal shape (issue #933)
# --------------------------------------------------------------------------- #
# The gate detected `env["PATH"] = v` and `monkeypatch.setenv("PATH", v)` and
# claimed, in its success line, to cover "every constructed absence". It did not
# see `subprocess.run(..., env={"PATH": v})` - the same wholesale replacement, in
# a dict literal, just as visible to a parser. Six live sites used it, two of
# them fail-open tests of the exact #695 class this gate was built from.
#
# This is the shape that matters most in these tests, because it is a blind spot
# INSIDE the class the gate named, not one of the acknowledged out-of-scope ones.
@pytest.mark.parametrize("body", [
    # inline keyword argument - the shape every live site used
    'def test_thing(tmp_path):\n'
    '    stub = tmp_path / "bin"\n'
    '    subprocess.run(["x"], env={"PATH": str(stub)})\n',
    # assigned to a name first
    'def test_thing(tmp_path):\n'
    '    stub = tmp_path / "bin"\n'
    '    env = {"PATH": str(stub)}\n'
    '    subprocess.run(["x"], env=env)\n',
    # returned from a helper
    'def _env(tmp_path):\n'
    '    return {"PATH": str(tmp_path / "bin")}\n',
    # nested among other keys, which is how the live sites actually looked
    'def test_thing(tmp_path):\n'
    '    subprocess.run(["x"], env={"HOME": "/h", "PATH": str(tmp_path), "TZ": "UTC"})\n',
])
def test_fires_on_a_dict_literal_replacement(tmp_path: Path, body: str) -> None:
    findings = _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body)
    assert len(findings) == 1, f"a dict-literal PATH replacement must be seen: {findings}"


@pytest.mark.parametrize("body", [
    # A PREPEND in dict-literal form ADDS a stub without removing anything, so it
    # constructs no absence. This is the case that stops the widening becoming an
    # over-correction, and it is why the derived test is shared with the other
    # shapes rather than re-implemented for this one.
    'def test_thing(tmp_path):\n'
    '    subprocess.run(["x"], env={"PATH": f"{tmp_path}:{os.environ[\'PATH\']}"})\n',
    'def test_thing(tmp_path):\n'
    '    subprocess.run(["x"], env={"PATH": str(tmp_path) + ":" + os.environ["PATH"]})\n',
    'def test_thing(tmp_path, monkeypatch):\n'
    '    subprocess.run(["x"], env={"PATH": f"{tmp_path}:{os.getenv(\'PATH\')}"})\n',
    # a dict with no PATH key at all is ordinary test setup
    'def test_thing(tmp_path):\n'
    '    subprocess.run(["x"], env={"HOME": str(tmp_path), "TZ": "UTC"})\n',
])
def test_silent_on_a_derived_dict_literal(tmp_path: Path, body: str) -> None:
    findings = _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body)
    assert findings == [], f"a prepend adds without removing and must never be flagged: {findings}"


def test_a_dict_literal_with_a_precondition_is_clear(tmp_path: Path) -> None:
    """Widening must not flag correct code - the other half of the two-sided control."""
    body = (
        'def test_thing(tmp_path):\n'
        '    stub = tmp_path / "bin"\n'
        '    assert shutil.which("git", path=str(stub)) is None, "fixture must lack git"\n'
        '    subprocess.run(["x"], env={"PATH": str(stub)})\n'
    )
    assert _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body) == []


# --------------------------------------------------------------------------- #
# The claim the success line makes (issue #933)
# --------------------------------------------------------------------------- #
_BANNED_QUANTIFIERS = ("every constructed absence", "every ")


def test_the_success_line_reports_a_denominator_not_a_quantifier(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """"every" is a claim about a class; this gate inspects three shapes of one.

    The failure being prevented is not a wording nit. A green that means "I
    inspected eight sites and all eight assert" and a green that means "I could
    not see any of them" were the same sentence, and the second is what shipped
    for six live sites. detector-contracts.md question 1, applied to this gate's
    own output.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(
        PREAMBLE + "import subprocess\n\n"
        'def test_thing(tmp_path):\n'
        '    stub = tmp_path / "bin"\n'
        '    assert shutil.which("git", path=str(stub)) is None, "must lack git"\n'
        '    subprocess.run(["x"], env={"PATH": str(stub)})\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out

    assert "1 wholesale PATH replacement(s) in 1 of 1 test file(s)" in out, out

    # Scoped to the VERDICT line, not the whole output. The `not inspected:`
    # line legitimately says "one `which` assert clears EVERY replacement in its
    # function" - that is a limitation being disclosed, not a claim being made,
    # and a whole-output ban cannot tell those apart. The first draft of this
    # assertion banned the substring everywhere and failed on the very caveat
    # written to make the gate honest.
    verdict_line = out.splitlines()[0]
    for banned in _BANNED_QUANTIFIERS:
        assert banned not in verdict_line, (
            f"the verdict line must not claim {banned!r} - it inspects three "
            f"syntactic shapes of one class, and says so: {verdict_line!r}"
        )


def test_the_success_line_names_what_it_did_not_inspect(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Narrowing a claim without naming the gap converts an overclaim into a silence.

    A silence reads as clean. The #952 denominator form is "what I inspected AND
    what I did not", so the shapes this gate cannot see are printed where the
    reader of the green line meets them - not only in the docstring.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(PREAMBLE + "def test_thing():\n    pass\n", encoding="utf-8")
    assert checker.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out

    assert "not inspected:" in out, out
    for shape in ("chmod", "exit status", "container image", "import patching", "fixture"):
        assert shape in out, f"the uninspected shape {shape!r} must be named: {out!r}"


def test_a_zero_population_is_not_reported_as_coverage(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Zero sites inspected must not read like eight sites cleared.

    The #840 empty-scan guards cover a missing or empty tests/ directory. This is
    the remaining shape: a tests/ full of real files, none of which constructs an
    absence. That is a legitimate exit 0, and the denominator is what stops it
    being mistaken for coverage.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(PREAMBLE + "def test_thing():\n    pass\n", encoding="utf-8")
    assert checker.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "0 wholesale PATH replacement(s) in 0 of 1 test file(s)" in out, (
        f"a zero population must be VISIBLE in the success line, not implied: {out!r}"
    )


def test_every_site_in_a_function_is_counted_not_just_the_first(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The denominator counts SITES, and a function may hold more than one.

    Caught by mutation, not by review: making `_function_sites` stop at the
    first replacement left every test green, because none of them had a function
    with two. A denominator that silently undercounts is worse than no
    denominator - it is a specific, checkable-looking number that is wrong, and
    nothing downstream re-derives it.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_two.py").write_text(
        PREAMBLE + "import subprocess\n\n"
        'def test_thing(tmp_path):\n'
        '    a = tmp_path / "a"\n'
        '    b = tmp_path / "b"\n'
        '    assert shutil.which("git", path=str(a)) is None, "must lack git"\n'
        '    subprocess.run(["x"], env={"PATH": str(a)})\n'
        '    subprocess.run(["y"], env={"PATH": str(b)})\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2 wholesale PATH replacement(s)" in out, (
        f"both replacements in the one function must be counted: {out!r}"
    )


def test_a_replacement_nested_inside_a_block_is_still_seen(tmp_path: Path) -> None:
    """A dict literal inside `with`/`if`/`for`, not at the function's top level.

    This pins the traversal that the M3 mutation showed is doing the real work:
    the scan reaches statements nested inside compound statements, so moving a
    replacement into a `with` block cannot hide it.
    """
    body = (
        'def test_thing(tmp_path):\n'
        '    stub = tmp_path / "bin"\n'
        '    if True:\n'
        '        with open(tmp_path / "log", "w"):\n'
        '            subprocess.run(["x"], env={"PATH": str(stub)})\n'
    )
    findings = _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body)
    assert len(findings) == 1, f"a nested replacement must still be seen: {findings}"


@pytest.mark.parametrize("shape", [
    '        env["PATH"] = str(stub)\n',
    '        monkeypatch.setenv("PATH", str(stub))\n',
])
def test_a_nested_subscript_or_setenv_is_still_seen(tmp_path: Path, shape: str) -> None:
    """The traversal, not the per-statement scan, is what reaches these.

    A dict literal nested in a `with` block is found from its top-level ancestor,
    because the dict scan walks the whole statement subtree. The subscript and
    setenv shapes are NOT: they are matched on the statement itself, so only
    `ast.walk(func)` reaches them once they sit inside a compound statement.

    Two mutations of that traversal survived the whole suite before this case
    existed - both looked like real regressions and were invisible because every
    other nested test happened to use the dict shape. The bug a control cannot
    see is the one its cases all share an accident.
    """
    body = (
        'def test_thing(tmp_path, monkeypatch):\n'
        '    stub = tmp_path / "bin"\n'
        '    if True:\n'
        + shape
    )
    findings = _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body)
    assert len(findings) == 1, f"a nested {shape.strip()!r} must still be seen: {findings}"


@pytest.mark.parametrize("body,expected", [
    # An explicit PATH entry alongside `**` unpacking is still a wholesale write.
    ('def test_thing(tmp_path):\n'
     '    subprocess.run(["x"], env={**os.environ, "PATH": str(tmp_path)})\n', 1),
    # `**` alone carries no statically-knowable PATH, so there is nothing to claim.
    ('def test_thing(tmp_path):\n'
     '    subprocess.run(["x"], env={**os.environ})\n', 0),
    # and a derived value stays derived even beside an unpack
    ('def test_thing(tmp_path):\n'
     '    subprocess.run(["x"], env={**os.environ, "PATH": f"{tmp_path}:{os.environ[\'PATH\']}"})\n', 0),
])
def test_dict_unpacking_does_not_confuse_the_scan(tmp_path: Path, body: str, expected: int) -> None:
    """`{**base, "PATH": v}` has a None key for the unpack entry.

    mypy found this before any test did - `_literal_str` tolerates a None key and
    `key.lineno` does not - which would have been a crash on a shape that appears
    in real fixtures. A gate that raises on valid input is not a stricter gate,
    it is an unavailable one, and `make verify` would have failed for a reason
    unrelated to anything the author changed.
    """
    findings = _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body)
    assert len(findings) == expected, f"{body!r} -> {findings}"


# --------------------------------------------------------------------------- #
# Found by independent review of the #933 change (Codex gpt-5.5)
# --------------------------------------------------------------------------- #
def test_the_allow_hatch_does_not_suppress_the_NEXT_line(tmp_path: Path) -> None:
    """An exemption must exempt what it names, and nothing else.

    `# negative-fixture: allow` is honoured on the line ABOVE so the comment can
    sit on its own line. When the line above is ANOTHER replacement, that
    allowance silently removed the neighbour - not merely unreported, but gone
    from the denominator, so the gate printed "0 wholesale replacement(s)" for a
    file holding two. An exemption mechanism that quietly widens itself is the
    same overclaim this change exists to remove, arriving by a different route.
    """
    body = (
        'def test_thing(tmp_path):\n'
        '    a = {"PATH": "/a"}  # negative-fixture: allow the first one only\n'
        '    b = {"PATH": "/b"}\n'
        '    print(a, b)\n'
    )
    findings = _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body)
    assert len(findings) == 1, (
        f"the unexempted neighbour must survive its neighbour's hatch: {findings}"
    )


def test_the_standalone_comment_above_form_still_exempts(tmp_path: Path) -> None:
    """The other side of that fix: the documented comment-above form must work.

    Narrowing the hatch is two-sided. If this case ever breaks, the fix above has
    become an over-correction and the escape hatch is unusable in its documented
    form.
    """
    body = (
        'def test_thing(tmp_path):\n'
        '    # negative-fixture: allow a stub PATH with nothing to assert\n'
        '    a = {"PATH": "/a"}\n'
        '    print(a)\n'
    )
    assert _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body) == []


def test_two_replacements_in_one_statement_are_both_counted(tmp_path: Path) -> None:
    """One statement can carry two dict literals, on two lines."""
    body = (
        'def test_thing(tmp_path):\n'
        '    envs = [\n'
        '        {"PATH": "/a"},\n'
        '        {"PATH": "/b"},\n'
        '    ]\n'
        '    print(envs)\n'
    )
    findings = _findings(tmp_path, PREAMBLE + "import subprocess\n\n" + body)
    assert len(findings) == 1, "one function, so one finding"


def test_the_failure_numerator_and_denominator_share_a_unit(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """"1 of 2" was printed for a function whose TWO replacements both lacked one.

    `len(findings)` counts FUNCTIONS - `_check_function` returns at most one
    finding however many replacements a function holds - while the denominator
    counts SITES. A ratio whose halves count different things is a specific,
    checkable-looking number that is wrong, which is worse than no number.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_two.py").write_text(
        PREAMBLE + "import subprocess\n\n"
        'def test_thing(tmp_path):\n'
        '    subprocess.run(["x"], env={"PATH": str(tmp_path / "a")})\n'
        '    subprocess.run(["y"], env={"PATH": str(tmp_path / "b")})\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "2 of 2 wholesale PATH replacement(s) lack a precondition assertion" in out, out
    assert "in 1 function(s)" in out, f"the function count is reported separately: {out!r}"


def test_the_success_line_does_not_claim_each_site_asserts_its_own_path(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The gate knows the FUNCTION asserts something, not that THIS site is covered.

    One `which` assertion clears every replacement in its function, so two
    replacements and one assertion previously read as "2 ... assert their
    precondition". That is the issue's own defect - a claim wider than the
    inspection - reintroduced by the sentence written to remove it.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_one.py").write_text(
        PREAMBLE + "import subprocess\n\n"
        'def test_thing(tmp_path):\n'
        '    a = tmp_path / "a"\n'
        '    b = tmp_path / "b"\n'
        '    assert shutil.which("git", path=str(a)) is None, "must lack git"\n'
        '    subprocess.run(["x"], env={"PATH": str(a)})\n'
        '    subprocess.run(["y"], env={"PATH": str(b)})\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "are in functions that assert a precondition" in out, out
    assert "assert their precondition" not in out, (
        f"only ONE of these two replacements is actually covered: {out!r}"
    )
    assert "WHICH path an assertion covers" in out, (
        "and the limit must be named where the reader of the green line meets it"
    )
