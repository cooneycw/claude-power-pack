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


# --------------------------------------------------------------------------- #
# Issue #1110 - waivers and sites must share ONE coordinate system
# --------------------------------------------------------------------------- #

#: The characters `str.splitlines()` ends a line on and CPython's tokenizer does
#: not. Built with chr() rather than written literally, because a raw separator
#: smuggled into tests/ would be read by this very gate and by every other gate
#: that scans this directory - the fixture would become part of the population.
SPLITLINES_ONLY = "".join(chr(c) for c in (0x2028, 0x2029, 0x0085, 0x000B, 0x000C, 0x001C))


def _waiver_by_splitlines(source: str) -> int:
    """Where the gate's OLD numbering put the waiver - the defective coordinate."""
    return next(
        i for i, line in enumerate(source.splitlines(), start=1) if checker.ALLOW_RE.search(line)
    )


def _waiver_by_tokenizer(source: str) -> int:
    """Where `ast` puts the waiver - the coordinate the sites are in."""
    return next(
        i for i, line in enumerate(source.split("\n"), start=1) if checker.ALLOW_RE.search(line)
    )


def _separators(count: int) -> str:
    """`count` raw separator characters, cycling the set."""
    return "".join(SPLITLINES_ONLY[i % len(SPLITLINES_ONLY)] for i in range(count))


WAIVED_AFTER_SEPARATORS = (
    'SEPARATORS = "' + _separators(3) + '"\n'
    "\n"
    "\n"
    "def test_waived(tmp_path):\n"
    "    stub = tmp_path / 'bin'\n"
    "    stub.mkdir()\n"
    "    # negative-fixture: allow PATH is isolation, not an absence\n"
    "    subprocess.run(['a'], env={'PATH': str(stub)}, capture_output=True)\n"
)


def test_a_correct_waiver_survives_separators_before_it(tmp_path: Path) -> None:
    """A waiver keeps matching its site when a raw separator precedes it (#1110).

    COVERS SITE `_check_module` - the FINDINGS channel, which is also what the
    exit code and the committed control cases read.

    THE SHIFT MUST EXCEED ONE LINE, and that is specific to THIS gate rather
    than a general rule. `_function_sites` honours a waiver on the site line OR
    the line above, so a +/-1 window absorbs a one-character shift: a
    single-separator fixture passes against the UNFIXED gate and proves
    nothing.

    The sibling gate `check-test-binary-guards` reaches the same bound by a
    DIFFERENT route, and the difference matters to anyone extending this to a
    fourth site. It has no tolerance window at all - it matches exactly, via
    `func.lineno in allow_lines` - but its honoured SET is the def line plus
    the shell-out lines, and in the ordinary layout those are adjacent, so a
    one-line shift slides the waiver from one honoured line onto another and is
    absorbed anyway. Measured on the unfixed gate rather than reasoned about:
    shift 1 absorbed, shift 2 surfaced. So `> 1` holds at every site so far,
    but "why" is per-site and a fourth site owes its own measurement.

    The precondition below fails loudly rather than letting this test quietly
    stop measuring anything.
    """
    full = PREAMBLE + "import subprocess\n\n" + WAIVED_AFTER_SEPARATORS
    shift = _waiver_by_splitlines(full) - _waiver_by_tokenizer(full)
    assert shift > 1, (
        f"fixture shifts the waiver by {shift} line(s); the +/-1 waiver window "
        "absorbs a shift of 1, so this test would pass against the unfixed gate "
        "and is no longer a regression case"
    )
    assert _findings(tmp_path, "import subprocess\n\n" + WAIVED_AFTER_SEPARATORS) == []


def _shifted_exemption_source() -> tuple[str, str]:
    """A module-level waiver whose OLD number lands exactly on an unwaived site.

    Self-calibrating: the separator count is derived from the distance between
    the waiver and the site in the assembled source, so an edit to PREAMBLE or
    to the body cannot silently leave the waiver landing somewhere harmless.
    """
    body = (
        'SEPARATORS = "@SEPS@"\n'
        "\n"
        "# negative-fixture: allow this waiver belongs to no site at all\n"
        "\n"
        "\n"
        "def test_unwaived(tmp_path):\n"
        "    stub = tmp_path / 'bin'\n"
        "    stub.mkdir()\n"
        "    subprocess.run(['b'], env={'PATH': str(stub)}, capture_output=True)\n"
    )
    probe = PREAMBLE + "import subprocess\n\n" + body.replace("@SEPS@", "")
    site = next(
        i for i, line in enumerate(probe.split("\n"), start=1) if "subprocess.run(['b']" in line
    )
    need = site - _waiver_by_tokenizer(probe)
    return body.replace("@SEPS@", _separators(need)), "import subprocess\n\n"


