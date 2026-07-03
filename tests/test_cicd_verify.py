"""Tests for lib/cicd/verify.py - deploy verification (deploy-confidence).

Covers baseline capture/persistence, probe classification, verdict
aggregation (PROCEED / REVIEW / ROLLBACK), and the verify CLI subcommand.
Health and smoke runners are mocked so no real curl/subprocess/network runs.
"""

from __future__ import annotations

from unittest.mock import patch

from lib.cicd.config import CICDConfig, DeployVerificationConfig
from lib.cicd.models import (
    HealthCheckEntry,
    HealthCheckResult,
    SmokeTestEntry,
    SmokeTestResult,
)
from lib.cicd.verify import (
    CLASS_LATENCY,
    CLASS_NEW_FAILURE,
    CLASS_NEW_PROBE,
    CLASS_OK,
    CLASS_PREEXISTING,
    CLASS_RECOVERED,
    CLASS_REGRESSION,
    DeployVerifyResult,
    ProbeDiff,
    ProbeResult,
    Verdict,
    VerificationSnapshot,
    _classify,
    _decide,
    capture_snapshot,
    load_baseline,
    save_baseline,
    verify_deployment,
)


def _probe(name: str, kind: str, passed: bool, ms: float = 10.0) -> ProbeResult:
    return ProbeResult(name=name, kind=kind, passed=passed, elapsed_ms=ms)


def _diff(cls: str, base: bool | None, now: bool, name: str = "API", kind: str = "health") -> ProbeDiff:
    return ProbeDiff(
        name=name,
        kind=kind,
        classification=cls,
        baseline_passed=base,
        current_passed=now,
        baseline_ms=None if base is None else 10.0,
        current_ms=10.0,
    )


class TestProbeResult:
    def test_key(self) -> None:
        assert _probe("API", "health", True).key == "health:API"

    def test_roundtrip(self) -> None:
        p = ProbeResult(name="API", kind="health", passed=True, elapsed_ms=42.5, detail="HTTP 200")
        restored = ProbeResult.from_dict(p.to_dict())
        assert restored == p

    def test_from_dict_defaults(self) -> None:
        p = ProbeResult.from_dict({"name": "x"})
        assert p.kind == "" and p.passed is False and p.elapsed_ms == 0.0


class TestVerificationSnapshot:
    def test_counts(self) -> None:
        snap = VerificationSnapshot(
            probes=[_probe("a", "health", True), _probe("b", "smoke", False)]
        )
        assert snap.total == 2
        assert snap.passed == 1
        assert snap.failed == 1
        assert not snap.all_passed

    def test_all_passed_requires_probes(self) -> None:
        assert not VerificationSnapshot().all_passed
        assert VerificationSnapshot(probes=[_probe("a", "health", True)]).all_passed

    def test_by_key(self) -> None:
        snap = VerificationSnapshot(probes=[_probe("a", "health", True), _probe("a", "smoke", True)])
        keys = set(snap.by_key().keys())
        assert keys == {"health:a", "smoke:a"}

    def test_roundtrip(self) -> None:
        snap = VerificationSnapshot(
            probes=[_probe("a", "health", True, 5.0)], commit="abc123", captured_at="2026-07-03T00:00:00"
        )
        restored = VerificationSnapshot.from_dict(snap.to_dict())
        assert restored.commit == "abc123"
        assert restored.probes[0].name == "a"


