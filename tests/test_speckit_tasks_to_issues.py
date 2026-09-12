"""Behavioural tests for the speckit task-to-issue converter (issues #700, #857).

`scripts/speckit-tasks-to-issues.sh` turns a spec-kit tasks.md into one GitHub
issue per task. #857 fixed what it could not see and what it silently guessed:

  * the BOLD task id `.specify/templates/tasks-template.md` actually writes was
    unreadable, so the converter finished successfully having created nothing
  * a task was identified by a bare `T001` found in any issue title, so one
    feature's T001 made every other feature's T001 look already-filed
  * a failed `gh issue list` was swallowed and read as an empty inventory
  * task-like lines that did not parse were skipped without a word

Identity is now the pair (feature, task id), recorded as an HTML comment in the
issue body, with the feature half taken from the tasks file's repository-relative
path. Pre-#857 issues carry no marker, so the only feature evidence they have is
the `Auto-created from <path>` line this script has always written - which is
used where it exists and reported as unresolved where it does not. A description
match is NEVER treated as provenance: two features routinely share both a task
number and its wording.

The `gh` stub models list/create/view/edit against a JSON state file and pipes
`issue list` through the REAL `jq` with the filter the script supplies, so these
tests exercise the script's own jq program and the producer/reader separator
agreement rather than a re-implementation of either.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "speckit-tasks-to-issues.sh"

# These tests drive real `git`, `bash` and `jq` subprocesses. The Woodpecker
# `validate` step runs in `uv:python3.11-bookworm-slim`, which ships bash but NOT
# git, so without this guard the module errors and turns CI red (core directive;
# #602).
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None
    or shutil.which("bash") is None
    or shutil.which("jq") is None,
    reason="requires git, bash and jq on PATH",
)

GH_STUB = r'''#!/usr/bin/env python3
"""Stub gh: issue list/create/view/edit over a JSON state file."""
import json, os, subprocess, sys
from pathlib import Path

STATE = Path(os.environ["GH_STUB_STATE"])
argv = sys.argv[1:]

def load():
    return json.loads(STATE.read_text())

def save(state):
    STATE.write_text(json.dumps(state))

if argv[:2] == ["issue", "list"]:
    if os.environ.get("GH_STUB_LIST_FAIL") == "1":
        sys.stderr.write("gh: API rate limit exceeded for this host\n")
        sys.exit(1)
    state = load()
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 30
    # Model --state the way gh does: without it, only OPEN issues come back. A
    # dedup scan that forgot `--state all` would therefore stop seeing closed
    # tasks here, exactly as it would against real gh.
    wanted = argv[argv.index("--state") + 1].upper() if "--state" in argv else "OPEN"
    issues = [
        i for i in state["issues"]
        if wanted == "ALL" or i.get("state", "OPEN").upper() == wanted
    ]
    rows = [{k: i[k] for k in ("number", "title", "body")} for i in issues[:limit]]
    jq_filter = argv[argv.index("--jq") + 1] if "--jq" in argv else "."
    done = subprocess.run(
        ["jq", "-r", jq_filter], input=json.dumps(rows), capture_output=True, text=True
    )
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    sys.exit(done.returncode)

if argv[:2] == ["issue", "create"]:
    state = load()
    number = state["next"]
    state["next"] = number + 1
    state["issues"].append(
        {
            "number": number,
            "title": argv[argv.index("--title") + 1],
            "body": argv[argv.index("--body") + 1],
        }
    )
    save(state)
    print("https://github.com/acme/widget/issues/%d" % number)
    sys.exit(0)

if argv[:2] == ["issue", "view"]:
    for issue in load()["issues"]:
        if str(issue["number"]) == argv[2]:
            print(issue["body"])
            sys.exit(0)
    sys.stderr.write("gh: not found\n")
    sys.exit(1)

if argv[:2] == ["issue", "edit"]:
    if os.environ.get("GH_STUB_EDIT_FAIL") == "1":
        sys.stderr.write("gh: could not update issue\n")
        sys.exit(1)
    state = load()
    source = argv[argv.index("--body-file") + 1]
    body = sys.stdin.read() if source == "-" else Path(source).read_text()
    for issue in state["issues"]:
        if str(issue["number"]) == argv[2]:
            issue["body"] = body
            save(state)
            sys.exit(0)
    sys.stderr.write("gh: not found\n")
    sys.exit(1)

sys.exit(0)
'''

# What the shipped template writes: bold id, story tag, and the comma story form
# from its own T007 line.
BOLD_TASKS = "- [ ] **T001** [US1] Build the widget\n"


def _marker(feature: str, tid: str) -> str:
    return f"<!-- speckit-task:v1:{feature}:{tid} -->"


def _provenance(tasks_path: str, tid: str) -> str:
    return f"Auto-created from {tasks_path} ({tid}) by CPP speckit-tasks-to-issues."


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def project(tmp_path: Path):
    """A git repo with a GitHub origin, a stub `gh` on PATH, and issue state."""

    def _make(tasks: dict[str, str], issues: list[dict] | None = None, next_number: int = 100):
        repo = tmp_path / "repo"
        repo.mkdir(exist_ok=True)
        _git(repo, "init", "-q")
        _git(repo, "remote", "add", "origin", "https://github.com/acme/widget.git")
        for rel, text in tasks.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        bindir = tmp_path / "bin"
        bindir.mkdir(exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(GH_STUB, encoding="utf-8")
        gh.chmod(0o755)

        state = tmp_path / "state.json"
        state.write_text(json.dumps({"next": next_number, "issues": issues or []}))
        return repo, bindir, state

    return _make


def _run(
    repo: Path,
    bindir: Path,
    state: Path,
    *args: str,
    list_fails: bool = False,
    edit_fails: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HOME": str(repo.parent),
        "GH_STUB_STATE": str(state),
    }
    if list_fails:
        env["GH_STUB_LIST_FAIL"] = "1"
    if edit_fails:
        env["GH_STUB_EDIT_FAIL"] = "1"
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def _issues(state: Path) -> list[dict]:
    return json.loads(state.read_text())["issues"]


class TestParsing:
    """Acceptance 1 and 6: read what the templates write; never a silent zero."""

    def test_bold_task_id_from_the_shipped_template_is_read(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": BOLD_TASKS})
        assert "**T001**" in BOLD_TASKS, "fixture must use the bold form under test"

        result = _run(repo, bindir, state, "--dry-run", "--tasks", "a/tasks.md")

        assert result.returncode == 0, result.stderr
        assert "would create: T001 (a/tasks.md): Build the widget" in result.stdout

    def test_plain_and_bold_ids_produce_the_same_task(self, project) -> None:
        repo, bindir, state = project(
            {"bold/tasks.md": BOLD_TASKS, "plain/tasks.md": "- [ ] T001: [US1] Build the widget\n"}
        )

        bold = _run(repo, bindir, state, "--dry-run", "--tasks", "bold/tasks.md", "--feature", "f")
        plain = _run(repo, bindir, state, "--dry-run", "--tasks", "plain/tasks.md", "--feature", "f")

        assert bold.returncode == plain.returncode == 0
        assert "would create: T001 (f): Build the widget" in bold.stdout
        assert "would create: T001 (f): Build the widget" in plain.stdout

    def test_comma_story_tag_does_not_leak_into_the_title(self, project) -> None:
        """The template's own T007 line carries `[US1,US2]`."""
        repo, bindir, state = project(
            {"a/tasks.md": "- [ ] **T007** [US1,US2] Integration testing\n"}
        )

        result = _run(repo, bindir, state, "--dry-run", "--tasks", "a/tasks.md")

        assert "would create: T007 (a/tasks.md): Integration testing" in result.stdout
        assert "US1,US2" not in result.stdout

    def test_malformed_t_number_fails_with_a_line_number(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": "- [ ] T1: too few digits\n"})

        result = _run(repo, bindir, state, "--dry-run", "--tasks", "a/tasks.md")

        assert result.returncode == 3
        assert "a/tasks.md:1" in result.stderr
        assert "malformed T-number" in result.stderr
        assert "0 to create" not in result.stdout

    @pytest.mark.parametrize(
        "clause, offending",
        [
            ("T002, T1", "T1"),        # partly invalid: the bad half used to vanish
            ("T0020", "T0020"),        # over-long: used to match its own first four chars
            ("T1", "T1"),              # nothing valid at all
            ("nothing", "nothing"),    # not a task id in any spelling
        ],
    )
    def test_unreadable_dependency_tokens_are_diagnosed(
        self, project, clause: str, offending: str
    ) -> None:
        """Whole tokens are validated, never substrings.

        Extracting `T[0-9]{3}` out of the clause accepted two corruptions in
        silence: `T002, T1` wrote a partial edge and dropped the invalid half,
        and `T0020` matched its own first four characters and wrote an edge to
        T002 - a dependency nobody declared. A fabricated edge is worse than a
        missing one, because the planner treats it as a real constraint.

        These inputs also cover the earlier failure this replaced: `grep` exits 1
        when a clause names nothing valid, and under `set -e` that took the run
        down with exit 1 and no message at all. Every case here must exit 3 WITH
        a source line.
        """
        repo, bindir, state = project(
            {
                "a/tasks.md": (
                    f"- [ ] **T001** Build A (depends on {clause})\n"
                    "- [ ] **T002** Build B\n"
                )
            }
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert result.returncode == 3, result.stdout + result.stderr
        assert "a/tasks.md:1" in result.stderr
        assert offending in result.stderr
        assert _issues(state) == [], "a parse failure must happen before any write"

    @pytest.mark.parametrize(
        "clause, expected",
        [
            ("T002", ["#101"]),
            ("T002, T003", ["#101", "#102"]),
            ("T002 T003", ["#101", "#102"]),
            ("T002 and T003", ["#101", "#102"]),
            ("T002, T002", ["#101"]),
        ],
    )
    def test_supported_dependency_spellings_still_write_their_edges(
        self, project, clause: str, expected: list[str]
    ) -> None:
        """Control: tightening the parse must not narrow what already worked."""
        repo, bindir, state = project(
            {
                "a/tasks.md": (
                    f"- [ ] **T001** Build A (depends on {clause})\n"
                    "- [ ] **T002** Build B\n"
                    "- [ ] **T003** Build C\n"
                )
            }
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert result.returncode == 0, result.stderr
        body = {i["number"]: i["body"] for i in _issues(state)}[100]
        edges = [
            line.split()[-1] for line in body.splitlines() if line.startswith("- Blocked by")
        ]
        assert edges == expected

    def test_file_with_no_tasks_is_an_error_not_a_success(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": "# Tasks\n\nNothing here yet.\n"})

        result = _run(repo, bindir, state, "--dry-run", "--tasks", "a/tasks.md")

        assert result.returncode == 3
        assert "no tasks found" in result.stderr

    def test_non_task_checkbox_is_reported_but_does_not_fail_the_run(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": BOLD_TASKS + "- [ ] Checkpoint verified\n"})

        result = _run(repo, bindir, state, "--dry-run", "--tasks", "a/tasks.md")

        assert result.returncode == 0, result.stderr
        assert "Checkpoint verified" in result.stderr
        assert "would create: T001 (a/tasks.md): Build the widget" in result.stdout


class TestFeatureScopedIdentity:
    """Acceptance 2 and 3: T001 belongs to a feature, and re-runs are stable."""

    def test_two_features_with_identical_t001_get_distinct_issues(self, project) -> None:
        """The wording is identical on purpose: description is not provenance."""
        tasks = "- [ ] **T001** [US1] Add tests\n"
        repo, bindir, state = project({"a/tasks.md": tasks, "b/tasks.md": tasks})

        first = _run(repo, bindir, state, "--tasks", "a/tasks.md")
        second = _run(repo, bindir, state, "--tasks", "b/tasks.md")

        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr
        assert "create T001" in second.stdout, (
            "feature b's T001 was swallowed by feature a's - the #857 collision"
        )
        numbers = [i["number"] for i in _issues(state)]
        assert len(numbers) == len(set(numbers)) == 2

    def test_rerun_creates_nothing_and_is_stable(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": BOLD_TASKS})
        _run(repo, bindir, state, "--tasks", "a/tasks.md")

        again = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert again.returncode == 0, again.stderr
        assert "skip  T001" in again.stdout
        assert len(_issues(state)) == 1

    def test_closed_issues_still_count_as_filed(self, project) -> None:
        """A finished task stays filed: the scan must ask for closed issues too.

        The stub returns only OPEN issues unless the caller passes `--state all`,
        so this fixture fails if that flag is ever dropped - which is the whole
        claim the test makes. A fixture with no state would pass either way and
        prove nothing.
        """
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {
                    "number": 7,
                    "title": "T001 (a/tasks.md): Build the widget",
                    "body": _marker("a/tasks.md", "T001"),
                    "state": "CLOSED",
                }
            ],
        )
        assert _issues(state)[0]["state"] == "CLOSED", (
            "fixture must be CLOSED, or it does not exercise the --state all query"
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert result.returncode == 0, result.stderr
        assert "skip  T001 (issue #7" in result.stdout
        assert len(_issues(state)) == 1, "a closed task must not be filed again"

    def test_explicit_feature_flag_overrides_the_path(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": BOLD_TASKS})

        _run(repo, bindir, state, "--tasks", "a/tasks.md", "--feature", "widget-v2")

        assert _marker("widget-v2", "T001") in _issues(state)[0]["body"]


class TestLegacyIdentity:
    """Acceptance 4: adopt on evidence, diagnose ambiguity, never guess."""

    def test_legacy_issue_from_this_tasks_file_is_adopted(self, project) -> None:
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {
                    "number": 50,
                    "title": "T001: Build the widget",
                    "body": _provenance("a/tasks.md", "T001"),
                }
            ],
        )
        assert "speckit-task:v1" not in _issues(state)[0]["body"], (
            "fixture must be a PRE-marker issue, or it tests the marker path instead"
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert result.returncode == 0, result.stderr
        assert "skip  T001 (issue #50" in result.stdout
        assert "recorded source path" in result.stdout
        assert len(_issues(state)) == 1

    def test_legacy_issue_from_another_tasks_file_does_not_block_this_one(
        self, project
    ) -> None:
        """A body naming a different source is a known other feature, not a claim."""
        repo, bindir, state = project(
            {"b/tasks.md": "- [ ] **T001** [US1] Add tests\n"},
            issues=[
                {
                    "number": 50,
                    "title": "T001: Add tests",
                    "body": _provenance("a/tasks.md", "T001"),
                }
            ],
        )

        result = _run(repo, bindir, state, "--tasks", "b/tasks.md")

        assert result.returncode == 0, result.stderr
        assert "create T001" in result.stdout
        assert len(_issues(state)) == 2

    def test_legacy_issue_with_no_provenance_is_reported_not_guessed(self, project) -> None:
        repo, bindir, state = project(
            {"b/tasks.md": "- [ ] **T001** [US1] Add tests\n"},
            issues=[{"number": 50, "title": "T001: Add tests", "body": "Filed by hand.\n"}],
        )
        body = _issues(state)[0]["body"]
        assert "speckit-task:v1" not in body and "Auto-created from" not in body, (
            "fixture must carry NO feature evidence, or the ambiguity under test cannot arise"
        )

        result = _run(repo, bindir, state, "--tasks", "b/tasks.md")

        assert result.returncode == 5
        assert "unresolved identity" in result.stderr
        assert "#50" in result.stderr
        assert len(_issues(state)) == 1, "an unresolved identity must create nothing"

    def test_two_markers_for_the_same_task_are_ambiguous(self, project) -> None:
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {"number": 50, "title": "T001 (a/tasks.md): x", "body": _marker("a/tasks.md", "T001")},
                {"number": 51, "title": "T001 (a/tasks.md): y", "body": _marker("a/tasks.md", "T001")},
            ],
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert result.returncode == 5
        assert "claim this feature's task" in result.stderr
        assert "#50" in result.stderr and "#51" in result.stderr

    def test_a_marker_and_a_provenance_claim_on_different_issues_are_ambiguous(
        self, project
    ) -> None:
        """Two claims of DIFFERENT kinds are still two claims.

        Counting each kind separately reads one marker and one recorded-source
        issue as "one of each, no conflict" and silently picks the marker, which
        is the guess this criterion forbids. The claimants are counted across
        both kinds instead.
        """
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {"number": 7, "title": "T001 (f): x", "body": _marker("f", "T001")},
                {
                    "number": 8,
                    "title": "T001: legacy",
                    "body": _provenance("a/tasks.md", "T001"),
                },
            ],
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md", "--feature", "f")

        assert result.returncode == 5, result.stdout + result.stderr
        assert "#7" in result.stderr and "#8" in result.stderr
        assert len(_issues(state)) == 2, "an unresolved identity must create nothing"

    def test_a_feature_name_that_is_a_prefix_of_another_does_not_match(
        self, project
    ) -> None:
        """`--feature f` must not adopt `f:other`'s task.

        A prefix test on `speckit-task:v1:<feature>:` accepts any feature whose
        name starts with this one and contains a colon, handing one feature's
        issue to another - the identity collision this change exists to remove,
        reintroduced by the matching rule itself.
        """
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {"number": 7, "title": "T001 (f:other): x", "body": _marker("f:other", "T001")}
            ],
        )
        assert "f:other" in _issues(state)[0]["body"], (
            "fixture marker must name a DIFFERENT feature that extends this one"
        )

        result = _run(repo, bindir, state, "--dry-run", "--tasks", "a/tasks.md", "--feature", "f")

        assert result.returncode == 0, result.stderr
        assert "would create: T001 (f): Build the widget" in result.stdout
        assert "skip  T001" not in result.stdout

    def test_exact_feature_with_a_colon_still_matches_its_own_task(self, project) -> None:
        """Control: the colon-bearing feature name is not simply rejected."""
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {"number": 7, "title": "T001 (f:other): x", "body": _marker("f:other", "T001")}
            ],
        )

        result = _run(
            repo, bindir, state, "--dry-run", "--tasks", "a/tasks.md", "--feature", "f:other"
        )

        assert result.returncode == 0, result.stderr
        assert "skip  T001 (issue #7" in result.stdout


