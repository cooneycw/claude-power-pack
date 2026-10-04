"""Deploy verification (deploy-confidence) for CI/CD & Verification.

Validates the *deployment*, not just the code: capture a pre-deploy baseline
of health checks and smoke tests, re-run them after deploy, diff the two, and
emit one actionable verdict - PROCEED, REVIEW, or ROLLBACK.

The novel piece here is the baseline comparison. Raw health/smoke runs already
exist (lib.cicd.health, lib.cicd.smoke); this module composes them into a
regression check so a deploy that makes things *worse* than 60 seconds ago is
caught, not just a deploy whose code passed tests.

Reuses run_health_checks / run_smoke_tests - no new dependencies (curl +
subprocess, matching health.py). Baseline snapshots persist to
.claude/deploy-baseline.json (per-workstation runtime state, like .claude/runs/).
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .config import CICDConfig, DeployVerificationConfig
from .health import run_health_checks
from .smoke import run_smoke_tests


class Verdict(str, Enum):
    """Actionable deploy-confidence verdict."""

    PROCEED = "proceed"
    REVIEW = "review"
    ROLLBACK = "rollback"


# Probe classifications, ordered roughly by severity.
CLASS_REGRESSION = "regression"  # passed in baseline, fails now -> ROLLBACK
CLASS_NEW_FAILURE = "new_failure"  # failing now, no known-good baseline -> ROLLBACK
CLASS_PREEXISTING = "preexisting_failure"  # failing before and after -> REVIEW
CLASS_LATENCY = "latency_regression"  # passing but markedly slower -> REVIEW/ROLLBACK
CLASS_RECOVERED = "recovered"  # was failing, passes now -> ok
CLASS_NEW_PROBE = "new_probe"  # passing, not in baseline -> ok
CLASS_OK = "ok"  # passing before and after -> ok


@dataclass
class ProbeResult:
    """A single normalized probe (health check or smoke test) outcome."""

    name: str
    kind: str  # "health" | "smoke"
    passed: bool
    elapsed_ms: float = 0.0
    detail: str = ""

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "passed": self.passed,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProbeResult:
        return cls(
            name=str(data["name"]),
            kind=str(data.get("kind", "")),
            passed=bool(data.get("passed", False)),
            elapsed_ms=float(data.get("elapsed_ms", 0.0)),
            detail=str(data.get("detail", "")),
        )


@dataclass
class VerificationSnapshot:
    """A point-in-time capture of all health + smoke probes."""

    probes: list[ProbeResult] = field(default_factory=list)
    commit: str = ""
    captured_at: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for p in self.probes if p.passed)

    @property
    def failed(self) -> int:
        return sum(1 for p in self.probes if not p.passed)

    @property
    def total(self) -> int:
        return len(self.probes)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.failed == 0

    def by_key(self) -> dict[str, ProbeResult]:
        return {p.key: p for p in self.probes}

    def to_dict(self) -> dict[str, Any]:
        return {
            "probes": [p.to_dict() for p in self.probes],
            "commit": self.commit,
            "captured_at": self.captured_at,
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationSnapshot:
        return cls(
            probes=[ProbeResult.from_dict(p) for p in data.get("probes", [])],
            commit=str(data.get("commit", "")),
            captured_at=str(data.get("captured_at", "")),
        )


@dataclass
class ProbeDiff:
    """The before/after comparison of a single probe."""

    name: str
    kind: str
    classification: str
    baseline_passed: Optional[bool]
    current_passed: bool
    baseline_ms: Optional[float]
    current_ms: float
    detail: str = ""

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "classification": self.classification,
            "baseline_passed": self.baseline_passed,
            "current_passed": self.current_passed,
            "baseline_ms": None if self.baseline_ms is None else round(self.baseline_ms, 1),
            "current_ms": round(self.current_ms, 1),
            "detail": self.detail,
        }


@dataclass
class DeployVerifyResult:
    """Aggregated verification outcome with an actionable verdict."""

    verdict: Verdict
    reasons: list[str]
    diffs: list[ProbeDiff]
    snapshot: VerificationSnapshot
    baseline: Optional[VerificationSnapshot] = None

    @property
    def has_baseline(self) -> bool:
        return self.baseline is not None

    @property
    def exit_code(self) -> int:
        """1 for ROLLBACK (actionable stop), 0 for PROCEED/REVIEW (advisory)."""
        return 1 if self.verdict is Verdict.ROLLBACK else 0

    def diffs_by_class(self, classification: str) -> list[ProbeDiff]:
        return [d for d in self.diffs if d.classification == classification]

    def summary_line(self) -> str:
        base = f"Deploy verdict: {self.verdict.value.upper()}"
        if self.reasons:
            return f"{base} - {self.reasons[0]}"
        if self.snapshot.total == 0:
            return f"{base} - no probes configured"
        return f"{base} - {self.snapshot.passed}/{self.snapshot.total} probes passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "exit_code": self.exit_code,
            "has_baseline": self.has_baseline,
            "reasons": self.reasons,
            "diffs": [d.to_dict() for d in self.diffs],
            "snapshot": self.snapshot.to_dict(),
            "baseline": self.baseline.to_dict() if self.baseline else None,
        }


# --------------------------------------------------------------------------- #
# Capture / persistence
# --------------------------------------------------------------------------- #


def capture_snapshot(
    config: Optional[CICDConfig] = None,
    project_root: Optional[str] = None,
) -> VerificationSnapshot:
    """Run all health checks and smoke tests and normalize them into a snapshot."""
    if config is None:
        config = CICDConfig.load(project_root)

    probes: list[ProbeResult] = []

    health = run_health_checks(config=config, project_root=project_root)
    for check in health.checks:
        probes.append(
            ProbeResult(
                name=check.name,
                kind="health",
                passed=check.passed,
                elapsed_ms=check.elapsed_ms,
                detail=check.detail,
            )
        )

    smoke = run_smoke_tests(config=config, project_root=project_root)
    for test in smoke.tests:
        probes.append(
            ProbeResult(
                name=test.name,
                kind="smoke",
                passed=test.passed,
                elapsed_ms=test.elapsed_ms,
                detail=test.detail,
            )
        )

    return VerificationSnapshot(
        probes=probes,
        commit=_git_commit(project_root),
        captured_at=_now(),
    )


def _baseline_path(config: Optional[CICDConfig], project_root: Optional[str]) -> Path:
    root = Path(project_root) if project_root else Path(".")
    vconf = config.health.deploy_verification if config else DeployVerificationConfig()
    return root / vconf.baseline_file


def save_baseline(
    snapshot: VerificationSnapshot,
    config: Optional[CICDConfig] = None,
    project_root: Optional[str] = None,
) -> Path:
    """Persist a snapshot as the pre-deploy baseline."""
    path = _baseline_path(config, project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.to_dict(), indent=2))
    return path


def load_baseline(
    config: Optional[CICDConfig] = None,
    project_root: Optional[str] = None,
) -> Optional[VerificationSnapshot]:
    """Load the pre-deploy baseline, or None if absent/unreadable (fail-open)."""
    path = _baseline_path(config, project_root)
    if not path.exists():
        return None
    try:
        return VerificationSnapshot.from_dict(json.loads(path.read_text()))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
        return None


# --------------------------------------------------------------------------- #
# Diff / verdict
# --------------------------------------------------------------------------- #


def _classify(
    baseline: Optional[ProbeResult],
    current: ProbeResult,
    vconf: DeployVerificationConfig,
) -> tuple[str, str]:
    """Classify a single probe's before/after state. Returns (class, detail)."""
    if baseline is None:
        if current.passed:
            return CLASS_NEW_PROBE, "not in baseline (passing)"
        return CLASS_NEW_FAILURE, current.detail or "failing, no baseline to compare"

    if baseline.passed and not current.passed:
        return CLASS_REGRESSION, current.detail or "passed in baseline, fails now"

    if not baseline.passed and not current.passed:
        return CLASS_PREEXISTING, current.detail or "was already failing before deploy"

    if not baseline.passed and current.passed:
        return CLASS_RECOVERED, "was failing in baseline, passes now"

    # Both passed - check for a latency regression.
    if vconf.on_latency_regression != "ignore" and _is_latency_regression(baseline, current, vconf):
        pct = ((current.elapsed_ms - baseline.elapsed_ms) / baseline.elapsed_ms) * 100
        return (
            CLASS_LATENCY,
            f"{current.elapsed_ms:.0f}ms vs baseline {baseline.elapsed_ms:.0f}ms (+{pct:.0f}%)",
        )

    return CLASS_OK, "ok"