class TestClassify:
    def setup_method(self) -> None:
        self.vconf = DeployVerificationConfig()

    def test_regression(self) -> None:
        cls, _ = _classify(_probe("a", "health", True), _probe("a", "health", False), self.vconf)
        assert cls == CLASS_REGRESSION

    def test_preexisting_failure(self) -> None:
        cls, _ = _classify(_probe("a", "health", False), _probe("a", "health", False), self.vconf)
        assert cls == CLASS_PREEXISTING

    def test_recovered(self) -> None:
        cls, _ = _classify(_probe("a", "health", False), _probe("a", "health", True), self.vconf)
        assert cls == CLASS_RECOVERED

    def test_ok(self) -> None:
        cls, _ = _classify(_probe("a", "health", True, 10.0), _probe("a", "health", True, 11.0), self.vconf)
        assert cls == CLASS_OK

    def test_new_probe(self) -> None:
        cls, _ = _classify(None, _probe("a", "health", True), self.vconf)
        assert cls == CLASS_NEW_PROBE

    def test_new_failure(self) -> None:
        cls, _ = _classify(None, _probe("a", "health", False), self.vconf)
        assert cls == CLASS_NEW_FAILURE

    def test_latency_regression(self) -> None:
        # 100ms baseline, 300ms now: +200% over the 50% threshold, above 100ms floor.
        cls, detail = _classify(_probe("a", "health", True, 100.0), _probe("a", "health", True, 300.0), self.vconf)
        assert cls == CLASS_LATENCY
        assert "+200%" in detail

    def test_latency_below_floor_is_ok(self) -> None:
        # 10ms -> 40ms is +300% but under the 100ms floor, so not flagged.
        cls, _ = _classify(_probe("a", "health", True, 10.0), _probe("a", "health", True, 40.0), self.vconf)
        assert cls == CLASS_OK

    def test_latency_ignored_when_configured(self) -> None:
        vconf = DeployVerificationConfig(on_latency_regression="ignore")
        cls, _ = _classify(_probe("a", "health", True, 100.0), _probe("a", "health", True, 500.0), vconf)
        assert cls == CLASS_OK

    def test_zero_baseline_ms_no_regression(self) -> None:
        cls, _ = _classify(_probe("a", "health", True, 0.0), _probe("a", "health", True, 500.0), self.vconf)
        assert cls == CLASS_OK


class TestDecide:
    def setup_method(self) -> None:
        self.vconf = DeployVerificationConfig()

    def _snap(self, *probes: ProbeResult) -> VerificationSnapshot:
        return VerificationSnapshot(probes=list(probes))

    def test_regression_rollback(self) -> None:
        diffs = [_diff(CLASS_REGRESSION, True, False)]
        verdict, reasons = _decide(diffs, self._snap(_probe("API", "health", False)), self._snap(), self.vconf)
        assert verdict is Verdict.ROLLBACK
        assert "regression" in reasons[0]

    def test_new_failure_rollback(self) -> None:
        diffs = [_diff(CLASS_NEW_FAILURE, None, False)]
        verdict, _ = _decide(diffs, self._snap(_probe("API", "health", False)), None, self.vconf)
        assert verdict is Verdict.ROLLBACK

    def test_all_ok_proceed(self) -> None:
        diffs = [_diff(CLASS_OK, True, True)]
        verdict, _ = _decide(diffs, self._snap(_probe("API", "health", True)), self._snap(), self.vconf)
        assert verdict is Verdict.PROCEED

    def test_recovered_proceed(self) -> None:
        diffs = [_diff(CLASS_RECOVERED, False, True)]
        verdict, reasons = _decide(diffs, self._snap(_probe("API", "health", True)), self._snap(), self.vconf)
        assert verdict is Verdict.PROCEED
        assert reasons and "recovered" in reasons[0]

    def test_latency_review_by_default(self) -> None:
        diffs = [_diff(CLASS_LATENCY, True, True)]
        verdict, _ = _decide(diffs, self._snap(_probe("API", "health", True)), self._snap(), self.vconf)
        assert verdict is Verdict.REVIEW

    def test_latency_rollback_when_configured(self) -> None:
        vconf = DeployVerificationConfig(on_latency_regression="rollback")
        diffs = [_diff(CLASS_LATENCY, True, True)]
        verdict, _ = _decide(diffs, self._snap(_probe("API", "health", True)), self._snap(), vconf)
        assert verdict is Verdict.ROLLBACK

    def test_preexisting_failure_review(self) -> None:
        diffs = [_diff(CLASS_PREEXISTING, False, False)]
        verdict, _ = _decide(diffs, self._snap(_probe("API", "health", False)), self._snap(), self.vconf)
        assert verdict is Verdict.REVIEW

    def test_no_probes_review(self) -> None:
        verdict, reasons = _decide([], self._snap(), None, self.vconf)
        assert verdict is Verdict.REVIEW
        assert "no health or smoke probes" in reasons[0]

    def test_require_baseline_downgrades_to_review(self) -> None:
        vconf = DeployVerificationConfig(require_baseline=True)
        diffs = [_diff(CLASS_NEW_PROBE, None, True)]
        verdict, reasons = _decide(diffs, self._snap(_probe("API", "health", True)), None, vconf)
        assert verdict is Verdict.REVIEW
        assert any("no baseline" in r for r in reasons)

    def test_regression_beats_latency(self) -> None:
        diffs = [_diff(CLASS_REGRESSION, True, False), _diff(CLASS_LATENCY, True, True, name="B")]
        verdict, _ = _decide(diffs, self._snap(_probe("API", "health", False)), self._snap(), self.vconf)
        assert verdict is Verdict.ROLLBACK


