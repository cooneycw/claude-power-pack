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

    def test_planner_is_bundled_with_codex_skill(self) -> None:
        bundled = ROOT / "codex" / "skills" / "flow-wave" / "scripts" / "flow-wave-plan.py"
        assert bundled.read_text() == (ROOT / "scripts" / "flow-wave-plan.py").read_text()

    def test_planner_is_allowlisted_in_permissions_template(self) -> None:
        template = (ROOT / "templates" / "claude-settings-permissions.json").read_text()
        assert "Bash(~/.claude/scripts/flow-wave-plan.py:*)" in template

    def test_wave_doc_mandates_replan_on_verdict(self) -> None:
        doc = (ROOT / ".claude" / "commands" / "flow" / "wave.md").read_text()
        assert "verdict issued -> planner re-run -> contention diff checked" in doc
        assert "approve-with-conditions" in doc


class TestEdgeGrammar:
    """Issue #607 widened the grammar to four keyword forms - and gate
    condition 1 pins its NEGATIVE space: dependency-position only, so prose
    cannot fabricate edges that would silently freeze startability."""

    def test_four_keyword_forms_create_edges(self) -> None:
        plan = _plan(
            _issue(1),
            _issue(2),
            _issue(3),
            _issue(4),
            _issue(5, "Depends on #1\nblocked by #2\nRequires: #3\nAfter #4"),
        )
        assert plan["issues"]["5"]["blocked_by"] == [1, 2, 3, 4]

    def test_comma_and_lists(self) -> None:
        plan = _plan(_issue(1), _issue(2), _issue(3), _issue(4, "Depends on #1, #2 and #3"))
        assert plan["issues"]["4"]["blocked_by"] == [1, 2, 3]

    def test_prose_references_do_not_create_edges(self) -> None:
        # The exact shapes from the gate condition: references in running
        # prose, narrative "after", and case citations must NOT be edges.
        plan = _plan(
            _issue(
                9,
                "This is the complement of #592.\n"
                "see #12 for background\n"
                "It was filed after #600 merged.\n"
                "The #521 case applies here.\n",
            )
        )
        assert plan["issues"]["9"]["blocked_by"] == []

    def test_trailing_prose_after_ref_list_stops_the_list(self) -> None:
        plan = _plan(_issue(1), _issue(2, "Blocked by #1 which shipped after #99 merged"))
        assert plan["issues"]["2"]["blocked_by"] == [1]

    def test_related_and_see_also_are_not_dependencies(self) -> None:
        plan = _plan(_issue(7, "Related to #3\nSee also #4"))
        assert plan["issues"]["7"]["blocked_by"] == []


class TestContractConvergence:
    """Issue #648: the DECIDED partial convergence with contract v1.3.

    Adopted: code stripped before edge parsing; bounded emphasis tolerance in
    declaration position. Distinct (documented in the planner header +
    wave.md): grading/uncertain, field labels, dash-ranges, duplicate-claim
    semantics. The 2026-08-11 sensitivity controls are PERMANENT tests here,
    not a one-night harness (gate condition 5).
    """

    def test_fenced_keyword_line_never_fabricates(self) -> None:
        # The original sensitivity control: a YAML/shell sample inside a fence
        # carried '- after #30' and 'depends on #31' - the pre-#648 grammar
        # fabricated both edges from it.
        body = "Example config:\n```yaml\n- after #30\ndepends on #31\n```\nreal text"
        plan = _plan(_issue(30), _issue(31), _issue(9, body))
        assert plan["issues"]["9"]["blocked_by"] == []

    def test_emphasis_wrapped_declaration_creates_edge(self) -> None:
        # The other control: the contract's flagship human-written form was
        # invisible pre-#648.
        plan = _plan(_issue(12), _issue(9, "**Blocked by:** #12"))
        assert plan["issues"]["9"]["blocked_by"] == [12]

    def test_emphasis_variants_bounded_to_contract_forms(self) -> None:
        plan = _plan(
            _issue(5),
            _issue(6),
            _issue(7),
            _issue(9, "__Depends on__ #5\n- *Requires*: #6\n_After_ #7"),
        )
        assert plan["issues"]["9"]["blocked_by"] == [5, 6, 7]

    def test_strip_runs_before_emphasis_parse(self) -> None:
        # Gate condition 1 (order pin): a DECORATED declaration inside a fence
        # is the one shape only the strip-then-parse order gets right -
        # emphasis tolerance alone would fabricate an edge from it.
        body = "```\n**Depends on:** #31\n```\n"
        plan = _plan(_issue(31), _issue(9, body))
        assert plan["issues"]["9"]["blocked_by"] == []

    def test_inline_coded_declaration_never_fabricates(self) -> None:
        plan = _plan(_issue(12), _issue(9, "`**Blocked by:** #12`\n`Depends on #12`"))
        assert plan["issues"]["9"]["blocked_by"] == []

    def test_real_283_shape_immediate_refs_saves_it(self) -> None:
        # Gate condition 3: the REAL CPP #283 line - a decorated keyword whose
        # continuation is prose, not refs. The immediate-refs requirement is
        # what keeps it edge-free under emphasis tolerance.
        plan = _plan(
            _issue(9, "- **Requires**: Go 1.24.6+, a Woodpecker server, and patience")
        )
        assert plan["issues"]["9"]["blocked_by"] == []

    def test_issue_648_own_body_is_edge_free(self) -> None:
        # Gate condition 2, the self-referential canary: #648's body QUOTES
        # disagreement examples ('**Blocked by:** #12', a fenced '# runs after
        # #30') as inline code - the planner over its own body must see none
        # of them as edges.
        fixture = ROOT / "tests" / "fixtures" / "issue-648-body.md"
        plan = _plan(_issue(648, fixture.read_text()))
        assert plan["issues"]["648"]["blocked_by"] == []

    def test_paths_inside_code_still_feed_contention(self) -> None:
        # Gate condition 4, the deliberate asymmetry: stripping applies to
        # EDGE parsing only - BACKTICK_PATH_RE intentionally reads inline code
        # and fenced samples, so path-contention detection must be unchanged.
        body_a = "Touches `lib/cicd/steps.py` here.\n```\nlib/cicd/runner.py\n```"
        body_b = "Also edits lib/cicd/steps.py and lib/cicd/runner.py directly."
        plan = _plan(_issue(1, body_a), _issue(2, body_b))
        assert "lib/cicd/steps.py" in plan["path_contention"]
        assert "lib/cicd/runner.py" in plan["path_contention"]

    def test_plain_and_decorated_forms_parse_identically(self) -> None:
        plain = _plan(_issue(1), _issue(9, "Depends on #1"))
        decorated = _plan(_issue(1), _issue(9, "**Depends on:** #1"))
        assert (
            plain["issues"]["9"]["blocked_by"]
            == decorated["issues"]["9"]["blocked_by"]
            == [1]
        )


