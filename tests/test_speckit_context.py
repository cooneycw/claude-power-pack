"""Tests for the generated-issue context cache (issue #858).

`scripts/speckit-context.py` resolves a task's DECLARED context - its `[USn]`
story tag, and the Functional Requirements rows whose `User Story` column names
that story - and renders a bounded, fingerprinted block into the issue body.

The properties under test are the ones a string can actually carry:

  * only DECLARED relationships are used, and anything that does not resolve is
    disclosed rather than invented
  * requirements belonging to another story stay out
  * cross-cutting sections (no story mapping) are named for the reader to inspect,
    never attributed to this task
  * the task's own wording is labelled as task wording whose authority must be
    resolved, not blanket-labelled replaceable
  * a refresh touches only the managed block, and declines outright when the block
    was edited or its boundaries are damaged
  * freshness states describe BYTES that changed, not materiality

What these tests CANNOT establish, and what #861's pilots exist for: that a
receiving agent actually reads the source, correctly separates a proposal from a
binding constraint, or plans accordingly. Every assertion here is about generated
text and file state.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "speckit-context.py"


def _load():
    spec = importlib.util.spec_from_file_location("speckit_context", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["speckit_context"] = module
    spec.loader.exec_module(module)
    return module


CTX = _load()

SPEC = """# Feature Specification: Exports

## User Stories

### US1: Responsive exports [P1]

**As a** analyst,
**I want** the page to stay usable while an export runs,
**So that** I can keep working.

**Acceptance Criteria:**
- [ ] The page responds within 200ms while an export of 50k rows runs
- [ ] Progress is visible and updates at least every 2 seconds

### US2: Scheduled exports [P2]

**As a** manager,
**I want** exports on a schedule,
**So that** reports arrive without me asking.

**Acceptance Criteria:**
- [ ] A schedule can be set per report

## Out of Scope

- Export formats other than CSV

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | Export runs without holding a request thread | Must | US1 |
| R2 | Progress endpoint returns percent complete | Should | US1 |
| R3 | Schedules persist across restarts | Could | US2 |

### Non-Functional Requirements

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR1 | No new infrastructure service | zero new containers |
"""

TASKS = """# Tasks: Exports

- [ ] **T001** [US1] Use a background queue so the page stays responsive
- [ ] **T002** [US2] Add the schedule table
- [ ] **T003** Untagged task with no story
- [ ] **T004** [US9] Tagged with a story the spec does not have
- [ ] **T005** [US1] Must use PostgreSQL to integrate with the supported database
"""


@pytest.fixture
def feature(tmp_path: Path) -> Path:
    """A spec-kit feature directory with a spec and its tasks."""
    directory = tmp_path / "specs" / "exports"
    directory.mkdir(parents=True)
    (directory / "spec.md").write_text(SPEC, encoding="utf-8")
    (directory / "tasks.md").write_text(TASKS, encoding="utf-8")
    return directory


def _block(feature: Path, task: str = "T001", root: Path | None = None) -> str:
    """Render with an explicit project root, the contract `check --root` relies on."""
    base = root if root is not None else feature.parent.parent
    return CTX.render(
        CTX.resolve(feature / "tasks.md", task, base), "specs/exports/tasks.md"
    )


class TestDeclaredMappingOnly:
    def test_story_acceptance_is_carried(self, feature: Path) -> None:
        block = _block(feature)

        assert "The page responds within 200ms" in block
        assert "Progress is visible" in block

    def test_another_storys_acceptance_stays_out(self, feature: Path) -> None:
        """US2 is in the same spec and must not leak into a US1 task."""
        block = _block(feature)

        assert "A schedule can be set per report" not in block
        assert "Scheduled exports" not in block

    def test_requirements_follow_the_declared_user_story_column(self, feature: Path) -> None:
        block = _block(feature)

        assert "R1" in block and "R2" in block
        assert "R3" not in block, "R3 is declared against US2 and is not this task's"

    def test_cross_cutting_sections_are_named_not_attributed(self, feature: Path) -> None:
        """NFR and Out of Scope carry no story mapping, so they are pointers."""
        block = _block(feature)

        assert "Non-Functional Requirements" in block
        assert "Out of Scope" in block
        assert "No new infrastructure service" not in block, (
            "an unmapped requirement must not be copied in as though it were this task's"
        )

    def test_granularity_is_disclosed(self, feature: Path) -> None:
        assert "user-story level" in _block(feature)


class TestUnresolvedIsDisclosed:
    def test_task_without_a_story_tag(self, feature: Path) -> None:
        block = _block(feature, "T003")

        assert "declares no [USn] story tag" in block
        assert "incomplete context, not an absence of constraints" in block

    def test_story_tag_with_no_matching_section(self, feature: Path) -> None:
        block = _block(feature, "T004")

        assert "US9" in block and "has no '### US9:' section" in block

    def test_no_sibling_spec(self, tmp_path: Path) -> None:
        directory = tmp_path / "specs" / "lonely"
        directory.mkdir(parents=True)
        (directory / "tasks.md").write_text(TASKS, encoding="utf-8")
        assert not (directory / "spec.md").exists(), "fixture must omit the spec"

        block = CTX.render(CTX.resolve(directory / "tasks.md", "T001"), "f")

        assert "no spec.md beside" in block
        assert "Reference source:** none resolved" in block


class TestTaskWordingAuthority:
    def test_a_proposal_is_not_declared_replaceable_by_the_block(self, feature: Path) -> None:
        """#856's distinction survives: the block does not rule on the line."""
        block = _block(feature, "T001")

        assert '"Use a background queue so the page stays responsive"' in block
        assert "Resolve its authority against the sections above" in block

    def test_an_explicit_mechanism_constraint_is_not_labelled_revisable(
        self, feature: Path
    ) -> None:
        """A task line CAN carry a binding constraint; the block must not demote it."""
        block = _block(feature, "T005")

        assert "Must use PostgreSQL" in block
        assert "revisable" not in block.lower(), (
            "the block must not label task wording replaceable - that is the consumer's "
            "resolution against the source, not a rendering decision"
        )


