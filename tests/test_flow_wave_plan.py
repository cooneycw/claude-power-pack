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

import pytest

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


# The spelling `.specify/templates/tasks-template.md` actually writes, and that
# every tasks.md in this repo's own .specify/specs/ uses. Identical in content to
# TASKS_MD above; only the task-id emphasis differs.
TASKS_MD_BOLD = """# Tasks

- [ ] **T031** [US1] Add visual regression tests (depends on T027, T033)
- [x] **T027** [US1] Base harness
- [ ] **T033** Watchdog groundwork

## Issue Sync

| Task | Issue |
|------|-------|
| T031 | #52 |
| T027 | #40 |
| T033 | #56 |
"""


class TestBoldTaskIdsDeclareTheSameEdges:
    """Issue #857: an emphasised task id must not silently erase its edges.

    The planner read only the bare `T031` spelling, so a tasks.md written in the
    shipped template's BOLD form parsed as zero tasks. That is worse than a parse
    error: `parse_specs` reports what it cannot resolve, but a line it never
    recognised as a task has nothing to report - the dependency simply was not
    there, and the plan looked healthy.

    The assertion is therefore about EDGES, not about the regex: the bold file
    must produce the same graph as the plain one.
    """

    def _specs(self, tmp_path, text):
        d = tmp_path / "specs" / "feature-x"
        d.mkdir(parents=True)
        (d / "tasks.md").write_text(text)
        return tmp_path / "specs"

    def test_bold_ids_produce_the_same_edges_as_plain_ids(self, tmp_path) -> None:
        bold_edges, _ = MOD.parse_specs(self._specs(tmp_path / "bold", TASKS_MD_BOLD))
        plain_edges, _ = MOD.parse_specs(
            self._specs(
                tmp_path / "plain",
                TASKS_MD_BOLD.replace("**", ""),
            )
        )

        assert bold_edges == {52: {40, 56}}, (
            "bold task ids produced no spec edges - the #857 representation defect"
        )
        assert bold_edges == plain_edges

    def test_bold_dependency_reaches_the_plan_and_blocks_startability(self, tmp_path) -> None:
        """End to end: the edge changes the answer `/flow:wave` acts on."""
        spec_edges, unresolved = MOD.parse_specs(self._specs(tmp_path, TASKS_MD_BOLD))
        plan = MOD.build_plan(
            MOD.parse_issues([_issue(52), _issue(40, state="CLOSED"), _issue(56)]),
            spec_edges,
            unresolved,
        )

        assert plan["issues"]["52"]["blocked_by"] == [40, 56]
        # #56 is OPEN, so #52 is blocked. Before the fix it read as startable,
        # and a wave would have handed out an issue whose dependency was open.
        assert 52 not in plan["startable"]


# --------------------------------------------------------------------------- #
# #1026 - exit 4 stays, but the two populations behind it become legible
#
# A wave carrying standing holds is permanently exit 4. That is the hold WORKING
# - the ledger entry stands until something explicitly supersedes it, and while
# it stands it keeps a ready issue out of the assignment pool. The defect was
# never the firing; it was that the exit code alone cannot tell that quiescent
# state apart from a worker who is on a held issue RIGHT NOW.
#
# The remedy is legibility, not a narrower gate. #645's assertion is that a hold
# in the active set must RAISE rather than silently supersede, and quieting a
# correct refusal because it is always on is how that distinction gets lost.
# --------------------------------------------------------------------------- #


class TestVerdictConflictPopulations:
    HOLD = {"issue": 10, "ruling": "hold", "reason": "waits behind #11", "ts": "t"}

    def _conflicts(self, in_flight=None) -> list[dict]:
        issues = MOD.parse_issues([_issue(10), _issue(11)])
        plan = MOD.build_plan(issues, in_flight=in_flight, verdicts={10: self.HOLD})
        return plan["verdict_conflicts"]

    def test_a_held_candidate_is_startable_not_in_flight(self) -> None:
        """The quiescent state: nobody is on it, and the hold is why."""
        (c,) = self._conflicts()
        assert c["in"] == "startable"
        assert c["also_startable"] is True

    def test_a_worker_on_a_held_issue_reads_in_flight(self) -> None:
        """THE RED CASE this classification exists for.

        An assigned issue is very often ALSO startable - nothing stops the graph
        calling it ready while somebody works on it. Reading ``startable`` first
        labelled exactly that case "startable", i.e. the hold merely keeping a
        candidate out of the pool, when it is the opposite: a live contradiction.

        Assignment is caller knowledge and is the stronger, actionable fact;
        startability is a property of the graph and is kept BESIDE it in
        ``also_startable`` rather than instead of it, so nothing is lost.
        """
        (c,) = self._conflicts(in_flight={10})
        assert c["in"] == "in-flight", (
            "an issue the caller declared assigned must not read as a mere candidate"
        )
        assert c["also_startable"] is True

    def test_the_gate_still_fires_in_both_populations(self) -> None:
        """The control on the control: making it legible must not make it quiet.

        If either population stopped raising, #645's DP2b assertion would be gone
        and this whole group would still pass on the ``in`` values alone.
        """
        assert len(self._conflicts()) == 1
        assert len(self._conflicts(in_flight={10})) == 1

    def test_an_unheld_issue_raises_nothing(self) -> None:
        """The green case - without it, a planner that flagged everything would
        satisfy every assertion above."""
        issues = MOD.parse_issues([_issue(10), _issue(11)])
        plan = MOD.build_plan(issues, in_flight={10}, verdicts={})
        assert plan["verdict_conflicts"] == []