TASKS_MD = """# Tasks

- [ ] T031 [US1] Add visual regression tests (depends on T027, T033)
- [x] T027 [US1] Base harness
- [ ] T033 Watchdog groundwork
- [ ] T040 Uses an unmapped dep (depends on T099)

## Issue Sync

| Task | Issue |
|------|-------|
| T031 | #52 |
| T027 | #40 |
| T033 | #56 |
| T040 | #60 |
"""


class TestSpecDeclaredDeps:
    """Issue #607: --specs unions tasks.md edges via the Issue Sync join."""

    def _specs(self, tmp_path):
        d = tmp_path / "specs" / "feature-x"
        d.mkdir(parents=True)
        (d / "tasks.md").write_text(TASKS_MD)
        return tmp_path / "specs"

    def _plan_with_specs(self, tmp_path, *issues):
        spec_edges, unresolved = MOD.parse_specs(self._specs(tmp_path))
        return MOD.build_plan(MOD.parse_issues(list(issues)), spec_edges, unresolved)

    def test_spec_edges_union_and_drift(self, tmp_path) -> None:
        # #52's issue text names only #40; the spec adds #56 - union, never
        # replace, and the omission surfaces as spec_drift.
        plan = self._plan_with_specs(
            tmp_path,
            _issue(52, "Depends on #40"),
            _issue(40, state="CLOSED"),
            _issue(56),
        )
        assert plan["issues"]["52"]["blocked_by"] == [40, 56]
        assert plan["issues"]["52"]["blocked_by_spec"] == [40, 56]
        assert plan["spec_drift"] == {"52": [56]}
        # #56 is OPEN -> #52 must not be startable (the #607 wrong-top-pick).
        assert 52 not in plan["startable"]

    def test_no_drift_when_text_matches_spec(self, tmp_path) -> None:
        plan = self._plan_with_specs(
            tmp_path,
            _issue(52, "Depends on #40, #56"),
            _issue(40, state="CLOSED"),
            _issue(56, state="CLOSED"),
        )
        assert plan["spec_drift"] == {}
        assert 52 in plan["startable"]

    def test_unresolved_task_reported_not_dropped(self, tmp_path) -> None:
        plan = self._plan_with_specs(tmp_path, _issue(60))
        assert any(
            u["task"] == "T040" and "T099" in u["unresolved"] for u in plan["unresolved_tasks"]
        )
        # The unresolvable dep creates no edge - #60 stays startable.
        assert 60 in plan["startable"]

    def test_speckit_emitted_body_parses_end_to_end(self, tmp_path) -> None:
        # The exact body shape scripts/speckit-tasks-to-issues.sh now writes
        # (#607): the T-id line alone creates no edge; the Blocked-by bullets
        # are the planner's native grammar. This is the CI-side coverage for
        # the gh-dependent script.
        body = (
            "Auto-created from .specify/specs/x/tasks.md (T031) by CPP "
            "speckit-tasks-to-issues.\n\n"
            "Depends on: T027, T033\n"
            "- Blocked by #40\n"
            "- Blocked by #56\n"
        )
        plan = _plan(_issue(52, body), _issue(40, state="CLOSED"), _issue(56))
        assert plan["issues"]["52"]["blocked_by"] == [40, 56]
        assert 52 not in plan["startable"]

    def test_cli_specs_flag(self, tmp_path) -> None:
        import subprocess
        import sys as _sys

        specs = self._specs(tmp_path)
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(
            json.dumps([_issue(52, "Depends on #40"), _issue(40, state="CLOSED"), _issue(56)])
        )
        proc = subprocess.run(
            [_sys.executable, str(SCRIPT), str(issues_file), "--specs", str(specs)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        plan = json.loads(proc.stdout)
        assert plan["spec_drift"] == {"52": [56]}
