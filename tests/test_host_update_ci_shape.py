"""Owned Git transports plus actual umask-000 checkout inputs."""
import json
import os
import shutil

import pytest

from tests.test_host_update_adapters import cli, git
from tests.test_host_update_adapters import source_template as template_fixture

source_template = template_fixture
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for CI source shapes")


@pytest.mark.parametrize("mask", [0o022, 0o000])
@pytest.mark.parametrize("shape", ["full", "shallow", "worktree"])
def test_actual_entry_source_shapes(source_template, tmp_path, mask, shape):
    source, home = tmp_path / "source", tmp_path / "home"
    home.mkdir()
    previous = os.umask(mask)
    try:
        if shape == "worktree":
            clone = tmp_path / "clone"
            git(tmp_path, "clone", "-q", str(source_template), str(clone))
            git(clone, "worktree", "add", "--detach", str(source), "HEAD")
        else:
            flags = ["--depth=1"] if shape == "shallow" else []
            git(tmp_path, "clone", "-q", *flags, source_template.as_uri(), str(source))
    finally:
        os.umask(previous)
    if mask == 0:
        assert (source / "docs/skills/python-packaging.md").stat().st_mode & 0o777 == 0o666
    if shape == "shallow":
        assert git(source, "rev-parse", "--is-shallow-repository") == "true"
    from tests.test_host_update_links import seed

    seed(home, source)
    result, report = cli(source, home, "refresh", "--select", "codex", "--select", "antigravity",
                         "--select", "claude-topics", cwd=tmp_path)
    assert result.returncode == 0, result.stderr + str(report)
    for row in report["results"]:
        if not row["selected"]:
            continue
        assert row["after"]["state"] == "current" and row["revision"] == report["revision"]
    for root in [home / ".codex/skills", home / ".claude/skills", home / ".gemini/config/skills"]:
        assert next(root.glob("*/SKILL.md")).stat().st_mode & 0o777 == 0o644
    assert git(source, "status", "--porcelain") == ""


def test_dirty_source_does_not_mutate_home(source_template, tmp_path):
    source, home = tmp_path / "source", tmp_path / "home"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    home.mkdir()
    with (source / "CLAUDE.md").open("a") as out:
        out.write("\ndirty input\n")
    assert git(source, "status", "--porcelain")
    result, report = cli(source, home, "refresh", "--select", "antigravity")
    assert result.returncode == 4 and all(r["action"] == "not-attempted" for r in report["results"] if r["selected"])
    assert list(home.iterdir()) == []


def test_moved_source_is_unknown_and_preserves_installation(source_template, tmp_path):
    from tests.test_host_update_adapters import files

    source, home = tmp_path / "source", tmp_path / "home"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    home.mkdir()
    initial, seeded = cli(source, home, "refresh", "--select", "antigravity")
    assert initial.returncode == 0, seeded
    before = files(home)
    source.rename(tmp_path / "moved-source")
    assert not source.exists()
    result, report = cli(source, home, "refresh")
    assert result.returncode == 4 and report["results"][2]["selected"]
    assert report["results"][2]["action"] == "not-attempted"
    assert report["results"][2]["after"]["state"] == "unknown"
    assert files(home) == before


def test_private_snapshot_never_registers_in_source(source_template, tmp_path):
    from lib.host_update.source import pinned_source
    from tests.test_host_update_adapters import files

    source = tmp_path / "source"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    registrations = git(source, "worktree", "list", "--porcelain")
    metadata = files(source / ".git")
    with pinned_source(source) as revision:
        assert git(source, "worktree", "list", "--porcelain") == registrations
        assert files(source / ".git") == metadata
        assert git(revision.snapshot_root, "rev-parse", "HEAD") == revision.commit
    assert files(source / ".git") == metadata