def test_a_shifted_waiver_does_not_exempt_an_unwaived_site(tmp_path: Path) -> None:
    """The SILENT direction: a displaced waiver must not excuse a real site (#1110).

    COVERS SITE `_check_module` - the FINDINGS channel.

    This is the direction that motivated the issue. The noisy direction
    announces itself with a red build; this one produces a green the gate did
    not earn. The waiver here exempts nothing as written - it sits at module
    level - and the separators move its computed number onto a replacement that
    carries no waiver at all.
    """
    body, prefix = _shifted_exemption_source()
    full = PREAMBLE + prefix + body
    landed = _waiver_by_splitlines(full)
    site = next(
        i for i, line in enumerate(full.split("\n"), start=1) if "subprocess.run(['b']" in line
    )
    assert landed == site, (
        f"the shifted waiver lands on line {landed}, not on the site at {site} - "
        "the fixture no longer reproduces the silent exemption and this test is "
        "not measuring anything"
    )
    assert _findings(tmp_path, prefix + body) != []


def test_the_survey_counts_are_in_tokenizer_coordinates(tmp_path: Path) -> None:
    """COVERS SITE `survey_paths` - and this test is the ONLY guard it has.

    NOT ordinary coverage. An exit-code negative control CANNOT reach this
    site, which was measured while fixing #1110: repairing `_check_module`
    alone turns every committed case GREEN - both directions, both gates -
    while `survey_paths` still numbers waivers with `splitlines()`. The
    findings list and the exit code both come from `_check_module`; only the
    printed COUNTS come from here. With this site still broken the gate emitted

        negative-fixture: 0 of 0 wholesale PATH replacement(s) lack a
        precondition assertion, in 1 function(s)

    a self-contradicting line that no exit code distinguishes from a healthy
    one. So if this test is deleted, weakened, or reduced to asserting the
    findings list, site `survey_paths` has no guard whatsoever and a regression
    there will ship green.

    The assertion is therefore on the COUNTS specifically, never on findings.
    """
    path = tmp_path / "test_sample.py"
    path.write_text(PREAMBLE + "import subprocess\n\n" + WAIVED_AFTER_SEPARATORS, encoding="utf-8")
    survey = checker.survey_paths([path])
    assert survey.sites == 0, (
        f"survey_paths counted {survey.sites} site(s); the only replacement in "
        "this source is waived, so a non-zero count means the waiver was numbered "
        "in splitlines() coordinates while the site was numbered by ast"
    )
    assert survey.unasserted_sites == 0


def test_survey_paths_does_not_crash_on_an_unparseable_file(tmp_path: Path) -> None:
    """REPRODUCES A CRASH against pre-guard code (#1110).

    `_check_module` swallows SyntaxError and returns [] - "a broken test file is
    pytest's problem" - and `survey_paths` re-parsed the same source two lines
    later with no guard, so the gate died with an uncaught SyntaxError on exactly
    the input the comment above it says is tolerated. It produced no verdict at
    all and redded `make verify` for a reason unrelated to what it checks.

    PRE-EXISTING, not a regression from this issue's fix: reproduces against
    merge base e3a053f. Stated as a ref a reviewer can check, because "predates
    my change" is not checkable and "reproduces against e3a053f" is.
    """
    path = tmp_path / "test_broken.py"
    path.write_text("def test_broken(\n", encoding="utf-8")

    survey = checker.survey_paths([path])  # raised SyntaxError before the guard

    assert survey.unparseable == (path,)
    assert survey.sites == 0


