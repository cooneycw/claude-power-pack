"""Behavioral tests for the /flow:wave residual ledger (issue #719)."""

from __future__ import annotations

import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-wave-residuals.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("flow_wave_residuals", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["flow_wave_residuals"] = module
    spec.loader.exec_module(module)
    return module


MOD = _load_module()
WAVE = "test-wave"


def _ledger_path(tmp_path: Path, wave: str = WAVE) -> Path:
    return tmp_path / "cc-flow-wave" / wave / "residuals.json"


def _record(
    path: Path,
    classification: str,
    *,
    source_issue: int,
    generation: int = 1,
    consequence: str = "Users see incorrect behavior",
    evidence: str = "Reproduced with the named fixture",
    dedupe_of: str | None = None,
    source_links: list[str] | None = None,
) -> dict:
    return MOD.record_candidate(
        path,
        wave=WAVE,
        root_issue=719,
        source_issue=source_issue,
        classification=classification,
        consequence=consequence,
        evidence=evidence,
        generation=generation,
        dedupe_of=dedupe_of,
        source_links=source_links,
        now=f"2026-08-16T12:{source_issue % 60:02d}:00+00:00",
    )


def _candidate(ledger: dict, candidate_id: str) -> dict:
    return next(item for item in ledger["candidates"] if item["candidate_id"] == candidate_id)


class TestClassification:
    @pytest.mark.parametrize(
        ("classification", "disposition"),
        [
            ("current-issue-failure", "fix-before-close"),
            ("active-pr-defect", "fix-current-pr"),
            ("pre-existing-oos", "eligible"),
            ("emergency", "eligible-emergency"),
            ("speculative", "ledger-only"),
        ],
    )
    def test_disposition_is_derived(self, tmp_path: Path, classification: str, disposition: str) -> None:
        candidate = _record(_ledger_path(tmp_path), classification, source_issue=10)
        assert candidate["classification"] == classification
        assert candidate["disposition"] == disposition
        assert candidate["dedupe_of"] is None

    def test_unknown_classification_is_rejected(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        with pytest.raises(MOD.ValidationError, match="unknown classification"):
            _record(path, "wishlist", source_issue=10)

    def test_duplicate_requires_an_existing_canonical_candidate(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        _record(path, "speculative", source_issue=10)
        ledger = MOD.read_ledger(path, WAVE)
        assert not any(item["candidate_id"] == "candidate-999999" for item in ledger["candidates"])
        with pytest.raises(MOD.ValidationError, match="names no canonical candidate"):
            _record(
                path,
                "duplicate",
                source_issue=11,
                dedupe_of="candidate-999999",
            )


class TestDuplicateMerging:
    def test_duplicate_merges_evidence_and_all_sources_without_a_sibling_candidate(
        self, tmp_path: Path
    ) -> None:
        path = _ledger_path(tmp_path)
        canonical = _record(
            path,
            "pre-existing-oos",
            source_issue=20,
            consequence="First consequence",
            evidence="First reproduction",
            source_links=["https://example.test/review/20"],
        )
        duplicate = _record(
            path,
            "duplicate",
            source_issue=21,
            consequence="Second consequence",
            evidence="Second reproduction",
            dedupe_of=canonical["candidate_id"],
            source_links=["https://example.test/review/21", "https://example.test/log/21"],
        )

        ledger = MOD.read_ledger(path, WAVE)
        merged = _candidate(ledger, canonical["candidate_id"])
        assert len(ledger["candidates"]) == 1
        assert len(ledger["duplicate_links"]) == 1
        assert duplicate["disposition"] == "duplicate"
        assert duplicate["canonical_candidate_id"] == canonical["candidate_id"]
        assert merged["source_issues"] == [20, 21]
        assert merged["source_links"] == [
            "https://example.test/review/20",
            "https://example.test/review/21",
            "https://example.test/log/21",
        ]
        assert "First reproduction" in merged["evidence"]
        assert "Second reproduction" in merged["evidence"]
        assert len(merged["evidence_entries"]) == 2

    def test_duplicate_link_cannot_be_promoted(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        canonical = _record(path, "pre-existing-oos", source_issue=20)
        duplicate = _record(
            path,
            "duplicate",
            source_issue=21,
            dedupe_of=canonical["candidate_id"],
        )
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")

        ledger = MOD.read_ledger(path, WAVE)
        stored_duplicate = next(
            item for item in ledger["duplicate_links"] if item["candidate_id"] == duplicate["candidate_id"]
        )
        assert stored_duplicate["disposition"] == "duplicate"
        assert stored_duplicate["dedupe_of"] == canonical["candidate_id"]
        with pytest.raises(MOD.PolicyError, match="is a duplicate"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=duplicate["candidate_id"],
                approved_by="release-manager",
            )


class TestPromotionPolicy:
    def test_open_wave_refuses_promotion(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        eligible = _record(path, "pre-existing-oos", source_issue=30)

        ledger = MOD.read_ledger(path, WAVE)
        stored = _candidate(ledger, eligible["candidate_id"])
        assert ledger["state"] == "active"
        assert stored["promotion"] is None
        with pytest.raises(MOD.PolicyError, match="wave is active"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=eligible["candidate_id"],
                approved_by="release-manager",
            )

    def test_active_pr_defect_routes_back_to_current_pr(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        defect = _record(path, "active-pr-defect", source_issue=31)
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")

        stored = _candidate(MOD.read_ledger(path, WAVE), defect["candidate_id"])
        assert stored["disposition"] == "fix-current-pr"
        assert stored["promotion"] is None
        with pytest.raises(MOD.PolicyError, match="never promotable"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=defect["candidate_id"],
                approved_by="release-manager",
            )

    def test_generation_two_emergency_needs_explicit_override(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        emergency = _record(path, "emergency", source_issue=32, generation=2)
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")

        stored = _candidate(MOD.read_ledger(path, WAVE), emergency["candidate_id"])
        assert stored["generation"] >= 2
        assert stored["disposition"] == "eligible-emergency"
        assert stored["promotion"] is None
        with pytest.raises(MOD.PolicyError, match="emergency candidates require"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=emergency["candidate_id"],
                approved_by="security-lead",
            )

    def test_generation_two_emergency_can_be_human_overridden(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        emergency = _record(path, "emergency", source_issue=33, generation=2)
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")

        stored = _candidate(MOD.read_ledger(path, WAVE), emergency["candidate_id"])
        assert stored["generation"] >= 2
        assert stored["promotion"] is None
        promoted = MOD.promote_candidate(
            path,
            wave=WAVE,
            candidate_id=emergency["candidate_id"],
            approved_by="security-lead",
            emergency_override=True,
            override_reason="Reproducible data-loss path blocks safe operation",
        )
        assert promoted["promotion"]["approved_by"] == "security-lead"
        assert promoted["promotion"]["emergency_override"] is True

    def test_generation_two_non_emergency_cannot_use_override(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        candidate = _record(path, "pre-existing-oos", source_issue=34, generation=2)
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")

        stored = _candidate(MOD.read_ledger(path, WAVE), candidate["candidate_id"])
        assert stored["generation"] >= 2
        assert stored["disposition"] == "eligible"
        assert stored["promotion"] is None
        with pytest.raises(MOD.PolicyError, match="emergency classification"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=candidate["candidate_id"],
                approved_by="release-manager",
                emergency_override=True,
                override_reason="Not an emergency classification",
            )

    def test_unattributed_promotion_is_rejected(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        candidate = _record(path, "pre-existing-oos", source_issue=35)
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")

        stored = _candidate(MOD.read_ledger(path, WAVE), candidate["candidate_id"])
        assert stored["promotion"] is None
        with pytest.raises(MOD.ValidationError, match="approving human"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=candidate["candidate_id"],
                approved_by="",
            )

    def test_candidate_without_evidence_remains_recorded_but_ineligible(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        candidate = _record(path, "pre-existing-oos", source_issue=36, evidence="")
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")

        stored = _candidate(MOD.read_ledger(path, WAVE), candidate["candidate_id"])
        assert stored["evidence"] == ""
        assert stored["revalidation"]["evidence_reviewed"] is False
        assert stored["promotion"] is None
        with pytest.raises(MOD.PolicyError, match="no reproducible evidence"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=candidate["candidate_id"],
                approved_by="release-manager",
            )


class TestCloseAndMetrics:
    def test_close_is_idempotent_and_record_cannot_reopen_wave(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        _record(path, "speculative", source_issue=40)
        first = MOD.close_wave(
            path,
            wave=WAVE,
            at_commit="abc1234",
            now="2026-08-16T13:00:00+00:00",
        )
        second = MOD.close_wave(
            path,
            wave=WAVE,
            at_commit="abc1234",
            now="2026-08-16T14:00:00+00:00",
        )
        assert first == second

        ledger = MOD.read_ledger(path, WAVE)
        assert ledger["state"] == "closed"
        assert len(ledger["close_history"]) == 1
        with pytest.raises(MOD.PolicyError, match="cannot silently reopen"):
            _record(path, "speculative", source_issue=41)

    def test_later_final_tree_invalidates_a_stale_promotion(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        candidate = _record(path, "pre-existing-oos", source_issue=42)
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")
        MOD.promote_candidate(
            path,
            wave=WAVE,
            candidate_id=candidate["candidate_id"],
            approved_by="release-manager",
        )

        before = _candidate(MOD.read_ledger(path, WAVE), candidate["candidate_id"])
        assert before["promotion"]["status"] == "promoted"
        MOD.close_wave(path, wave=WAVE, at_commit="def5678")
        after = _candidate(MOD.read_ledger(path, WAVE), candidate["candidate_id"])
        assert after["promotion"]["status"] == "stale-final-tree"
        assert after["revalidation"]["at_commit"] == "def5678"
        assert MOD.metrics(path, wave=WAVE, seed_count=1)["promoted"] == 0

    def test_zero_seed_amplification_is_the_not_applicable_string(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        MOD.close_wave(path, wave=WAVE, at_commit="abc1234")
        result = MOD.metrics(path, wave=WAVE, seed_count=0)
        assert result["seed_count"] == 0
        assert isinstance(result["amplification"], str)
        assert result["amplification"] == "not-applicable"
        assert result["promotion_rate"] == "not-applicable"


class TestBehavioralCheckpoint:
    def test_simulated_wave_records_routes_closes_and_promotes_once(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)
        active_pr = _record(path, "active-pr-defect", source_issue=50)
        eligible = _record(
            path,
            "pre-existing-oos",
            source_issue=51,
            source_links=["https://example.test/review/51"],
        )
        duplicate = _record(
            path,
            "duplicate",
            source_issue=52,
            dedupe_of=eligible["candidate_id"],
            source_links=["https://example.test/review/52"],
        )
        generation_two = _record(path, "emergency", source_issue=53, generation=2)

        open_ledger = MOD.read_ledger(path, WAVE)
        open_candidate = _candidate(open_ledger, eligible["candidate_id"])
        assert open_ledger["state"] == "active"
        assert open_candidate["promotion"] is None
        with pytest.raises(MOD.PolicyError, match="wave is active"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=eligible["candidate_id"],
                approved_by="release-manager",
            )

        MOD.close_wave(path, wave=WAVE, at_commit="final123")

        closed_ledger = MOD.read_ledger(path, WAVE)
        stored_active_pr = _candidate(closed_ledger, active_pr["candidate_id"])
        assert stored_active_pr["disposition"] == "fix-current-pr"
        assert stored_active_pr["promotion"] is None
        with pytest.raises(MOD.PolicyError, match="never promotable"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=active_pr["candidate_id"],
                approved_by="release-manager",
            )

        stored_duplicate = next(
            item
            for item in closed_ledger["duplicate_links"]
            if item["candidate_id"] == duplicate["candidate_id"]
        )
        assert stored_duplicate["disposition"] == "duplicate"
        assert stored_duplicate["dedupe_of"] == eligible["candidate_id"]
        with pytest.raises(MOD.PolicyError, match="is a duplicate"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=duplicate["candidate_id"],
                approved_by="release-manager",
            )

        stored_generation_two = _candidate(closed_ledger, generation_two["candidate_id"])
        assert stored_generation_two["generation"] >= 2
        assert stored_generation_two["promotion"] is None
        with pytest.raises(MOD.PolicyError, match="emergency candidates require"):
            MOD.promote_candidate(
                path,
                wave=WAVE,
                candidate_id=generation_two["candidate_id"],
                approved_by="security-lead",
            )

        promoted = MOD.promote_candidate(
            path,
            wave=WAVE,
            candidate_id=eligible["candidate_id"],
            approved_by="release-manager",
            now="2026-08-16T16:00:00+00:00",
        )
        assert promoted["promotion"]["approved_by"] == "release-manager"

        persisted = _candidate(MOD.read_ledger(path, WAVE), eligible["candidate_id"])
        assert persisted["promotion"]["approved_by"] == "release-manager"
        assert persisted["promotion"]["revalidated_at_commit"] == "final123"
        summary = MOD.metrics(path, wave=WAVE, seed_count=4)
        assert summary == {
            "seed_count": 4,
            "recorded": 4,
            "duplicates": 1,
            "promoted": 1,
            "amplification": 0.25,
            "promotion_rate": 0.5,
        }


class TestPersistenceAndCLI:
    def test_concurrent_records_survive_locked_atomic_updates(self, tmp_path: Path) -> None:
        path = _ledger_path(tmp_path)

        def record_one(source_issue: int) -> None:
            _record(path, "speculative", source_issue=source_issue)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(record_one, range(100, 108)))

        ledger = MOD.read_ledger(path, WAVE)
        assert len(ledger["candidates"]) == 8
        assert {item["candidate_id"] for item in ledger["candidates"]} == {
            f"candidate-{number:06d}" for number in range(1, 9)
        }

    def test_cli_accepts_split_and_equals_flags_and_emits_json_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        rc = MOD.main(
            [
                str(SCRIPT),
                "record",
                "--wave=cli-wave",
                "--root-issue",
                "719",
                "--source-issue=60",
                "--classification",
                "pre-existing-oos",
                "--consequence=Visible failure",
                "--evidence",
                "Fixture reproduces",
                "--source-link=review-a",
                "--source-link",
                "review-b",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.err == ""
        payload = json.loads(captured.out)
        assert payload["candidate_id"] == "candidate-000001"
        assert payload["disposition"] == "eligible"
        assert payload["source_links"] == ["review-a", "review-b"]

    def test_cli_requires_seed_count_because_metrics_has_no_network(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        path = MOD.ledger_path("cli-wave")
        MOD.close_wave(path, wave="cli-wave", at_commit="abc1234")

        ledger = MOD.read_ledger(path, "cli-wave")
        assert ledger["state"] == "closed"
        rc = MOD.main([str(SCRIPT), "metrics", "--wave", "cli-wave"])
        captured = capsys.readouterr()
        assert rc == 2
        assert captured.out == ""
        assert "missing required option(s): --seed-count" in captured.err


class TestWiring:
    def test_wave_command_routes_all_residual_transitions_through_the_tool(self) -> None:
        document = (ROOT / ".claude" / "commands" / "flow" / "wave.md").read_text()
        for verb in ("record", "close", "promote", "metrics"):
            assert f"scripts/flow-wave-residuals.py {verb}" in document
        assert "--approved-by <HUMAN_IDENTITY>" in document
        assert "must not run\n`gh issue create`" in document

    def test_script_history_is_documented(self) -> None:
        # #724 (T006) superseded the per-script CLAUDE.md inventory line this
        # test used to pin: the full scripts/ inventory now lives only in
        # docs/scripts.md, and CLAUDE.md's Project Map names `scripts/`
        # generically to keep the always-loaded file from re-growing one line
        # per script. The docs/scripts.md history entry - the part of the
        # original assertion that still matches current convention - is
        # unchanged and still required.
        memory = (ROOT / "CLAUDE.md").read_text()
        history = (ROOT / "docs" / "scripts.md").read_text()
        assert "## `flow-wave-residuals`" in history
        assert "$XDG_RUNTIME_DIR/cc-flow-wave/<wave>/residuals.json" in history
        assert "docs/scripts.md" in memory