class TestDeployVerifyResult:
    def test_exit_code(self) -> None:
        snap = VerificationSnapshot(probes=[_probe("a", "health", True)])
        assert DeployVerifyResult(Verdict.ROLLBACK, [], [], snap).exit_code == 1
        assert DeployVerifyResult(Verdict.REVIEW, [], [], snap).exit_code == 0
        assert DeployVerifyResult(Verdict.PROCEED, [], [], snap).exit_code == 0

    def test_has_baseline(self) -> None:
        snap = VerificationSnapshot(probes=[_probe("a", "health", True)])
        assert not DeployVerifyResult(Verdict.PROCEED, [], [], snap, baseline=None).has_baseline
        assert DeployVerifyResult(Verdict.PROCEED, [], [], snap, baseline=snap).has_baseline

    def test_summary_line(self) -> None:
        snap = VerificationSnapshot(probes=[_probe("a", "health", True)])
        r = DeployVerifyResult(Verdict.ROLLBACK, ["1 regression probe: health:a"], [], snap)
        assert "ROLLBACK" in r.summary_line()
        assert "regression" in r.summary_line()

    def test_to_dict(self) -> None:
        snap = VerificationSnapshot(probes=[_probe("a", "health", True)])
        d = DeployVerifyResult(Verdict.PROCEED, [], [], snap, baseline=snap).to_dict()
        assert d["verdict"] == "proceed"
        assert d["exit_code"] == 0
        assert d["has_baseline"] is True


class TestBaselinePersistence:
    def test_roundtrip(self, tmp_path) -> None:
        config = CICDConfig()
        snap = VerificationSnapshot(probes=[_probe("API", "health", True, 42.0)], commit="deadbee")
        path = save_baseline(snap, config=config, project_root=str(tmp_path))
        assert path.exists()
        loaded = load_baseline(config=config, project_root=str(tmp_path))
        assert loaded is not None
        assert loaded.commit == "deadbee"
        assert loaded.probes[0].name == "API"

    def test_load_missing_returns_none(self, tmp_path) -> None:
        assert load_baseline(config=CICDConfig(), project_root=str(tmp_path)) is None

    def test_load_corrupt_returns_none(self, tmp_path) -> None:
        baseline = tmp_path / ".claude" / "deploy-baseline.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_text("{ not valid json ]")
        assert load_baseline(config=CICDConfig(), project_root=str(tmp_path)) is None

    def test_custom_baseline_file(self, tmp_path) -> None:
        config = CICDConfig()
        config.health.deploy_verification.baseline_file = ".claude/custom-baseline.json"
        snap = VerificationSnapshot(probes=[_probe("a", "health", True)])
        path = save_baseline(snap, config=config, project_root=str(tmp_path))
        assert path.name == "custom-baseline.json"


class TestCaptureSnapshot:
    @patch("lib.cicd.verify._git_commit", return_value="abc123")
    @patch("lib.cicd.verify.run_smoke_tests")
    @patch("lib.cicd.verify.run_health_checks")
    def test_normalizes_probes(self, mock_health, mock_smoke, _mock_git) -> None:
        mock_health.return_value = HealthCheckResult(
            checks=[HealthCheckEntry(name="API", kind="endpoint", passed=True, detail="HTTP 200", elapsed_ms=5.0)]
        )
        mock_smoke.return_value = SmokeTestResult(
            tests=[SmokeTestEntry(name="CLI", command="x --version", passed=False, detail="exit 1", elapsed_ms=8.0)]
        )
        snap = capture_snapshot(config=CICDConfig())
        assert snap.commit == "abc123"
        assert len(snap.probes) == 2
        health_probe = snap.by_key()["health:API"]
        smoke_probe = snap.by_key()["smoke:CLI"]
        assert health_probe.kind == "health" and health_probe.passed
        assert smoke_probe.kind == "smoke" and not smoke_probe.passed