class TestInventoryHonesty:
    """Acceptance 5: an inventory you cannot establish is not an empty one."""

    def test_failed_lookup_refuses_instead_of_refiling(self, project) -> None:
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {
                    "number": 7,
                    "title": "T001 (a/tasks.md): Build the widget",
                    "body": _marker("a/tasks.md", "T001"),
                }
            ],
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md", list_fails=True)

        assert result.returncode == 4
        assert "not an empty one" in result.stderr
        assert len(_issues(state)) == 1, "the already-filed task must not be filed again"

    def test_possibly_truncated_inventory_refuses(self, project) -> None:
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[{"number": n, "title": f"unrelated {n}", "body": ""} for n in (1, 2, 3)],
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md", "--limit", "3")

        assert result.returncode == 4
        assert "may be truncated" in result.stderr
        assert len(_issues(state)) == 3

    def test_empty_field_in_a_record_does_not_shift_the_next_one(self, project) -> None:
        """The #700 property, on the field that is now EMPTY on the ordinary path.

        Every pre-marker issue produces an empty marker field, so the separator's
        empty-field behaviour is no longer a latent concern: under an IFS-whitespace
        separator the empty marker collapses, the provenance path shifts into the
        marker slot, and this legacy issue stops being recognised as this feature's
        - which re-files a task that already has an issue. `\\037` is not IFS
        whitespace, so the empty field survives and the provenance still matches.
        """
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {
                    "number": 50,
                    "title": "T001: Build the widget",
                    "body": _provenance("a/tasks.md", "T001"),
                }
            ],
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert "skip  T001 (issue #50" in result.stdout, (
            "the empty marker field shifted the provenance path out of position - "
            f"the #700 collapse. stdout:\n{result.stdout}"
        )
        assert len(_issues(state)) == 1

    def test_title_containing_whitespace_survives(self, project) -> None:
        """Control: a title carrying embedded tabs still round-trips."""
        repo, bindir, state = project(
            {"a/tasks.md": BOLD_TASKS},
            issues=[
                {
                    "number": 50,
                    "title": "T001:\tBuild\tthe\twidget",
                    "body": _marker("a/tasks.md", "T001"),
                }
            ],
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert result.returncode == 0, result.stderr
        assert "skip  T001" in result.stdout


class TestDependencies:
    """Acceptance 7: correct edges, forward references included, and resumable."""

    FORWARD = (
        "- [ ] **T001** [US1] Build A (depends on T002)\n"
        "- [ ] **T002** [US1] Build B\n"
    )

    def test_forward_reference_resolves_to_an_edge(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": self.FORWARD})

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert result.returncode == 0, result.stderr
        bodies = {i["number"]: i["body"] for i in _issues(state)}
        assert "- Blocked by #101" in bodies[100]
        assert "Depends on: T002" in bodies[100]

    def test_failed_edit_is_reconciled_by_the_next_run(self, project) -> None:
        """The resumability property: created-but-unlinked must not be permanent."""
        repo, bindir, state = project({"a/tasks.md": self.FORWARD})

        broken = _run(repo, bindir, state, "--tasks", "a/tasks.md", edit_fails=True)
        assert broken.returncode == 6, broken.stderr
        bodies = {i["number"]: i["body"] for i in _issues(state)}
        assert "- Blocked by" not in bodies[100], "fixture must leave the edge unwritten"

        repaired = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert repaired.returncode == 0, repaired.stderr
        assert len(_issues(state)) == 2, "reconciliation must not create duplicates"
        bodies = {i["number"]: i["body"] for i in _issues(state)}
        assert "- Blocked by #101" in bodies[100]

    def test_reconciliation_preserves_existing_body_content(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": self.FORWARD})
        _run(repo, bindir, state, "--tasks", "a/tasks.md", edit_fails=True)
        issues = json.loads(state.read_text())
        for issue in issues["issues"]:
            if issue["number"] == 100:
                issue["body"] += "\n\nA human wrote this paragraph.\n"
        state.write_text(json.dumps(issues))

        _run(repo, bindir, state, "--tasks", "a/tasks.md")

        body = {i["number"]: i["body"] for i in _issues(state)}[100]
        assert "A human wrote this paragraph." in body
        assert "- Blocked by #101" in body

    def test_edges_are_not_rewritten_on_a_clean_rerun(self, project) -> None:
        repo, bindir, state = project({"a/tasks.md": self.FORWARD})
        _run(repo, bindir, state, "--tasks", "a/tasks.md")

        again = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert "link  T001" not in again.stdout
        body = {i["number"]: i["body"] for i in _issues(state)}[100]
        assert body.count("- Blocked by #101") == 1

    def test_dependency_outside_this_feature_writes_no_edge(self, project) -> None:
        repo, bindir, state = project(
            {"a/tasks.md": "- [ ] **T001** [US1] Build A (depends on T009)\n"}
        )

        result = _run(repo, bindir, state, "--tasks", "a/tasks.md")

        assert result.returncode == 0, result.stderr
        assert "not a task in this feature" in result.stderr
        assert "- Blocked by" not in _issues(state)[0]["body"]


def test_no_whitespace_ifs_read_remains_in_scripts() -> None:
    """Class guard: no shell reader in scripts/ splits on an IFS-whitespace delimiter.

    The #700 site was the last one (#698 fixed the rest). A new tab- or
    space-delimited `read` fails silently - shifted fields, never an error - so
    the shape is worth pinning rather than rediscovering.
    """
    # `IFS=<value> read` - captures the value in each of the spellings this repo
    # uses: $'..', "..", '..', or bare.
    ifs_read = re.compile(r"""IFS=(\$'[^']*'|"[^"]*"|'[^']*'|\S*)[ \t]+read\b""")

    offenders: list[str] = []
    for script in sorted((ROOT / "scripts").glob("*.sh")):
        for lineno, line in enumerate(
            script.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = ifs_read.search(line)
            if match is None:
                continue
            value = match.group(1)
            # `IFS= read` - the empty-IFS whole-line idiom, correct and common.
            if value == "":
                continue
            if "\\t" in value or "\t" in value or value in ("' '", '" "', " "):
                offenders.append(
                    f"{script.relative_to(ROOT)}:{lineno}: {line.strip()}"
                )

    assert not offenders, (
        "whitespace-IFS read(s) reintroduced (#698/#700):\n" + "\n".join(offenders)
    )
