"""Tests for multi-model second-opinion completion-order results."""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path


def _load_second_opinion_server(monkeypatch):
    """Load server.py with component-only provider SDKs stubbed."""
    src_path = Path(__file__).parents[1] / "mcp-second-opinion" / "src"

    for env_var in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
    ):
        monkeypatch.delenv(env_var, raising=False)

    class NoopFastMCP:
        def __init__(self, *args, **kwargs):
            pass

        def custom_route(self, *args, **kwargs):
            return lambda func: func

        def tool(self, *args, **kwargs):
            return lambda func: func

        def run(self, *args, **kwargs):
            pass

    class NoopClient:
        def __init__(self, *args, **kwargs):
            pass

    class JSONResponse:
        def __init__(self, content, status_code=200):
            self.content = content
            self.status_code = status_code

    def retry(*args, **kwargs):
        return lambda func: func

    fastmcp = types.ModuleType("fastmcp")
    fastmcp.FastMCP = NoopFastMCP

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None

    anthropic = types.ModuleType("anthropic")
    anthropic.AsyncAnthropic = NoopClient

    openai = types.ModuleType("openai")
    openai.AsyncOpenAI = NoopClient

    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    genai.Client = NoopClient
    genai_types = types.ModuleType("google.genai.types")
    genai.types = genai_types
    google.genai = genai

    starlette = types.ModuleType("starlette")
    starlette_requests = types.ModuleType("starlette.requests")
    starlette_requests.Request = type("Request", (), {})
    starlette_responses = types.ModuleType("starlette.responses")
    starlette_responses.JSONResponse = JSONResponse

    tenacity = types.ModuleType("tenacity")
    tenacity.retry = retry
    tenacity.retry_if_exception_type = lambda *args, **kwargs: None
    tenacity.stop_after_attempt = lambda *args, **kwargs: None
    tenacity.wait_exponential = lambda *args, **kwargs: None

    prompts = types.ModuleType("prompts")
    prompts.build_code_review_prompt = lambda *args, **kwargs: "prompt"
    prompts.scan_for_secrets = lambda *args, **kwargs: []

    sessions = types.ModuleType("sessions")
    sessions.get_session_manager = lambda: object()

    tools = types.ModuleType("tools")
    tools.FETCH_URL_DECLARATION = object()
    tools.WEB_SEARCH_DECLARATION = object()
    tools.approve_domain = lambda *args, **kwargs: None
    tools.fetch_url = lambda *args, **kwargs: None
    tools.get_approved_domains = lambda *args, **kwargs: []
    tools.revoke_domain = lambda *args, **kwargs: None
    tools.web_search = lambda *args, **kwargs: None

    monkeypatch.setitem(sys.modules, "fastmcp", fastmcp)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)
    monkeypatch.setitem(sys.modules, "anthropic", anthropic)
    monkeypatch.setitem(sys.modules, "openai", openai)
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", genai_types)
    monkeypatch.setitem(sys.modules, "starlette", starlette)
    monkeypatch.setitem(sys.modules, "starlette.requests", starlette_requests)
    monkeypatch.setitem(sys.modules, "starlette.responses", starlette_responses)
    monkeypatch.setitem(sys.modules, "tenacity", tenacity)
    monkeypatch.setitem(sys.modules, "prompts", prompts)
    monkeypatch.setitem(sys.modules, "sessions", sessions)
    monkeypatch.setitem(sys.modules, "tools", tools)

    sys.modules.pop("server", None)
    sys.modules.pop("config", None)
    monkeypatch.syspath_prepend(str(src_path))
    return importlib.import_module("server")


def test_multi_model_responses_are_drained_in_completion_order(monkeypatch):
    server = _load_second_opinion_server(monkeypatch)
    valid_models = ["slow", "fast", "medium"]
    delays = {
        "slow": 0.03,
        "fast": 0.0,
        "medium": 0.01,
    }

    monkeypatch.setattr(server.Config, "get_available_model_keys", staticmethod(lambda: valid_models))

    async def fake_single_model_response(prompt, model_key, max_tokens=server.Config.MAX_TOKENS):
        await asyncio.sleep(delays[model_key])
        return {
            "model_key": model_key,
            "success": True,
            "response": f"{model_key} response",
            "cost": 0.01,
            "elapsed_seconds": delays[model_key],
        }

    monkeypatch.setattr(server, "get_single_model_response", fake_single_model_response)

    result = asyncio.run(
        server.get_multi_model_responses(
            "prompt",
            ["slow", "fast", "medium", "invalid"],
            max_tokens=1,
        )
    )

    assert result["success"] is True
    assert result["response_order"] == "completion"
    assert result["invalid_models"] == ["invalid"]
    assert [response["model_key"] for response in result["responses"]] == ["fast", "medium", "slow"]
    assert [response["completion_order"] for response in result["responses"]] == [1, 2, 3]
    assert all("elapsed_seconds" in response for response in result["responses"])
    assert all("completed_at_seconds" in response for response in result["responses"])
    assert result["total_elapsed_seconds"] >= result["responses"][-1]["completed_at_seconds"]


def test_single_model_response_includes_elapsed_for_invalid_model(monkeypatch):
    server = _load_second_opinion_server(monkeypatch)

    result = asyncio.run(server.get_single_model_response("prompt", "missing-model"))

    assert result["success"] is False
    assert result["model_key"] == "missing-model"
    assert "elapsed_seconds" in result
    assert result["elapsed_seconds"] >= 0
