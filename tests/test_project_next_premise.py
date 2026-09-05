"""Premise-staleness annotation for spec-derived issues (#770).

WSJF ranking reads value, effort, and unblocking - all properties of the issue
itself - so an issue whose parent specification was written under a premise a
later decision retired still ranks as small, well-formed, and safe. These tests
pin the pairing rule, the exclusions that keep it from crying wolf, and the
invariant that the annotation never touches the engine's decision.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-next.py"
SPEC = importlib.util.spec_from_file_location("cpp_project_next_premise", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
project_next = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = project_next
SPEC.loader.exec_module(project_next)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(
    root: Path,
    filename: str,
    *,
    title: str,
    status: str,
    decided: str | None,
    domains: str = "",
) -> None:
    lines = [f"# ADR {filename[:4]}: {title}", "", f"- Status: {status}"]
    if decided is not None:
        lines.append(f"- Date: {decided}")
    lines.append("- Deciders: owner")
    if domains:
        lines.append(f"- Domains: {domains}")
    _write(root / "docs" / "decisions" / filename, "\n".join(lines) + "\n")


def _spec(
    root: Path,
    slug: str,
    *,
    title: str,
    created: str | None,
    amended: str = "",
    domains: str = "",
) -> None:
    lines = [f"# Feature Specification: {title}", ""]
    if created is not None:
        lines.append(f"> **Created:** {created}")
    if amended:
        lines.append(f"> **Amended:** {amended} - premise revisited")
    if domains:
        lines.append(f"> **Domains:** {domains}")
    lines.extend(("> **Status:** Approved", "", "## Overview", ""))
    _write(root / ".specify" / "specs" / slug / "spec.md", "\n".join(lines) + "\n")


def _state(**overrides: object) -> object:
    data = {
        "repository": "example/project",
        "default_branch": "main",
        "collected_at": "2026-09-05T12:00:00Z",
    }
    data.update(overrides)
    return project_next.RepositoryState.from_dict(data)


def _spec_derived_state(slug: str, issue_number: int = 12, *, with_feature: bool = True) -> object:
    """One open issue reachable only through its parent spec's task mapping."""
    features = [{"name": slug, "path": f".specify/specs/{slug}", "has_spec": True}] if with_feature else []
    return _state(
        issues=[{"number": issue_number, "title": "Implement the mapped task", "labels": ["enhancement"]}],
        spec_features=features,
        spec_tasks=[
            {
                "task_id": "T001",
                "title": "Implement the mapped task",
                "feature": slug,
                "source": f".specify/specs/{slug}/tasks.md",
                "issue_numbers": [issue_number],
                "mapping_status": "mapped",
                "mapping_state": "OPEN",
            }
        ],
    )


def test_a_spec_predating_a_live_decision_flags_its_open_issues(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-worktree-base-location.md",
        title="Configurable worktree base location",
        status="Accepted (owner decision recorded 2026-08-01)",
        decided="2026-08-01",
    )
    _spec(tmp_path, "worktree-scaffolding", title="Worktree Scaffolding", created="2026-05-01")
    state = _spec_derived_state("worktree-scaffolding")
    result = project_next.recommend(state)

    records, _ = project_next._decision_records(tmp_path)
    assert [(item.identifier, item.status, item.date) for item in records] == [("ADR 0007", "accepted", "2026-08-01")]
    assert 12 in set(result.classification.available) | set(result.classification.uncertain)

    flags, warnings = project_next.premise_flags(tmp_path, state, result)

    assert [flag.issue_number for flag in flags] == [12]
    flag = flags[0]
    assert flag.spec_slug == "worktree-scaffolding"
    assert flag.spec_dated == "2026-05-01"
    assert flag.decision_id == "ADR 0007"
    assert flag.decision_dated == "2026-08-01"
    assert flag.domain == "worktree"
    assert flag.match == "shared-term"
    # The criterion is a reason naming BOTH sides, not only a score change.
    assert "worktree-scaffolding" in flag.reason
    assert "ADR 0007" in flag.reason
    assert "Configurable worktree base location" in flag.reason
    assert "2026-05-01" in flag.reason and "2026-08-01" in flag.reason
    assert warnings == ()


def test_a_spec_written_after_the_decision_is_not_flagged(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-worktree-base-location.md",
        title="Configurable worktree base location",
        status="Accepted",
        decided="2026-08-01",
    )
    _spec(tmp_path, "worktree-scaffolding", title="Worktree Scaffolding", created="2026-09-01")
    state = _spec_derived_state("worktree-scaffolding")
    result = project_next.recommend(state)

    # Precondition: both sides parsed and share a domain, so an empty result can
    # only mean the ordering rule fired - not that a read silently failed.
    records, _ = project_next._decision_records(tmp_path)
    premise = project_next._spec_premise(tmp_path, "worktree-scaffolding", ".specify/specs/worktree-scaffolding")
    assert [item.status for item in records] == ["accepted"]
    assert premise is not None and premise.as_of == "2026-09-01"
    assert premise.as_of > records[0].date
    assert project_next._premise_domain_match(premise, records[0]) == ("shared-term", "worktree")

    flags, warnings = project_next.premise_flags(tmp_path, state, result)

    assert flags == ()
    assert warnings == ()


