"""Adversarial planner fixture from the poker-measure four-worker wave (#645).

Real scenario, contributed by that wave's orchestrating session: seven issues
naming one unowned file (src/poker_measure/cli.py) with no dependency edge
between any pair; two startability flips 21 minutes apart (DP1/DP2); and a
ruling-site footprint change (DP3 - an approval condition made #160
migration-bearing while its body never said migration). The fixture is
SELF-CONTAINED: edges and states are verified internally consistent with the
assertion set, not against the live poker-measure repo (which keeps moving) -
the donated numbers are the shape of the failure, not a live-repo contract.

The #645 capability under test (stateless, caller-owned persistence):
- --in-flight -> path_contention_active: contention among (startable UNION
  in-flight) only - the set that can collide NOW. Assertion 5's negative
  control is what makes the flag believable.
- --verdicts -> the wave's ruling ledger: an unsuperseded `hold` on an
  active-set issue exits 4 (plan still emitted) instead of being silently
  contradicted (DP2b - the contributor's highest-weighted assertion);
  `adds_serialized` markers union into serialized_resources so a ruling-site
  footprint change surfaces on the next re-plan (DP3).

Gate condition 2 pins (named, not incidental): a run without the new flags is
byte-identical to the pre-#645 planner (the new keys are flag-gated and no
un-gated code path changed - asserted by key-set and content equality across
the old surface), and exit 4 still emits the complete plan JSON.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-wave-plan.py"

CLI = "src/poker_measure/cli.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("flow_wave_plan_adv", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["flow_wave_plan_adv"] = module
    spec.loader.exec_module(module)
    return module


MOD = _load_module()

NEGATIVE_CONTROL = {131, 134, 148, 149, 151}


def _issue(number: int, body: str = "", state: str = "OPEN") -> dict:
    return {"number": number, "title": f"issue {number}", "body": body, "state": state}


def _fixture(*, dp2: bool) -> list[dict]:
    """The poker-measure wave's issue set. dp2=False is the DP1 snapshot
    (#146 still open); dp2=True is DP2/DP3 (#146 merged, #147 startable)."""
    return [
        _issue(129, state="CLOSED"),
        _issue(130),  # stays OPEN throughout - keeps #131/#134 blocked
        _issue(131, f"- Blocked by #129\n- Blocked by #130\nauto-note rule CRUD in {CLI}"),
        _issue(132, state="CLOSED"),
        _issue(133, state="CLOSED"),
        _issue(
            134,
            "- Blocked by #130\n- Blocked by #131\n- Blocked by #132\n"
            f"- Blocked by #133\ntyped review API + CLI in {CLI}",
        ),
        _issue(145, state="CLOSED"),
        _issue(146, state="CLOSED" if dp2 else "OPEN"),
        _issue(
            147,
            "- Blocked by #145\n- Blocked by #146\n"
            f"T014 wires pot-share derivation into runner + {CLI}\n"
            "adds migrations/0009_pot_share.py",
        ),
        _issue(148, f"- Blocked by #147\nsame derivation wiring, {CLI}"),
        _issue(149, f"- Blocked by #147\nT030 tournament-result derivation, {CLI}"),
        _issue(150),  # stays OPEN - keeps #151 blocked
        _issue(151, f"- Blocked by #150\nT044 endpoints + CLI equivalents in {CLI}"),
        _issue(160, "pure compiler.py ordering fix"),  # body says NO migration
        _issue(170, state="CLOSED"),
        _issue(
            179,
            f"- Blocked by #170\nseven commands, name-or-id resolution, rewrite of {CLI}",
        ),
    ]


def _plan(issues, in_flight=None, verdicts=None):
    return MOD.build_plan(MOD.parse_issues(issues), None, None, in_flight, verdicts)


class TestDP1:
    def test_179_startable_contention_one_no_flag(self) -> None:
        plan = _plan(_fixture(dp2=False), in_flight=set())
        assert 179 in plan["startable"]
        assert 147 not in plan["startable"]  # #146 still open
        # Raw index still sees all seven (forensics)...
        assert len(plan["path_contention"].get(CLI, [])) == 7
        # ...but the ACTIVE view has one member -> no flag.
        assert CLI not in plan["path_contention_active"]


class TestDP2:
    def test_147_startable_cli_flagged_across_both(self) -> None:
        plan = _plan(_fixture(dp2=True), in_flight={179})
        assert 147 in plan["startable"]
        assert plan["path_contention_active"][CLI] == [147, 179]

    def test_no_recommendation_field_emitted(self) -> None:
        # #637 posture (the fixture's own scope note concedes it): the planner
        # SURFACES contention; widest-first is wave.md judgment. Any emitted
        # recommendation would risk being merge-order-based - so there is none.
        plan = _plan(_fixture(dp2=True), in_flight={179})
        assert not any("recommend" in k.lower() for k in plan)


class TestDP2bVerdictPersistence:
    HOLD = [
        {
            "issue": 147,
            "ruling": "hold",
            "holds_behind": [179],
            "reason": "cli.py after #179; #179 owns the convention",
            "ts": "2026-08-11T00:20:00Z",
        }
    ]

    def test_assignment_contradicting_hold_raises(self, tmp_path: Path) -> None:
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(_fixture(dp2=True)))
        ledger = tmp_path / "verdicts.json"
        ledger.write_text(json.dumps(self.HOLD))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(issues_file), "--in-flight", "179",
             "--verdicts", str(ledger)],
            capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 4, proc.stderr
        assert "VERDICT CONTRADICTION" in proc.stderr
        plan = json.loads(proc.stdout)
        assert [c["issue"] for c in plan["verdict_conflicts"]] == [147]

    def test_recorded_supersede_clears_the_raise(self, tmp_path: Path) -> None:
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(_fixture(dp2=True)))
        ledger = tmp_path / "verdicts.json"
        ledger.write_text(json.dumps(self.HOLD + [
            {
                "issue": 147,
                "ruling": "approved",
                "reason": "override: region-disjoint (derive vs saved/report) per ruling record",
                "ts": "2026-08-11T00:38:00Z",
            }
        ]))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(issues_file), "--in-flight", "179",
             "--verdicts", str(ledger)],
            capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["verdict_conflicts"] == []


