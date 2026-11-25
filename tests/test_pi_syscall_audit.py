"""Trace classifier tests assert opposite states, never real syscall acceptance."""
import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = runpy.run_path(str(ROOT / "scripts/pi-syscall-audit.py"))["audit"]


@pytest.mark.parametrize("path", sorted((ROOT / "controls/pi-syscall-observer/cases").glob("*/case.json")),
                         ids=lambda p: p.parent.name)
def test_committed_trace_cases(path):
    seed = json.loads(path.read_text())
    assert AUDIT(seed["record"])["state"] == {"GOOD": "matches", "BAD": "finding", "UNKNOWN": "unknown"}[seed["expect"]]


def test_actual_descriptor_target_cannot_hide_behind_allowed_path():
    record = json.loads((ROOT / "controls/pi-syscall-observer/cases/allowed-install/case.json").read_text())["record"]
    record["traces"]["10"] = ('1.0 openat(AT_FDCWD, "/fixture/agent/skills/link", O_RDONLY) '
                                '= 3</fixture/agent/auth.json>\n2.0 +++ exited with 0 +++\n')
    assert any("authentication probe" in f for f in AUDIT(record)["findings"])


def test_empty_trace_and_unknown_syscall_are_not_clean():
    original = json.loads((ROOT / "controls/pi-syscall-observer/cases/allowed-install/case.json").read_text())["record"]
    empty = copy.deepcopy(original)
    empty["traces"] = {}
    assert AUDIT(empty)["state"] == "unknown"
    original["traces"]["10"] = ('1.0 unsupported_path_operation("/fixture/agent/skills") = 0\n'
                                '2.0 +++ exited with 0 +++\n')
    assert AUDIT(original)["state"] == "unknown"


def test_a_cloned_child_omitted_entirely_is_unknown():
    record = json.loads((ROOT / "controls/pi-syscall-observer/cases/allowed-install/case.json").read_text())["record"]
    record["traces"]["10"] = record["traces"]["10"].replace(
        "2.0 +++", "1.8 clone(child_stack=NULL, flags=SIGCHLD) = 11\n2.0 +++")
    assert "11" not in record["traces"] and " = 11" in record["traces"]["10"]
    assert AUDIT(record)["state"] == "unknown"


def test_credential_spelling_remains_forbidden_when_alias_target_is_ordinary_source():
    record = json.loads((ROOT / "controls/pi-syscall-observer/cases/auth-file-stat/case.json").read_text())["record"]
    record["allowance"]["aliases"] = {"/fixture/agent/auth.json": "/fixture/source/ordinary.md"}
    assert "auth.json" in record["traces"]["10"]
    assert AUDIT(record)["state"] == "finding"


@pytest.mark.parametrize("operation", [
    'ppoll([{fd=7</fixture/agent/auth.json>, events=POLLIN}], 1, NULL, NULL, 8)',
    'select(8, [7</fixture/agent/auth.json>], NULL, NULL, NULL)',
    'pselect6(8, NULL, [7</fixture/agent/auth.json>], NULL, NULL, {sigmask=NULL, sigsetsize=8})',
    'epoll_ctl(6<anon_inode:[eventpoll]>, EPOLL_CTL_ADD, 7</fixture/agent/auth.json>, NULL)',
    'epoll_wait(7</fixture/agent/auth.json>, [], 1, 0)',
])
def test_multiplexing_checks_each_resolved_descriptor(operation):
    record = json.loads((ROOT / "controls/pi-syscall-observer/cases/allowed-install/case.json").read_text())["record"]
    record["traces"]["10"] = record["traces"]["10"].replace("2.0 +++", "1.8 " + operation + " = 0\n2.0 +++")
    assert "auth.json" in operation
    assert AUDIT(record)["state"] == "finding"


def test_unresolved_multiplexing_descriptor_remains_unknown():
    record = json.loads((ROOT / "controls/pi-syscall-observer/cases/allowed-install/case.json").read_text())["record"]
    record["traces"]["10"] = record["traces"]["10"].replace(
        "2.0 +++", "1.8 poll([{fd=7, events=POLLIN}], 1, -1) = 0\n2.0 +++")
    assert AUDIT(record)["state"] == "unknown"
