"""Tests for lib.cpp_memory.harness: the multi-harness tag resolver (issue #557).

The shared friction ledger is written by more than one harness (Claude Code and,
per codex-power-pack epic #67, Codex). ``resolve_harness`` decides the tag with an
explicit-first precedence so the Codex writer has an unambiguous target and never
depends on us guessing its environment.
"""
from __future__ import annotations

import pytest

from lib.cpp_memory import KNOWN_HARNESSES, resolve_harness
from lib.cpp_memory import harness as harness_mod


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts with no harness-declaring env vars set."""
    monkeypatch.delenv("CPP_HARNESS", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)


class TestNormalize:
    def test_folds_case_and_whitespace(self):
        assert harness_mod.normalize("  Codex ") == "codex"
        assert harness_mod.normalize("CLAUDE") == "claude"

    def test_empty_is_none(self):
        assert harness_mod.normalize("") is None
        assert harness_mod.normalize("   ") is None
        assert harness_mod.normalize(None) is None

    def test_unknown_passes_through(self):
        # Not rejected: the ledger stays open to a future harness.
        assert harness_mod.normalize("gemini") == "gemini"


class TestResolveHarness:
    def test_known_set(self):
        assert {"claude", "codex", "shell"} <= set(KNOWN_HARNESSES)

    def test_explicit_wins_over_everything(self, monkeypatch):
        monkeypatch.setenv("CPP_HARNESS", "codex")
        monkeypatch.setenv("CLAUDECODE", "1")
        assert resolve_harness("shell") == "shell"

    def test_explicit_is_normalized(self):
        assert resolve_harness("  Codex ") == "codex"

    def test_env_used_when_no_explicit(self, monkeypatch):
        monkeypatch.setenv("CPP_HARNESS", "codex")
        assert resolve_harness() == "codex"

    def test_env_beats_claude_autodetect(self, monkeypatch):
        # A non-Claude harness may run *inside* a Claude Code shell; its explicit
        # CPP_HARNESS declaration must win over the CLAUDECODE auto-detect.
        monkeypatch.setenv("CPP_HARNESS", "codex")
        monkeypatch.setenv("CLAUDECODE", "1")
        assert resolve_harness() == "codex"

    def test_claude_autodetected_from_claudecode(self, monkeypatch):
        monkeypatch.setenv("CLAUDECODE", "1")
        assert resolve_harness() == "claude"

    def test_none_when_unresolved(self):
        # No arg, no env, no CLAUDECODE -> unattributed (NULL sighting), the
        # backward-compatible pre-#557 shape.
        assert resolve_harness() is None
        assert resolve_harness("") is None