class TestVerifyDeploymentIntegration:
    @patch("lib.cicd.verify._git_commit", return_value="")
    @patch("lib.cicd.verify.run_smoke_tests")
    @patch("lib.cicd.verify.run_health_checks")
    def test_regression_against_baseline(self, mock_health, mock_smoke, _git) -> None:
        mock_health.return_value = HealthCheckResult(
            checks=[HealthCheckEntry(name="API", kind="endpoint", passed=False, detail="HTTP 500", elapsed_ms=5.0)]
        )
        mock_smoke.return_value = SmokeTestResult()

        baseline = VerificationSnapshot(probes=[_probe("API", "health", True, 5.0)])
        result = verify_deployment(config=CICDConfig(), baseline=baseline)
        assert result.verdict is Verdict.ROLLBACK
        assert result.exit_code == 1
        assert result.diffs[0].classification == CLASS_REGRESSION

    @patch("lib.cicd.verify._git_commit", return_value="")
    @patch("lib.cicd.verify.run_smoke_tests")
    @patch("lib.cicd.verify.run_health_checks")
    def test_proceed_against_baseline(self, mock_health, mock_smoke, _git) -> None:
        mock_health.return_value = HealthCheckResult(
            checks=[HealthCheckEntry(name="API", kind="endpoint", passed=True, detail="HTTP 200", elapsed_ms=5.0)]
        )
        mock_smoke.return_value = SmokeTestResult()
        baseline = VerificationSnapshot(probes=[_probe("API", "health", True, 5.0)])
        result = verify_deployment(config=CICDConfig(), baseline=baseline)
        assert result.verdict is Verdict.PROCEED
        assert result.exit_code == 0

    @patch("lib.cicd.verify._git_commit", return_value="")
    @patch("lib.cicd.verify.run_smoke_tests")
    @patch("lib.cicd.verify.run_health_checks")
    def test_no_probes_reviews(self, mock_health, mock_smoke, _git) -> None:
        mock_health.return_value = HealthCheckResult()
        mock_smoke.return_value = SmokeTestResult()
        result = verify_deployment(config=CICDConfig())
        assert result.verdict is Verdict.REVIEW
        assert result.exit_code == 0


class TestConfig:
    def test_defaults(self) -> None:
        vconf = DeployVerificationConfig()
        assert vconf.enabled is False
        assert vconf.baseline_file == ".claude/deploy-baseline.json"
        assert vconf.latency_regression_pct == 50.0
        assert vconf.on_latency_regression == "review"

    def test_health_has_deploy_verification(self) -> None:
        config = CICDConfig()
        assert isinstance(config.health.deploy_verification, DeployVerificationConfig)

    def test_loads_from_yaml(self, tmp_path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "cicd.yml").write_text(
            "health:\n"
            "  deploy_verification:\n"
            "    enabled: true\n"
            "    on_latency_regression: rollback\n"
        )
        config = CICDConfig.load(str(tmp_path))
        assert config.health.deploy_verification.enabled is True
        assert config.health.deploy_verification.on_latency_regression == "rollback"


class TestVerifyCLI:
    def test_baseline_capture_and_verify(self, tmp_path, capsys) -> None:
        from lib.cicd.cli import main

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "cicd.yml").write_text(
            "health:\n"
            "  smoke_tests:\n"
            "    - name: ok\n"
            '      command: "true"\n'
            "      expected_exit: 0\n"
        )
        # Capture baseline
        rc = main(["verify", "--baseline", "--summary", "--path", str(tmp_path)])
        assert rc == 0
        assert (claude_dir / "deploy-baseline.json").exists()
        capsys.readouterr()
        # Verify -> PROCEED
        rc = main(["verify", "--summary", "--path", str(tmp_path)])
        assert rc == 0
        assert "PROCEED" in capsys.readouterr().out

    def test_verify_json_rollback_exit(self, tmp_path, capsys) -> None:
        import json as _json

        from lib.cicd.cli import main

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "cicd.yml").write_text(
            "health:\n"
            "  smoke_tests:\n"
            "    - name: ok\n"
            '      command: "true"\n'
            "      expected_exit: 0\n"
        )
        main(["verify", "--baseline", "--path", str(tmp_path)])
        capsys.readouterr()
        # Break the probe, then verify as JSON.
        (claude_dir / "cicd.yml").write_text(
            "health:\n"
            "  smoke_tests:\n"
            "    - name: ok\n"
            '      command: "false"\n'
            "      expected_exit: 0\n"
        )
        rc = main(["verify", "--json", "--path", str(tmp_path)])
        assert rc == 1
        payload = _json.loads(capsys.readouterr().out)
        assert payload["verdict"] == "rollback"
        assert payload["exit_code"] == 1
