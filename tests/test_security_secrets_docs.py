"""Bounded public claims, backed by existing code and owned credential fixtures."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from lib import creds
from lib.creds.base import SecretBundle
from lib.creds.providers.dotenv import DotEnvSecretsProvider

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/security-secrets-docs/claims.json").read_text())


def assert_claims(text, contract):
    normalized = text.casefold()
    for claim in contract["forbidden"]:
        assert claim.casefold() not in normalized, f"forbidden claim: {claim}"
    for claim in contract["required"]:
        assert claim.casefold() in normalized, f"missing bounded claim: {claim}"


@pytest.mark.parametrize("document", CASES["contracts"])
def test_actual_public_claims(document):
    assert_claims((ROOT / document).read_text(), CASES["contracts"][document])


@pytest.mark.parametrize("document", CASES["contracts"])
def test_committed_true_claims_are_accepted_and_empty_text_is_refused(document):
    contract = CASES["contracts"][document]
    assert_claims(CASES["good"][document], contract)
    with pytest.raises(AssertionError, match="missing bounded claim"):
        assert_claims("", contract)


@pytest.mark.parametrize("case", CASES["bad"], ids=lambda row: row["claim"])
def test_committed_false_claims_are_refused(case):
    contract = CASES["contracts"][case["document"]]
    good = CASES["good"][case["document"]]
    assert case["claim"].casefold() not in good.casefold()
    assert_claims(good, contract)
    bad = good + "\n" + case["claim"]
    assert case["claim"] in bad
    with pytest.raises(AssertionError, match="forbidden claim"):
        assert_claims(bad, contract)


@pytest.mark.parametrize("name", ["help", "get"])
def test_actual_generated_codex_claims(name):
    spec = importlib.util.spec_from_file_location("security_claims_sync", ROOT / "scripts/codex-skill-sync.py")
    assert spec and spec.loader
    sync = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = sync
    spec.loader.exec_module(sync)
    source = ROOT / f".claude/commands/secrets/{name}.md"
    files = sync.generate_skill(source, "secrets", sync.generated_names(sync.FAMILIES))
    assert set(files) == {"SKILL.md"}, "claims-only change must preserve the existing inline member"
    assert_claims(files["SKILL.md"], CASES["contracts"][source.relative_to(ROOT).as_posix()])


def test_runtime_examples_remain_identical_to_the_predecessor():
    assert sum("PYTHONPATH=" in line for line in CASES["runtime_lines"]["lib/security/README.md"]) == 5
    for document, expected in CASES["runtime_lines"].items():
        actual = [line for line in (ROOT / document).read_text().splitlines()
                  if re.search(r"PYTHONPATH=|uv run|uv sync", line)]
        assert actual == expected, f"runtime changes belong to PR2: {document}"


def test_local_store_is_plaintext_with_owner_only_permissions(tmp_path, monkeypatch):
    config = tmp_path / "owned-config"
    config.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    provider = DotEnvSecretsProvider()
    provider.put_bundle(SecretBundle(project_id="docs-fixture", secrets={"DOCS_MARKER": "owned fixture value"}),
                        mode="replace")
    path = config / "claude-power-pack/secrets/docs-fixture/.env"
    assert "owned fixture value" in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert provider.get_bundle("docs-fixture").secrets == {"DOCS_MARKER": "owned fixture value"}


@pytest.mark.parametrize("aws_available", [False, True])
def test_get_auto_prefers_available_aws_otherwise_environment(monkeypatch, aws_available):
    class FakeAWS:
        def is_available(self):
            return aws_available

    class FakeEnv:
        pass

    monkeypatch.setattr(creds, "AWSSecretsProvider", FakeAWS)
    monkeypatch.setattr(creds, "EnvSecretsProvider", FakeEnv)
    assert isinstance(creds.get_provider(), FakeAWS if aws_available else FakeEnv)
