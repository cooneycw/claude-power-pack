#!/usr/bin/env python3
"""Smoke-test advertised OpenAI-compatible model IDs with configured provider keys."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    import openai
except ImportError as exc:  # pragma: no cover - exercised only outside test envs without server deps
    raise SystemExit(
        "openai package is required. Run through uv from mcp-second-opinion, e.g. "
        "`uv run --directory mcp-second-opinion python scripts/smoke-model-catalog.py`."
    ) from exc

Config = importlib.import_module("config").Config


PROVIDER_CONFIG = {
    "mistral": ("MISTRAL_API_KEY", Config.MISTRAL_BASE_URL),
    "groq": ("GROQ_API_KEY", Config.GROQ_BASE_URL),
    "openrouter": ("OPENROUTER_API_KEY", Config.OPENROUTER_BASE_URL),
    "deepseek": ("DEEPSEEK_API_KEY", Config.DEEPSEEK_BASE_URL),
}


@dataclass(frozen=True)
class CatalogModel:
    key: str
    provider: str
    model_id: str


async def smoke_model(model: CatalogModel, *, max_tokens: int, timeout: float) -> tuple[CatalogModel, str | None]:
    """Return an error string when a one-token provider request fails."""
    api_key_attr, base_url = PROVIDER_CONFIG[model.provider]
    client = openai.AsyncOpenAI(api_key=getattr(Config, api_key_attr), base_url=base_url)

    try:
        await asyncio.wait_for(
            client.chat.completions.create(
                model=model.model_id,
                messages=[{"role": "user", "content": "Reply with OK."}],
                max_tokens=max_tokens,
                temperature=0,
            ),
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - provider-specific SDK exceptions vary
        return model, str(exc)

    return model, None


def select_models(providers: set[str], model_keys: set[str]) -> list[CatalogModel]:
    """Select advertised models whose provider key is configured."""
    selected = []
    for key, info in Config.AVAILABLE_MODELS.items():
        provider = info["provider"]
        if provider not in providers:
            continue
        if model_keys and key not in model_keys:
            continue

        api_key_attr, _base_url = PROVIDER_CONFIG[provider]
        if not getattr(Config, api_key_attr, None):
            continue

        selected.append(CatalogModel(key=key, provider=provider, model_id=info["model_id"]))

    return selected


async def run(args: argparse.Namespace) -> int:
    providers = set(args.provider or PROVIDER_CONFIG)
    unknown_providers = providers - set(PROVIDER_CONFIG)
    if unknown_providers:
        print(f"Unknown provider(s): {', '.join(sorted(unknown_providers))}", file=sys.stderr)
        return 2

    model_keys = set(args.model or [])
    unknown_models = model_keys - set(Config.AVAILABLE_MODELS)
    if unknown_models:
        print(f"Unknown model key(s): {', '.join(sorted(unknown_models))}", file=sys.stderr)
        return 2

    selected = select_models(providers, model_keys)
    configured_providers = {
        provider
        for provider, (api_key_attr, _base_url) in PROVIDER_CONFIG.items()
        if getattr(Config, api_key_attr, None)
    }
    scoped_configured = configured_providers & providers

    if not scoped_configured:
        print("No scoped OpenAI-compatible provider API keys are configured; skipping model catalog smoke.")
        return 0

    if not selected:
        print("No advertised model entries matched the configured scoped provider keys; skipping.")
        return 0

    failures = []
    for model in selected:
        print(f"smoke {model.provider}/{model.key} -> {model.model_id}")
        _model, error = await smoke_model(model, max_tokens=args.max_tokens, timeout=args.timeout)
        if error:
            failures.append((model, error))
            print(f"FAIL {model.key}: {error}", file=sys.stderr)
        else:
            print(f"OK   {model.key}")

    if failures:
        print("", file=sys.stderr)
        print(f"{len(failures)} model catalog smoke check(s) failed:", file=sys.stderr)
        for model, error in failures:
            print(f"- {model.provider}/{model.key} ({model.model_id}): {error}", file=sys.stderr)
        return 1

    print(f"All {len(selected)} configured model catalog smoke check(s) passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        action="append",
        choices=sorted(PROVIDER_CONFIG),
        help="Provider to check. May be repeated. Defaults to all OpenAI-compatible providers.",
    )
    parser.add_argument(
        "--model",
        action="append",
        help="Catalog model key to check. May be repeated. Defaults to all matching configured providers.",
    )
    parser.add_argument("--max-tokens", type=int, default=1, help="Max output tokens for each provider request.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-model request timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
