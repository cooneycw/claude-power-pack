"""RPC reader and lifecycle tests; these do not require or simulate live pi."""
import copy
import json
import runpy
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = runpy.run_path(str(ROOT / "scripts/pi-host-fixture.py"))


@pytest.mark.parametrize("path", sorted((ROOT / "controls/pi-rpc-observer/cases").glob("*/case.json")),
                         ids=lambda p: p.parent.name)
def test_committed_rpc_cases(path):
    seed = json.loads(path.read_text())
    try:
        state = SUBJECT["rpc_audit"](seed["record"])["state"]
    except (ValueError, KeyError, TypeError):
        state = "unknown"
    assert state == {"GOOD": "matches", "BAD": "finding", "UNKNOWN": "unknown"}[seed["expect"]]


def test_missing_tool_inventory_never_borrowed_from_discovery():
    seed = json.loads((ROOT / "controls/pi-rpc-observer/cases/populated-baseline-pair/case.json").read_text())
    record = copy.deepcopy(seed["record"])
    record["tools"] = None
    assert SUBJECT["rpc_audit"](record)["state"] == "unknown"


def test_timeout_stops_and_reaps_actual_fixture_child(tmp_path):
    result = SUBJECT["run_child"]([sys.executable, "-c", "import time; time.sleep(30)"],
                                   tmp_path, {"HOME": str(tmp_path)}, timeout=0.05)
    assert result["forced_stop"] and result["exit"] is not None and result["exit"] != 0


@pytest.mark.skipif(shutil.which("git") is None, reason="requires Git for isolated fixture tool selection")
def test_fixture_path_drops_unselected_home_search_entries(tmp_path, monkeypatch):
    foreign = tmp_path / "foreign-home/bin"
    assert shutil.which("git", path=str(foreign)) is None
    monkeypatch.setenv("PATH", str(foreign) + ":/usr/bin:/bin")
    env, git = SUBJECT["fixture_environment"](tmp_path)
    assert str(foreign) not in env["PATH"].split(":")
    assert str(Path(git).parent) in env["PATH"].split(":")
    assert env["HOME"] == str(tmp_path / "home") and env["PYTHONNOUSERSITE"] == "1"
    assert env["PI_CODING_AGENT_DIR"] == str(tmp_path / "agent")


@pytest.mark.skipif(shutil.which("git") is None, reason="requires Git for source metadata binding")
def test_worktree_storage_derived_from_source_not_main_working_tree(tmp_path):
    from tests.test_pi_skill_install import Case
    case = Case(tmp_path)
    linked = tmp_path / "linked"
    case.git("worktree", "add", "--detach", str(linked), case.revision)
    assert (linked / ".git").is_file()
    env, git = SUBJECT["fixture_environment"](tmp_path)
    env["GIT_DIR"] = str(tmp_path / "wrong-repo")
    result = SUBJECT["source_git_directories"](linked, env, git, case.cwd)
    assert result["git_common_dir"] == str(case.source / ".git")
    assert result["git_dir"].startswith(str(case.source / ".git/worktrees/"))
    assert str(case.source) not in (result["git_dir"], result["git_common_dir"])


@pytest.mark.skipif(shutil.which("git") is None, reason="requires Git for fixture executable resolution")
def test_runtime_paths_come_from_isolated_fixture_interpreter(tmp_path):
    (tmp_path / "home").mkdir()
    env, git = SUBJECT["fixture_environment"](tmp_path)
    observed = SUBJECT["runtime_allowance"](env, tmp_path, git)
    assert observed["probe"]["argv"][1] == "-I"
    assert not {"/usr", "/lib", "/home", "/etc", "/proc", "/sys"} & set(observed["runtime_reads"])
    assert all(Path(p).is_absolute() for p in observed["runtime_reads"])
    assert "/etc/locale.alias" in observed["runtime_files"]


@pytest.mark.skipif(shutil.which("git") is None, reason="requires Git for fixture executable resolution")
def test_observed_bootstrap_paths_are_exact_read_files(tmp_path):
    env, git = SUBJECT["fixture_environment"](tmp_path)
    observed = SUBJECT["runtime_allowance"](env, tmp_path, git)
    executable = Path(sys.executable)
    version = f"{sys.version_info.major}{sys.version_info.minor}"
    required = {str(executable.parent / "pyvenv.cfg"), str(executable.parent.parent / "pyvenv.cfg"),
                str(executable.parent / "pybuilddir.txt"), str(executable.parent / "Modules/Setup.local"),
                str(executable.parent / f"lib/python{version}.zip"),
                str(executable.parent / f"python{sys.version_info.major}._pth"),
                str(executable.parent / f"python{sys.version_info.major}.{sys.version_info.minor}._pth"),
                "/usr/lib/ssl/openssl.cnf", "/usr/share/locale/locale.alias",
                "/usr/share/locale/C.UTF-8/LC_MESSAGES/messages.mo",
                "/usr/share/locale-langpack/C.UTF-8/LC_MESSAGES/messages.mo"}
    assert required <= set(observed["runtime_files"])
    assert str(executable.parent / "Modules/Setup.foreign") not in observed["runtime_files"]
    assert str(executable.parent) not in observed["runtime_reads"]


