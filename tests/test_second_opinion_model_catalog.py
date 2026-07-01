"""Tests for second-opinion model catalog freshness and provider scope.

Issue #402 trimmed the catalog to the three reliable providers (Gemini, OpenAI,
Anthropic) and dropped Mistral, Groq, OpenRouter, and DeepSeek.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import patch

RELIABLE_PROVIDERS = {"gemini", "openai", "anthropic"}
REMOVED_PROVIDERS = {"mistral", "groq", "openrouter", "deepseek"}


def _load_config():
    """Load second-opinion config without requiring python-dotenv in the root test env."""
    src_path = str(Path(__file__).resolve().parent.parent / "mcp-second-opinion" / "src")
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *_args, **_kwargs: None

    with patch.dict(sys.modules, {"dotenv": dotenv_stub}):
        sys.modules.pop("config", None)
        sys.path.insert(0, src_path)
        try:
            return importlib.import_module("config").Config
        finally:
            sys.path.remove(src_path)
            sys.modules.pop("config", None)


Config = _load_config()


def test_catalog_only_exposes_reliable_providers() -> None:
    catalog_providers = {info["provider"] for info in Config.AVAILABLE_MODELS.values()}
    assert catalog_providers <= RELIABLE_PROVIDERS
    assert catalog_providers.isdisjoint(REMOVED_PROVIDERS)


def test_removed_providers_are_fully_purged() -> None:
    # No leftover per-provider config attributes for the removed providers.
    for provider in REMOVED_PROVIDERS:
        upper = provider.upper()
        for attr in (f"{upper}_API_KEY", f"{upper}_BASE_URL", f"{upper}_PRICING"):
            assert not hasattr(Config, attr), attr

    # Provider -> API-key map only routes the reliable providers.
    assert set(Config._PROVIDER_API_KEY_MAP) == RELIABLE_PROVIDERS


def test_default_models_reference_existing_catalog_entries() -> None:
    assert set(Config.DEFAULT_MODELS) <= set(Config.AVAILABLE_MODELS)
    # Every default routes to a reliable provider.
    for key in Config.DEFAULT_MODELS:
        assert Config.AVAILABLE_MODELS[key]["provider"] in RELIABLE_PROVIDERS


def test_every_catalog_model_is_priced() -> None:
    priced_model_ids = set().union(
        Config.GEMINI_PRICING,
        Config.OPENAI_PRICING,
        Config.ANTHROPIC_PRICING,
    )
    for key, info in Config.AVAILABLE_MODELS.items():
        assert info["model_id"] in priced_model_ids, key
