"""The generated-issue handoff, end to end across its real stages (#861, criterion 1).

Every stage of this path already has isolated coverage: the converter is tested in
`test_speckit_tasks_to_issues.py`, the context helper in `test_speckit_context.py`.
A chain of green isolated tests does not establish that the chain carries anything -
each stage is exercised against inputs a test author wrote, and the thing that
actually travels between stages is a generated issue body nobody re-reads.

So these tests exercise the SHIPPED converter and the SHIPPED helper as
subprocesses, and forward the bytes each stage produces into the next one:

    tasks.md + spec.md  --(real converter)-->  issue body
    issue body          --(real helper)---->   freshness verdict
    issue body          --(real converter re-run, reading it back)-->  stable/stale

Nothing here re-implements selection, identity or digest logic. A handwritten
reconstruction of the production rule is how a test comes to agree with itself, and
it is the mechanism that produced the #860 false positive; where a value has to be
named (an exit code, a marker's spelling) it is named literally, not recomputed.

**Distinct governing promises with a shared task id.** Both features declare `T001`
with IDENTICAL task wording - description is not provenance - while their specs
promise different things. That combination is the point: if feature association
leaked anywhere in the chain, the two issues would still get distinct NUMBERS (which
`test_two_features_with_identical_t001_get_distinct_issues` already pins) while
carrying the wrong promise, and no existing test would see it.

**What these tests do NOT establish.** They mock GitHub, so they say nothing about
real `gh` behaviour, rate limits or API shape. They observe deterministic data
handoff between processes - not an agent's judgment about what it read; that is a
separate criterion with separate evidence. And a `current` verdict is a statement
about BYTES, never a ruling that acceptance did not change.

The `gh` stub here is written independently of the one in
`test_speckit_tasks_to_issues.py` rather than imported from it. They are meant to be
able to disagree: two stubs that share an implementation also share its blind spots,
and agreement between them would then establish nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONVERTER = ROOT / "scripts" / "speckit-tasks-to-issues.sh"
HELPER = ROOT / "scripts" / "speckit-context.py"

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
"""Stub gh for the handoff tests: issue list/create/view over a JSON state file.

Deliberately independent of the converter suite's stub. `issue list` pipes through
the REAL jq with the filter the script supplies, so the script's own jq program and
its field separator are exercised rather than re-implemented.
"""
import json, os, subprocess, sys
from pathlib import Path

STATE = Path(os.environ["GH_STUB_STATE"])
argv = sys.argv[1:]


def load():
    return json.loads(STATE.read_text())


if argv[:2] == ["issue", "list"]:
    state = load()
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 30
    wanted = argv[argv.index("--state") + 1].upper() if "--state" in argv else "OPEN"
    rows = [
        {k: i[k] for k in ("number", "title", "body")}
        for i in state["issues"]
        if wanted == "ALL" or i.get("state", "OPEN").upper() == wanted
    ][:limit]
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
    STATE.write_text(json.dumps(state))
    print("https://github.com/acme/handoff/issues/%d" % number)
    sys.exit(0)

if argv[:2] == ["issue", "view"]:
    for issue in load()["issues"]:
        if str(issue["number"]) == argv[2]:
            print(issue["body"])
            sys.exit(0)
    sys.stderr.write("gh: not found\n")
    sys.exit(1)

if argv[:2] == ["issue", "edit"]:
    state = load()
    source = argv[argv.index("--body-file") + 1]
    body = sys.stdin.read() if source == "-" else Path(source).read_text()
    for issue in state["issues"]:
        if str(issue["number"]) == argv[2]:
            issue["body"] = body
            STATE.write_text(json.dumps(state))
            sys.exit(0)
    sys.stderr.write("gh: not found\n")
    sys.exit(1)

sys.exit(0)
'''

# Identical wording on both features, on purpose: the descriptions must not be what
# tells these two tasks apart.
SHARED_TASK_LINE = "- [ ] **T001** [US1] Add tests\n"

EXPORTS_SPEC = """# Feature Specification: Exports

