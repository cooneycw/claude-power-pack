"""Tests for security scanner modules and orchestrator."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from lib.security.config import SecurityConfig
from lib.security.models import Finding, ScanResult, Severity, Suppression
from lib.security.modules import debug_flags, gitignore, permissions, secrets
from lib.security.orchestrator import _apply_suppressions, check_gate


class TestGitignoreScanner:
    """Test gitignore coverage scanner."""

    def test_all_patterns_covered(self, tmp_project: Path) -> None:
        result = gitignore.scan(str(tmp_project))
        assert len(result.findings) == 0
        assert len(result.passed) > 0

    def test_missing_gitignore(self, tmp_path: Path) -> None:
        result = gitignore.scan(str(tmp_path))
        assert len(result.findings) == 1
        assert result.findings[0].id == "GITIGNORE_MISSING"
        assert result.findings[0].severity == Severity.HIGH

    def test_missing_env_pattern(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.pem\n*.key\n")
        result = gitignore.scan(str(tmp_path))
        ids = [f.id for f in result.findings]
        assert "GITIGNORE_GAP" in ids
        # .env is CRITICAL
        env_finding = next(f for f in result.findings if ".env" in f.title and ".env." not in f.title)
        assert env_finding.severity == Severity.CRITICAL

    def test_pattern_covered_by_wildcard(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text(
            ".env\n.env.*\n*.pem\n*.key\nsecrets.*\n*.p12\n.claude/security.yml\n"
        )
        result = gitignore.scan(str(tmp_path))
        assert len(result.findings) == 0


class TestPermissionsScanner:
    """Test file permissions scanner."""

    def test_no_sensitive_files(self, tmp_project: Path) -> None:
        result = permissions.scan(str(tmp_project))
        assert len(result.findings) == 0

    def test_world_readable_key(self, tmp_project: Path) -> None:
        key_file = tmp_project / "server.pem"
        key_file.write_text("FAKE KEY")
        os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        result = permissions.scan(str(tmp_project))
        assert len(result.findings) == 1
        assert result.findings[0].id == "FILE_PERMISSIONS"

    def test_restricted_key(self, tmp_project: Path) -> None:
        key_file = tmp_project / "server.pem"
        key_file.write_text("FAKE KEY")
        os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)  # 600
        result = permissions.scan(str(tmp_project))
        assert len(result.findings) == 0


class TestSecretsScanner:
    """Test native secret detection scanner."""

    def test_clean_project(self, tmp_project: Path) -> None:
        src = tmp_project / "main.py"
        src.write_text("# Clean file\nprint('hello')\n")
        result = secrets.scan(str(tmp_project))
        assert len(result.findings) == 0

    def test_detect_aws_key(self, tmp_project: Path) -> None:
        src = tmp_project / "config.py"
        src.write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        result = secrets.scan(str(tmp_project))
        aws_findings = [f for f in result.findings if f.id == "AWS_ACCESS_KEY"]
        assert len(aws_findings) == 1
        assert aws_findings[0].severity == Severity.CRITICAL

    def test_detect_github_pat(self, tmp_project: Path) -> None:
        src = tmp_project / "config.py"
        src.write_text('TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"\n')
        result = secrets.scan(str(tmp_project))
        gh_findings = [f for f in result.findings if f.id == "GITHUB_PAT"]
        assert len(gh_findings) == 1

    def test_detect_hardcoded_password(self, tmp_project: Path) -> None:
        src = tmp_project / "config.py"
        src.write_text('password = "super_secret_password_123"\n')
        result = secrets.scan(str(tmp_project))
        pw_findings = [f for f in result.findings if f.id == "HARDCODED_PASSWORD"]
        assert len(pw_findings) == 1
        assert pw_findings[0].severity == Severity.HIGH

    def test_skip_pattern_files(self, tmp_project: Path) -> None:
        # Files in SKIP_PATTERN_FILES should be skipped
        src = tmp_project / "masking.py"
        src.write_text('PATTERN = r"AKIA[0-9A-Z]{16}"\n')
        result = secrets.scan(str(tmp_project))
        assert len(result.findings) == 0

    def test_no_source_files(self, tmp_path: Path) -> None:
        result = secrets.scan(str(tmp_path))
        assert len(result.skipped) > 0


class TestDebugFlagsScanner:
    """Test debug flag detection scanner."""

    def test_clean_config(self, tmp_project: Path) -> None:
        cfg = tmp_project / "settings.py"
        cfg.write_text("DEBUG = False\n")
        result = debug_flags.scan(str(tmp_project))
        assert len(result.findings) == 0

    def test_detect_debug_true(self, tmp_project: Path) -> None:
        cfg = tmp_project / "settings.py"
        cfg.write_text("DEBUG = True\n")
        result = debug_flags.scan(str(tmp_project))
        assert len(result.findings) == 1
        assert result.findings[0].id == "DEBUG_FLAG"
        assert result.findings[0].severity == Severity.MEDIUM

    def test_detect_flask_debug(self, tmp_project: Path) -> None:
        cfg = tmp_project / "config.py"
        cfg.write_text("FLASK_DEBUG = 1\n")
        result = debug_flags.scan(str(tmp_project))
        # Matches both DEBUG=1 and FLASK_DEBUG=1 patterns
        assert len(result.findings) >= 1
        titles = [f.title for f in result.findings]
        assert any("Flask" in t for t in titles)

    def test_skip_test_directories(self, tmp_project: Path) -> None:
        test_dir = tmp_project / "tests"
        test_dir.mkdir()
        cfg = test_dir / "settings.py"
        cfg.write_text("DEBUG = True\n")
        result = debug_flags.scan(str(tmp_project))
        assert len(result.findings) == 0


class TestCheckGate:
    """Test gate checking logic."""

    def test_pass_no_findings(self) -> None:
        result = ScanResult()
        config = SecurityConfig._defaults()
        passed, messages = check_gate(result, "flow_finish", config)
        assert passed is True
        assert len(messages) == 0

    def test_block_on_critical(self) -> None:
        result = ScanResult(findings=[
            Finding(id="A", severity=Severity.CRITICAL, title="Critical issue"),
        ])
        config = SecurityConfig._defaults()
        passed, messages = check_gate(result, "flow_finish", config)
        assert passed is False
        assert any("BLOCKED" in m for m in messages)

    def test_warn_on_high(self) -> None:
        result = ScanResult(findings=[
            Finding(id="A", severity=Severity.HIGH, title="High issue"),
        ])
        config = SecurityConfig._defaults()
        passed, messages = check_gate(result, "flow_finish", config)
        assert passed is True
        assert any("WARNING" in m for m in messages)

    def test_deploy_gate_blocks_high(self) -> None:
        result = ScanResult(findings=[
            Finding(id="A", severity=Severity.HIGH, title="High issue"),
        ])
        config = SecurityConfig._defaults()
        passed, messages = check_gate(result, "flow_deploy", config)
        assert passed is False

    def test_unknown_gate(self) -> None:
        result = ScanResult(findings=[
            Finding(id="A", severity=Severity.CRITICAL, title="Critical"),
        ])
        config = SecurityConfig._defaults()
        passed, _ = check_gate(result, "nonexistent_gate", config)
        assert passed is True


class TestApplySuppressions:
    """Test suppression logic."""

    def test_suppress_finding(self) -> None:
        result = ScanResult(findings=[
            Finding(id="HARDCODED_SECRET", severity=Severity.HIGH, title="Secret", file_path="tests/test.py"),
            Finding(id="DEBUG_FLAG", severity=Severity.MEDIUM, title="Debug"),
        ])
        config = SecurityConfig(suppressions=[
            Suppression(id="HARDCODED_SECRET", path=r"tests/.*", reason="Test fixtures"),
        ])
        _apply_suppressions(result, config)
        assert len(result.findings) == 1
        assert result.findings[0].id == "DEBUG_FLAG"
        assert "suppressed" in result.passed[0]

    def test_no_suppressions(self) -> None:
        result = ScanResult(findings=[
            Finding(id="A", severity=Severity.HIGH, title="A"),
        ])
        config = SecurityConfig()
        _apply_suppressions(result, config)
        assert len(result.findings) == 1
