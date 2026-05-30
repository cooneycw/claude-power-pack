"""Tests for second-opinion model catalog freshness."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import patch

STALE_PROVIDER_MODEL_IDS = {
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "deepseek-r1-distill-llama-70b",
    "qwen-qwq-32b",
    "deepseek/deepseek-chat-v4-0324:free",
    "minimax/minimax-m2-5:free",
}


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


def test_issue_328_stale_provider_ids_are_not_advertised_or_priced() -> None:
    catalog_model_ids = {info["model_id"] for info in Config.AVAILABLE_MODELS.values()}
    pricing_model_ids = set().union(
        Config.GROQ_PRICING,
        Config.OPENROUTER_PRICING,
        Config.DEEPSEEK_PRICING,
    )

    assert STALE_PROVIDER_MODEL_IDS.isdisjoint(catalog_model_ids)
    assert STALE_PROVIDER_MODEL_IDS.isdisjoint(pricing_model_ids)


def test_default_models_reference_existing_catalog_entries() -> None:
    assert set(Config.DEFAULT_MODELS) <= set(Config.AVAILABLE_MODELS)
    assert "groq-llama4-maverick" not in Config.DEFAULT_MODELS


def test_groq_catalog_uses_current_replacement_model_ids() -> None:
    assert "groq-llama4-maverick" not in Config.AVAILABLE_MODELS
    assert "groq-deepseek-r1" not in Config.AVAILABLE_MODELS
    assert Config.AVAILABLE_MODELS["groq-gpt-oss-120b"]["model_id"] == "openai/gpt-oss-120b"
    assert Config.AVAILABLE_MODELS["groq-qwen-32b"]["model_id"] == "qwen/qwen3-32b"


def test_free_openrouter_catalog_entries_use_free_slugs() -> None:
    openrouter_free_entries = {
        key: info
        for key, info in Config.AVAILABLE_MODELS.items()
        if info["provider"] == "openrouter" and info.get("free")
    }

    assert openrouter_free_entries
    for key, info in openrouter_free_entries.items():
        assert info["model_id"].endswith(":free"), key


def test_openai_compatible_catalog_entries_have_pricing() -> None:
    pricing_tables = {
        "mistral": Config.MISTRAL_PRICING,
        "groq": Config.GROQ_PRICING,
        "openrouter": Config.OPENROUTER_PRICING,
        "deepseek": Config.DEEPSEEK_PRICING,
    }

    for key, info in Config.AVAILABLE_MODELS.items():
        pricing_table = pricing_tables.get(info["provider"])
        if pricing_table is None:
            continue
        assert info["model_id"] in pricing_table, key