## User Stories

### US1: Responsive exports [P1]

**As a** analyst,
**I want** the page to stay usable while an export runs,
**So that** I can keep working.

**Acceptance Criteria:**
- [ ] The page responds within 200ms while an export of 50k rows runs

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | Export runs without holding a request thread | Must | US1 |
"""

BILLING_SPEC = """# Feature Specification: Billing

## User Stories

### US1: Refunds settle predictably [P1]

**As a** customer,
**I want** a refund to reach my card on a known schedule,
**So that** I can reconcile my statement.

**Acceptance Criteria:**
- [ ] A refund is credited within one billing cycle

## Requirements

### Functional Requirements

| ID | Requirement | Priority | User Story |
|----|-------------|----------|------------|
| R1 | Refunds are idempotent per charge id | Must | US1 |
"""

# The one sentence each feature promises and the other does not. Asserting on these
# is what distinguishes "two issues exist" from "each issue carries its own promise".
EXPORTS_PROMISE = "The page responds within 200ms while an export of 50k rows runs"
BILLING_PROMISE = "A refund is credited within one billing cycle"

EXPORTS_TASKS = ".specify/specs/exports/tasks.md"
BILLING_TASKS = ".specify/specs/billing/tasks.md"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _install_stub_gh(bindir: Path) -> None:
    bindir.mkdir(parents=True, exist_ok=True)
    stub = bindir / "gh"
    stub.write_text(GH_STUB, encoding="utf-8")
    stub.chmod(0o755)


def _env(repo: Path, bindir: Path, state: Path) -> dict[str, str]:
    return {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HOME": str(repo.parent),
        "GH_STUB_STATE": str(state),
    }


class Handoff:
    """One project, two features, and the real scripts run against it."""

    def __init__(self, repo: Path, bindir: Path, state: Path, converter: Path) -> None:
        self.repo = repo
        self.bindir = bindir
        self.state = state
        self.converter = converter

    def convert(self, tasks: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(self.converter), "--tasks", tasks, *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=_env(self.repo, self.bindir, self.state),
        )

    def check(self, body: str) -> subprocess.CompletedProcess[str]:
        """The helper, invoked exactly as the converter invokes it on a re-run."""
        return subprocess.run(
            ["python3", str(HELPER), "check", "--body-file", "-", "--root", "."],
            cwd=self.repo,
            input=body,
            capture_output=True,
            text=True,
            env=_env(self.repo, self.bindir, self.state),
        )

    def issues(self) -> list[dict]:
        return json.loads(self.state.read_text())["issues"]

    def body_for(self, tasks: str) -> str:
        """The generated body carrying this feature's marker - the travelling bytes."""
        marker = f"<!-- speckit-task:v1:{tasks}:T001 -->"
        matches = [i["body"] for i in self.issues() if marker in i["body"]]
        assert len(matches) == 1, f"expected exactly one issue marked {marker}"
        return matches[0]


@pytest.fixture
def handoff(tmp_path: Path):
    """Two features sharing T001, promising different things."""
    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "remote", "add", "origin", "https://github.com/acme/handoff.git")

    for tasks_rel, spec in ((EXPORTS_TASKS, EXPORTS_SPEC), (BILLING_TASKS, BILLING_SPEC)):
        tasks_path = repo / tasks_rel
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text(SHARED_TASK_LINE, encoding="utf-8")
        (tasks_path.parent / "spec.md").write_text(spec, encoding="utf-8")

    bindir = tmp_path / "bin"
    _install_stub_gh(bindir)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"next": 100, "issues": []}))
    return Handoff(repo, bindir, state, CONVERTER)


