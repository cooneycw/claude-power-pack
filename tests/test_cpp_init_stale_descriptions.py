"""The remaining wording promises current features, without reviving retired ones."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"


def test_local_qwen_uses_its_current_harness():
    text = INIT.read_text()
    tier = text.split("Tier 6 is optional and additive:", 1)[1].split("Tier 7 is likewise", 1)[0]
    assert "Qwen Code" in tier
    assert "reuses the Codex CLI" not in tier


def test_tier2_does_not_promise_live_output_masking():
    text = INIT.read_text()
    assert "| 2 | **Standard** | + Scripts, hooks, shell prompt |" not in text
    tier = text.split("### Tier 2 Disclosure", 1)[1].split("### Tier 3 Disclosure", 1)[0]
    assert "rm .claude/hooks.json" not in tier
    assert "hook-mask-output.sh" in tier, "the standalone helper still ships"
    assert "not registered" in tier.lower()
    assert "nothing live" in tier.lower()
    assert "files at rest" in tier.lower()


def test_cpp_distribution_uses_current_symlinks():
    text = INIT.read_text()
    assert "(or /plugin for the marketplace)" not in text
    assert "CANONICAL command surface" in text
    assert "retired /plugin marketplace families" in text


def test_status_observations_do_not_promise_readiness():
    text = INIT.read_text()
    assert "same logic as `/cpp:status`" not in text
    assert "presence observations" in text


def test_git_allowance_discloses_mutating_operations():
    text = INIT.read_text()
    assert "read-only git/gh plumbing" not in text
    assert "fetches and worktree creation" in text


def assert_no_retired_finish_claim(text: str) -> None:
    stale = r"`?/flow:finish`?\s*(?:→|->)\s*runs\s+`?make lint`?\s+and\s+`?make test`?"
    assert not re.search(stale, text), "retired fixed gate description returned"


def test_retired_makefile_finish_description_stays_absent():
    # The offer containing the old positive description was retired by R3.
    # Preserve the stale-claim guard without requiring that dead offer's text.
    assert_no_retired_finish_claim(INIT.read_text())


@pytest.mark.parametrize("stale", [
    "/flow:finish  → runs `make lint` and `make test`",
    "/flow:finish -> runs make lint and make test",
    "`/flow:finish` → runs `make lint` and `make test`",
])
def test_retired_finish_description_guard_rejects_known_bad_claims(stale):
    assert "/flow:finish" in stale and "make lint" in stale and "make test" in stale
    with pytest.raises(AssertionError, match="retired fixed gate description"):
        assert_no_retired_finish_claim(stale)


def test_retired_finish_guard_allows_a_correct_description_without_requiring_it():
    # This remains valid prose elsewhere, but cpp:init no longer needs to offer
    # a project Makefile in order to carry it.
    assert_no_retired_finish_claim("/flow:finish → runs the project's declared quality gates")


def test_codex_authentication_is_not_api_key_only():
    text = INIT.read_text()
    assert "Requires: OpenAI API key (codex login)" not in text
    assert "Codex commands require an OpenAI API key to function" not in text
    assert "ChatGPT sign-in or API-key authentication" in text
    assert "authentication unverified" in text


def test_smoke_zero_and_reruns_are_not_overclaimed():
    text = INIT.read_text()
    assert "Zero is the\n`/v1` signature" not in text
    assert "Zero is inconclusive" in text
    assert "This wizard is **idempotent**" not in text
    assert "Re-running can repeat optional writes" in text


def test_memory_harness_installation_tier_is_accurate():
    text = INIT.read_text()
    assert "Tier 2+ installed the\n`cpp-memory` harness" not in text
    assert "Tier 5f installs the PATH harness" in text


def test_minimal_tier_mentions_default_stash_guard():
    text = INIT.read_text()
    assert "| 1 | **Minimal** | Commands symlink only |" not in text
    assert "Commands symlinks and project stash guard" in text
