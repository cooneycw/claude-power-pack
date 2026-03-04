"""Tests for lib/creds/masking.py."""

from __future__ import annotations

from lib.creds.masking import OutputMasker, mask_output, scan_for_secrets


class TestOutputMasker:
    """Test OutputMasker class."""

    def test_mask_connection_string(self) -> None:
        masker = OutputMasker()
        text = "postgresql://user:secret_pass@localhost:5432/db"
        result = masker.mask(text)
        assert "secret_pass" not in result
        assert "****" in result
        assert "user:" in result

    def test_mask_openai_key(self) -> None:
        masker = OutputMasker()
        text = "OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno345pqr678"
        result = masker.mask(text)
        assert "abc123def456" not in result

    def test_mask_github_token(self) -> None:
        masker = OutputMasker()
        text = "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl"
        result = masker.mask(text)
        assert "ABCDEFGHIJKLMNOPQRS" not in result

    def test_mask_aws_key(self) -> None:
        masker = OutputMasker()
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = masker.mask(text)
        assert "IOSFODNN7EXAMPLE" not in result

    def test_mask_password_assignment(self) -> None:
        masker = OutputMasker()
        text = 'password = "my_super_secret"'
        result = masker.mask(text)
        assert "my_super_secret" not in result

    def test_mask_bearer_token(self) -> None:
        masker = OutputMasker()
        text = "Authorization: bearer eyJhbGciOiJIUzI1NiJ9.test"
        result = masker.mask(text)
        assert "eyJhbGciOiJIUzI1NiJ9" not in result

    def test_mask_anthropic_key(self) -> None:
        masker = OutputMasker()
        text = "key = sk-ant-api03-abcdefghijklmnopqrstuvwx"
        result = masker.mask(text)
        assert "abcdefghijklmnopqrst" not in result

    def test_mask_private_key(self) -> None:
        masker = OutputMasker()
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        result = masker.mask(text)
        assert "MIIEpAIBAAKCAQEA" not in result
        assert "REDACTED" in result

    def test_mask_empty_string(self) -> None:
        masker = OutputMasker()
        assert masker.mask("") == ""

    def test_mask_no_secrets(self) -> None:
        masker = OutputMasker()
        text = "Hello, this is a normal log line with no secrets."
        result = masker.mask(text)
        assert result == text

    def test_registered_secret(self) -> None:
        masker = OutputMasker()
        masker.register_secret("my_custom_secret_value")
        text = "The value is my_custom_secret_value in the output"
        result = masker.mask(text)
        assert "my_custom_secret_value" not in result
        assert "****" in result

    def test_register_ignores_short(self) -> None:
        masker = OutputMasker()
        masker.register_secret("abc")  # Too short
        assert len(masker._known_secrets) == 0

    def test_register_ignores_none(self) -> None:
        masker = OutputMasker()
        masker.register_secret(None)
        assert len(masker._known_secrets) == 0

    def test_unregister_secret(self) -> None:
        masker = OutputMasker()
        masker.register_secret("my_secret_value")
        masker.unregister_secret("my_secret_value")
        text = "Contains my_secret_value here"
        result = masker.mask(text)
        assert "my_secret_value" in result

    def test_additional_patterns(self) -> None:
        masker = OutputMasker(additional_patterns=[
            (r"CUSTOM_[A-Z]+", "****"),
        ])
        text = "Value: CUSTOM_TOKEN"
        result = masker.mask(text)
        assert "CUSTOM_TOKEN" not in result


class TestScan:
    """Test secret scanning."""

    def test_scan_detects_secrets(self) -> None:
        masker = OutputMasker()
        text = 'password = "secret123"'
        warnings = masker.scan(text)
        assert len(warnings) > 0

    def test_scan_registered_secret(self) -> None:
        masker = OutputMasker()
        masker.register_secret("specific_value_here")
        warnings = masker.scan("Contains specific_value_here")
        assert any("Registered secret" in w for w in warnings)

    def test_scan_empty(self) -> None:
        masker = OutputMasker()
        assert masker.scan("") == []

    def test_scan_clean(self) -> None:
        masker = OutputMasker()
        # A simple string with no patterns
        warnings = masker.scan("Hello world")
        assert len(warnings) == 0


class TestModuleLevelFunctions:
    """Test convenience functions."""

    def test_mask_output(self) -> None:
        result = mask_output("postgresql://user:pass@host/db")
        assert "pass" not in result

    def test_scan_for_secrets(self) -> None:
        warnings = scan_for_secrets('api_key = "abc123def456ghi789"')
        assert len(warnings) > 0
