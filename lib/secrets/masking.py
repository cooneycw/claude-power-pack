"""Pattern-based output masking for secrets.

This module provides tools to detect and mask secrets in text output:
- OutputMasker: Class for masking secrets in strings
- mask_output: Convenience function for quick masking
- scan_for_secrets: Detect potential secrets without masking

Usage:
    from lib.secrets.masking import OutputMasker, mask_output

    # Quick masking
    safe_output = mask_output("password=secret123")
    # "password=****"

    # With custom patterns
    masker = OutputMasker()
    masker.register_secret("my_api_key_value")
    safe = masker.mask(some_output)

Pattern sources:
    mcp-second-opinion/src/prompts.py:7-30
"""

from __future__ import annotations

import re
import logging
from typing import List, Set, Tuple, Optional

logger = logging.getLogger(__name__)


# Secret patterns: (regex_pattern, replacement_or_None)
# If replacement is None, the pattern is used for detection only
SECRET_PATTERNS: List[Tuple[str, Optional[str]]] = [
    # Connection strings - mask password portion
    (r"(postgresql://[^:]+:)([^@]+)(@)", r"\1****\3"),
    (r"(postgres://[^:]+:)([^@]+)(@)", r"\1****\3"),
    (r"(mysql://[^:]+:)([^@]+)(@)", r"\1****\3"),
    (r"(mongodb://[^:]+:)([^@]+)(@)", r"\1****\3"),
    (r"(redis://[^:]+:)([^@]+)(@)", r"\1****\3"),
    # API keys with known prefixes
    (r"(sk-)[A-Za-z0-9]{20,}", r"\1**********"),  # OpenAI
    (r"(AIza)[A-Za-z0-9_-]{35}", r"\1**********"),  # Google
    (r"(ghp_)[A-Za-z0-9]{36,}", r"\1**********"),  # GitHub token
    (r"(github_pat_)[A-Za-z0-9]{22,}", r"\1**********"),  # GitHub PAT
    (r"(glpat-)[A-Za-z0-9_-]{20,}", r"\1**********"),  # GitLab PAT
    (r"(gho_)[A-Za-z0-9]{36,}", r"\1**********"),  # GitHub OAuth
    (r"(ghu_)[A-Za-z0-9]{36,}", r"\1**********"),  # GitHub user token
    (r"(ghs_)[A-Za-z0-9]{36,}", r"\1**********"),  # GitHub server token
    # AWS keys
    (r"(AKIA)[A-Z0-9]{16}", r"\1**********"),  # AWS Access Key ID
    (r"(ASIA)[A-Z0-9]{16}", r"\1**********"),  # AWS Temp Access Key
    # Slack tokens
    (r"(xox[baprs]-)[A-Za-z0-9-]+", r"\1**********"),
    # Stripe keys
    (r"(sk_live_)[A-Za-z0-9]{24,}", r"\1**********"),
    (r"(sk_test_)[A-Za-z0-9]{24,}", r"\1**********"),
    (r"(pk_live_)[A-Za-z0-9]{24,}", r"\1**********"),
    (r"(pk_test_)[A-Za-z0-9]{24,}", r"\1**********"),
    # Generic key=value patterns (case insensitive)
    (r'(password\s*[=:]\s*["\']?)([^"\'\s}{,\]]+)(["\']?)', r"\1****\3"),
    (r'(passwd\s*[=:]\s*["\']?)([^"\'\s}{,\]]+)(["\']?)', r"\1****\3"),
    (r'(pwd\s*[=:]\s*["\']?)([^"\'\s}{,\]]+)(["\']?)', r"\1****\3"),
    (r'(secret\s*[=:]\s*["\']?)([^"\'\s}{,\]]+)(["\']?)', r"\1****\3"),
    (r'(api[_-]?key\s*[=:]\s*["\']?)([^"\'\s}{,\]]+)(["\']?)', r"\1****\3"),
    (r'(apikey\s*[=:]\s*["\']?)([^"\'\s}{,\]]+)(["\']?)', r"\1****\3"),
    (r'(auth[_-]?token\s*[=:]\s*["\']?)([^"\'\s}{,\]]+)(["\']?)', r"\1****\3"),
    (r'(access[_-]?token\s*[=:]\s*["\']?)([^"\'\s}{,\]]+)(["\']?)', r"\1****\3"),
    (r'(bearer\s+)([A-Za-z0-9._-]+)', r"\1****"),
    # Private keys (multiline - replace entire block)
    (
        r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----",
        "-----BEGIN PRIVATE KEY-----\n[REDACTED]\n-----END PRIVATE KEY-----",
    ),
    # JWT tokens (header.payload.signature format)
    (r"(eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.)[A-Za-z0-9_-]+", r"\1****"),
]


