"""Signing-key persistence through the real host bootstrap entry points (#1572)."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GRPC = "WOODPECKER_GRPC_SECRET"


@pytest.fixture(params=["woodpecker/bootstrap-secrets.py", "templates/woodpecker/bootstrap-secrets.py.example"])
def bootstrap(request, tmp_path, monkeypatch):
    source = ROOT / request.param
    copied = tmp_path / "bootstrap.py"
    copied.write_text(source.read_text())
    payload = {"WOODPECKER_HOST": "https://ci.example.invalid"}
    client = types.SimpleNamespace(get_secret_value=lambda **kwargs: {"SecretString": json.dumps(payload)})
    def fake_session(**kwargs):
        return types.SimpleNamespace(client=lambda *args: client)
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(Session=fake_session))
    loader = importlib.machinery.SourceFileLoader("host_bootstrap", str(copied))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    monkeypatch.setattr(sys, "argv", [str(copied), "--secret-name", "dummy-test"])
    return module, tmp_path / "docker.env", payload


def test_regeneration_retains_existing_signing_secret(bootstrap, capsys):
    module, path, payload = bootstrap
    dummy = "dummy-existing-signing-key"
    payload[GRPC] = "dummy-different-source-key"
    path.write_text(f"{GRPC}={dummy}\nSTALE_KEY=discard-me\n")
    module.main()
    assert f"{GRPC}={dummy}\n" in path.read_text()
    assert "STALE_KEY=" not in path.read_text()
    captured = capsys.readouterr()
    assert dummy not in captured.out + captured.err
    assert "dummy-different-source-key" not in path.read_text()


def test_fresh_file_without_signing_key_has_no_fallback(bootstrap, capsys):
    module, path, _ = bootstrap
    assert not path.exists()
    module.main()
    assert GRPC + "=" not in path.read_text()
    assert "dummy" not in capsys.readouterr().out.replace("dummy-test", "")


def test_fresh_file_carries_explicit_durable_source(bootstrap, capsys):
    module, path, payload = bootstrap
    payload[GRPC] = "dummy-durable-source-key"
    assert not path.exists()
    module.main()
    assert f"{GRPC}=dummy-durable-source-key\n" in path.read_text()
    captured = capsys.readouterr()
    assert "dummy-durable-source-key" not in captured.out + captured.err
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("assignment", [
    "WOODPECKER_GRPC_SECRET=", "WOODPECKER_GRPC_SECRET=''",
    "WOODPECKER_GRPC_SECRET=one\nWOODPECKER_GRPC_SECRET=two", "WOODPECKER_GRPC_SECRET malformed",
])
def test_bad_existing_assignment_cannot_truncate_file(bootstrap, assignment):
    module, path, _ = bootstrap
    original = assignment + "\nWOODPECKER_HOST=old\n"
    path.write_text(original)
    assert path.read_text() == original
    with pytest.raises((ValueError, SystemExit)):
        module.main()
    assert path.read_text() == original


def test_replace_failure_leaves_previous_file(bootstrap, monkeypatch):
    module, path, _ = bootstrap
    original = "WOODPECKER_GRPC_SECRET=dummy-survivor\n"
    path.write_text(original)
    assert path.read_text() == original
    def fail(*args):
        raise OSError("simulated replacement failure")
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError, match="simulated replacement"):
        module.main()
    assert path.read_text() == original
    assert not list(path.parent.glob(".docker-env-*"))


@pytest.mark.parametrize("value", [None, ""])
def test_empty_source_does_not_create_a_fallback(bootstrap, value):
    module, path, payload = bootstrap
    payload[GRPC] = value
    assert not path.exists()
    module.main()
    assert GRPC + "=" not in path.read_text()


def test_failed_flush_leaves_previous_file(bootstrap, monkeypatch):
    module, path, _ = bootstrap
    original = "WOODPECKER_GRPC_SECRET=dummy-old-key\n"
    path.write_text(original)
    assert path.read_text() == original
    def fail(*args):
        raise OSError("simulated flush failure")
    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError, match="simulated flush"):
        module.main()
    assert path.read_text() == original
    assert not list(path.parent.glob(".docker-env-*"))


def test_newline_source_cannot_truncate_or_disclose(bootstrap, capsys):
    module, path, payload = bootstrap
    original = "WOODPECKER_HOST=old\n"
    path.write_text(original)
    payload[GRPC] = "dummy-invalid\nINJECTED=bad"
    assert path.read_text() == original
    with pytest.raises(ValueError, match="one line"):
        module.main()
    assert path.read_text() == original
    captured = capsys.readouterr()
    assert "dummy-invalid" not in captured.out + captured.err


def test_quoted_existing_value_survives_regeneration(bootstrap):
    module, path, _ = bootstrap
    path.write_text("WOODPECKER_GRPC_SECRET='dummy-quoted-key'\n")
    module.main()
    assert "WOODPECKER_GRPC_SECRET='dummy-quoted-key'\n" in path.read_text()


def test_explicit_template_keys_still_preserve_local_signing_key(bootstrap, monkeypatch, capsys):
    module, path, payload = bootstrap
    payload[GRPC] = "dummy-source-excluded"
    path.write_text("WOODPECKER_GRPC_SECRET=dummy-local-kept\n")
    monkeypatch.setattr(sys, "argv", [module.__file__, "--secret-name", "dummy-test", "--keys", "WOODPECKER_HOST"])
    module.main()
    assert "WOODPECKER_GRPC_SECRET=dummy-local-kept\n" in path.read_text()
    assert "dummy-source-excluded" not in path.read_text()
    captured = capsys.readouterr()
    assert "dummy-source-excluded" not in captured.out + captured.err
    assert "dummy-local-kept" not in captured.out + captured.err


def test_explicit_template_keys_do_not_import_excluded_aws_secret(bootstrap, monkeypatch, capsys):
    module, path, payload = bootstrap
    payload[GRPC] = "dummy-source-excluded"
    assert not path.exists()
    monkeypatch.setattr(sys, "argv", [module.__file__, "--secret-name", "dummy-test", "--keys", "WOODPECKER_HOST"])
    module.main()
    if hasattr(module, "DEFAULT_KEYS"):  # Only the distributed template exposes --keys.
        assert GRPC + "=" not in path.read_text()
    else:
        assert "WOODPECKER_GRPC_SECRET=dummy-source-excluded\n" in path.read_text()
    captured = capsys.readouterr()
    assert "dummy-source-excluded" not in captured.out + captured.err


def test_unrelated_env_syntax_does_not_block_preservation(bootstrap):
    module, path, _ = bootstrap
    path.write_text("UNRELATED='multi\nline'\nexport OTHER=value\nWOODPECKER_GRPC_SECRET_NEIGHBOR=x\n"
                    "WOODPECKER_GRPC_SECRET=dummy-local-kept\n")
    module.main()
    assert "WOODPECKER_GRPC_SECRET=dummy-local-kept\n" in path.read_text()
    assert "UNRELATED" not in path.read_text()
    assert "NEIGHBOR" not in path.read_text()


@pytest.mark.parametrize("prefix", ["  ", "\t"])
def test_leading_whitespace_local_key_is_retained_once(bootstrap, prefix):
    module, path, payload = bootstrap
    payload[GRPC] = "dummy-conflicting-source"
    path.write_text(prefix + "WOODPECKER_GRPC_SECRET=dummy-old\n")
    module.main()
    result = path.read_text()
    assert result.count("WOODPECKER_GRPC_SECRET=") == 1
    assert "WOODPECKER_GRPC_SECRET=dummy-old\n" in result
    assert "dummy-conflicting-source" not in result


@pytest.mark.parametrize("value", ["${UNSET_SIGNING_KEY}", "abc #def", "'quoted'", '"quoted"', r"back\slash", "$NAME"])
def test_unsupported_aws_expression_refuses_before_replacement(bootstrap, value, capsys):
    module, path, payload = bootstrap
    original = "WOODPECKER_HOST=old\n"
    path.write_text(original)
    payload[GRPC] = value
    assert path.read_text() == original
    with pytest.raises(ValueError, match="WOODPECKER_GRPC_SECRET"):
        module.main()
    assert path.read_text() == original
    captured = capsys.readouterr()
    assert value not in captured.out + captured.err


@pytest.mark.parametrize("value", ["${SIGNING_KEY}", '"${SIGNING_KEY}"', "$UNRESOLVED"])
def test_interpolation_dependency_cannot_silently_rotate(bootstrap, value):
    module, path, payload = bootstrap
    original = "SIGNING_KEY=dummy-old\nWOODPECKER_GRPC_SECRET=" + value + "\n"
    path.write_text(original)
    payload[GRPC] = "dummy-conflicting-aws"
    assert path.read_text() == original
    with pytest.raises(ValueError, match="WOODPECKER_GRPC_SECRET"):
        module.main()
    assert path.read_text() == original


@pytest.mark.parametrize("real_assignment", [False, True])
def test_assignment_shaped_multiline_neighbor_is_not_the_key(bootstrap, real_assignment):
    module, path, payload = bootstrap
    neighbor = "OTHER='first\nWOODPECKER_GRPC_SECRET=decoy\nlast'\n"
    path.write_text(neighbor + ("WOODPECKER_GRPC_SECRET=dummy-real\n" if real_assignment else ""))
    payload[GRPC] = "dummy-aws"
    module.main()
    assert path.read_text().count("WOODPECKER_GRPC_SECRET=") == 1
    assert "decoy" not in path.read_text()
    expected = "dummy-real" if real_assignment else "dummy-aws"
    assert f"WOODPECKER_GRPC_SECRET={expected}\n" in path.read_text()


@pytest.mark.parametrize(("line", "token"), [
    ("WOODPECKER_GRPC_SECRET = dummy-value", "dummy-value"),
    ("WOODPECKER_GRPC_SECRET='dummy-value' # comment", "'dummy-value'"),
    ("WOODPECKER_GRPC_SECRET='#literal'", "'#literal'"),
    ("export WOODPECKER_GRPC_SECRET = 'literal${UNCHANGED}'", "'literal${UNCHANGED}'"),
    ('WOODPECKER_GRPC_SECRET="escaped\\\\path" # comment', '"escaped\\\\path"'),
])
def test_valid_literal_syntax_preserves_consumer_token(bootstrap, line, token):
    module, path, _ = bootstrap
    path.write_text(line + "\n")
    module.main()
    assert f"WOODPECKER_GRPC_SECRET={token}\n" in path.read_text()


@pytest.mark.parametrize("value", ["'one'junk'", '"one"junk"', "'unterminated", '"unterminated'])
def test_malformed_quote_trailing_content_cannot_replace(bootstrap, value):
    module, path, _ = bootstrap
    original = "WOODPECKER_GRPC_SECRET=" + value + "\n"
    path.write_text(original)
    assert path.read_text() == original
    with pytest.raises(ValueError, match="WOODPECKER_GRPC_SECRET"):
        module.main()
    assert path.read_text() == original


@pytest.mark.parametrize("neighbor_key", ["OTHER.KEY", "OTHER-KEY"])
def test_other_key_spellings_still_hide_multiline_decoys(bootstrap, neighbor_key):
    module, path, payload = bootstrap
    path.write_text(neighbor_key + "='first\nWOODPECKER_GRPC_SECRET=decoy\nlast'\n")
    payload[GRPC] = "dummy-aws"
    module.main()
    assert "WOODPECKER_GRPC_SECRET=dummy-aws\n" in path.read_text()
    assert "decoy" not in path.read_text()