def _is_latency_regression(
    baseline: ProbeResult,
    current: ProbeResult,
    vconf: DeployVerificationConfig,
) -> bool:
    if baseline.elapsed_ms <= 0:
        return False
    if current.elapsed_ms < vconf.latency_floor_ms:
        return False
    threshold = baseline.elapsed_ms * (1 + vconf.latency_regression_pct / 100.0)
    return current.elapsed_ms > threshold


def verify_deployment(
    config: Optional[CICDConfig] = None,
    project_root: Optional[str] = None,
    baseline: Optional[VerificationSnapshot] = None,
) -> DeployVerifyResult:
    """Run post-deploy probes, diff against the baseline, and compute a verdict.

    Args:
        config: CI/CD config (loaded from project_root if None).
        project_root: Project root for config + baseline loading.
        baseline: Explicit baseline (loaded from disk if None).
    """
    if config is None:
        config = CICDConfig.load(project_root)
    vconf = config.health.deploy_verification

    current = capture_snapshot(config=config, project_root=project_root)
    if baseline is None:
        baseline = load_baseline(config=config, project_root=project_root)

    base_by_key = baseline.by_key() if baseline else {}

    diffs: list[ProbeDiff] = []
    for probe in current.probes:
        prior = base_by_key.get(probe.key)
        classification, detail = _classify(prior, probe, vconf)
        diffs.append(
            ProbeDiff(
                name=probe.name,
                kind=probe.kind,
                classification=classification,
                baseline_passed=None if prior is None else prior.passed,
                current_passed=probe.passed,
                baseline_ms=None if prior is None else prior.elapsed_ms,
                current_ms=probe.elapsed_ms,
                detail=detail,
            )
        )

    verdict, reasons = _decide(diffs, current, baseline, vconf)
    return DeployVerifyResult(
        verdict=verdict,
        reasons=reasons,
        diffs=diffs,
        snapshot=current,
        baseline=baseline,
    )


