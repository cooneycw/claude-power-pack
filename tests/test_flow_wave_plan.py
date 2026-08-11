"""Tests for the deterministic wave planner (issue #637).

Covers ``scripts/flow-wave-plan.py``, the pure function `/flow:wave` re-runs
after every scope ruling.

Contract:
- ``- Blocked by #N`` edges build the graph; the transitive closure and the
  startable set (OPEN, no OPEN blocker, not in a cycle) come out per issue.
- Gate condition 3 (#637): a Blocked-by cycle is a broken graph, not an empty
  backlog - cycle members are always reported in ``cycles``, excluded from
  ``startable``, and the process exits 3 (plan still emitted) so an
  orchestrator can tell "nothing startable" from "graph is broken".
- ``path_contention`` indexes path-looking tokens named by more than one OPEN
  issue - the invisible-contention case; closed issues never contend.
- ``serialized_resources`` groups explicit ``Serialized-resource:`` markers
  and the built-in migration heuristic.
- Blockers absent from the input are assumed CLOSED but surfaced under
  ``external_blockers`` so the assumption is visible.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-wave-plan.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("flow_wave_plan", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["flow_wave_plan"] = module
    spec.loader.exec_module(module)
    return module


MOD = _load_module()


def _issue(number: int, body: str = "", state: str = "OPEN", title: str = "t") -> dict:
    return {"number": number, "title": title, "body": body, "state": state}


def _plan(*issues: dict) -> dict:
    return MOD.build_plan(MOD.parse_issues(list(issues)))


class TestGraph:
    def test_blocked_by_edges_and_closure(self) -> None:
        plan = _plan(
            _issue(1),
            _issue(2, "- Blocked by #1"),
            _issue(3, "- Blocked by #2"),
        )
        assert plan["issues"]["3"]["blocked_by"] == [2]
        assert plan["issues"]["3"]["blocked_by_transitive"] == [1, 2]

    def test_startable_requires_open_and_unblocked(self) -> None:
        plan = _plan(
            _issue(1, state="CLOSED"),
            _issue(2, "- Blocked by #1"),
            _issue(3, "- Blocked by #2"),
            _issue(4, state="CLOSED"),
        )
        # 1 closed, 2 unblocked (its blocker is closed), 3 blocked by open 2.
        assert plan["startable"] == [2]

    def test_case_insensitive_and_star_bullets(self) -> None:
        plan = _plan(_issue(1), _issue(2, "* blocked BY #1"))
        assert plan["issues"]["2"]["blocked_by"] == [1]

    def test_external_blocker_assumed_closed_but_surfaced(self) -> None:
        plan = _plan(_issue(2, "- Blocked by #99"))
        assert plan["startable"] == [2]
        assert plan["external_blockers"] == {"2": [99]}


class TestCycles:
    """Gate condition 3 (#637): broken graph != empty backlog."""

    def test_cycle_members_reported_and_not_startable(self) -> None:
        plan = _plan(
            _issue(1, "- Blocked by #2"),
            _issue(2, "- Blocked by #1"),
            _issue(3),
        )
        assert plan["cycles"] == [[1, 2]]
        assert plan["issues"]["1"]["in_cycle"] is True
        assert plan["startable"] == [3]

    def test_self_loop_is_a_cycle(self) -> None:
        plan = _plan(_issue(1, "- Blocked by #1"))
        assert plan["cycles"] == [[1]]
        assert plan["startable"] == []

    def test_cli_exits_3_on_cycle_with_plan_still_emitted(self, tmp_path: Path) -> None:
        payload = [
            _issue(1, "- Blocked by #2"),
            _issue(2, "- Blocked by #1"),
        ]
        f = tmp_path / "issues.json"
        f.write_text(json.dumps(payload))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(f)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 3
        plan = json.loads(proc.stdout)
        assert plan["cycles"] == [[1, 2]]
        assert "CYCLE" in proc.stderr

    def test_cli_exits_0_when_nothing_startable_but_graph_ok(self, tmp_path: Path) -> None:
        payload = [_issue(1, state="CLOSED")]
        f = tmp_path / "issues.json"
        f.write_text(json.dumps(payload))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(f)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert json.loads(proc.stdout)["startable"] == []


class TestContention:
    def test_path_named_by_two_open_issues_is_contended(self) -> None:
        plan = _plan(
            _issue(1, "touches src/pkg/cli.py for options"),
            _issue(2, "also rewrites `src/pkg/cli.py` output"),
            _issue(3, "unrelated docs/readme.md"),
        )
        assert plan["path_contention"] == {"src/pkg/cli.py": [1, 2]}

    def test_closed_issue_does_not_contend(self) -> None:
        plan = _plan(
            _issue(1, "touches src/pkg/cli.py"),
            _issue(2, "touches src/pkg/cli.py", state="CLOSED"),
        )
        assert plan["path_contention"] == {}

    def test_serialized_marker_groups_issues(self) -> None:
        plan = _plan(
            _issue(1, "Serialized-resource: alembic-head"),
            _issue(2, "serialized-resource: Alembic-Head"),
        )
        assert plan["serialized_resources"]["alembic-head"] == [1, 2]

    def test_migration_heuristic_flags_shared_resource(self) -> None:
        plan = _plan(
            _issue(1, "adds a column via migrations/0009_x.py"),
            _issue(2, "new alembic revision for the index"),
        )
        assert plan["serialized_resources"]["migration"] == [1, 2]
        assert plan["issues"]["1"]["migration_bearing"] is True

    def test_single_holder_is_not_contention(self) -> None:
        plan = _plan(_issue(1, "adds migrations/0009_x.py"), _issue(2, "docs only"))
        assert plan["serialized_resources"] == {}


class TestWiring:
    """Read-only wiring assertions."""

    def test_planner_is_in_installed_family(self) -> None:
        installer = (ROOT / "scripts" / "flow-helpers-install.sh").read_text()
        assert "flow-wave-plan.py" in installer

    def test_planner_is_bundled_with_flow_plugin(self) -> None:
        sync = (ROOT / "scripts" / "plugin-sync.sh").read_text()
        assert "scripts/flow-wave-plan.py" in sync

    def test_planner_is_allowlisted_in_permissions_template(self) -> None:
        template = (ROOT / "templates" / "claude-settings-permissions.json").read_text()
        assert "Bash(~/.claude/scripts/flow-wave-plan.py:*)" in template

    def test_wave_doc_mandates_replan_on_verdict(self) -> None:
        doc = (ROOT / ".claude" / "commands" / "flow" / "wave.md").read_text()
        assert "verdict issued -> planner re-run -> contention diff checked" in doc
        assert "approve-with-conditions" in doc
