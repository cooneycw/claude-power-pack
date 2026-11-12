"""Exercise source resolution, honest classification and a failed population scan."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


checker = load("cpp_init_promises", ROOT / "scripts/check-cpp-init-promises.py")
cases = load("cpp_init_promises_cases", ROOT / "controls/cpp-init-promises/run-case.py")


def test_fixed_real_document_resolves():
    report = checker.scan((ROOT / checker.DOCUMENT).read_text(), ROOT, checker.MIN_PROMISES)
    assert not report.findings
    assert len(report.supplied) >= 43
    assert {c.kind for c in report.claims} >= {"cpp", "generated", "consumer", "external", "retirement"}


@pytest.mark.parametrize(
    "scenario",
    [
        "bad-braced-source",
        "bad-generation-hides-source",
        "bad-source-retirement-comment",
        "bad-negative-then-positive",
        "bad-generation-source-operand",
        "bad-unknown-before-known",
        "bad-unknown-after-known",
        "bad-braced-home",
        "bad-source-modifier",
        "bad-generated-cache-hides-install",
        "bad-parent-source",
        "bad-uppercase-source-relation",
        "bad-conditional-retirement-comment",
        "bad-uppercase-unknown-operand",
        "bad-missing-helper",
        "bad-real-hooks-json",
        "bad-unclassified",
        "bad-empty",
        "bad-near-empty",
        "bad-retirement-hides-promise",
        "bad-placeholder",
        "bad-escape",
        "good-fixed",
        "good-retirement",
    ],
)
def test_committed_cases(tmp_path, scenario):
    cases.populate(tmp_path, scenario)
    report = checker.scan((tmp_path / checker.DOCUMENT).read_text(), tmp_path, checker.MIN_PROMISES)
    assert bool(report.findings) == scenario.startswith("bad-")
    if scenario == "bad-real-hooks-json":
        assert any(".claude/hooks.json" in f for f in report.findings)
        assert all("hook-mask-output.sh" not in f for f in report.findings)
    if scenario == "bad-unclassified":
        assert any("unclassified promise at .claude/commands/cpp/init.md:" in f for f in report.findings)


@pytest.mark.parametrize("separator", ["; ", ". ", " but ", " and now ", ", ", " and "])
def test_retirement_does_not_hide_positive_promise(tmp_path, separator):
    assert not (tmp_path / "scripts/missing.sh").exists()
    text = f"Retired scripts/old.sh{separator}installs scripts/missing.sh"
    report = checker.scan(text, tmp_path, 1)
    assert any("missing.sh" in finding for finding in report.findings)


def test_supported_path_forms_and_non_cpp_targets(tmp_path):
    for name in ["scripts/helper.sh", ".claude/commands/family/action.md"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("present\n")
    text = """## Step 4: Disclose
### Tier 2 (~/.claude/scripts/)
  - helper.sh standalone
