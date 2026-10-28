"""Exercise source resolution, honest classification and a failed population scan."""

from __future__ import annotations

import importlib.util
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