class TestFreshness:
    def _issue_body(self, feature: Path, task: str = "T001") -> str:
        return "Auto-created from specs/exports/tasks.md.\n\n" + _block(feature, task)

    def test_unchanged_source_reads_current(self, feature: Path, tmp_path: Path) -> None:
        state, _ = CTX.check(self._issue_body(feature), tmp_path)

        assert state == "current"

    def test_change_inside_the_mapped_sections(self, feature: Path, tmp_path: Path) -> None:
        body = self._issue_body(feature)
        (feature / "spec.md").write_text(
            SPEC.replace("within 200ms", "within 100ms"), encoding="utf-8"
        )

        state, detail = CTX.check(body, tmp_path)

        assert state == "changed-in-scope"
        assert any("not a ruling that acceptance changed" in line for line in detail)

    def test_change_outside_the_story_is_reported_as_such(
        self, feature: Path, tmp_path: Path
    ) -> None:
        """A cross-cutting constraint change is visible without invented relevance."""
        body = self._issue_body(feature)
        (feature / "spec.md").write_text(
            SPEC.replace("No new infrastructure service", "One managed queue is allowed"),
            encoding="utf-8",
        )

        state, detail = CTX.check(body, tmp_path)

        assert state == "changed-outside-scope"
        assert any("nothing here claims it is relevant" in line for line in detail)

    def test_irrelevant_story_only_change_is_also_outside_scope(
        self, feature: Path, tmp_path: Path
    ) -> None:
        body = self._issue_body(feature)
        (feature / "spec.md").write_text(
            SPEC.replace("A schedule can be set per report", "A schedule can be set per user"),
            encoding="utf-8",
        )

        state, _ = CTX.check(body, tmp_path)

        assert state == "changed-outside-scope"

    def test_missing_source_is_named(self, feature: Path, tmp_path: Path) -> None:
        body = self._issue_body(feature)
        (feature / "spec.md").unlink()
        assert not (feature / "spec.md").exists(), "fixture must remove the source"

        state, _ = CTX.check(body, tmp_path)

        assert state == "source-missing"

    def test_issue_without_a_block_is_not_a_fault(self, tmp_path: Path) -> None:
        """Lightweight issues stay first-class: no block is a normal state."""
        state, _ = CTX.check("A plain issue body with its own acceptance.\n", tmp_path)

        assert state == "absent"