def test_superseded_and_rejected_records_never_retire_a_premise(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-worktree-base-location.md",
        title="Configurable worktree base location",
        status="Superseded by ADR 0009 (2026-08-20)",
        decided="2026-08-01",
    )
    _decision(
        tmp_path,
        "0008-worktree-sandbox-threat-model.md",
        title="Worktree sandbox threat model",
        status="Rejected / Superseded (epic abandoned)",
        decided="2026-08-02",
    )
    _spec(tmp_path, "worktree-scaffolding", title="Worktree Scaffolding", created="2026-05-01")
    state = _spec_derived_state("worktree-scaffolding")
    result = project_next.recommend(state)

    # Precondition: both records PARSED, with a date the spec predates. Without
    # this, an empty flag list would equally describe a header the reader could
    # not read at all - the passing state would carry no information.
    records, warnings = project_next._decision_records(tmp_path)
    assert [(item.identifier, item.status) for item in records] == [
        ("ADR 0007", "superseded"),
        ("ADR 0008", "rejected"),
    ]
    assert all(item.date > "2026-05-01" for item in records)
    assert warnings == []

    flags, _ = project_next.premise_flags(tmp_path, state, result)

    assert flags == ()


def test_an_amended_spec_is_not_accused_of_predating_the_decision_it_absorbed(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-worktree-base-location.md",
        title="Configurable worktree base location",
        status="Accepted",
        decided="2026-08-01",
    )
    _spec(
        tmp_path,
        "worktree-scaffolding",
        title="Worktree Scaffolding",
        created="2026-05-01",
        amended="2026-08-16",
    )
    state = _spec_derived_state("worktree-scaffolding")
    result = project_next.recommend(state)

    premise = project_next._spec_premise(tmp_path, "worktree-scaffolding", ".specify/specs/worktree-scaffolding")
    assert premise is not None and premise.as_of == "2026-08-16"

    flags, _ = project_next.premise_flags(tmp_path, state, result)

    assert flags == ()


def test_declared_domains_match_when_the_titles_share_no_significant_term(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-single-owner-model.md",
        title="Single-owner authentication posture",
        status="Accepted",
        decided="2026-08-01",
        domains="identity, auth",
    )
    _spec(
        tmp_path,
        "discord-rollcall",
        title="Discord Roll Call",
        created="2026-05-01",
        domains="identity",
    )
    state = _spec_derived_state("discord-rollcall")
    result = project_next.recommend(state)

    records, _ = project_next._decision_records(tmp_path)
    premise = project_next._spec_premise(tmp_path, "discord-rollcall", ".specify/specs/discord-rollcall")
    assert premise is not None
    # Precondition: the heuristic fallback CANNOT explain this match, so the
    # assertion below is about declared domains and nothing else.
    shared = project_next._premise_terms(premise.spec_slug, premise.title) & project_next._premise_terms(
        records[0].title, Path(records[0].path).stem
    )
    assert shared == frozenset()

    flags, _ = project_next.premise_flags(tmp_path, state, result)

    assert [(flag.match, flag.domain) for flag in flags] == [("declared", "identity")]
    assert "declared domain" in flags[0].reason


def test_unrelated_titles_and_shared_generic_words_do_not_match(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-main-branch-protection-posture.md",
        title="Main branch-protection posture",
        status="Accepted",
        decided="2026-08-01",
    )
    _decision(
        tmp_path,
        "0008-project-decision-record-design.md",
        title="Project decision record design",
        status="Accepted",
        decided="2026-08-02",
    )
    _spec(tmp_path, "tavily-mcp-integration", title="Tavily MCP Integration", created="2026-05-01")
    _spec(tmp_path, "project-feature-spec", title="Project Feature Specification", created="2026-05-02")
    state = _state(
        issues=[
            {"number": 12, "title": "Tavily task"},
            {"number": 13, "title": "Project task"},
        ],
        spec_features=[
            {"name": "tavily-mcp-integration", "path": ".specify/specs/tavily-mcp-integration", "has_spec": True},
            {"name": "project-feature-spec", "path": ".specify/specs/project-feature-spec", "has_spec": True},
        ],
        spec_tasks=[
            {
                "task_id": "T001",
                "title": "Tavily task",
                "feature": "tavily-mcp-integration",
                "source": ".specify/specs/tavily-mcp-integration/tasks.md",
                "issue_numbers": [12],
                "mapping_status": "mapped",
                "mapping_state": "OPEN",
            },
            {
                "task_id": "T002",
                "title": "Project task",
                "feature": "project-feature-spec",
                "source": ".specify/specs/project-feature-spec/tasks.md",
                "issue_numbers": [13],
                "mapping_status": "mapped",
                "mapping_state": "OPEN",
            },
        ],
    )
    result = project_next.recommend(state)

    # Precondition: two live records, both dated after both specs, so only the
    # domain rule can be responsible for the empty result.
    records, _ = project_next._decision_records(tmp_path)
    assert [item.status for item in records] == ["accepted", "accepted"]
    assert all(item.date > "2026-05-02" for item in records)
    # "project", "feature", "specification", "decision", "record" and "design"
    # are repository-generic, so the second pair shares no evidence at all.
    assert project_next._premise_terms("project-feature-spec", "Project Feature Specification") == frozenset()

    flags, _ = project_next.premise_flags(tmp_path, state, result)

    assert flags == ()


