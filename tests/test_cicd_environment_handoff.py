"""CPP uv selection restores caller target-environment policy only after boot."""

import builtins
import os
import runpy
import sys
from types import SimpleNamespace

import pytest

from lib.cicd import __main__ as entry

VALUE = "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT"
PRESENT = VALUE + "_PRESENT"


@pytest.mark.parametrize("original", [None, "", ".target-env", "/owned target/.venv", ".env $literal $(not-eval)"])
def test_handoff_restores_exact_value_and_presence(original):
    environment = {
        VALUE: original or "",
        PRESENT: "" if original is None else "x",
        "UV_PROJECT_ENVIRONMENT": "/wrong-cpp-env",
        "UNRELATED": "keep",
    }
    entry.restore_target_environment(environment)
    assert ("UV_PROJECT_ENVIRONMENT" in environment) is (original is not None)
    if original is not None:
        assert environment["UV_PROJECT_ENVIRONMENT"] == original
    assert VALUE not in environment and PRESENT not in environment
    assert environment["UNRELATED"] == "keep"


def test_unmarked_direct_cli_caller_keeps_its_policy():
    environment = {"UV_PROJECT_ENVIRONMENT": ".direct-user-env"}
    entry.restore_target_environment(environment)
    assert environment == {"UV_PROJECT_ENVIRONMENT": ".direct-user-env"}


@pytest.mark.parametrize(
    "metadata",
    [{VALUE: "orphan"}, {PRESENT: "x"}, {PRESENT: "invalid", VALUE: "value"}, {PRESENT: "", VALUE: "inconsistent"}],
)
def test_incomplete_or_invalid_handoff_is_not_readiness(metadata):
    with pytest.raises(ValueError, match="environment policy"):
        entry.restore_target_environment(metadata)


def test_invalid_launch_refuses_before_cli_import_or_dispatch(monkeypatch, capsys):
    original = builtins.__import__
    imported = []

    def observe(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "cli" and level == 1:
            imported.append(True)
        return original(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", observe)
    monkeypatch.setenv(VALUE, "private-fixture-value")
    monkeypatch.setenv(PRESENT, "invalid-fixture-status")
    monkeypatch.setattr(sys, "argv", ["lib.cicd", "detect", "--json"])
    monkeypatch.delitem(sys.modules, "lib.cicd.__main__", raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("lib.cicd", run_name="__main__")
    assert exc.value.code == 1 and not imported
    output = capsys.readouterr()
    assert not output.out
    assert "environment policy is unverified" in output.err
    assert "private-fixture-value" not in output.err
    assert "invalid-fixture-status" not in output.err


@pytest.mark.parametrize("command", ["detect", "check", "run", "verify", "pipeline", "container"])
def test_all_commands_restore_before_import_and_dispatch(monkeypatch, command):
    original = builtins.__import__
    observed = []
    policy = ".target env $literal $(not-eval)"

    def record():
        observed.append((os.environ.get("UV_PROJECT_ENVIRONMENT"), VALUE in os.environ, PRESENT in os.environ))

    def observe(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "cli" and level == 1:
            record()
            return SimpleNamespace(run=record)
        return original(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", observe)
    monkeypatch.setenv(VALUE, policy)
    monkeypatch.setenv(PRESENT, "x")
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.setattr(sys, "argv", ["lib.cicd", command])
    monkeypatch.delitem(sys.modules, "lib.cicd.__main__", raising=False)
    runpy.run_module("lib.cicd", run_name="__main__")
    assert observed == [(policy, False, False), (policy, False, False)]