class TestVerdictConflictReportNamesThePopulation:
    """The stderr report is what an orchestrator actually reads, so the split has
    to be there and not only in the JSON."""

    HOLD = [{"issue": 10, "ruling": "hold", "reason": "waits behind #11", "ts": "t"}]

    def _run(self, tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps([_issue(10), _issue(11)]))
        ledger = tmp_path / "verdicts.json"
        ledger.write_text(json.dumps(self.HOLD))
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(issues_file), "--verdicts", str(ledger), *extra],
            capture_output=True, text=True, check=False,
        )

    def test_startable_only_is_named_as_the_hold_working(self, tmp_path: Path) -> None:
        """The reassurance requires an INSPECTED assignment population.

        ``--in-flight ''`` is the caller saying "nothing is assigned" - which is
        knowledge. Only then can the run say the hold is merely doing its job.
        """
        proc = self._run(tmp_path, "--in-flight", "")
        assert proc.returncode == 4, proc.stderr
        assert "0 in-flight" in proc.stderr, proc.stderr
        assert "1 startable (#10)" in proc.stderr, proc.stderr
        assert "standing hold WORKING" in proc.stderr, proc.stderr

    def test_an_unknown_assignment_state_is_never_reassured(self, tmp_path: Path) -> None:
        """THE RED CASE for the reassurance itself.

        Without ``--in-flight`` every conflict defaults to "startable" - not
        because nothing is assigned, but because nobody said. A worker sitting on
        a held issue lands in that same bucket and is invisible. Printing "the
        hold is working, nothing went wrong" there claims more than the input
        population supports, and it is precisely the reading that would hide the
        one case worth acting on.
        """
        proc = self._run(tmp_path)
        assert "--in-flight was NOT passed" in proc.stderr, proc.stderr
        assert "NOT a report that nothing went wrong" in proc.stderr, proc.stderr
        assert "standing hold WORKING" not in proc.stderr, (
            "an uninspected population must not be reassured about"
        )

    def test_in_flight_is_named_as_the_live_contradiction(self, tmp_path: Path) -> None:
        proc = self._run(tmp_path, "--in-flight", "10")
        assert proc.returncode == 4, proc.stderr
        assert "1 in-flight (#10)" in proc.stderr, proc.stderr
        assert "live contradiction" in proc.stderr, proc.stderr
        # ...and it must NOT print the reassurance meant for the other population.
        assert "standing hold WORKING" not in proc.stderr, proc.stderr


# ── #1189 defect 2: one unrecordable ruling must not disable the ledger ──────
#
# The verdict ledger exists so rulings outlive the session that made them. Every
# entry was keyed `latest[int(e["issue"])] = e`, so an entry whose subject is not
# a number did not merely go unrecorded - int() raised, and the planner rejected
# THE WHOLE FILE, taking every other ruling down with it.
#
# The wave's own doctrine routes small in-lane findings to a fix rather than a
# ticket, and that work still reaches a gate. So the better a wave follows its
# own don't-file-it rule, the more of its decisions fall outside the record built
# to keep decisions - and, before this change, one hand-written line disabled the
# rest of it.
#
# The fixtures are hand-written ledgers. That is a genuine input the reader
# already accepts, not a stand-in: no producer can emit a slug subject yet, since
# the GATE parser still refuses one, and that half is deferred on a lane
# constraint rather than on judgement.