class TestRecordedRevision:
    def test_a_structured_record_is_surfaced_but_not_judged(
        self, feature: Path, tmp_path: Path
    ) -> None:
        body = _block(feature) + "\n\nAcceptance-revision: source-digest=deadbeef01 ref=#99\n"

        _, detail = CTX.check(body, tmp_path)

        joined = " ".join(detail)
        assert "recorded revision" in joined
        assert "does not judge whether it" in joined

    def test_free_text_acknowledgement_is_not_a_record(
        self, feature: Path, tmp_path: Path
    ) -> None:
        body = _block(feature) + "\n\nWe acknowledged the new requirement in standup.\n"

        _, detail = CTX.check(body, tmp_path)

        assert not any("recorded revision" in line for line in detail)


class TestRefreshSafety:
    def test_text_outside_the_block_is_preserved(self, feature: Path) -> None:
        body = (
            "Human notes at the top.\n\n"
            + _block(feature)
            + "\nA human decision written afterwards.\n"
        )
        (feature / "spec.md").write_text(
            SPEC.replace("within 200ms", "within 100ms"), encoding="utf-8"
        )

        updated, message = CTX.refresh(body, _block(feature))

        assert updated is not None, message
        assert "Human notes at the top." in updated
        assert "A human decision written afterwards." in updated
        assert "within 100ms" in updated

    def test_an_edit_inside_the_block_refuses_and_changes_nothing(
        self, feature: Path
    ) -> None:
        """Delimiters mark where generated text began, not that it is untouched."""
        body = _block(feature).replace("200ms", "500ms")
        assert "500ms" in body, "fixture must carry the in-block edit under test"

        updated, message = CTX.refresh(body, _block(feature))

        assert updated is None
        assert "refused" in message and "edited" in message

    def test_duplicate_boundaries_refuse(self, feature: Path) -> None:
        body = _block(feature) + "\n" + _block(feature)

        updated, message = CTX.refresh(body, _block(feature))

        assert updated is None
        assert "duplicate" in message

    def test_a_truncated_block_refuses_rather_than_rewriting(self, feature: Path) -> None:
        body = _block(feature).replace(CTX.BLOCK_END, "")
        assert CTX.BLOCK_END not in body, "fixture must be missing its end boundary"

        updated, message = CTX.refresh(body, _block(feature))

        assert updated is None
        assert "missing" in message

    def test_an_issue_with_no_block_gains_one_additively(self, feature: Path) -> None:
        """A pre-#858 issue may receive its first block; its body is preserved."""
        body = "Auto-created from specs/exports/tasks.md.\n\nDepends on: T002\n"

        updated, message = CTX.refresh(body, _block(feature))

        assert updated is not None
        assert updated.startswith(body.rstrip("\n"))
        assert "attached" in message

    def test_an_unchanged_rerun_is_byte_identical(self, feature: Path) -> None:
        body = "Top.\n\n" + _block(feature) + "\nBottom.\n"

        updated, message = CTX.refresh(body, _block(feature))

        assert updated == body
        assert "unchanged" in message

    def test_a_refused_refresh_can_be_retried_after_the_edit_moves_out(
        self, feature: Path
    ) -> None:
        """Failure then retry must not corrupt the body along the way."""
        edited = _block(feature).replace("200ms", "500ms")
        first, _ = CTX.refresh(edited, _block(feature))
        assert first is None

        recovered = "A human note moved outside.\n\n" + _block(feature)
        second, message = CTX.refresh(recovered, _block(feature))

        assert second is not None, message
        assert "A human note moved outside." in second