class TestEachFeatureCarriesItsOwnPromise:
    """Criterion 1: a shared task id must not merge two features' governing context."""

    def test_the_task_wording_really_is_identical(self, handoff: Handoff) -> None:
        """Guard on the fixture, not the code.

        Every assertion below is only meaningful because the two task lines are
        indistinguishable. If a later edit makes them differ, these tests would keep
        passing while testing something much weaker, so the premise is pinned here
        where the failure names itself.
        """
        exports = (handoff.repo / EXPORTS_TASKS).read_text(encoding="utf-8")
        billing = (handoff.repo / BILLING_TASKS).read_text(encoding="utf-8")

        assert exports == billing == SHARED_TASK_LINE
        assert "**T001**" in SHARED_TASK_LINE

    def test_two_features_sharing_t001_get_their_own_governing_promise(
        self, handoff: Handoff
    ) -> None:
        exports = handoff.convert(EXPORTS_TASKS)
        billing = handoff.convert(BILLING_TASKS)

        assert exports.returncode == 0, exports.stderr
        assert billing.returncode == 0, billing.stderr
        assert len(handoff.issues()) == 2, "one T001 swallowed the other"

        exports_body = handoff.body_for(EXPORTS_TASKS)
        billing_body = handoff.body_for(BILLING_TASKS)

        assert EXPORTS_PROMISE in exports_body
        assert BILLING_PROMISE not in exports_body, (
            "the exports issue carries billing's promise - feature context leaked"
        )
        assert BILLING_PROMISE in billing_body
        assert EXPORTS_PROMISE not in billing_body, (
            "the billing issue carries exports' promise - feature context leaked"
        )

    def test_each_block_names_its_own_source_spec(self, handoff: Handoff) -> None:
        """The block's `source:` is what a reader is sent to; it must not cross over."""
        handoff.convert(EXPORTS_TASKS)
        handoff.convert(BILLING_TASKS)

        assert "source: .specify/specs/exports/spec.md" in handoff.body_for(EXPORTS_TASKS)
        assert "source: .specify/specs/billing/spec.md" in handoff.body_for(BILLING_TASKS)

    def test_identity_does_not_ride_on_the_task_text(self, handoff: Handoff) -> None:
        """A shared `task-digest` is CORRECT here, and is why the rest must not share.

        Both task lines are byte-identical, so the digest over them is identical too.
        That is the precise condition under which identity has to come from the
        feature and the source - and the two issues stay distinct anyway.
        """
        handoff.convert(EXPORTS_TASKS)
        handoff.convert(BILLING_TASKS)

        def digest_line(body: str, field: str) -> str:
            line = next(l for l in body.splitlines() if l.startswith(f"{field}: "))
            return line.split(": ", 1)[1]

        exports_body = handoff.body_for(EXPORTS_TASKS)
        billing_body = handoff.body_for(BILLING_TASKS)

        assert digest_line(exports_body, "task-digest") == digest_line(
            billing_body, "task-digest"
        ), "fixture no longer shares a task line; this test's premise is gone"
        assert digest_line(exports_body, "source-digest") != digest_line(
            billing_body, "source-digest"
        )
        numbers = {i["number"] for i in handoff.issues()}
        assert len(numbers) == 2


class TestTheGeneratedBodyIsWhatTheNextStageReads:
    """The join: bytes produced by stage 1 are the literal input to stage 2."""

    def test_a_freshly_generated_body_reads_as_current(self, handoff: Handoff) -> None:
        handoff.convert(EXPORTS_TASKS)

        result = handoff.check(handoff.body_for(EXPORTS_TASKS))

        assert result.returncode == 0, result.stderr
        assert "SPECKIT_CONTEXT_STATE: current" in result.stdout
        assert "source=.specify/specs/exports/spec.md" in result.stdout

    def test_the_helper_resolves_the_body_against_the_readers_own_tree(
        self, handoff: Handoff
    ) -> None:
        """Paths in the block are project-relative, so a reader re-resolves locally.

        The body is forwarded verbatim into a SEPARATE checkout of the same project
        whose exports spec differs. A block that had recorded the producer's absolute
        path would keep reading the producer's file and answer `current` here.
        """
        handoff.convert(EXPORTS_TASKS)
        body = handoff.body_for(EXPORTS_TASKS)

        consumer = handoff.repo.parent / "consumer"
        shutil.copytree(handoff.repo, consumer)
        (consumer / ".specify/specs/exports/spec.md").write_text(
            EXPORTS_SPEC.replace("200ms", "900ms"), encoding="utf-8"
        )

        result = subprocess.run(
            ["python3", str(HELPER), "check", "--body-file", "-", "--root", "."],
            cwd=consumer,
            input=body,
            capture_output=True,
            text=True,
            env=_env(handoff.repo, handoff.bindir, handoff.state),
        )

        assert "SPECKIT_CONTEXT_STATE: changed-in-scope" in result.stdout, (
            "the consumer was told its own changed spec was current"
        )


