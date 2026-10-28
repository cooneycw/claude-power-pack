"""Real argparse syntax, honest population and committed anti-control cases."""
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


checker = load("cpp_init_cicd_args", ROOT / "scripts/check-cpp-init-cicd-args.py")
cases = load("cpp_init_cicd_args_cases", ROOT / "controls/cpp-init-cicd-args/run-case.py")
SCENARIOS = [p.name for p in (ROOT / "controls/cpp-init-cicd-args/cases").iterdir()]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_committed_case(tmp_path, scenario):
    cases.populate(tmp_path, scenario)
    report = checker.scan(tmp_path)
    assert bool(report.findings) == scenario.startswith("bad-"), report.findings
    if scenario == "bad-flag":
        assert len(report.invocations) == 6, "invalid call must not be hidden by a population failure"
        assert len(report.findings) == 1
        assert "arguments rejected by real" in report.findings[0]
    if scenario in {"good-helper", "good-python-helper"}:
        assert len(report.invocations) == 6
        assert "scripts/child." in " ".join(report.files)


def test_repairing_the_planted_flag_stops_detection(tmp_path):
    cases.populate(tmp_path, "bad-flag")
    document = tmp_path / checker.DOCUMENT
    text = document.read_text()
    assert text.count("--no-such-flag") == 1, "fixture must contain exactly the planted defect"
    before = checker.scan(tmp_path)
    assert len(before.findings) == 1 and len(before.invocations) == 6
    document.write_text(text.replace("--no-such-flag", "--json"))
    after = checker.scan(tmp_path)
    assert not after.findings
    assert len(after.invocations) == after.parsed == 6


def test_neither_command_dispatch_nor_handlers_execute(tmp_path, monkeypatch):
    from lib.cicd import cli

    def forbidden(*args, **kwargs):
        raise AssertionError("syntax checking dispatched a real command")
    monkeypatch.setattr(cli, "main", forbidden)
    for name in vars(cli):
        if name.startswith("cmd_"):
            monkeypatch.setattr(cli, name, forbidden)
    cases.populate(tmp_path, "good-basic")
    assert not checker.scan(tmp_path).findings
    assert not (tmp_path / "Makefile").exists()


def test_cli_factory_changes_are_authoritative(tmp_path, monkeypatch):
    cases.populate(tmp_path, "bad-flag")
    real_factory = checker.create_parser

    def expanded_factory():
        parser = real_factory()
        subparsers = next(a for a in parser._actions if isinstance(a, checker.argparse._SubParsersAction))
        subparsers.choices["detect"].add_argument("--no-such-flag", action="store_true")
        return parser
    assert checker.scan(tmp_path).findings
    monkeypatch.setattr(checker, "create_parser", expanded_factory)
    assert not checker.scan(tmp_path).findings


def test_real_document_population_is_measured():
    report = checker.scan(ROOT)
    direct = [i for i in report.invocations if i.path == checker.DOCUMENT]
    assert len(direct) == checker.MIN_INVOCATIONS == 5
    assert {i.argv[0] for i in direct} == {"detect", "check", "pipeline", "container"}


def test_unreadable_document_is_not_clean(tmp_path, capsys):
    assert not (tmp_path / checker.DOCUMENT).exists()
    assert checker.main(["--root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "unreadable population" in output
    assert "below measured floor" in output


def test_dynamic_choice_uses_the_selected_subcommand(tmp_path, monkeypatch):
    cases.populate(tmp_path, "good-basic")
    document = tmp_path / checker.DOCUMENT
    document.write_text(document.read_text().replace("python -m lib.cicd detect --json",
                                                    'python -m lib.cicd detect --pick "$VALUE"'))
    real_factory = checker.create_parser

    def context_factory():
        parser = real_factory()
        children = next(a for a in parser._actions if isinstance(a, checker.argparse._SubParsersAction)).choices
        children["detect"].add_argument("--pick", choices=["detect-value"])
        children["check"].add_argument("--pick", choices=["neighbor-value"])
        return parser
    monkeypatch.setattr(checker, "create_parser", context_factory)
    assert not checker.scan(tmp_path).findings


@pytest.mark.skipif(shutil.which(sys.executable) is None, reason="Python not on PATH")
def test_parser_gate_runs_without_site_packages(tmp_path):
    cases.populate(tmp_path, "good-basic")
    result = subprocess.run([sys.executable, "-S", str(ROOT / "scripts/check-cpp-init-cicd-args.py"),
                             "--root", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "5/5 invocations parsed" in result.stdout
