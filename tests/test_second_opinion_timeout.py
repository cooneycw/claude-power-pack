"""Tests for the second-opinion per-model response timeout (issue #356).

The server module pulls in component-only provider SDKs that are not installed
in the root test environment, so - like the other second-opinion tests - these
load config.py in isolation and exercise the timeout configuration directly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_second_opinion_config(monkeypatch):
    """Load config.py without requiring component-only dependencies."""
    dotenv = ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)

    config_path = Path(__file__).parents[1] / "mcp-second-opinion" / "src" / "config.py"
    spec = importlib.util.spec_from_file_location("second_opinion_config_for_tests", config_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Config


def test_model_response_timeout_has_generous_default(monkeypatch):
    monkeypatch.delenv("MODEL_RESPONSE_TIMEOUT", raising=False)
    config = _load_second_opinion_config(monkeypatch)

    assert config.MODEL_RESPONSE_TIMEOUT == 600


def test_model_response_timeout_never_truncates_in_depth_responses(monkeypatch):
    """A legitimate in_depth response finishes in ~1-4 min; the default must not
    cut it off, so the timeout has to comfortably exceed any realistic stream."""
    monkeypatch.delenv("MODEL_RESPONSE_TIMEOUT", raising=False)
    config = _load_second_opinion_config(monkeypatch)

    # 5+ minutes of headroom over the slowest legitimate (in_depth) response.
    assert config.MODEL_RESPONSE_TIMEOUT >= 300


def test_model_response_timeout_is_env_tunable(monkeypatch):
    monkeypatch.setenv("MODEL_RESPONSE_TIMEOUT", "45")
    config = _load_second_opinion_config(monkeypatch)

    assert config.MODEL_RESPONSE_TIMEOUT == 45