@pytest.mark.skipif(shutil.which("git") is None, reason="requires Git for fixture executable resolution")
def test_prefix_landmarks_are_metadata_only(tmp_path):
    env, git = SUBJECT["fixture_environment"](tmp_path)
    observed = SUBJECT["runtime_allowance"](env, tmp_path, git)
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    root = Path(sys.executable).parent / "lib" / version
    required = {str(root / name) for name in ("os.py", "os.pyc", "lib-dynload")}
    assert required <= set(observed.get("runtime_metadata", []))
    assert not required & set(observed["runtime_files"])
    assert all(not any(Path(p).is_relative_to(Path(r)) for r in observed["runtime_reads"]) for p in required)


def test_localtime_target_is_exact_bounded_and_recorded(tmp_path):
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()
    target = zoneinfo / "fixture-city"
    target.write_text("synthetic timezone bytes")
    localtime = tmp_path / "localtime"
    localtime.symlink_to(target)
    observed = SUBJECT["localtime_target"](localtime, zoneinfo)
    assert observed == {"path": str(localtime), "target": str(target)}


@pytest.mark.parametrize("escape", [True, False], ids=["outside-root", "ambiguous-chain"])
def test_localtime_target_cannot_authorize_escape_or_alias_chain(tmp_path, escape):
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()
    foreign = tmp_path / "foreign"
    foreign.write_text("synthetic sentinel")
    target = zoneinfo / "fixture-city"
    target.symlink_to(foreign if escape else zoneinfo / "other")
    localtime = tmp_path / "localtime"
    localtime.symlink_to(foreign if escape else target)
    assert localtime.is_symlink() and (escape or target.is_symlink())
    with pytest.raises(ValueError):
        SUBJECT["localtime_target"](localtime, zoneinfo)


@pytest.mark.skipif(shutil.which("git") is None, reason="requires Git for fixture executable resolution")
def test_runtime_derivation_retains_exact_localtime_binding(tmp_path, monkeypatch):
    binding = {"path": "/fixture/localtime", "target": "/fixture/system-zoneinfo/fixture-city"}
    monkeypatch.setitem(SUBJECT["runtime_allowance"].__globals__, "localtime_target", lambda: binding)
    env, git = SUBJECT["fixture_environment"](tmp_path)
    observed = SUBJECT["runtime_allowance"](env, tmp_path, git)
    assert binding["target"] in observed["runtime_files"]
    assert observed["localtime"] == binding
    assert str(Path(binding["target"]).parent) not in observed["runtime_reads"]


def test_localtime_bounded_alias_chain_and_regular_file(tmp_path):
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()
    target = zoneinfo / "fixture-city"
    target.write_text("synthetic timezone")
    alias = zoneinfo / "fixture-alias"
    alias.symlink_to(target.name)
    localtime = tmp_path / "localtime"
    localtime.symlink_to(alias)
    assert SUBJECT["localtime_target"](localtime, zoneinfo)["target"] == str(target)
    localtime.unlink()
    localtime.write_text("synthetic regular localtime")
    assert SUBJECT["localtime_target"](localtime, zoneinfo)["target"] == str(localtime)


@pytest.mark.parametrize("cycle", [False, True], ids=["alias-escape", "alias-cycle"])
def test_localtime_alias_cannot_touch_outside_target_or_loop(tmp_path, monkeypatch, cycle):
    zoneinfo = tmp_path / "zoneinfo"
    zoneinfo.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("synthetic sentinel")
    alias = zoneinfo / "alias"
    alias.symlink_to(alias if cycle else outside)
    localtime = tmp_path / "localtime"
    localtime.symlink_to(alias)
    assert alias.is_symlink() and localtime.is_symlink()
    lstat = Path.lstat

    def bounded_lstat(path, *args, **kwargs):
        assert path != outside, "escape must be rejected before outside metadata"
        return lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", bounded_lstat)
    with pytest.raises(ValueError):
        SUBJECT["localtime_target"](localtime, zoneinfo)


def test_row_blockers_identify_residual_allowance_without_changing_verdict():
    case = ROOT / "controls/pi-syscall-observer/cases/runtime-landmark-metadata/case.json"
    record = json.loads(case.read_text())["record"]
    audit = SUBJECT["load_auditor"]().audit
    answer = audit(record)
    assert answer["state"] == "matches"
    assert SUBJECT["audit_blockers"](answer, "matches") == {}
    record["allowance"]["runtime_metadata"] = []
    blocked = audit(record)
    assert blocked["state"] == "finding" and not blocked["unknown"]
    summary = SUBJECT["audit_blockers"](blocked, "matches")
    assert summary["observed"] == "finding" and summary["expected"] == "matches"
    assert len(summary["findings"]) == 3 and all(count == 1 for count in summary["findings"].values())
    assert all("metadata outside read allowance" in reason for reason in summary["findings"])
    assert summary["unknown"] == {} and audit(record) == blocked
