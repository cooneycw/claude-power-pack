"""The observer's mocked local population is explicit; no host state decides it."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OBSERVER = ROOT / "scripts" / "flow-preflight.py"
BOOTSTRAP = ROOT / "scripts" / "flow-preflight.sh"


def test_selected_population_never_probes_unselected_prerequisites(observer, monkeypatch):
    module, args, _, _ = observer
    args.checks = ("gh", "engine")
    monkeypatch.setattr(module, "python_check", lambda *a: pytest.fail("unselected Python probe"))
    monkeypatch.setattr(module.shutil, "which", lambda name: "gh" if name == "gh" else pytest.fail(name))
    report, code = module.observe(args)
    assert code == 0 and report["status"] == "selected_ready"
    assert report["scope"] == "selected" and report["full_host_ready"] is None
    assert report["selected_checks"] == ["gh", "engine"]
    assert report["unexamined_checks"] == ["uv", "cpp_python", "user.name", "user.email", "codex"]
    assert [item["id"] for item in report["checks"]] == ["gh", "engine"]


@pytest.mark.parametrize("selector", ["", "gh,", "unknown", "gh,gh", "all,gh", " gh", "gh,,engine"])
def test_invalid_or_ambiguous_selector_is_a_usage_error(observer, selector):
    module, _, _, _ = observer
    with pytest.raises(argparse.ArgumentTypeError):
        module.parse_checks(selector)


def test_selector_order_is_canonical_and_default_all_remains_full(observer):
    module, args, _, _ = observer
    assert module.parse_checks("engine,gh") == ("gh", "engine")
    assert module.parse_checks("all") == module.CHECK_IDS
    report, code = module.observe(args)
    assert report["status"] == "ready" and code == 0
    assert report["scope"] == "full" and report["full_host_ready"] is True
    assert report["selected_checks"] == list(module.CHECK_IDS)
    assert report["unexamined_checks"] == []


@pytest.mark.parametrize(
    "corruption", ["schema", "population", "scope", "status", "counts", "required", "exit", "duplicate", "missing"]
)
def test_report_validator_refuses_zero_exit_with_unproved_readiness(observer, corruption):
    module, args, _, _ = observer
    args.checks = ("gh", "engine")
    report, code = module.observe(args)
    assert code == 0
    assert module.validate_report(json.dumps(report), code, args.checks) == report
    if corruption == "schema":
        report["schema"] = True
    elif corruption == "population":
        report["checks"].pop()
    elif corruption == "scope":
        report["full_host_ready"] = True
    elif corruption == "status":
        report["checks"][0]["status"] = "unknown"
    elif corruption == "counts":
        report["required_gaps"] = True
    elif corruption == "required":
        report["checks"][0]["required"] = False
    elif corruption == "exit":
        code = 3
    elif corruption == "missing":
        del report["unexamined_checks"]
    raw = json.dumps(report)
    if corruption == "duplicate":
        raw = '{"schema":999,' + raw[1:]
    with pytest.raises(ValueError):
        module.validate_report(raw, code, args.checks)


def test_valid_unknown_and_gap_reports_retain_their_nonzero_exit(observer, monkeypatch):
    module, args, _, _ = observer
    args.checks = ("gh",)
    for status, code in (("unknown", 3), ("missing", 1)):
        monkeypatch.setattr(module, "gh_check", lambda *a: module.check("gh", status, "controlled"))
        report, actual = module.observe(args)
        assert actual == code
        assert module.validate_report(json.dumps(report), actual, args.checks) == report
        with pytest.raises(ValueError):
            module.validate_report(json.dumps(report), 0, args.checks)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bootstrap requires bash")
@pytest.mark.parametrize("shell", [False, True])
@pytest.mark.parametrize("outcome", [0, 1, 3, "usage", "exception"])
def test_exit_markers_preserve_status_and_data(tmp_path, shell, outcome):
    """Exercise the shipped entrypoint wrapper with a controlled observer body."""
    source = OBSERVER.read_text()
    if outcome == "usage":
        stub = ""  # Real argparse rejects the unknown argument below.
    elif outcome == "exception":
        stub = '\ndef main():\n    raise RuntimeError("controlled failure")\n\n'
    else:
        stub = f"\ndef main():\n    print('{{\"controlled\":true}}')\n    return {outcome}\n\n"
    assert source.count('if __name__ == "__main__":') == 1
    payload = tmp_path / OBSERVER.name
    payload.write_text(source.replace('if __name__ == "__main__":', stub + 'if __name__ == "__main__":'))
    launcher = tmp_path / BOOTSTRAP.name
    launcher.write_text(BOOTSTRAP.read_text())
    argv = ["bash", str(launcher)] if shell else [sys.executable, str(payload)]
    result = subprocess.run(argv + ["--invalid-argument"], capture_output=True, text=True, timeout=30)
    expected = 2 if outcome == "usage" else 1 if outcome == "exception" else outcome
    assert result.returncode == expected
    namespace = "FLOW_PREFLIGHT_BOOTSTRAP" if shell else "FLOW_PREFLIGHT"
    assert result.stderr.splitlines()[-1] == f"{namespace}_EXIT={expected}"
    if isinstance(outcome, int):
        assert json.loads(result.stdout) == {"controlled": True}
    if outcome == "exception":
        assert "RuntimeError: controlled failure" in result.stderr
    combined = subprocess.run(
        argv + ["--invalid-argument"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30
    )
    assert combined.stdout.splitlines()[-1] == f"{namespace}_EXIT={expected}"


@pytest.mark.skipif(
    not Path("/dev/full").exists() or shutil.which("bash") is None, reason="requires /dev/full and bash"
)
@pytest.mark.parametrize("shell", [False, True])
def test_failed_stdout_flush_keeps_error_status_and_last_marker(tmp_path, shell):
    source = OBSERVER.read_text()
    entry = 'if __name__ == "__main__":'
    assert source.count(entry) == 1
    payload = tmp_path / OBSERVER.name
    payload.write_text(source.replace(entry, '\ndef main():\n    print("buffered output")\n    return 0\n\n' + entry))
    launcher = tmp_path / BOOTSTRAP.name
    launcher.write_text(BOOTSTRAP.read_text())
    argv = ["bash", str(launcher)] if shell else [sys.executable, str(payload)]
    with Path("/dev/full").open("w") as full:
        result = subprocess.run(argv, stdout=full, stderr=subprocess.PIPE, text=True, timeout=30)
    assert result.returncode == 1  # Interpreter shutdown must not replace it with 120.
    assert "OSError: [Errno 28]" in result.stderr
    namespace = "FLOW_PREFLIGHT_BOOTSTRAP" if shell else "FLOW_PREFLIGHT"
    assert result.stderr.splitlines()[-1] == f"{namespace}_EXIT=1"


@pytest.fixture
def observer(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("flow_preflight", OBSERVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    home = tmp_path / "home"
    home.mkdir()
    engine = home / ".claude/scripts/project-next.py"
    engine.parent.mkdir(parents=True)
    engine.write_text("from lib.project_next.rank import CONTRACT_VERSION\n")
    library = home / ".claude/lib/project_next"
    library.mkdir(parents=True)
    (library / "ownership.json").write_text(
        json.dumps({"owner": "cooneycw/claude-power-pack", "contract_version": "1.6"})
    )
    (library / "rank.py").write_text('CONTRACT_VERSION = "1.6"\n')
    monkeypatch.setattr(module.Path, "home", lambda: home)
    monkeypatch.setattr(module.shutil, "which", lambda name: name)

    def local_run(argv, cwd, env=None):
        if argv[:2] == ["gh", "--version"]:
            return 0, "gh version 2.103.2\n", ""
        if argv[0] == "gh":
            fields = sorted(module.REQUIRED_FIELDS[argv[1]])
            text = f'Unknown JSON field: "{module.SENTINEL}"\nAvailable fields:\n'
            return 1, "", text + "\n".join("  " + field for field in fields)
        if argv[0].startswith("python"):
            return 0, "Python 3.11.14\n", ""
        if argv[:3] == ["git", "config", "--get"]:
            return 0, "dummy-identity-value\n", ""
        raise AssertionError("Unexpected command population")

    module._original_probe = module.run
    monkeypatch.setattr(module, "run", local_run)
    args = argparse.Namespace(repo=str(tmp_path), harness="claude", engine=None)
    return module, args, home, engine


def test_known_healthy_population_and_identity_values_withheld(observer):
    module, args, _, _ = observer
    report, code = module.observe(args)
    assert code == 0 and report["status"] == "ready"
    assert len(report["checks"]) == 7
    assert "dummy-identity-value" not in json.dumps(report)


def test_optional_only_absence_is_warning_not_required_gap(observer, monkeypatch):
    module, args, _, _ = observer
    monkeypatch.setattr(module.shutil, "which", lambda name: None if name == "codex" else name)
    report, code = module.observe(args)
    assert code == 0 and report["status"] == "ready"
    assert next(c for c in report["checks"] if c["id"] == "codex")["status"] == "warning"


def test_all_gaps_are_aggregated_and_unknowns_not_erased(observer, monkeypatch):
    module, args, _, engine = observer
    engine.unlink()
    assert not engine.exists()
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(module, "run", lambda *args: (None, "", ""))
    report, code = module.observe(args)
    assert code == 1 and report["status"] == "gaps"
    assert report["required_gaps"] >= 4 and report["required_unknown"] == 2
    assert len(report["checks"]) == 7


def test_unknown_gh_is_not_ready_and_provider_output_is_not_disclosed(observer, monkeypatch):
    module, args, _, _ = observer
    original = module.run
    monkeypatch.setattr(
        module,
        "run",
        lambda argv, *rest: (4, "", "dummy-provider-private-output") if argv[0] == "gh" else original(argv, *rest),
    )
    report, code = module.observe(args)
    assert code == 3 and report["status"] == "unknown"
    assert "dummy-provider-private-output" not in json.dumps(report)


def test_neighbor_metadata_cannot_replace_missing_selected_engine(observer):
    module, args, home, engine = observer
    engine.unlink()
    assert (home / ".claude/lib/project_next/ownership.json").is_file()
    assert not engine.exists()
    result = module.engine_check("claude", None, home)
    assert result["status"] == "missing"


def test_manifest_mismatch_and_corruption_are_distinct(observer):
    module, _, home, _ = observer
    manifest = home / ".claude/lib/project_next/ownership.json"
    manifest.write_text(json.dumps({"owner": "cooneycw/claude-power-pack", "contract_version": "different"}))
    assert module.engine_check("claude", None, home)["status"] == "unsupported"
    manifest.write_text("not JSON")
    assert module.engine_check("claude", None, home)["status"] == "unknown"


@pytest.mark.parametrize("code", [None, -15, 4, 1])
def test_interrupted_and_unrelated_provider_errors_remain_unknown(observer, monkeypatch, code):
    module, args, _, _ = observer
    original = module.run
    monkeypatch.setattr(
        module,
        "run",
        lambda argv, *rest: (code, "", "unrelated diagnostic") if argv[0] == "gh" else original(argv, *rest),
    )
    report, exit_code = module.observe(args)
    assert exit_code == 3 and report["required_unknown"] == 1
    assert len(report["checks"]) == 7


def test_known_field_population_without_required_capability_is_unsupported(observer, monkeypatch):
    module, args, _, _ = observer
    original = module.run

    def old_fields(argv, *rest):
        if argv[:2] == ["gh", "issue"]:
            return 1, "", f'Unknown JSON field: "{module.SENTINEL}"\nAvailable fields:\n  assignees\n'
        return original(argv, *rest)

    monkeypatch.setattr(module, "run", old_fields)
    report, code = module.observe(args)
    assert code == 1
    gh = next(item for item in report["checks"] if item["id"] == "gh")
    assert gh["status"] == "unsupported" and "blockedBy" in gh["evidence"]["missing_fields"]


def test_field_enumeration_with_extra_provider_output_is_unknown(observer, monkeypatch):
    module, args, _, _ = observer
    original = module.run

    def noisy(argv, *rest):
        code, out, err = original(argv, *rest)
        if argv[:2] == ["gh", "issue"]:
            err += "\nHTTP request debug must not be accepted\n"
        return code, out, err

    monkeypatch.setattr(module, "run", noisy)
    report, code = module.observe(args)
    assert code == 3 and report["status"] == "unknown"


def test_explicit_engine_follows_its_symlink_and_ignores_neighbor_pin(observer, tmp_path):
    module, _, home, engine = observer
    link = tmp_path / "active-entry.py"
    link.symlink_to(engine)
    assert link.is_symlink()
    result = module.engine_check("claude", link, home)
    assert result["status"] == "ok" and result["evidence"]["contract"] == "1.6"


def test_codex_harness_resolves_the_declared_install_not_claude_neighbor(observer, monkeypatch, tmp_path):
    module, _, home, engine = observer
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    assert engine.exists()
    assert module.engine_check("codex", None, home)["status"] == "missing"


def test_ambiguous_auto_harness_does_not_select_a_neighbor(observer, monkeypatch):
    module, _, home, _ = observer
    monkeypatch.setenv("CODEX_THREAD_ID", "dummy-native")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "dummy-other")
    assert module.engine_check("auto", None, home)["status"] == "unknown"


def test_invalid_interpreter_does_not_make_runtime_ready(observer, monkeypatch):
    module, args, home, _ = observer
    original = module.run
    monkeypatch.setattr(
        module,
        "run",
        lambda argv, *rest: (
            (0, "unexpected runtime output", "") if argv[0].startswith("python") else original(argv, *rest)
        ),
    )
    result = module.python_check(Path(args.repo), home)
    assert result["status"] == "unknown"


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("sh") is None, reason="needs bash and sh")
@pytest.mark.parametrize("old_python", [False, True])
def test_bootstrap_reports_unknown_before_observer_import(tmp_path, old_python):
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    if old_python:
        fake = binary_dir / "python3"
        fake.write_text("#!" + shutil.which("sh") + "\nexit 1\n")
        fake.chmod(0o755)
        assert shutil.which("python3", path=str(binary_dir)) == str(fake)
    else:
        assert shutil.which("python3", path=str(binary_dir)) is None
    result = subprocess.run(
        [shutil.which("bash"), str(BOOTSTRAP), "--json"],
        env=dict(os.environ, PATH=str(binary_dir)),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3
    report = json.loads(result.stdout)
    assert report["status"] == "unknown" and report["checks"][0]["id"] == "observer_python"
    assert result.stderr.strip() == "FLOW_PREFLIGHT_BOOTSTRAP_EXIT=3"


def test_timeout_and_nonexecutable_probes_are_unknown_without_output(observer, monkeypatch):
    module, args, _, _ = observer

    def timeout(*argv, **kwargs):
        raise subprocess.TimeoutExpired("dummy-command", 10)

    monkeypatch.setattr(module.subprocess, "run", timeout)
    assert module._original_probe(["dummy-command"], Path(args.repo)) == (None, "", "")

    def denied(*argv, **kwargs):
        raise PermissionError("dummy-private-output")

    monkeypatch.setattr(module.subprocess, "run", denied)
    assert module._original_probe(["dummy-command"], Path(args.repo)) == (None, "", "")


def test_observer_parses_as_310_syntax_without_claiming_310_runtime():
    ast.parse(OBSERVER.read_text(), feature_version=(3, 10))


def test_unreadable_managed_runtime_inventory_is_unknown(observer, monkeypatch):
    module, args, home, _ = observer
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    assert module.shutil.which("python3.11") is None

    def denied(path):
        raise PermissionError("dummy-private-directory")

    monkeypatch.setattr(module.Path, "iterdir", denied)
    assert module.python_check(Path(args.repo), home)["status"] == "unknown"


def test_gh_probes_override_inherited_telemetry_and_update_settings(observer, monkeypatch):
    module, args, _, _ = observer
    original = module.run
    calls = []
    monkeypatch.setenv("GH_TELEMETRY", "on")
    monkeypatch.setenv("DO_NOT_TRACK", "0")
    monkeypatch.setenv("GH_NO_UPDATE_NOTIFIER", "0")
    monkeypatch.setenv("GH_NO_EXTENSION_UPDATE_NOTIFIER", "0")

    def recorded(argv, cwd, env=None):
        if argv[0] == "gh":
            calls.append(argv)
            assert env is not None
            assert env["GH_TELEMETRY"] == "off"
            assert env["DO_NOT_TRACK"] == "1"
            assert env["GH_NO_UPDATE_NOTIFIER"] == "1"
            assert env["GH_NO_EXTENSION_UPDATE_NOTIFIER"] == "1"
            assert env["GH_CONFIG_DIR"].startswith(str(module.Path.home()))
        return original(argv, cwd, env)

    monkeypatch.setattr(module, "run", recorded)
    report, code = module.observe(args)
    assert code == 0 and report["status"] == "ready"
    assert calls == [
        ["gh", "--version"],
        ["gh", "issue", "list", "--json", module.SENTINEL],
        ["gh", "pr", "list", "--json", module.SENTINEL],
    ]


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("dirname") is None, reason="effects fixture requires bash and dirname"
)
def test_effects_detector_rejects_the_committed_writing_provider(tmp_path):
    case = ROOT / "controls/flow-preflight/effects-cases/writes-home"
    assert json.loads((case / "case.json").read_text())["mode"] == "writing-provider"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "controls/flow-preflight/run-case.py"),
            str(case),
            str(BOOTSTRAP),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "unexpected observer writes" in result.stderr
    assert "FLOW_PREFLIGHT_CONTROL: ready" not in result.stdout


@pytest.mark.skipif(shutil.which("python3") is None, reason="requires a real Python provider process")
def test_invalid_provider_bytes_remain_unknown_and_other_checks_are_reported(observer, monkeypatch, capsys):
    module, args, _, _ = observer
    command = [sys.executable, "-c", "import os; os.write(1, bytes([255]))"]
    raw = subprocess.run(command, cwd=args.repo, capture_output=True)
    assert raw.returncode == 0 and raw.stdout == bytes([255])
    with pytest.raises(UnicodeDecodeError):
        raw.stdout.decode("utf-8")
    original = module.run

    def invalid_provider(argv, cwd, env=None):
        if argv[0] == "gh":
            return module._original_probe(command, cwd, env)
        return original(argv, cwd, env)

    monkeypatch.setattr(module, "run", invalid_provider)
    report, code = module.observe(args)
    assert code == 3 and report["status"] == "unknown"
    assert len(report["checks"]) == 7
    assert next(c for c in report["checks"] if c["id"] == "engine")["status"] == "ok"
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_usable_path_python_is_not_outvoted_by_unreadable_neighbor(observer, monkeypatch):
    module, args, home, _ = observer

    def denied(path):
        raise PermissionError("dummy-neighbor")

    monkeypatch.setattr(module.Path, "iterdir", denied)
    assert module.python_check(Path(args.repo), home)["status"] == "ok"


def test_looping_engine_does_not_abort_aggregate(observer):
    module, args, _, engine = observer
    engine.unlink()
    engine.symlink_to(engine.name)
    assert engine.is_symlink()
    report, code = module.observe(args)
    assert code == 3 and len(report["checks"]) == 7
    assert next(item for item in report["checks"] if item["id"] == "engine")["status"] == "unknown"


def test_looping_repository_does_not_abort_independent_observations(observer, tmp_path):
    module, args, _, _ = observer
    loop = tmp_path / "loop"
    loop.symlink_to(loop.name)
    args.repo = str(loop)
    assert loop.is_symlink()
    report, code = module.observe(args)
    assert code == 3 and len(report["checks"]) == 7
    assert next(item for item in report["checks"] if item["id"] == "engine")["status"] == "ok"
    assert next(item for item in report["checks"] if item["id"] == "user.email")["status"] == "unknown"


@pytest.mark.parametrize("namespace", ["lib.project_next_neighbor", ".lib.project_next"])
def test_neighbor_or_relative_import_is_not_cpp_identity(observer, namespace):
    module, _, home, engine = observer
    engine.write_text(f"from {namespace} import main\n")
    assert (home / ".claude/lib/project_next/ownership.json").exists()
    assert module.engine_check("claude", None, home)["status"] == "unknown"


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("dirname") is None,
    reason="control bootstrap requires bash and dirname",
)
def test_all_gaps_control_does_not_depend_on_host_python_version(tmp_path):
    import shlex

    wrapper = tmp_path / "host-python"
    wrapper.write_text(
        "#!" + shutil.which("bash") + "\n"
        "if [[ ${1:-} == --version ]]; then printf 'Python 3.11.14\\n'; exit 0; fi\n"
        "exec " + shlex.quote(sys.executable) + ' "$@"\n'
    )
    wrapper.chmod(0o755)
    version = subprocess.run([str(wrapper), "--version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout == "Python 3.11.14\n"
    # Simulate sys.executable reporting 3.11 for the fixture's version observation;
    # execution still delegates to this test's interpreter, not a native 3.11 claim.
    driver = ROOT / "controls/flow-preflight/run-case.py"
    case = ROOT / "controls/flow-preflight/cases/bad-all-gaps"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys,runpy; p=sys.argv[2]; sys.executable=sys.argv[1]; "
            "sys.argv=sys.argv[2:]; runpy.run_path(p,run_name='__main__')",
            str(wrapper),
            str(driver),
            str(case),
            str(BOOTSTRAP),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "FLOW_PREFLIGHT_CONTROL: blocked" in result.stdout


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("dirname") is None,
    reason="adverse command fixture requires bash and dirname",
)
@pytest.mark.parametrize("case_name", ["gh-auth-command", "uv-install-command"])
def test_fixture_allowlist_rejects_committed_unexpected_fake_commands(case_name):
    case = ROOT / "controls/flow-preflight/effects-cases" / case_name
    data = json.loads((case / "case.json").read_text())
    assert data["mode"] == "unexpected-command"
    assert data["unexpected"] in (["gh", "auth", "status"], ["uv", "python", "install", "3.11"])
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "controls/flow-preflight/run-case.py"),
            str(case),
            str(BOOTSTRAP),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "unexpected side-effect-capable command" in result.stderr
    assert "FLOW_PREFLIGHT_CONTROL: ready" not in result.stdout


@pytest.mark.parametrize("creation_order", [("good", "broken"), ("broken", "good")])
def test_usable_managed_python_wins_over_looping_neighbor(observer, monkeypatch, tmp_path, creation_order):
    module, args, home, _ = observer
    managed = tmp_path / "managed"
    good = managed / "cpython-3.11.good/bin/python3.11"
    broken = managed / "cpython-3.11.broken/bin/python3.11"
    for kind in creation_order:
        candidate = good if kind == "good" else broken
        candidate.parent.mkdir(parents=True)
        if kind == "good":
            candidate.write_text("dummy interpreter observation")
        else:
            candidate.symlink_to(candidate.name)
    assert good.is_file() and broken.is_symlink()
    with pytest.raises(OSError):
        broken.stat()
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(managed))
    original = module.run
    monkeypatch.setattr(
        module,
        "run",
        lambda argv, *rest: (0, "Python 3.11.14\n", "") if argv[0] == str(good) else original(argv, *rest),
    )
    assert module.python_check(Path(args.repo), home)["status"] == "ok"


def test_only_broken_managed_python_stays_unknown(observer, monkeypatch, tmp_path):
    module, args, home, _ = observer
    managed = tmp_path / "managed"
    broken = managed / "cpython-3.11.broken/bin/python3.11"
    broken.parent.mkdir(parents=True)
    broken.symlink_to(broken.name)
    with pytest.raises(OSError):
        broken.stat()
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(managed))
    assert module.python_check(Path(args.repo), home)["status"] == "unknown"


def test_known_nonselected_python_and_empty_managed_root_is_missing(observer, monkeypatch, tmp_path):
    module, args, home, _ = observer
    managed = tmp_path / "empty-managed"
    managed.mkdir()
    assert managed.is_dir() and not list(managed.iterdir())
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(managed))
    monkeypatch.setattr(module.shutil, "which", lambda name: "python3" if name == "python3" else None)
    monkeypatch.setattr(module, "run", lambda *argv: (0, "Python 3.12.3\n", ""))
    assert module.python_check(Path(args.repo), home)["status"] == "missing"


def test_invalid_only_managed_candidate_is_unknown(observer, monkeypatch, tmp_path):
    module, args, home, _ = observer
    managed = tmp_path / "managed"
    invalid = managed / "cpython-3.11.invalid/bin/python3.11"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("dummy-invalid-provider")
    assert invalid.is_file()
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(managed))
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(module, "run", lambda *argv: (0, "not a Python version\n", ""))
    assert module.python_check(Path(args.repo), home)["status"] == "unknown"
