"""Tests for security scanner modules and orchestrator."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from lib.security import cli
from lib.security.config import SecurityConfig
from lib.security.models import Finding, ScanResult, Severity, Suppression
from lib.security.modules import debug_flags, gitignore, permissions, secrets
from lib.security.orchestrator import _apply_suppressions, check_gate

# CPP's Woodpecker `validate` step runs in a container without git, so tests
# that drive a real git repo must skip there (issue #430 pattern).
requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available in this environment"
)


def _git(cwd: Path, *args: str) -> None:
    """Run a git command in cwd (test helper for building fixture repos)."""
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


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

    @requires_git
    def test_skip_gitignored_file(self, tmp_path: Path) -> None:
        # A secret in a gitignored, untracked file must NOT be flagged: it is
        # never committable, so flagging it is a false positive on the gate
        # (issue #470 - recurred on /flow:auto #441 and #461).
        _git(tmp_path, "init")
        (tmp_path / ".gitignore").write_text(".claude/settings.local.json\n")
        settings = tmp_path / ".claude" / "settings.local.json"
        settings.parent.mkdir(parents=True)
        settings.write_text('{"key": "AKIAIOSFODNN7EXAMPLE"}\n')
        result = secrets.scan(str(tmp_path))
        assert len(result.findings) == 0

    @requires_git
    def test_tracked_secret_still_detected(self, tmp_path: Path) -> None:
        # Regression guard: a secret in a git-tracked file still fails the gate,
        # even when that file also matches a .gitignore pattern (check-ignore is
        # index-aware, so tracked paths are never treated as ignored).
        _git(tmp_path, "init")
        (tmp_path / ".gitignore").write_text("*.local.json\n")
        tracked = tmp_path / "config.local.json"
        tracked.write_text('{"key": "AKIAIOSFODNN7EXAMPLE"}\n')
        _git(tmp_path, "add", "-f", "config.local.json")
        result = secrets.scan(str(tmp_path))
        aws_findings = [f for f in result.findings if f.id == "AWS_ACCESS_KEY"]
        assert len(aws_findings) == 1

    def test_outside_git_repo_unchanged(self, tmp_path: Path) -> None:
        # Fail-open: with no git repo, a gitignore file has no effect and the
        # scanner behaves exactly as before (the secret is still flagged).
        (tmp_path / ".gitignore").write_text("*.local.json\n")
        src = tmp_path / "config.local.json"
        src.write_text('{"key": "AKIAIOSFODNN7EXAMPLE"}\n')
        result = secrets.scan(str(tmp_path))
        aws_findings = [f for f in result.findings if f.id == "AWS_ACCESS_KEY"]
        assert len(aws_findings) == 1


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

    def test_findings_carry_their_location(self) -> None:
        """A gate message must say WHERE (kyle issue #838).

        The gate emitted five HIGH "Hardcoded password in source code" lines
        with no file, no line and no id, which cannot be triaged: a reader
        cannot separate a real finding from a known-ignorable one without
        re-deriving the whole scan. The location was never missing - `Finding`
        carries `file_path` and `line_number` and exposes `location`, and the
        secrets scanner populates both - it was discarded when the message was
        built.

        Consequence of leaving it: a genuine HIGH arrives in a list of five
        indistinguishable ones, and the only way to spot it is to already know
        which five to ignore. That is alert fatigue with a mechanism, on a
        security gate.
        """
        result = ScanResult(findings=[
            Finding(
                id="HARDCODED_PASSWORD",
                severity=Severity.HIGH,
                title="Hardcoded password in source code",
                file_path="config/settings.py",
                line_number=372,
            ),
        ])
        config = SecurityConfig._defaults()

        passed, messages = check_gate(result, "flow_finish", config)

        assert passed is True
        assert len(messages) == 1
        assert "config/settings.py:372" in messages[0]
        assert "HARDCODED_PASSWORD" in messages[0]

    def test_a_finding_without_a_location_still_reads_cleanly(self) -> None:
        """`location` is empty for a finding with no file - a scanner that
        reports a project-wide condition. The message must not grow a dangling
        separator or an empty pair of brackets for it."""
        result = ScanResult(findings=[
            Finding(id="NO_GITIGNORE", severity=Severity.HIGH, title="No .gitignore"),
        ])
        config = SecurityConfig._defaults()

        _, messages = check_gate(result, "flow_finish", config)

        assert messages == [
            "WARNING: \U0001f7e1 HIGH: No .gitignore [NO_GITIGNORE]"
        ]

    def test_the_matched_text_is_never_printed(self) -> None:
        """Locations yes, secrets no (kyle issue #838).

        `raw_match` may BE the secret - the model carries `mask_secret` for
        exactly that reason - and gate messages land in shared logs, PR bodies
        and terminal scrollback. Untriageable-but-safe beats triageable-and-
        leaked, and the location alone is enough to go and look.
        """
        result = ScanResult(findings=[
            Finding(
                id="HARDCODED_PASSWORD",
                severity=Severity.HIGH,
                title="Hardcoded password in source code",
                file_path="app/config.py",
                line_number=9,
                raw_match='password = "hunter2-actual-secret"',
            ),
        ])
        config = SecurityConfig._defaults()

        _, messages = check_gate(result, "flow_finish", config)

        assert "hunter2-actual-secret" not in messages[0]
        assert "app/config.py:9" in messages[0]

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


class TestCmdGate:
    """`python -m lib.security gate` must print a verdict on EVERY exit path
    (issue #1027 - the same class as flow-finish-gate's ok/warn/skipped
    confusion, one repo layer down).

    Before this: a PASSING gate with WARN-level findings printed nothing but
    the WARNING lines themselves - no verdict, no threshold, no counts. A
    measured example from the issue: 22 lines, every one `WARNING: HIGH: ...`,
    and `... | tail -20` rendered it indistinguishable from a gate one line
    short of a real failure. `cmd_gate` always re-scans `args.path` from disk
    (it has no way to accept a pre-built `ScanResult`), so these monkeypatch
    `scan_quick` at the CLI module boundary rather than driving real scanners.
    """

    @staticmethod
    def _args(gate_name: str = "flow_finish", path: str = ".") -> argparse.Namespace:
        return argparse.Namespace(gate_name=gate_name, path=path)

    def test_passing_gate_with_warnings_prints_verdict_threshold_and_counts(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = ScanResult(findings=[
            Finding(id="A", severity=Severity.HIGH, title="High issue"),
        ])
        monkeypatch.setattr(cli, "scan_quick", lambda path, config: result)

        exit_code = cli.cmd_gate(self._args())

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "WARNING" in out
        assert "SECURITY_GATE: flow_finish PASS (blocked=0 warned=1;" in out
        assert "blocks-on=CRITICAL warns-on=HIGH" in out

    def test_failing_gate_prints_verdict_too(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = ScanResult(findings=[
            Finding(id="A", severity=Severity.CRITICAL, title="Critical issue"),
        ])
        monkeypatch.setattr(cli, "scan_quick", lambda path, config: result)

        exit_code = cli.cmd_gate(self._args())

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "SECURITY_GATE: flow_finish FAIL (blocked=1 warned=0;" in out
        assert "FAILED" in out

    def test_clean_gate_prints_the_verdict_line_too(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A gate with NOTHING to report must still print the summary line -
        the pre-fix code only did this by coincidence, when `messages` was
        empty; this asserts it as its own property so it cannot regress
        independently of the warnings case above."""
        monkeypatch.setattr(cli, "scan_quick", lambda path, config: ScanResult())

        exit_code = cli.cmd_gate(self._args())

        out = capsys.readouterr().out
        assert exit_code == 0
        assert "SECURITY_GATE: flow_finish PASS (blocked=0 warned=0;" in out


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


class TestGateLineCarriesCoverage:
    """The gate line must say what the scan EXAMINED, not only what it found.

    `blocked=0 warned=0` is what a clean scan of 575 files reports AND what a
    scan that opened nothing reports - the same line for opposite facts. That is
    the #1027 shape at the security layer: a verdict whose passing and no-op
    renderings are byte-identical.

    Measured before this was written: on a tree with no source files and an
    otherwise-clean policy, the gate printed
    `SECURITY_GATE: flow_finish PASS (blocked=0 warned=0; ...)` and exited 0.
    """

    @staticmethod
    def _args(gate_name: str = "flow_finish", path: str = ".") -> argparse.Namespace:
        return argparse.Namespace(gate_name=gate_name, path=path)

    def test_a_scan_that_examined_nothing_says_so(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = ScanResult(skipped=["No source files found to scan"])
        result.units_scanned = 0
        monkeypatch.setattr(cli, "scan_quick", lambda path, config: result)

        exit_code = cli.cmd_gate(self._args())

        out = capsys.readouterr().out
        assert exit_code == 0, "the gate PASSES - that is exactly the false green"
        assert "secrets-scanned=0" in out

    def test_a_real_scan_reports_its_count(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other half: a covered scan must NOT look like an empty one."""
        result = ScanResult(passed=["No secrets found in 575 source files"])
        result.units_scanned = 575
        monkeypatch.setattr(cli, "scan_quick", lambda path, config: result)

        cli.cmd_gate(self._args())

        out = capsys.readouterr().out
        assert "secrets-scanned=575" in out
        assert "secrets-scanned=0" not in out

    def test_an_unstated_count_is_unknown_not_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`units_scanned=None` must not render as a zero nobody measured.

        A fabricated 0 here would manufacture a zero-coverage warning in the
        runner one layer up, on a scan that simply did not report.
        """
        monkeypatch.setattr(cli, "scan_quick", lambda path, config: ScanResult())

        cli.cmd_gate(self._args())

        out = capsys.readouterr().out
        assert "secrets-scanned=unknown" in out

    def test_merge_preserves_unknown_and_sums_numbers(self) -> None:
        """Two modules stating nothing must not add up to a confident 0."""
        both_silent = ScanResult()
        both_silent.merge(ScanResult())
        assert both_silent.units_scanned is None

        one_counts = ScanResult()
        other = ScanResult()
        other.units_scanned = 7
        one_counts.merge(other)
        assert one_counts.units_scanned == 7

        summed = ScanResult()
        summed.units_scanned = 3
        addend = ScanResult()
        addend.units_scanned = 4
        summed.merge(addend)
        assert summed.units_scanned == 7


class TestUnreadableFilesAreNotCountedAsExamined:
    """A file the scanner could not open was NOT examined (#1027 review).

    `files_scanned` incremented above the `try`, so an unreadable file still
    counted. Harmless while the number was only prose; once it became the
    exported coverage figure, one unreadable file reported `secrets-scanned=1`
    for a scan that inspected no content - the same looked-vs-nothing-to-look-at
    collapse the field exists to prevent, reintroduced inside its own fix.
    """

    def test_an_unreadable_file_yields_zero_coverage(self, tmp_path: Path) -> None:
        target = tmp_path / "unreadable.py"
        target.write_text("api_key = 'placeholder'\n")
        target.chmod(0o000)
        try:
            if os.access(target, os.R_OK):
                pytest.skip("cannot make a file unreadable here (running as root?)")
            result = secrets.scan(str(tmp_path))
        finally:
            target.chmod(0o644)

        assert result.units_scanned == 0, (
            "a file that could not be opened was not examined"
        )
        assert any("could not be read" in m for m in result.skipped), result.skipped

    def test_a_readable_file_is_counted(self, tmp_path: Path) -> None:
        """The other half - the count must not become uniformly zero."""
        (tmp_path / "ok.py").write_text("x = 1\n")
        result = secrets.scan(str(tmp_path))
        assert result.units_scanned == 1
