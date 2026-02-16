"""Data models for security scanning.

Provides:
- Severity: Enum for finding severity levels
- Finding: A single security issue detected by a scanner
- ScanResult: Aggregated results from all scanners
- Suppression: Configuration to suppress known findings
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional


class Severity(IntEnum):
    """Severity levels for security findings, ordered by importance."""

    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1

    @property
    def icon(self) -> str:
        icons = {
            Severity.CRITICAL: "\U0001f534",  # red circle
            Severity.HIGH: "\U0001f7e1",  # yellow circle
            Severity.MEDIUM: "\U0001f7e0",  # orange circle
            Severity.LOW: "\u26aa",  # white circle
        }
        return icons[self]

    @property
    def label(self) -> str:
        return self.name


@dataclass
class Finding:
    """A single security issue detected by a scanner module."""

    id: str
    severity: Severity
    title: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    why: str = ""
    fix: str = ""
    command: Optional[str] = None
    time_estimate: Optional[str] = None
    scanner: str = "native"
    raw_match: Optional[str] = None

    @property
    def location(self) -> str:
        if self.file_path and self.line_number:
            return f"{self.file_path}:{self.line_number}"
        if self.file_path:
            return self.file_path
        return ""

    def mask_secret(self, value: str) -> str:
        """Mask a secret value, showing only a prefix."""
        if len(value) <= 4:
            return "****"
        return value[:4] + "*" * min(16, len(value) - 4)


@dataclass
class Suppression:
    """A suppression rule for known/accepted findings."""

    id: str
    path: Optional[str] = None
    reason: str = ""

    def matches(self, finding: Finding) -> bool:
        if finding.id != self.id:
            return False
        if self.path and finding.file_path:
            return bool(re.match(self.path, finding.file_path))
        if self.path:
            return False
        return True


@dataclass
class ScanResult:
    """Aggregated results from all scanner modules."""

    findings: list[Finding] = field(default_factory=list)
    passed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.LOW)

    @property
    def has_blockers(self) -> bool:
        return self.critical_count > 0

    @property
    def has_warnings(self) -> bool:
        return self.high_count > 0

    def summary_line(self) -> str:
        parts = []
        if self.critical_count:
            parts.append(f"{self.critical_count} critical")
        if self.high_count:
            parts.append(f"{self.high_count} high")
        if self.medium_count:
            parts.append(f"{self.medium_count} medium")
        if self.low_count:
            parts.append(f"{self.low_count} low")
        if not parts:
            return "No issues found"
        return ", ".join(parts)

    def merge(self, other: ScanResult) -> None:
        self.findings.extend(other.findings)
        self.passed.extend(other.passed)
        self.skipped.extend(other.skipped)
        self.errors.extend(other.errors)