class TestALedgerSurvivesAnUnplannableRuling:
    NUMERIC_HOLD = {"issue": 10, "ruling": "hold", "reason": "waits behind #11", "ts": "t"}
    SLUG_RULING = {
        "subject": "journal-false-red",
        "ruling": "approved",
        "reason": "no ticket by design",
        "ts": "t",
    }

    def _run(self, tmp_path: Path, entries: list[dict]) -> subprocess.CompletedProcess[str]:
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps([_issue(10), _issue(11)]))
        ledger = tmp_path / "verdicts.json"
        ledger.write_text(json.dumps(entries))
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(issues_file), "--verdicts", str(ledger),
             "--in-flight", ""],
            capture_output=True, text=True, check=False,
        )

    def test_a_slug_subject_does_not_take_the_whole_ledger_down(self, tmp_path: Path) -> None:
        """THE RED CASE. A numeric hold and a slug ruling in one file.

        The numeric hold must still be enforced. Before this change the planner
        exited 2 with `invalid literal for int()` and produced no plan at all, so
        the hold on #10 stopped being read because of an entry that had nothing
        to do with #10.
        """
        proc = self._run(tmp_path, [self.NUMERIC_HOLD, self.SLUG_RULING])
        assert proc.returncode == 4, (
            "one unplannable ruling rejected the whole ledger:\n" + proc.stderr
        )
        assert "standing hold" in proc.stderr, proc.stderr

    def test_a_slug_ruling_is_reported_rather_than_silently_dropped(
        self, tmp_path: Path
    ) -> None:
        """A skipped entry that nothing mentions is indistinguishable from a file
        that never held one. The planner says how many rulings it read but could
        not plan against, so `0` and `some` stay different observations."""
        proc = self._run(tmp_path, [self.NUMERIC_HOLD, self.SLUG_RULING])
        assert "1 ruling(s) recorded against a non-issue subject" in proc.stderr, proc.stderr

    def test_a_numeric_looking_subject_still_gates_its_issue(self, tmp_path: Path) -> None:
        """The guard on the tolerant side.

        `subject: "10"` names issue 10 in every sense a reader cares about, and a
        run that treated it as an unplannable slug would silently STOP ENFORCING a
        hold - the failure this change exists to prevent, arriving through its own
        new field. A numeric subject is a numeric subject however it was spelled.
        """
        entry = dict(self.NUMERIC_HOLD)
        del entry["issue"]
        entry["subject"] = "10"
        proc = self._run(tmp_path, [entry])
        assert proc.returncode == 4, (
            "a numeric subject stopped gating its issue:\n" + proc.stderr
        )
        assert "non-issue subject" not in proc.stderr, (
            "a numeric subject was miscounted as unplannable:\n" + proc.stderr
        )

    def test_a_genuinely_malformed_entry_still_refuses(self, tmp_path: Path) -> None:
        """The guard on the strict side, and it must already pass.

        Tolerating a slug must not become tolerating anything. An entry with no
        ruling at all is not an unplannable subject - it is a broken record, and
        refusing the file is the right answer. If this ever goes green only
        because the loader stopped checking, the change has traded one silence
        for another.
        """
        proc = self._run(tmp_path, [{"issue": 10}])
        assert proc.returncode == 2, proc.stderr
        assert "cannot read verdict ledger" in proc.stderr, proc.stderr

    def test_a_hash_prefixed_issue_number_still_gates_its_issue(
        self, tmp_path: Path
    ) -> None:
        """`{"issue": "#10"}` names issue 10, and must still hold it.

        The first cut of this change keyed `issue` and `subject` through one
        int() and counted every failure as an unplannable slug. That turned a
        typo'd issue reference from a LOUD refusal into a SILENTLY UNENFORCED
        HOLD - the planner exited 0 with no conflicts and #10 became startable.
        A hold that stops being enforced because of how its number was spelled is
        this issue's own defect class, arriving through its fix.
        """
        proc = self._run(tmp_path, [{"issue": "#10", "ruling": "hold", "reason": "r", "ts": "t"}])
        assert proc.returncode == 4, (
            "a '#'-spelled issue number stopped gating its issue:\n" + proc.stderr
        )
        assert "non-issue subject" not in proc.stderr, (
            "an issue number was miscounted as unplannable:\n" + proc.stderr
        )

    @pytest.mark.parametrize(
        "entry",
        [
            pytest.param({"issue": "abc", "ruling": "hold"}, id="issue-not-a-number"),
            pytest.param({"issue": None, "ruling": "hold"}, id="issue-null"),
            pytest.param({"issue": [], "ruling": "hold"}, id="issue-array"),
            pytest.param({"subject": "", "ruling": "hold"}, id="subject-empty"),
            pytest.param({"subject": None, "ruling": "hold"}, id="subject-null"),
            pytest.param({"subject": [], "ruling": "hold"}, id="subject-array"),
        ],
    )
    def test_a_malformed_identifier_refuses_rather_than_becoming_a_slug(
        self, tmp_path: Path, entry: dict
    ) -> None:
        """THE TOLERANCE BOUNDARY, and it is drawn by the KEY NAME.

        `issue` asserts "this is an issue number"; a value that is not one is a
        broken record and must refuse the file, exactly as before this change.
        `subject` asserts "this may name work with no issue", but null, a
        container or an empty string names nothing at all.

        Counting any of these as a deliberately-ticketless subject would claim
        the ledger recorded a decision about work nobody can identify, and would
        let a mistyped hold pass as a successful plan.
        """
        proc = self._run(tmp_path, [entry])
        assert proc.returncode == 2, (
            f"{entry} was accepted as an unplannable subject:\n" + proc.stderr
        )
        assert "cannot read verdict ledger" in proc.stderr, proc.stderr