class TestDP3RulingSiteFootprint:
    def test_approval_condition_adds_migration_conflict(self) -> None:
        issues = _fixture(dp2=True)
        # Assignment-time runs: #147 is the only migration-bearing issue ->
        # no serialized conflict in either footprint.
        pre = _plan(issues, in_flight={179, 147})
        assert "migration" not in pre["serialized_resources"]
        # The #160 approval-with-conditions ("evict the stale cache entries")
        # makes it migration-bearing - carried ONLY by the ledger.
        verdicts = {
            160: {
                "issue": 160,
                "ruling": "approved-with-conditions",
                "adds_serialized": ["migration"],
                "reason": "evict stale cache entries; do not age out",
                "ts": "2026-08-11T00:45:00Z",
            }
        }
        post = _plan(issues, in_flight={179, 147}, verdicts=verdicts)
        # The caller-style diff across the two runs: the conflict is NEW.
        assert post["serialized_resources"]["migration"] == [147, 160]


class TestNegativeControl:
    def test_blocked_five_never_startable_or_active(self) -> None:
        for dp2 in (False, True):
            plan = _plan(_fixture(dp2=dp2), in_flight={179})
            for n in NEGATIVE_CONTROL:
                assert n not in plan["startable"], (dp2, n)
                for members in plan["path_contention_active"].values():
                    assert n not in members, (dp2, n)


class TestBackCompat:
    """Gate condition 2, named pins."""

    def test_no_new_flags_is_byte_identical_to_pre645_output(self, tmp_path: Path) -> None:
        # The #645 keys are flag-gated and no un-gated code path changed, so
        # a no-flags run must carry EXACTLY the pre-#645 surface: no new keys,
        # exit 0, and the same content the library call produces.
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(_fixture(dp2=True)))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(issues_file)],
            capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 0, proc.stderr
        plan = json.loads(proc.stdout)
        assert "path_contention_active" not in plan
        assert "verdict_conflicts" not in plan
        assert json.dumps(plan, indent=2) + "\n" == proc.stdout

    def test_exit_4_still_emits_complete_plan(self, tmp_path: Path) -> None:
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps(_fixture(dp2=True)))
        ledger = tmp_path / "verdicts.json"
        ledger.write_text(json.dumps(TestDP2bVerdictPersistence.HOLD))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(issues_file), "--in-flight", "179",
             "--verdicts", str(ledger)],
            capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 4
        plan = json.loads(proc.stdout)
        # Loud but never obstructive: the full plan surface is present.
        for key in ("issues", "startable", "cycles", "path_contention",
                    "path_contention_active", "verdict_conflicts"):
            assert key in plan, key