Installs: /family:action
Links: $CPP_DIR/.claude/commands/<family>
Copies: "$CPP_DIR"/scripts/*.sh
Copies: "${CPP_DIR}/scripts/helper.sh"
Links: "${HOME}/.claude/scripts/helper.sh"
Creates: .claude/generated.json
To undo:
  rm .claude/generated.json
Proceed? [y/N]
## Step 5: Execute
Installs: ~/.config/consumer/config.json
Installs: https://example.invalid/service
"""
    report = checker.scan(text, tmp_path, 1)
    assert not report.findings
    assert len(report.supplied) == 5
    assert {c.kind for c in report.claims} >= {"cpp", "generated", "consumer", "external"}


def test_missing_document_is_unknown(tmp_path, capsys):
    assert not (tmp_path / checker.DOCUMENT).exists()
    assert checker.main(["--root", str(tmp_path)]) == 2
    assert "UNKNOWN - cannot read population" in capsys.readouterr().out


@pytest.mark.parametrize(
    "statement",
    [
        "Installs unknown-runtime-target",
        "Installs: scripts/missing.sh and https://example.invalid/scripts/missing.sh",
    ],
)
def test_unknown_and_missing_are_not_hidden_by_other_text(tmp_path, statement):
    assert not (tmp_path / "scripts/missing.sh").exists()
    report = checker.scan(statement, tmp_path, 1)
    assert any("unclassified promise" in f or "missing promised path" in f for f in report.findings)


# --- a promised path must be tracked (issue #1716, seq 626) -----------------

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _checkout(root: Path, *tracked: str) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for name in tracked:
        subprocess.run(["git", "-C", str(root), "add", "--", name], check=True)


def _helper_tree(root: Path) -> str:
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "helper.sh").write_text("#!/bin/sh\n")
    return 'cp "$CPP_DIR/scripts/helper.sh" /consumer/destination'


@requires_git
def test_a_promised_file_that_is_tracked_resolves(tmp_path):
    text = _helper_tree(tmp_path)
    _checkout(tmp_path, "scripts/helper.sh")
    report = checker.scan(text, tmp_path, 1)
    assert report.tracked_checked
    assert not report.findings


@requires_git
def test_a_promised_file_that_exists_but_is_not_tracked_is_a_finding(tmp_path):
    """The #626 case: an untracked local file passed `Path.exists()` and does not ship."""
    text = _helper_tree(tmp_path)
    _checkout(tmp_path)
    assert (tmp_path / "scripts" / "helper.sh").is_file()  # precondition: it EXISTS
    listed = subprocess.run(
        ["git", "-C", str(tmp_path), "ls-files"], capture_output=True, text=True, check=True
    )
    assert listed.stdout == ""  # precondition: nothing is tracked
    report = checker.scan(text, tmp_path, 1)
    assert report.tracked_checked
    assert len(report.findings) == 1
    assert report.findings[0].startswith("untracked promised path at .claude/commands/cpp/init.md:1:")
    assert "does not ship" in report.findings[0]


@requires_git
def test_a_promised_directory_needs_a_tracked_file_inside_it(tmp_path):
    (tmp_path / ".claude" / "commands" / "family").mkdir(parents=True)
    (tmp_path / ".claude" / "commands" / "family" / "action.md").write_text("present\n")
    text = "Links: $CPP_DIR/.claude/commands/<family>"
    _checkout(tmp_path)
    assert any("untracked promised path" in f for f in checker.scan(text, tmp_path, 1).findings)
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", ".claude/commands/family/action.md"], check=True)
    assert not checker.scan(text, tmp_path, 1).findings


@requires_git
def test_a_glob_is_judged_on_its_tracked_matches(tmp_path):
    """Local debris beside shipped files is not a promise; a glob matching ONLY debris is a finding."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "helper.sh").write_text("#!/bin/sh\n")
    (tmp_path / "scripts" / "__pycache__").mkdir()
    (tmp_path / "scripts" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    text = 'Copies: "$CPP_DIR"/scripts/*'
    _checkout(tmp_path, "scripts/helper.sh")
    assert not checker.scan(text, tmp_path, 1).findings
    subprocess.run(["git", "-C", str(tmp_path), "rm", "-q", "--cached", "scripts/helper.sh"], check=True)
    findings = checker.scan(text, tmp_path, 1).findings
    assert len(findings) == 1 and "nothing it matches is tracked" in findings[0]


def test_outside_a_git_checkout_the_tracked_check_does_not_run_and_says_so(tmp_path, capsys):
    """Not "each is tracked", and not silence: the summary names the check it did not run."""
    cases.populate(tmp_path, "good-fixed")
    assert not (tmp_path / ".git").exists()  # precondition: not a checkout
    assert checker.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "tracked check NOT RUN" in out
    assert "each is tracked" not in out
    assert out.strip().splitlines()[-1].startswith("cpp-init-promises: ok - 43 CPP-supplied paths resolve;")


@requires_git
def test_a_directory_nested_in_another_checkout_is_not_judged_by_that_checkout(tmp_path):
    """`git ls-files` from a subdirectory answers for the ENCLOSING repository."""
    _checkout(tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    text = _helper_tree(nested)
    report = checker.scan(text, nested, 1)
    assert not report.tracked_checked
    assert not report.findings


def test_this_repository_is_clean_under_the_tracked_check():
    report = checker.scan((ROOT / checker.DOCUMENT).read_text(), ROOT, checker.MIN_PROMISES)
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout: the tracked check cannot run here")
    assert report.tracked_checked, "the tracked check did not run on the repository's own checkout"
    assert not [f for f in report.findings if f.startswith("untracked promised path")]


# --- the per-line boundary (issue #1716, seq 674) ---------------------------

# Reproduced inside the disclosure step, which is where a bare path on its own
# line is read as something CPP supplies. Outside it neither shape is a claim.
_DISCLOSURE = "## Step 4: Disclose\n{body}## Step 5: Execute\n"
ONE_LINE = _DISCLOSURE.format(body="Every selected tier also creates project `.claude/cpp-install.json`.\n")
WRAPPED = _DISCLOSURE.format(body="Every selected tier also creates project\n`.claude/cpp-install.json`.\n")


def test_a_generated_file_declared_on_one_line_is_not_a_missing_source(tmp_path):
    assert not (tmp_path / ".claude" / "cpp-install.json").exists()
    report = checker.scan(ONE_LINE, tmp_path, 0)
    assert not report.findings
    assert [(c.kind, c.target) for c in report.claims] == [("generated", ".claude/cpp-install.json")]


def test_the_same_declaration_wrapped_before_its_path_is_a_finding_and_the_output_says_why(tmp_path, capsys):
    """The supported boundary, pinned: classification is per line, and the note names the remedy."""
    report = checker.scan(WRAPPED, tmp_path, 0)
    assert any(f.startswith("missing promised path") and "cpp-install.json" in f for f in report.findings)
    document = tmp_path / checker.DOCUMENT
    document.parent.mkdir(parents=True)
    document.write_text(WRAPPED)
    assert checker.main(["--root", str(tmp_path), "--min-promises", "1"]) == 1
    assert "keep its declaration and its path on one line" in capsys.readouterr().out