class TestPortableAcrossCheckouts:
    """The cache must be re-resolvable by whoever RECEIVES the issue."""

    def test_a_consumer_checks_its_own_checkout_not_the_producers(
        self, tmp_path: Path
    ) -> None:
        """Persisting the producer's path made the consumer check the wrong tree.

        Producer A renders, B is a separate clone of the same project, and B's
        acceptance then changes. Reported against B, the answer must describe B -
        even though A still exists on disk with its original content.
        """
        producer = tmp_path / "A"
        (producer / "specs" / "exports").mkdir(parents=True)
        (producer / "specs" / "exports" / "spec.md").write_text(SPEC, encoding="utf-8")
        (producer / "specs" / "exports" / "tasks.md").write_text(TASKS, encoding="utf-8")
        body = CTX.render(
            CTX.resolve(producer / "specs" / "exports" / "tasks.md", "T001", producer),
            "specs/exports/tasks.md",
        )

        consumer = tmp_path / "B"
        (consumer / "specs" / "exports").mkdir(parents=True)
        (consumer / "specs" / "exports" / "spec.md").write_text(
            SPEC.replace("within 200ms", "within 100ms"), encoding="utf-8"
        )
        (consumer / "specs" / "exports" / "tasks.md").write_text(TASKS, encoding="utf-8")
        assert (producer / "specs" / "exports" / "spec.md").read_text().count("200ms") == 1, (
            "the producer checkout must still hold the ORIGINAL text, or this proves nothing"
        )

        state, _ = CTX.check(body, consumer)

        assert state == "changed-in-scope", (
            "the check followed the producer's path instead of the consumer's root"
        )

    def test_a_path_outside_the_root_is_disclosed(self, tmp_path: Path) -> None:
        outside = tmp_path / "elsewhere" / "exports"
        outside.mkdir(parents=True)
        (outside / "spec.md").write_text(SPEC, encoding="utf-8")
        (outside / "tasks.md").write_text(TASKS, encoding="utf-8")
        root = tmp_path / "project"
        root.mkdir()

        block = CTX.render(CTX.resolve(outside / "tasks.md", "T001", root), "f")

        assert "lies outside the project root" in block


class TestTaskSideChanges:
    """The task line is a governing input, not just an index into the spec."""

    def test_a_changed_story_tag_is_not_reported_as_current(self, feature: Path, tmp_path: Path) -> None:
        body = "Top.\n\n" + _block(feature, "T001")
        (feature / "tasks.md").write_text(
            TASKS.replace(
                "- [ ] **T001** [US1] Use a background queue",
                "- [ ] **T001** [US2] Use a background queue",
            ),
            encoding="utf-8",
        )
        assert "spec.md" in [p.name for p in feature.iterdir()], "spec is untouched here"

        state, detail = CTX.check(body, tmp_path)

        assert state == "changed-task"
        assert any("[USn] tag" in line for line in detail)

    def test_changed_task_wording_is_not_reported_as_current(
        self, feature: Path, tmp_path: Path
    ) -> None:
        body = "Top.\n\n" + _block(feature, "T005")
        (feature / "tasks.md").write_text(
            TASKS.replace("Must use PostgreSQL", "May use any database"), encoding="utf-8"
        )

        state, _ = CTX.check(body, tmp_path)

        assert state == "changed-task", (
            "a task line that stopped carrying its constraint must not read as current"
        )

    def test_a_missing_tasks_file_is_named(self, feature: Path, tmp_path: Path) -> None:
        body = "Top.\n\n" + _block(feature, "T001")
        (feature / "tasks.md").unlink()
        assert not (feature / "tasks.md").exists(), "fixture must remove the tasks file"

        state, _ = CTX.check(body, tmp_path)

        assert state == "tasks-missing"


class TestMetadataIntegrity:
    def test_editing_the_task_field_is_detected(self, feature: Path, tmp_path: Path) -> None:
        """Covering only visible text left the identity metadata rewritable."""
        body = _block(feature, "T001").replace("task: T001", "task: T999")
        assert "task: T999" in body, "fixture must carry the metadata edit under test"

        state, _ = CTX.check(body, tmp_path)
        updated, message = CTX.refresh(body, _block(feature, "T001"))

        assert state == "block-edited"
        assert updated is None and "edited" in message

    def test_a_missing_required_field_refuses(self, feature: Path) -> None:
        body = "\n".join(
            line for line in _block(feature).splitlines() if not line.startswith("source:")
        )
        assert "\nsource: " not in body, "fixture must omit the header field under test"

        updated, message = CTX.refresh(body, _block(feature))

        assert updated is None and "missing metadata" in message

    def test_refreshing_with_another_tasks_block_refuses(self, feature: Path) -> None:
        body = "Top.\n\n" + _block(feature, "T001")

        updated, message = CTX.refresh(body, _block(feature, "T002"))

        assert updated is None
        assert "identity mismatch" in message


