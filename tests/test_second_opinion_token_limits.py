"""Tests for second-opinion provider output token ceilings."""

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


def test_no_provider_output_ceilings_configured(monkeypatch):
    """The reliable providers (Gemini/OpenAI/Anthropic) rely on their own
    per-request limits, so no provider-level output ceiling is configured."""
    config = _load_second_opinion_config(monkeypatch)

    assert config.PROVIDER_MAX_OUTPUT_TOKENS == {}
    assert all(
        "max_output_tokens" not in model_info
        for model_info in config.AVAILABLE_MODELS.values()
    )


def test_models_without_ceiling_keep_requested_tokens(monkeypatch):
    config = _load_second_opinion_config(monkeypatch)

    requested_tokens = config.VERBOSITY_MAX_TOKENS["in_depth"]

    assert config.clamp_max_tokens_for_model("gemini-3.5-flash", requested_tokens) == (requested_tokens, None)
