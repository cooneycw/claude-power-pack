"""Tests for dual-transport (SSE + streamable-http) MCP server configuration.

Tests nano-banana directly (lightweight deps, in pythonpath).
Tests second-opinion and playwright only if their deps are available.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

try:
    from starlette.testclient import TestClient
except ImportError:
    pytest.skip("starlette not installed", allow_module_level=True)


def _load_module(server_dir: str, module_name: str):
    """Load a server module, adding its src/ to sys.path temporarily."""
    src_path = str(Path(__file__).resolve().parent.parent / server_dir / "src")
    inserted = False
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        inserted = True
    if module_name in sys.modules:
        del sys.modules[module_name]
    try:
        mod = importlib.import_module(module_name)
    finally:
        if inserted:
            sys.path.remove(src_path)
    return mod


class TestNanoBananaDualTransport:
    """Nano-banana has lightweight deps available in the root project."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.server = _load_module("mcp-nano-banana", "server")

    def test_build_dual_transport_app_exists(self):
        assert hasattr(self.server, "_build_dual_transport_app")
        assert callable(self.server._build_dual_transport_app)

    def test_dual_transport_app_has_all_routes(self):
        app = self.server._build_dual_transport_app()
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/" in paths, "Health check route missing"
        assert "/sse" in paths, "SSE transport route missing"
        assert "/mcp" in paths, "Streamable HTTP transport route missing"

    def test_health_endpoint_responds_200(self):
        app = self.server._build_dual_transport_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_sse_route_registered(self):
        """SSE transport route is registered (don't actually stream - it blocks)."""
        app = self.server._build_dual_transport_app()
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/sse" in paths

    def test_mcp_route_registered(self):
        """Streamable HTTP transport route is registered."""
        app = self.server._build_dual_transport_app()
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/mcp" in paths

    def test_messages_mount_exists(self):
        """SSE transport needs /messages for JSON-RPC message posting."""
        app = self.server._build_dual_transport_app()
        path_types = {getattr(r, "path", None): type(r).__name__ for r in app.routes}
        assert "/messages" in path_types, "SSE /messages mount missing"


class TestSecondOpinionDualTransport:
    """Second-opinion has heavy deps - skip if not available."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        try:
            from unittest.mock import patch

            with patch.dict("os.environ", {
                "GEMINI_API_KEY": "",
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
            }):
                self.server = _load_module("mcp-second-opinion", "server")
        except ImportError as e:
            pytest.skip(f"second-opinion deps not available: {e}")

    def test_dual_transport_app_has_all_routes(self):
        app = self.server._build_dual_transport_app()
        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/" in paths
        assert "/sse" in paths
        assert "/mcp" in paths

    def test_health_endpoint_responds_200(self):
        app = self.server._build_dual_transport_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