class TestRealTemplateShape:
    """The simplified fixture hid a defect the shipped template exposes."""

    def test_a_horizontal_rule_is_not_an_acceptance_item(self, tmp_path: Path) -> None:
        real = ROOT / ".specify" / "specs" / "wave-6-polish-quality-dx"
        if not (real / "tasks.md").is_file():
            pytest.skip("the in-tree reference spec is no longer present")

        resolution = CTX.resolve(real / "tasks.md", "T001", ROOT)

        assert resolution.acceptance, "the reference task should resolve some acceptance"
        assert all(
            item.strip(" -*_") for _, item in resolution.acceptance
        ), f"a separator was read as an acceptance item: {resolution.acceptance}"

    def test_a_fenced_example_does_not_declare_a_story(self, tmp_path: Path) -> None:
        directory = tmp_path / "specs" / "fenced"
        directory.mkdir(parents=True)
        (directory / "tasks.md").write_text(
            "- [ ] **T001** [US1] Real task\n", encoding="utf-8"
        )
        (directory / "spec.md").write_text(
            "# S\n\n```\n### US1: Example inside a fence\n\n"
            "**Acceptance Criteria:**\n- [ ] Sample only\n```\n",
            encoding="utf-8",
        )

        block = CTX.render(CTX.resolve(directory / "tasks.md", "T001", tmp_path), "f")

        assert "Sample only" not in block
        assert "has no '### US1:' section" in block

    def test_a_duplicated_story_is_disclosed_not_chosen(self, tmp_path: Path) -> None:
        directory = tmp_path / "specs" / "dup"
        directory.mkdir(parents=True)
        (directory / "tasks.md").write_text(
            "- [ ] **T001** [US1] Real task\n", encoding="utf-8"
        )
        (directory / "spec.md").write_text(
            "# S\n\n### US1: First\n\n**Acceptance Criteria:**\n- [ ] One\n\n"
            "### US1: Second\n\n**Acceptance Criteria:**\n- [ ] Two\n",
            encoding="utf-8",
        )

        block = CTX.render(CTX.resolve(directory / "tasks.md", "T001", tmp_path), "f")

        assert "declared 2 times" in block
        assert "One" not in block and "Two" not in block


class TestBounded:
    def test_a_huge_outcome_does_not_produce_an_unbounded_block(
        self, tmp_path: Path
    ) -> None:
        directory = tmp_path / "specs" / "big"
        directory.mkdir(parents=True)
        (directory / "tasks.md").write_text(
            "- [ ] **T001** [US1] Do it\n", encoding="utf-8"
        )
        (directory / "spec.md").write_text(
            "# S\n\n### US1: Huge\n\n" + ("padding " * 4000) + "\n\n"
            "**Acceptance Criteria:**\n- [ ] Something\n",
            encoding="utf-8",
        )

        block = CTX.render(CTX.resolve(directory / "tasks.md", "T001", tmp_path), "f")

        assert len(block) <= CTX.MAX_BLOCK_CHARS + 1000, f"block is {len(block)} chars"
        assert "shortened" in block or "INCOMPLETE" in block


class TestRefreshWorkflowCli:
    """The documented existing-issue workflow, driven through the real CLI.

    `flow:wave` Phase 1 tells an orchestrator to fetch the body, run `refresh`, and
    write back only on exit 0. These pin that contract at the process boundary: a
    success prints a complete replacement body on stdout, and a refusal prints
    nothing to stdout and exits non-zero, so a `gh issue edit` guarded on exit status
    cannot write a half-formed body.
    """

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
        )

    def test_a_pre_858_issue_gains_its_block_and_keeps_its_body(
        self, feature: Path, tmp_path: Path
    ) -> None:
        body_file = tmp_path / "body.md"
        body_file.write_text(
            "Auto-created from specs/exports/tasks.md (T001).\n\nDepends on: T002\n",
            encoding="utf-8",
        )
        assert "speckit-context" not in body_file.read_text(), "fixture must have no block"

        result = self._run(
            "refresh",
            "--body-file", str(body_file),
            "--tasks", str(feature / "tasks.md"),
            "--task", "T001",
            "--feature", "specs/exports/tasks.md",
            "--root", str(tmp_path),
        )

        assert result.returncode == 0, result.stderr
        assert "Depends on: T002" in result.stdout
        assert "speckit-context:v1" in result.stdout
        assert "attached" in result.stderr

    def test_a_refusal_writes_nothing_to_stdout(self, feature: Path, tmp_path: Path) -> None:
        body_file = tmp_path / "edited.md"
        body_file.write_text(_block(feature, "T001", tmp_path).replace("200ms", "500ms"))
        assert "500ms" in body_file.read_text(), "fixture must carry the in-block edit"

        result = self._run(
            "refresh",
            "--body-file", str(body_file),
            "--tasks", str(feature / "tasks.md"),
            "--task", "T001",
            "--feature", "specs/exports/tasks.md",
            "--root", str(tmp_path),
        )

        assert result.returncode == 4
        assert result.stdout == "", (
            "a refusal that still printed a body could be written back by a caller "
            "that checked only for output"
        )
        assert "refused" in result.stderr


