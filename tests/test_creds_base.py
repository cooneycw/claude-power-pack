"""Tests for lib/creds/base.py."""

from __future__ import annotations

import pytest

from lib.creds.base import (
    ProviderCaps,
    ProviderNotAvailableError,
    SecretBundle,
    SecretNotFoundError,
    SecretsError,
    SecretValue,
)


class TestSecretValue:
    """Test SecretValue wrapper."""

    def test_get_secret_value(self) -> None:
        sv = SecretValue("my-secret")
        assert sv.get_secret_value() == "my-secret"

    def test_repr_masks(self) -> None:
        sv = SecretValue("my-secret")
        assert repr(sv) == "SecretValue('****')"
        assert "my-secret" not in repr(sv)

    def test_str_masks(self) -> None:
        sv = SecretValue("my-secret")
        assert str(sv) == "****"
        assert "my-secret" not in str(sv)

    def test_repr_none(self) -> None:
        sv = SecretValue(None)
        assert repr(sv) == "SecretValue(None)"

    def test_str_none(self) -> None:
        sv = SecretValue(None)
        assert str(sv) == ""

    def test_bool_true(self) -> None:
        assert bool(SecretValue("secret")) is True

    def test_bool_false_none(self) -> None:
        assert bool(SecretValue(None)) is False

    def test_bool_false_empty(self) -> None:
        assert bool(SecretValue("")) is False

    def test_equality(self) -> None:
        a = SecretValue("secret")
        b = SecretValue("secret")
        c = SecretValue("other")
        assert a == b
        assert a != c

    def test_equality_different_type(self) -> None:
        sv = SecretValue("secret")
        assert sv != "secret"

    def test_hash(self) -> None:
        a = SecretValue("secret")
        b = SecretValue("secret")
        assert hash(a) == hash(b)
        # Usable in sets
        s = {a, b}
        assert len(s) == 1

    def test_len(self) -> None:
        assert len(SecretValue("hello")) == 5
        assert len(SecretValue(None)) == 0


class TestSecretBundle:
    """Test SecretBundle dataclass."""

    def test_creation(self) -> None:
        bundle = SecretBundle(project_id="my-app", secrets={"KEY": "val"})
        assert bundle.project_id == "my-app"
        assert len(bundle) == 1

    def test_keys(self) -> None:
        bundle = SecretBundle(project_id="app", secrets={"A": "1", "B": "2"})
        assert sorted(bundle.keys) == ["A", "B"]

    def test_get(self) -> None:
        bundle = SecretBundle(project_id="app", secrets={"KEY": "value"})
        assert bundle.get("KEY") == "value"
        assert bundle.get("MISSING") is None

    def test_set(self) -> None:
        bundle = SecretBundle(project_id="app")
        bundle.set("NEW_KEY", "new_value")
        assert bundle.get("NEW_KEY") == "new_value"
        assert bundle.updated_at is not None

    def test_delete_existing(self) -> None:
        bundle = SecretBundle(project_id="app", secrets={"KEY": "val"})
        result = bundle.delete("KEY")
        assert result is True
        assert bundle.get("KEY") is None
        assert len(bundle) == 0

    def test_delete_missing(self) -> None:
        bundle = SecretBundle(project_id="app")
        result = bundle.delete("NOPE")
        assert result is False

    def test_repr_masks_values(self) -> None:
        bundle = SecretBundle(project_id="app", secrets={"KEY": "secret123"})
        r = repr(bundle)
        assert "secret123" not in r
        assert "KEY" in r

    def test_str_masks_values(self) -> None:
        bundle = SecretBundle(project_id="app", secrets={"KEY": "secret123"})
        s = str(bundle)
        assert "secret123" not in s
        assert "KEY = ****" in s


class TestProviderCaps:
    """Test ProviderCaps flags."""

    def test_defaults(self) -> None:
        caps = ProviderCaps()
        assert caps.can_read is True
        assert caps.can_write is False
        assert caps.can_delete is False

    def test_full_caps(self) -> None:
        caps = ProviderCaps(can_read=True, can_write=True, can_delete=True, can_list=True)
        assert caps.can_write is True
        assert caps.can_delete is True

    def test_frozen(self) -> None:
        caps = ProviderCaps()
        with pytest.raises(AttributeError):
            caps.can_read = False  # type: ignore[misc]


class TestExceptions:
    """Test exception hierarchy."""

    def test_secrets_error_base(self) -> None:
        with pytest.raises(SecretsError):
            raise SecretsError("test")

    def test_provider_not_available(self) -> None:
        with pytest.raises(SecretsError):
            raise ProviderNotAvailableError("no provider")

    def test_secret_not_found(self) -> None:
        with pytest.raises(SecretsError):
            raise SecretNotFoundError("missing")
