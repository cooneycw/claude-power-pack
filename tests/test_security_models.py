"""Tests for lib/security/models.py."""

from __future__ import annotations

from lib.security.models import Finding, ScanResult, Severity, Suppression


class TestSeverity:
    """Test Severity enum."""

    def test_ordering(self) -> None:
        assert Severity.CRITICAL > Severity.HIGH > Severity.MEDIUM > Severity.LOW

    def test_values(self) -> None:
        assert Severity.CRITICAL == 4
        assert Severity.HIGH == 3
        assert Severity.MEDIUM == 2
        assert Severity.LOW == 1

    def test_icon(self) -> None:
        assert Severity.CRITICAL.icon == "\U0001f534"
        assert Severity.LOW.icon == "\u26aa"

    def test_label(self) -> None:
        assert Severity.CRITICAL.label == "CRITICAL"
        assert Severity.LOW.label == "LOW"


class TestFinding:
    """Test Finding dataclass."""

    def test_location_with_file_and_line(self) -> None:
        f = Finding(id="TEST", severity=Severity.HIGH, title="Test", file_path="foo.py", line_number=10)
        assert f.location == "foo.py:10"

    def test_location_with_file_only(self) -> None:
        f = Finding(id="TEST", severity=Severity.HIGH, title="Test", file_path="foo.py")
        assert f.location == "foo.py"

    def test_location_empty(self) -> None:
        f = Finding(id="TEST", severity=Severity.HIGH, title="Test")
        assert f.location == ""

    def test_mask_secret_short(self) -> None:
        f = Finding(id="TEST", severity=Severity.HIGH, title="Test")
        assert f.mask_secret("abc") == "****"

    def test_mask_secret_long(self) -> None:
        f = Finding(id="TEST", severity=Severity.HIGH, title="Test")
        result = f.mask_secret("AKIA1234567890123456")
        assert result.startswith("AKIA")
        assert "****" in result or "*" in result

    def test_defaults(self) -> None:
        f = Finding(id="TEST", severity=Severity.LOW, title="Test")
        assert f.scanner == "native"
        assert f.why == ""
        assert f.fix == ""
        assert f.command is None
        assert f.raw_match is None


class TestSuppression:
    """Test Suppression matching."""

    def test_matches_by_id(self) -> None:
        s = Suppression(id="HARDCODED_SECRET")
        f = Finding(id="HARDCODED_SECRET", severity=Severity.HIGH, title="Secret found")
        assert s.matches(f) is True

    def test_no_match_different_id(self) -> None:
        s = Suppression(id="HARDCODED_SECRET")
        f = Finding(id="DEBUG_FLAG", severity=Severity.MEDIUM, title="Debug flag")
        assert s.matches(f) is False

    def test_matches_with_path_pattern(self) -> None:
        s = Suppression(id="HARDCODED_SECRET", path=r"tests/.*")
        f = Finding(id="HARDCODED_SECRET", severity=Severity.HIGH, title="Secret", file_path="tests/test_foo.py")
        assert s.matches(f) is True

    def test_no_match_path_mismatch(self) -> None:
        s = Suppression(id="HARDCODED_SECRET", path=r"tests/.*")
        f = Finding(id="HARDCODED_SECRET", severity=Severity.HIGH, title="Secret", file_path="src/main.py")
        assert s.matches(f) is False

    def test_path_suppression_requires_file_path(self) -> None:
        s = Suppression(id="HARDCODED_SECRET", path=r"tests/.*")
        f = Finding(id="HARDCODED_SECRET", severity=Severity.HIGH, title="Secret")
        assert s.matches(f) is False


class TestScanResult:
    """Test ScanResult aggregation."""

    def test_empty_result(self) -> None:
        r = ScanResult()
        assert r.critical_count == 0
        assert r.high_count == 0
        assert r.medium_count == 0
        assert r.low_count == 0
        assert r.has_blockers is False
        assert r.has_warnings is False
        assert r.summary_line() == "No issues found"

    def test_counts(self) -> None:
        r = ScanResult(findings=[
            Finding(id="A", severity=Severity.CRITICAL, title="A"),
            Finding(id="B", severity=Severity.CRITICAL, title="B"),
            Finding(id="C", severity=Severity.HIGH, title="C"),
            Finding(id="D", severity=Severity.MEDIUM, title="D"),
            Finding(id="E", severity=Severity.LOW, title="E"),
        ])
        assert r.critical_count == 2
        assert r.high_count == 1
        assert r.medium_count == 1
        assert r.low_count == 1
        assert r.has_blockers is True
        assert r.has_warnings is True

    def test_summary_line(self) -> None:
        r = ScanResult(findings=[
            Finding(id="A", severity=Severity.CRITICAL, title="A"),
            Finding(id="B", severity=Severity.HIGH, title="B"),
        ])
        line = r.summary_line()
        assert "1 critical" in line
        assert "1 high" in line

    def test_merge(self) -> None:
        r1 = ScanResult(
            findings=[Finding(id="A", severity=Severity.HIGH, title="A")],
            passed=["check1"],
        )
        r2 = ScanResult(
            findings=[Finding(id="B", severity=Severity.LOW, title="B")],
            passed=["check2"],
            errors=["err1"],
        )
        r1.merge(r2)
        assert len(r1.findings) == 2
        assert len(r1.passed) == 2
        assert len(r1.errors) == 1