class TestFencedTasksAndDuplicates:
    """Finding 4's boundary: tasks.md needs the same fence handling as the spec."""

    def test_a_fenced_example_task_does_not_outrank_the_real_one(
        self, tmp_path: Path
    ) -> None:
        directory = tmp_path / "specs" / "fencedtasks"
        directory.mkdir(parents=True)
        (directory / "spec.md").write_text(SPEC, encoding="utf-8")
        (directory / "tasks.md").write_text(
            "# Tasks\n\n```markdown\n- [ ] **T001** [US2] Example from the docs\n```\n\n"
            + TASKS,
            encoding="utf-8",
        )

        resolution = CTX.resolve(directory / "tasks.md", "T001", tmp_path)

        assert "Use a background queue" in resolution.task_wording, (
            f"the fenced sample won: {resolution.task_wording!r}"
        )
        assert resolution.outcomes and resolution.outcomes[0][0] == "US1"

    def test_an_indented_fence_is_still_a_fence(self, tmp_path: Path) -> None:
        directory = tmp_path / "specs" / "indented"
        directory.mkdir(parents=True)
        (directory / "spec.md").write_text(SPEC, encoding="utf-8")
        (directory / "tasks.md").write_text(
            "# Tasks\n\n  ```\n  - [ ] **T001** [US2] Indented example\n  ```\n\n" + TASKS,
            encoding="utf-8",
        )

        resolution = CTX.resolve(directory / "tasks.md", "T001", tmp_path)

        assert "Use a background queue" in resolution.task_wording

    def test_a_task_declared_twice_is_disclosed(self, tmp_path: Path) -> None:
        directory = tmp_path / "specs" / "duptask"
        directory.mkdir(parents=True)
        (directory / "spec.md").write_text(SPEC, encoding="utf-8")
        (directory / "tasks.md").write_text(
            "- [ ] **T001** [US1] First declaration\n"
            "- [ ] **T001** [US2] Second declaration\n",
            encoding="utf-8",
        )

        block = CTX.render(CTX.resolve(directory / "tasks.md", "T001", tmp_path), "f")

        assert "declared 2 times" in block


class TestSourceIsReferenceNotOverride:
    """Finding 8: newer bytes do not silently supersede an accepted decision."""

    def test_the_block_does_not_claim_the_source_governs(self, feature: Path) -> None:
        block = _block(feature)

        assert "the source governs" not in block
        assert "does not by itself override" in block

    def test_a_decision_naming_the_cached_version_is_flagged_as_predating(
        self, feature: Path, tmp_path: Path
    ) -> None:
        block = _block(feature)
        cached = [
            line.split(": ", 1)[1]
            for line in block.splitlines()
            if line.startswith("source-digest: ")
        ][0]
        body = block + f"\n\nAcceptance-revision: source-digest={cached} ref=#42\n"
        (feature / "spec.md").write_text(
            SPEC.replace("within 200ms", "within 100ms"), encoding="utf-8"
        )

        _, detail = CTX.check(body, tmp_path)

        joined = " ".join(detail)
        assert "THIS BLOCK CACHED" in joined
        assert "predates the change" in joined

    def test_a_decision_record_survives_a_refresh(self, feature: Path) -> None:
        record = "Acceptance-revision: source-digest=abc123def456 ref=#42"
        body = _block(feature) + f"\n\n{record}\n"
        (feature / "spec.md").write_text(
            SPEC.replace("within 200ms", "within 100ms"), encoding="utf-8"
        )

        updated, message = CTX.refresh(body, _block(feature))

        assert updated is not None, message
        assert record in updated, "a refresh must not drop the decision record"
        assert "within 100ms" in updated