@pytest.mark.parametrize("tmp_shape", ["physical", "alias"])
def test_control_declared_runtime_works_without_global_yaml(tmp_path, tmp_shape):
    import shlex
    import subprocess
    import sys
    from pathlib import Path

    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv required for the declared control runtime")
    root = Path(__file__).resolve().parents[1]
    tools = tmp_path / "tools"
    tools.mkdir()
    python = tools / "python3"
    python.write_text("#!/bin/sh\nexec " + shlex.quote(sys._base_executable) + ' -S "$@"\n')
    python.chmod(0o755)
    (tools / "uv").symlink_to(Path(uv).resolve())
    excluded = {Path(sys.prefix, "bin").resolve(), (root / ".venv/bin").resolve()}
    if os.environ.get("VIRTUAL_ENV"):
        excluded.add(Path(os.environ["VIRTUAL_ENV"], "bin").resolve())
    paths = [p for p in os.environ["PATH"].split(os.pathsep) if p and Path(p).resolve() not in excluded]
    physical = tmp_path / "runtime-tmp"
    physical.mkdir()
    temporary = physical
    if tmp_shape == "alias":
        temporary = tmp_path / "runtime-alias"
        temporary.symlink_to(physical, target_is_directory=True)
        assert temporary.is_symlink() and temporary.resolve() == physical
    env = dict(os.environ, PATH=os.pathsep.join([str(tools), *paths]), TMPDIR=str(temporary))
    for name in ("VIRTUAL_ENV", "PYTHONPATH", "UV_PROJECT_ENVIRONMENT"):
        env.pop(name, None)
    assert shutil.which("python3", path=env["PATH"]) == str(python)
    assert shutil.which("uv", path=env["PATH"]) == str(tools / "uv")
    probe = subprocess.run(["python3", "-c", "import yaml"], env=env, capture_output=True, text=True)
    assert probe.returncode != 0 and "No module named 'yaml'" in probe.stderr
    control = root / "controls/antigravity-skill-install-fidelity"
    specification = json.loads((control / "control.json").read_text())
    argv = [part.format(gate=root / "scripts/cpp-host-update.py", case=control / "cases/good-current")
            for part in specification["invocation"]]
    result = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    row = next(r for r in report["results"] if r["harness"] == "antigravity")
    assert row["after"]["state"] == "current" and row["after"]["expected_packages"] == 18


@pytest.mark.parametrize("fault", ["empty", "zero-count", "wrong-revision", "bad-summary",
                                         "missing-links", "mislabelled", "old-schema", "noncurrent-zero"])
def test_pinned_reader_rejects_bad_current_writer(source_template, tmp_path, fault):
    from lib.host_update.host import BACKENDS, DEFERRED, INCLUDED
    from lib.host_update.source import ExecutionFailure, execute_snapshot
    from tests.test_host_update_adapters import request

    source = tmp_path / "source"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    entry = source / "scripts/cpp-host-update.py"
    stage = {"state": "current", "expected_packages": 1, "expected_members": 1, "examined_members": 1}
    payload = {"schema": 2, "coverage": "partial", "backend": "mixed", "included": list(INCLUDED),
               "unimplemented": list(DEFERRED), "exit_code": 0,
               "results": [{"harness": n, "backend": BACKENDS[n], "selected": True, "exit_code": 0,
                            "before": stage, "after": stage,
                            "action": "unchanged", "reason": "", "remedy": ""} for n in INCLUDED]}
    if fault == "empty":
        payload["results"] = []
    elif fault == "zero-count":
        stage.update(expected_packages=0, expected_members=0, examined_members=0)
    elif fault == "bad-summary":
        payload["exit_code"] = 4
    elif fault == "missing-links":
        payload["results"] = [r for r in payload["results"] if r["harness"] != "claude-links"]
    elif fault == "mislabelled":
        payload["results"][-1]["backend"] = "copies"
    elif fault == "old-schema":
        payload["schema"] = 1
    elif fault == "noncurrent-zero":
        payload["results"][-1].update(selected=False, after=dict(stage, state="unknown", expected_packages=0,
                                                              expected_members=0, examined_members=0))
    bad_revision = "'f'*40" if fault == "wrong-revision" else "sys.argv[-1]"
    entry.write_text("#: PRODUCTION-HOST-ENTRY: 3\nimport json,sys\n"
                     + "r=json.loads(" + repr(json.dumps(payload)) + ")\n"
                     + f"r['revision']={bad_revision}\n"
                     + "for row in r['results']: row['revision']=r['revision']\n"
                     + "print(json.dumps(r))\n")
    git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-am", "known blind current producer")
    if fault == "empty":
        assert not payload["results"]
    elif fault == "zero-count":
        assert payload["results"][0]["after"]["expected_packages"] == 0
    elif fault == "wrong-revision":
        assert request(source).revision.commit != "f" * 40
    elif fault == "bad-summary":
        assert payload["exit_code"] == 4
    elif fault == "missing-links":
        assert len(payload["results"]) == 3
    elif fault == "mislabelled":
        assert payload["results"][-1]["backend"] != BACKENDS["claude-links"]
    elif fault == "old-schema":
        assert payload["schema"] == 1
    else:
        assert payload["results"][-1]["after"]["state"] == "unknown" and not payload["results"][-1]["selected"]
    with pytest.raises(ExecutionFailure, match="incomplete or inconsistent"):
        execute_snapshot(request(source).revision, ["verify", "--json"])