def test_an_unparseable_file_never_renders_as_a_clean_bill(tmp_path: Path, capsys) -> None:
    """Skipping the file is not enough - the verdict must not read `ok` (#1110).

    The guard alone converted a loud wrong-reason crash into a SILENT unearned
    green: `files_scanned` counts what was handed to the gate, not what it read,
    so an unparseable file sat in the denominator asserting an inspection that
    never happened. The fixture below hides a REAL unwaived wholesale PATH
    replacement inside the unparseable file, which is the case that makes this a
    false negative rather than a cosmetic overclaim.

    This is #840's rule at file granularity: that issue keyed the `ok` message on
    "a tests/ that exists but holds no test files" being the same
    examined-nothing condition as a missing directory. A file that exists but
    cannot be parsed is that condition one level down.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_broken.py").write_text(
        'import subprocess\ndef test_broken(\n    subprocess.run(["a"], env={"PATH": "/x"})\n',
        encoding="utf-8",
    )

    exit_code = checker.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 1, "an unexaminable population member must not exit 0"
    assert "UNKNOWN - " in out, (
        "the refusal must carry the harness's refusal marker, or the control "
        "scores it as a successful DETECTION - see the disjointness test below"
    )
    assert "could not be parsed" in out
    assert "test_broken.py" in out, "the unreadable file must be NAMED, not just counted"
    assert "ok -" not in out, (
        "the gate rendered its clean verdict over a file it could not read - the "
        "exact false clean bill #840 keyed the `ok` message against"
    )


def test_the_gate_still_reports_clean_when_every_file_parses(tmp_path: Path, capsys) -> None:
    """THE POSITIVE CONTROL for the test above, and it is not decoration.

    "An unparseable file does not produce a clean bill" passes trivially on a
    gate that has stopped being able to report clean AT ALL - a guard that reds
    everything satisfies it perfectly while destroying the instrument. This
    asserts the other direction on the same code path: a tree whose files all
    parse still reaches `ok` and still exits 0.

    Together the two pin a DISCRIMINATION rather than a behaviour: the verdict
    tracks whether the population was readable, not merely whether the gate is
    capable of saying no.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_fine.py").write_text(
        "def test_fine():\n    assert True\n", encoding="utf-8"
    )

    exit_code = checker.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "ok -" in out
    assert "could not be parsed" not in out


def test_a_parse_refusal_is_not_scored_as_a_detection(tmp_path: Path, capsys) -> None:
    """The refusal marker and the detection marker must be DISJOINT (#1110).

    FOUND BY COUNTER-MODEL REVIEW, against the first version of this fix. That
    version deliberately ended the refusal line in the gate's own "nothing was
    scanned" idiom so the registered control's `detect_signal` would match it
    with no regex change. The reasoning was about the detector's COVERAGE and
    missed what the match MEANS: `detect_signal` is how the harness scores a
    SUCCESSFUL DETECTION. A case whose neighbouring file merely failed to parse
    then earned `BAD` even when its planted violation was silently waived, so
    the control could no longer tell detecting OUR defect from failing to
    examine a NEIGHBOUR'S - detector-contracts question 2, breaking inside the
    instrument built to answer it.

    #1129's `unknown_signal` is the harness's first-class way to say "refused
    because of this input", and it is checked BEFORE `detect_signal`. This test
    asserts the two markers cannot both claim the same output, in BOTH
    directions - a refusal must not read as a detection, and a real detection
    must not read as a refusal. One direction alone would pass on a gate that
    emitted neither marker at all.

    It reads the live control.json rather than hardcoding the patterns, so
    editing either signal without re-checking the pairing fails here.
    """
    import json
    import re

    manifest = json.loads(
        (ROOT / "controls" / "check-negative-fixture-preconditions" / "control.json").read_text(
            encoding="utf-8"
        )
    )
    detect = manifest["detect_signal"]
    unknown = manifest["unknown_signal"]

    # --- a refusal -------------------------------------------------------- #
    refusal_dir = tmp_path / "refusal" / "tests"
    refusal_dir.mkdir(parents=True)
    (refusal_dir / "test_broken.py").write_text("def test_broken(\n", encoding="utf-8")
    assert checker.main(["--root", str(tmp_path / "refusal")]) == 1
    refusal_out = capsys.readouterr().out

    assert re.search(unknown, refusal_out, re.MULTILINE), "refusal must match unknown_signal"
    assert not re.search(detect, refusal_out, re.MULTILINE), (
        "the refusal line matches detect_signal, so the harness will score a "
        "parse refusal as a successful detection and the control can no longer "
        "distinguish its planted defect from an unparseable neighbour"
    )

    # --- a real detection, the other direction ---------------------------- #
    detect_dir = tmp_path / "detect" / "tests"
    detect_dir.mkdir(parents=True)
    (detect_dir / "test_real.py").write_text(
        "import subprocess\n\n\n"
        "def test_unwaived(tmp_path):\n"
        "    stub = tmp_path / 'bin'\n"
        "    stub.mkdir()\n"
        "    subprocess.run(['a'], env={'PATH': str(stub)}, capture_output=True)\n",
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path / "detect")]) == 1
    detect_out = capsys.readouterr().out

    assert re.search(detect, detect_out, re.MULTILINE), "a real violation must match detect_signal"
    assert not re.search(unknown, detect_out, re.MULTILINE), (
        "a real detection matches unknown_signal, so the harness would excuse it "
        "as a refusal - the fail-open direction of the same collision"
    )
