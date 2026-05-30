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


def test_groq_models_have_32768_output_token_ceiling(monkeypatch):
    config = _load_second_opinion_config(monkeypatch)

    groq_model_keys = [
        key for key, model_info in config.AVAILABLE_MODELS.items()
        if model_info["provider"] == "groq"
    ]

    assert groq_model_keys
    assert all(
        config.get_model_max_output_tokens(model_key) == 32768
        for model_key in groq_model_keys
    )


def test_groq_high_verbosity_tokens_are_clamped(monkeypatch):
    config = _load_second_opinion_config(monkeypatch)

    detailed_tokens = config.VERBOSITY_MAX_TOKENS["detailed"]
    in_depth_tokens = config.VERBOSITY_MAX_TOKENS["in_depth"]

    assert config.clamp_max_tokens_for_model("groq-llama-70b", detailed_tokens) == (32768, 32768)
    assert config.clamp_max_tokens_for_model("groq-llama-70b", in_depth_tokens) == (32768, 32768)


def test_groq_brief_tokens_are_not_clamped(monkeypatch):
    config = _load_second_opinion_config(monkeypatch)

    brief_tokens = config.VERBOSITY_MAX_TOKENS["brief"]

    assert config.clamp_max_tokens_for_model("groq-llama-70b", brief_tokens) == (brief_tokens, 32768)


def test_models_without_ceiling_keep_requested_tokens(monkeypatch):
    config = _load_second_opinion_config(monkeypatch)

    requested_tokens = config.VERBOSITY_MAX_TOKENS["in_depth"]

    assert config.clamp_max_tokens_for_model("gemini-3.5-flash", requested_tokens) == (requested_tokens, None)