class OutputMasker:
    """Masks secrets in output strings.

    Combines pattern-based detection with explicit secret registration.
    Use this when you know specific values that need masking.

    Example:
        masker = OutputMasker()
        masker.register_secret(os.getenv("MY_SECRET"))

        safe_output = masker.mask(potentially_sensitive_output)
    """

    def __init__(
        self,
        additional_patterns: Optional[List[Tuple[str, Optional[str]]]] = None,
    ) -> None:
        """Initialize the masker.

        Args:
            additional_patterns: Extra (pattern, replacement) tuples to use.
        """
        self.patterns = SECRET_PATTERNS.copy()
        if additional_patterns:
            self.patterns.extend(additional_patterns)

        # Track explicitly registered secret values
        self._known_secrets: Set[str] = set()

    def register_secret(self, value: Optional[str]) -> None:
        """Register a known secret value for explicit masking.

        Registered secrets are masked by exact string replacement,
        which is more reliable than pattern matching for known values.

        Args:
            value: The secret value to mask. Ignored if None or too short.
        """
        if value and len(value) >= 4:  # Only track meaningful secrets
            self._known_secrets.add(value)
            logger.debug(f"Registered secret of length {len(value)}")

    def unregister_secret(self, value: str) -> None:
        """Remove a secret from the registry.

        Args:
            value: The secret value to remove.
        """
        self._known_secrets.discard(value)

    def mask(self, text: str) -> str:
        """Apply all masking patterns to text.

        Order of operations:
        1. Replace explicitly registered secrets
        2. Apply regex pattern replacements

        Args:
            text: Input text that may contain secrets.

        Returns:
            Text with secrets masked.
        """
        if not text:
            return text

        result = text

        # First, mask explicitly registered secrets (exact match)
        # Sort by length (longest first) to avoid partial replacements
        for secret in sorted(self._known_secrets, key=len, reverse=True):
            if secret in result:
                result = result.replace(secret, "****")

        # Then apply pattern-based masking
        for pattern, replacement in self.patterns:
            if replacement is None:
                continue  # Detection-only pattern
            try:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            except re.error as e:
                logger.warning(f"Invalid regex pattern: {pattern}: {e}")

        return result

    def scan(self, text: str) -> List[str]:
        """Scan text for potential secrets without masking.

        Useful for detecting accidental secret exposure before
        sending to external services.

        Args:
            text: Text to scan.

        Returns:
            List of warning messages about detected patterns.
        """
        if not text:
            return []

        warnings: List[str] = []

        # Check registered secrets
        for secret in self._known_secrets:
            if secret in text:
                warnings.append(f"Registered secret found in text (length {len(secret)})")

        # Check patterns
        for pattern, _ in self.patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Truncate pattern for display
                display_pattern = pattern[:40] + "..." if len(pattern) > 40 else pattern
                warnings.append(f"Potential secret matching: {display_pattern}")

        return warnings


# Module-level masker instance for convenience
_default_masker = OutputMasker()


def mask_output(text: str) -> str:
    """Convenience function to mask secrets in text.

    Uses a module-level OutputMasker instance with default patterns.

    Args:
        text: Input text that may contain secrets.

    Returns:
        Text with secrets masked.

    Example:
        safe = mask_output("password=secret123")
        # Returns: "password=****"
    """
    return _default_masker.mask(text)


def scan_for_secrets(text: str) -> List[str]:
    """Scan text for potential secrets.

    Uses a module-level OutputMasker instance with default patterns.

    Args:
        text: Text to scan.

    Returns:
        List of warning messages about detected patterns.

    Example:
        warnings = scan_for_secrets(code_to_review)
        if warnings:
            print("Potential secrets detected!")
            for w in warnings:
                print(f"  - {w}")
    """
    return _default_masker.scan(text)


def register_secret(value: Optional[str]) -> None:
    """Register a secret with the default masker.

    Args:
        value: Secret value to register for masking.
    """
    _default_masker.register_secret(value)