@pytest.mark.parametrize("marker", ["PRODUCTION-COPY-ENTRY: 1", "PRODUCTION-HOST-ENTRY: 2"])
def test_unavailable_old_entry_is_unknown_before_execution(source_template, tmp_path, marker):
    source, home = tmp_path / "source", tmp_path / "home"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    entry = source / "scripts/cpp-host-update.py"
    entry.write_text(f"#: {marker}\nraise AssertionError('old entry must never execute')\n")
    git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-am", "unsupported old production entry")
    assert marker in entry.read_text() and "PRODUCTION-HOST-ENTRY: 3" not in entry.read_text()
    result, report = cli(source, home, "refresh", "--select", "antigravity")
    assert result.returncode == 4 and report["results"][2]["action"] == "not-attempted"
    assert not home.exists()


def test_executable_source_alias_never_runs(source_template, tmp_path):
    source, home = tmp_path / "source", tmp_path / "home"
    git(tmp_path, "clone", "-q", str(source_template), str(source))
    outside = tmp_path / "outside.py"
    outside.write_text("raise AssertionError('outside code must never execute')\n")
    entry = source / "lib/host_update/host.py"
    entry.unlink()
    entry.symlink_to(outside)
    git(source, "add", ".")
    git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "executable source alias")
    assert entry.is_symlink()
    result, report = cli(source, home, "refresh", "--select", "antigravity")
    assert result.returncode == 4 and report["results"][2]["action"] == "not-attempted"
    assert not home.exists()