def _decide(
    diffs: list[ProbeDiff],
    current: VerificationSnapshot,
    baseline: Optional[VerificationSnapshot],
    vconf: DeployVerificationConfig,
) -> tuple[Verdict, list[str]]:
    """Aggregate probe classifications into a verdict + human-readable reasons."""
    regressions = [d for d in diffs if d.classification == CLASS_REGRESSION]
    new_failures = [d for d in diffs if d.classification == CLASS_NEW_FAILURE]
    latency = [d for d in diffs if d.classification == CLASS_LATENCY]
    preexisting = [d for d in diffs if d.classification == CLASS_PREEXISTING]
    recovered = [d for d in diffs if d.classification == CLASS_RECOVERED]

    reasons: list[str] = []

    # Nothing to verify - be honest, do not claim PROCEED.
    if current.total == 0:
        return Verdict.REVIEW, [
            "no health or smoke probes configured - cannot verify the deployment"
        ]

    # ROLLBACK: a real, current failure caused by (or coincident with) this deploy.
    if regressions:
        reasons.append(_names_reason("regression", regressions))
    if new_failures:
        reasons.append(_names_reason("failing (no baseline)", new_failures))
    if vconf.on_latency_regression == "rollback" and latency:
        reasons.append(_names_reason("latency regression", latency))
    if reasons:
        return Verdict.ROLLBACK, reasons

    # REVIEW: soft signals worth a human look, but not a clear rollback trigger.
    if latency:
        reasons.append(_names_reason("latency regression", latency))
    if preexisting:
        reasons.append(_names_reason("still failing since before deploy", preexisting))
    if not baseline and vconf.require_baseline:
        reasons.append("no baseline captured - deployed without a comparison point")
    if reasons:
        return Verdict.REVIEW, reasons

    # PROCEED: everything green (optionally after recovering from a broken baseline).
    if recovered:
        reasons.append(_names_reason("recovered since baseline", recovered))
    return Verdict.PROCEED, reasons


def _names_reason(label: str, diffs: list[ProbeDiff]) -> str:
    names = ", ".join(d.key for d in diffs)
    noun = "probe" if len(diffs) == 1 else "probes"
    return f"{len(diffs)} {label} {noun}: {names}"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _git_commit(project_root: Optional[str]) -> str:
    """Short HEAD commit, or '' if git is unavailable (fail-open)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root or None,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _now() -> str:
    """ISO timestamp (local), matching state.py."""
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