def test_flags_render_in_every_mode_without_touching_the_engine_decision(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-worktree-base-location.md",
        title="Configurable worktree base location",
        status="Accepted",
        decided="2026-08-01",
    )
    _spec(tmp_path, "worktree-scaffolding", title="Worktree Scaffolding", created="2026-05-01")
    state = _spec_derived_state("worktree-scaffolding")
    result = project_next.recommend(state)
    flags, _ = project_next.premise_flags(tmp_path, state, result)
    assert flags, "fixture must produce at least one flag for the rendering assertions"

    flagged = project_next.CppExtensions((), (), (), (), flags)
    unflagged = project_next.CppExtensions((), (), (), ())
    for mode in ("brief", "compact", "full"):
        rendered = project_next.render_cpp(result, state, mode, flagged)
        empty = project_next.render_cpp(result, state, mode, unflagged)
        assert "Premise staleness" in rendered
        assert "#12" in rendered
        assert "/flow:eli5" in rendered
        assert "advisory" in rendered.casefold()
        # The vendored engine's own report is reproduced verbatim inside the CPP
        # render whether or not a flag exists: the annotation is additive, never
        # a re-rank or a filter.
        engine = project_next.render_result(result, state, mode)
        assert engine in rendered
        assert engine in empty
        if mode != "brief":
            assert "ADR 0007" in rendered
            assert "no spec predates a live decision" in empty


def test_a_decision_record_missing_its_date_is_warned_not_silently_skipped(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-worktree-base-location.md",
        title="Configurable worktree base location",
        status="Accepted",
        decided=None,
    )
    _spec(tmp_path, "worktree-scaffolding", title="Worktree Scaffolding", created="2026-05-01")
    state = _spec_derived_state("worktree-scaffolding")
    result = project_next.recommend(state)

    # Precondition: the file exists and is the only decision record present.
    assert (tmp_path / "docs" / "decisions" / "0007-worktree-base-location.md").is_file()

    flags, warnings = project_next.premise_flags(tmp_path, state, result)

    assert flags == ()
    assert any("0007-worktree-base-location.md" in warning and "Date" in warning for warning in warnings)


def test_a_spec_without_a_date_is_warned_when_live_decisions_exist(tmp_path: Path) -> None:
    _decision(
        tmp_path,
        "0007-worktree-base-location.md",
        title="Configurable worktree base location",
        status="Accepted",
        decided="2026-08-01",
    )
    _spec(tmp_path, "worktree-scaffolding", title="Worktree Scaffolding", created=None)
    # The feature list is omitted here so the reader also exercises its
    # .specify/specs/<slug> path fallback.
    state = _spec_derived_state("worktree-scaffolding", with_feature=False)
    result = project_next.recommend(state)

    premise = project_next._spec_premise(tmp_path, "worktree-scaffolding", ".specify/specs/worktree-scaffolding")
    assert premise is not None and premise.as_of == ""

    flags, warnings = project_next.premise_flags(tmp_path, state, result)

    assert flags == ()
    assert any("worktree-scaffolding" in warning and "Created" in warning for warning in warnings)


def test_a_repository_with_no_decision_records_produces_no_flags_and_no_warnings(tmp_path: Path) -> None:
    _spec(tmp_path, "worktree-scaffolding", title="Worktree Scaffolding", created=None)
    state = _spec_derived_state("worktree-scaffolding")
    result = project_next.recommend(state)

    assert not (tmp_path / "docs" / "decisions").exists()

    flags, warnings = project_next.premise_flags(tmp_path, state, result)

    # A repository that publishes no decisions has no premise evidence, so the
    # undated spec above must stay silent rather than warn about a check that
    # could never have run.
    assert flags == ()
    assert warnings == ()


def test_json_output_carries_the_premise_flags(tmp_path: Path, capsys: object) -> None:
    _decision(
        tmp_path,
        "0007-worktree-base-location.md",
        title="Configurable worktree base location",
        status="Accepted",
        decided="2026-08-01",
    )
    _spec(tmp_path, "worktree-scaffolding", title="Worktree Scaffolding", created="2026-05-01")
    fixture = tmp_path / "state.json"
    fixture.write_text(
        json.dumps(project_next.asdict(_spec_derived_state("worktree-scaffolding"))),
        encoding="utf-8",
    )

    assert project_next.main([str(tmp_path), "--json", "--input", str(fixture)]) == 0

    payload = json.loads(capsys.readouterr().out)
    premise = payload["cpp_extensions"]["premise_flags"]
    assert [item["issue_number"] for item in premise] == [12]
    assert premise[0]["decision_path"] == "docs/decisions/0007-worktree-base-location.md"
    assert premise[0]["spec_path"] == ".specify/specs/worktree-scaffolding/spec.md"