class TestRerunStability:
    """A second conversion of an unchanged feature must change nothing at all."""

    def test_rerun_creates_nothing_and_leaves_both_bodies_byte_identical(
        self, handoff: Handoff
    ) -> None:
        handoff.convert(EXPORTS_TASKS)
        handoff.convert(BILLING_TASKS)
        before = {t: handoff.body_for(t) for t in (EXPORTS_TASKS, BILLING_TASKS)}

        again = [handoff.convert(t) for t in (EXPORTS_TASKS, BILLING_TASKS)]

        for result in again:
            assert result.returncode == 0, result.stderr
            assert "skip  T001" in result.stdout
            assert "stale" not in result.stdout
        assert len(handoff.issues()) == 2
        assert {t: handoff.body_for(t) for t in before} == before

    def test_a_rerun_reports_this_features_own_drift(self, handoff: Handoff) -> None:
        handoff.convert(EXPORTS_TASKS)
        spec = handoff.repo / ".specify/specs/exports/spec.md"
        spec.write_text(EXPORTS_SPEC.replace("200ms", "900ms"), encoding="utf-8")

        again = handoff.convert(EXPORTS_TASKS)

        assert again.returncode == 0, again.stderr
        assert "stale T001 (context: changed-in-scope)" in again.stdout
        assert "skip  T001" in again.stdout, "a stale report must not re-file the task"

    def test_a_neighbours_drift_does_not_make_this_feature_stale(
        self, handoff: Handoff
    ) -> None:
        """The cross-feature half, and it is only observable by forwarding bodies.

        Only a re-run that reads back the issue it wrote can get this wrong, and
        getting it wrong is quiet: every issue sharing a task id would be reported
        stale whenever any feature's spec moved, which trains readers to ignore the
        report.
        """
        handoff.convert(EXPORTS_TASKS)
        handoff.convert(BILLING_TASKS)
        billing_spec = handoff.repo / ".specify/specs/billing/spec.md"
        billing_spec.write_text(
            BILLING_SPEC.replace("one billing cycle", "two billing cycles"),
            encoding="utf-8",
        )

        exports_again = handoff.convert(EXPORTS_TASKS)
        billing_again = handoff.convert(BILLING_TASKS)

        assert "stale" not in exports_again.stdout, (
            "exports was reported stale because BILLING's spec changed"
        )
        assert "stale T001 (context: changed-in-scope)" in billing_again.stdout


# --- The packaged converter, run where no CPP checkout can rescue it --------------

PACKAGED = sorted(
    (ROOT / "codex" / "skills").glob("*/scripts/speckit-tasks-to-issues.sh")
)
PACKAGED_IDS = [p.parent.parent.name for p in PACKAGED]

ISOLATED_TASKS = ".specify/specs/onboarding/tasks.md"
ISOLATED_PROMISE = "A first run completes with no outbound network call"
ISOLATED_SPEC = f"""# Feature Specification: Onboarding

## User Stories

### US1: First run completes offline [P1]

**As a** new operator,
**I want** the first run to finish without network access,
**So that** an air-gapped install is possible.

**Acceptance Criteria:**
- [ ] {ISOLATED_PROMISE}
"""


def _no_cpp_checkout_above(path: Path) -> list[str]:
    """Ancestors of `path` that are a CPP checkout, by its own distinctive file."""
    return [
        str(parent)
        for parent in path.resolve().parents
        if (parent / "scripts" / "codex-skill-sync.py").is_file()
    ]