def test_stable_helper_symlink_bootstraps_physical_repository(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    helper = tmp_path / "home/.claude/scripts/cpp-host-update.py"
    helper.parent.mkdir(parents=True)
    helper.symlink_to(root / "scripts/cpp-host-update.py")
    assert helper.is_symlink() and helper.parent.parent.parent != root
    result = subprocess.run([sys.executable, str(helper), "--help"], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "claude-links" in result.stdout and "--source-root" in result.stdout


def test_old_caller_refuses_new_entry_before_execution(source_template, tmp_path, monkeypatch):
    import hashlib
    import subprocess

    from lib.host_update import source as current_source
    from lib.host_update.models import AdapterError
    from tests.test_host_update_adapters import request

    # Exact B1 caller at b1cd1f16, retained so main-only CI needs no old ref.
    predecessor = """def execute_snapshot(revision: Revision, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    import sys

    entry = revision.snapshot_root / "scripts/cpp-host-update.py"
    content = _source_blob(revision, "scripts/cpp-host-update.py")
    authority = Scope(Policy(revision.snapshot_root, revision.snapshot_root / ".unused-ledger",
                             revision.snapshot_root / ".unused-lock", revision.snapshot_root / ".unused-work"))
    if authority.read(entry) != content or b"PRODUCTION-COPY-ENTRY: 1" not in content:
        raise AdapterError("requested revision has no supported pinned production entry", exit_code=4)
    try:
        result = subprocess.run([sys.executable, str(entry), *arguments, "--pinned", revision.commit],
                                capture_output=True, text=True, timeout=300, umask=0o022)
    except subprocess.SubprocessError as error:
        raise ExecutionFailure("pinned driver execution incomplete; inspect installed state", exit_code=1) from error
    try:
        report = json.loads(result.stdout)
    except ValueError as error:
        raise ExecutionFailure("pinned driver returned no readable report", exit_code=1) from error
    if not valid_report(report, result.returncode, revision.commit):
        raise ExecutionFailure("pinned driver returned incomplete or inconsistent report", exit_code=1)
    return result
"""
    assert hashlib.sha256(predecessor.encode()).hexdigest() == (
        "2d0ce797b4a512dc95f9e3577cf63b0e852d5d8e3d073a77ddfc7488da0d7bda")
    namespace = dict(vars(current_source))
    exec(compile(predecessor, "predecessor_source.py", "exec"), namespace)
    assert "PRODUCTION-HOST-ENTRY: 3" in (source_template / "scripts/cpp-host-update.py").read_text()
    original = subprocess.run

    def no_child(argv, *args, **kwargs):
        assert argv[0] == "git", "unsupported producer executed before marker refusal"
        return original(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", no_child)
    with pytest.raises(AdapterError, match="no supported pinned production entry"):
        namespace["execute_snapshot"](request(source_template).revision, ["verify", "--json"])


def test_b2a_reader_refuses_changed_coverage_producer_before_execution(source_template, monkeypatch):
    import hashlib
    import subprocess

    from lib.host_update import source as current_source
    from lib.host_update.models import AdapterError
    from tests.test_host_update_adapters import request

    predecessor = (
        r"""def execute_snapshot(revision: Revision, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    import sys

    entry = revision.snapshot_root / "scripts/cpp-host-update.py"
    content = _source_blob(revision, "scripts/cpp-host-update.py")
    authority = Scope(Policy(revision.snapshot_root, revision.snapshot_root / ".unused-ledger",
                             revision.snapshot_root / ".unused-lock", revision.snapshot_root / ".unused-work"))
    if authority.read(entry) != content or b"PRODUCTION-HOST-ENTRY: 2" not in content:
        raise AdapterError("requested revision has no supported pinned production entry", exit_code=4)
    try:
        result = subprocess.run([sys.executable, str(entry), *arguments, "--pinned", revision.commit],
                                capture_output=True, text=True, timeout=300, umask=0o022)
    except subprocess.SubprocessError as error:
        raise ExecutionFailure("pinned driver execution incomplete; inspect installed state", exit_code=1) from error
    try:
        report = json.loads(result.stdout)
    except ValueError as error:
        raise ExecutionFailure("pinned driver returned no readable report", exit_code=1) from error
    if not valid_report(report, result.returncode, revision.commit):
        raise ExecutionFailure("pinned driver returned incomplete or inconsistent report", exit_code=1)
    return result
""")
    assert hashlib.sha256(predecessor.encode()).hexdigest() == (
        "24edafd5e2b440976ca060b42ab7ae2fbe6ff6fa3992523075aad732fd99ef4f")
    namespace = dict(vars(current_source))
    exec(compile(predecessor, "b2a_predecessor_source.py", "exec"), namespace)
    original = subprocess.run

    def no_child(argv, *args, **kwargs):
        assert argv[0] == "git", "B2a caller executed changed producer before marker refusal"
        return original(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", no_child)
    with pytest.raises(AdapterError, match="no supported pinned production entry"):
        namespace["execute_snapshot"](request(source_template).revision, ["verify", "--json"])