def _isolated(tmp_path: Path, skill_scripts: Path) -> Handoff:
    """A receiving project plus an installed skill, both outside any CPP checkout."""
    installed = tmp_path / "installed"
    shutil.copytree(skill_scripts, installed / "scripts")

    repo = tmp_path / "receiving-project"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "remote", "add", "origin", "https://github.com/acme/receiving.git")
    tasks = repo / ISOLATED_TASKS
    tasks.parent.mkdir(parents=True, exist_ok=True)
    tasks.write_text(SHARED_TASK_LINE, encoding="utf-8")
    (tasks.parent / "spec.md").write_text(ISOLATED_SPEC, encoding="utf-8")

    bindir = tmp_path / "bin"
    _install_stub_gh(bindir)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"next": 500, "issues": []}))
    return Handoff(repo, bindir, state, installed / "scripts" / "speckit-tasks-to-issues.sh")


def test_the_packaged_set_is_not_empty() -> None:
    """Tripwire: a glob that stops matching would make every test below vacuous."""
    assert PACKAGED, "no packaged converter found under codex/skills/*/scripts/"


@pytest.mark.parametrize("skill_script", PACKAGED, ids=PACKAGED_IDS)
class TestPackagedConverterInAnIsolatedProject:
    """Run the SHIPPED bundle where borrowing the source checkout is impossible."""

    def test_the_isolated_install_has_no_cpp_checkout_above_it(
        self, tmp_path: Path, skill_script: Path
    ) -> None:
        """The premise of every other test in this class, checked rather than assumed.

        If a CPP checkout sat above the copy, a converter that resolved its helper by
        walking upwards would pass for exactly the wrong reason.
        """
        project = _isolated(tmp_path, skill_script.parent)

        assert _no_cpp_checkout_above(project.converter) == []
        assert _no_cpp_checkout_above(project.repo) == []

    def test_the_packaged_converter_renders_context_from_its_bundled_helper(
        self, tmp_path: Path, skill_script: Path
    ) -> None:
        project = _isolated(tmp_path, skill_script.parent)

        result = project.convert(ISOLATED_TASKS)

        assert result.returncode == 0, result.stderr
        body = project.body_for(ISOLATED_TASKS)
        assert "speckit-context:v1" in body
        assert ISOLATED_PROMISE in body, (
            "the packaged run produced an issue with no governing promise in it"
        )
        assert "source: .specify/specs/onboarding/spec.md" in body

    def test_without_its_bundled_helper_the_packaged_run_refuses(
        self, tmp_path: Path, skill_script: Path
    ) -> None:
        """Positive control for the test above, and it is not optional.

        A passing run only proves the BUNDLED helper was used if the run fails when
        that helper is removed. Without this, a converter quietly reaching some other
        `speckit-context.py` - on PATH, in the project, in a checkout overhead - would
        look identical to correct packaging. Exit 7 is the converter's documented
        "helper missing or failed"; it is named literally rather than recomputed.
        """
        project = _isolated(tmp_path, skill_script.parent)
        (project.converter.parent / "speckit-context.py").unlink()

        result = project.convert(ISOLATED_TASKS)

        assert result.returncode == 7, (
            "the packaged converter survived losing its own helper, so the passing "
            f"run above does not establish which helper it used:\n{result.stdout}"
        )
        assert "speckit-context.py is missing" in result.stderr
        assert project.issues() == [], "an issue was filed despite the refusal"

    def test_the_packaged_converter_is_stable_on_a_rerun(
        self, tmp_path: Path, skill_script: Path
    ) -> None:
        project = _isolated(tmp_path, skill_script.parent)
        project.convert(ISOLATED_TASKS)
        before = project.body_for(ISOLATED_TASKS)

        again = project.convert(ISOLATED_TASKS)

        assert again.returncode == 0, again.stderr
        assert "skip  T001" in again.stdout
        assert "stale" not in again.stdout
        assert len(project.issues()) == 1
        assert project.body_for(ISOLATED_TASKS) == before
