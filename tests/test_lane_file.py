"""`scripts/lane-file.py` and the surfaces that call it (issue #1696).

The committed control (`controls/lane-file-age`) pins the age verdict at the
threshold. This file pins what the control says it does not: the absent state,
every way a lane file can exist and be undatable, the stamp verb, root
resolution, and that the command documents still route to the helper.

The distinction every test in the first half protects: `absent` means the path
is ESTABLISHED not to exist and is the only silent state. A file that is there
and cannot be dated is `unknown`. Reading it as `absent` switches the advisory
off exactly where it is owed.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HELPER = REPO / "scripts" / "lane-file.py"
TODAY = "2026-03-02"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")
not_root = pytest.mark.skipif(
    os.geteuid() == 0, reason="root reads a mode-000 path, so the unreadable state cannot be built"
)

BODY = (
    "| Lane | Values | How it is exercised |\n"
    "|---|---|---|\n"
    "| Checkout | main checkout / linked worktree | tests build both |\n"
)


def lane_text(reviewed: str | None) -> str:
    stamp = f"Reviewed: {reviewed}\n\n" if reviewed is not None else ""
    return f"# Lanes\n\n{stamp}{BODY}"


def write_lanes(root: Path, reviewed: str | None) -> Path:
    path = root / ".claude" / "lanes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lane_text(reviewed), encoding="utf-8")
    return path


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), *args], capture_output=True, text=True, cwd=cwd, check=False
    )


def age(root: Path, *extra: str) -> tuple[int, str]:
    result = run("age", "--root", str(root), "--today", TODAY, *extra)
    return result.returncode, result.stdout.strip().splitlines()[-1]


# --- the age verdict ----------------------------------------------------------


def test_the_helper_is_executable() -> None:
    """The installers skip a helper that is not mode 755 (#1703's review finding)."""
    assert os.access(HELPER, os.X_OK)


@pytest.mark.parametrize(
    ("reviewed", "code", "word"),
    [
        ("2026-03-02", 0, "fresh"),   # today
        ("2026-01-01", 0, "fresh"),   # exactly 60 days: the boundary is inclusive
        ("2025-12-31", 3, "stale"),   # 61 days: one over
        ("2024-01-01", 3, "stale"),
    ],
)
def test_age_boundaries(tmp_path: Path, reviewed: str, code: int, word: str) -> None:
    write_lanes(tmp_path, reviewed)
    got_code, line = age(tmp_path)
    assert (got_code, line.split(" - ")[0]) == (code, f"LANE_FILE_AGE: {word}")


def test_a_stale_verdict_names_the_remedy(tmp_path: Path) -> None:
    write_lanes(tmp_path, "2025-12-31")
    assert age(tmp_path)[1].endswith("Run /lane:update")


def test_the_threshold_is_a_flag(tmp_path: Path) -> None:
    write_lanes(tmp_path, "2026-02-20")  # 10 days
    assert age(tmp_path, "--threshold-days", "9")[0] == 3
    assert age(tmp_path, "--threshold-days", "10")[0] == 0


def test_no_lane_file_is_absent_and_silent(tmp_path: Path) -> None:
    assert not (tmp_path / ".claude").exists()  # the negative precondition
    code, line = age(tmp_path)
    assert code == 0
    assert line.startswith("LANE_FILE_AGE: absent - ")
    assert "/lane:update" not in line


def test_a_claude_directory_with_no_lane_file_is_absent(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    assert not (tmp_path / ".claude" / "lanes.md").exists()  # the negative precondition
    assert age(tmp_path)[1].startswith("LANE_FILE_AGE: absent - ")


@requires_git
def test_a_lane_list_at_another_path_does_not_hide_what_was_checked(tmp_path: Path) -> None:
    git("init", "-q", cwd=tmp_path)
    alternate = tmp_path / "docs" / "testing" / "project-lanes.md"
    alternate.parent.mkdir(parents=True)
    alternate.write_text(lane_text(TODAY), encoding="utf-8")
    assert alternate.is_file()
    assert not (tmp_path / ".claude" / "lanes.md").exists()
    code, line = age(tmp_path)
    assert code == 0
    assert line.startswith(f"LANE_FILE_AGE: absent - no .claude/lanes.md under {tmp_path};"), line
    assert "a lane list kept at any other path is not read" in line, line
    assert alternate.read_text(encoding="utf-8") == lane_text(TODAY)


# --- exists, and cannot be dated: unknown, never absent, never fresh ----------


def assert_unknown(root: Path, fragment: str) -> None:
    code, line = age(root)
    assert code == 4, line
    assert line.startswith("LANE_FILE_AGE: unknown - "), line
    assert fragment in line, line
    assert line.endswith("Run /lane:update")


def test_no_review_date_is_unknown(tmp_path: Path) -> None:
    write_lanes(tmp_path, None)
    assert_unknown(tmp_path, "has no `Reviewed: YYYY-MM-DD` line")


@pytest.mark.parametrize("value", ["yesterday", "2026-3-2", "02/03/2026", "2026-02-30", "2026-13-01"])
def test_an_unparseable_or_impossible_date_is_unknown(tmp_path: Path, value: str) -> None:
    write_lanes(tmp_path, value)
    assert_unknown(tmp_path, "the review date")


def test_a_future_date_is_unknown_not_fresh(tmp_path: Path) -> None:
    write_lanes(tmp_path, "2026-03-03")
    assert_unknown(tmp_path, "is after today")


def test_disagreeing_dates_are_unknown(tmp_path: Path) -> None:
    path = write_lanes(tmp_path, "2026-03-01")
    path.write_text(path.read_text(encoding="utf-8") + "\nReviewed: 2020-01-01\n", encoding="utf-8")
    assert_unknown(tmp_path, "`Reviewed:` lines that disagree")


def test_a_repeated_identical_date_is_still_one_date(tmp_path: Path) -> None:
    path = write_lanes(tmp_path, "2026-03-01")
    path.write_text(path.read_text(encoding="utf-8") + "\nReviewed: 2026-03-01\n", encoding="utf-8")
    assert age(tmp_path)[0] == 0


def test_a_date_mentioned_in_prose_is_not_a_review_date(tmp_path: Path) -> None:
    path = write_lanes(tmp_path, None)
    path.write_text(path.read_text(encoding="utf-8") + "\nLast Reviewed: 2026-03-01 by nobody.\n", encoding="utf-8")
    assert_unknown(tmp_path, "has no `Reviewed: YYYY-MM-DD` line")


def test_a_directory_in_the_files_place_is_unknown(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "lanes.md").mkdir(parents=True)
    assert_unknown(tmp_path, "is not a regular file")


def test_a_dangling_symlink_is_unknown(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    link = tmp_path / ".claude" / "lanes.md"
    link.symlink_to(tmp_path / "gone.md")
    assert not link.exists() and link.is_symlink()  # the negative precondition: dangling
    assert_unknown(tmp_path, "symlink whose target cannot be read")


def test_a_symlink_to_a_real_lane_file_is_read(tmp_path: Path) -> None:
    real = tmp_path / "real.md"
    real.write_text(lane_text("2026-03-01"), encoding="utf-8")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "lanes.md").symlink_to(real)
    assert age(tmp_path)[0] == 0


@not_root
def test_an_unreadable_file_is_unknown(tmp_path: Path) -> None:
    path = write_lanes(tmp_path, "2026-03-01")
    path.chmod(0o000)
    try:
        assert not os.access(path, os.R_OK)  # the negative precondition
        assert_unknown(tmp_path, "could not be read")
    finally:
        path.chmod(0o644)


@not_root
def test_an_unsearchable_claude_directory_is_unknown(tmp_path: Path) -> None:
    """The lstat cannot tell whether the file is there. That is not `absent`."""
    path = write_lanes(tmp_path, "2026-03-01")
    path.parent.chmod(0o000)
    try:
        assert not os.access(path.parent, os.X_OK)  # the negative precondition
        assert_unknown(tmp_path, "could not be examined")
    finally:
        path.parent.chmod(0o755)


def test_non_utf8_content_is_unknown(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "lanes.md").write_bytes(b"Reviewed: 2026-03-01\n\xff\xfe\n")
    assert_unknown(tmp_path, "could not be read")


# --- usage --------------------------------------------------------------------


@pytest.mark.parametrize("args", [["age", "--today", "tomorrow"], ["age", "--threshold-days", "-1"]])
def test_bad_arguments_are_a_usage_error_not_a_verdict(tmp_path: Path, args: list[str]) -> None:
    result = run(*args, "--root", str(tmp_path))
    assert result.returncode == 2
    assert "LANE_FILE_AGE:" not in result.stdout


# --- root resolution ----------------------------------------------------------

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env={**os.environ, **GIT_ENV})


@requires_git
def test_the_lane_file_is_found_from_a_subdirectory(tmp_path: Path) -> None:
    git("init", "-q", cwd=tmp_path)
    write_lanes(tmp_path, "2025-12-31")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    result = run("age", "--today", TODAY, cwd=sub)
    assert result.returncode == 3
    assert "(git)" in result.stdout.splitlines()[0]


@requires_git
def test_a_linked_worktree_reads_its_own_lane_file(tmp_path: Path) -> None:
    """The Checkout lane (#1677's shape): never the main checkout's copy."""
    main = tmp_path / "main"
    main.mkdir()
    git("init", "-q", cwd=main)
    write_lanes(main, "2025-12-31")  # stale in the main checkout
    git("add", "-A", cwd=main)
    git("commit", "-qm", "lanes", cwd=main)
    linked = tmp_path / "linked"
    git("worktree", "add", "-q", "-b", "side", str(linked), cwd=main)
    assert (linked / ".git").is_file()  # a linked worktree, not a second clone
    write_lanes(linked, "2026-03-01")  # fresh in the linked worktree
    assert run("age", "--today", TODAY, cwd=linked).returncode == 0
    assert run("age", "--today", TODAY, cwd=main).returncode == 3


@requires_git
def test_outside_a_checkout_the_current_directory_is_used_and_said(tmp_path: Path) -> None:
    probe = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=tmp_path, capture_output=True, check=False)
    if probe.returncode == 0:
        pytest.skip("the temporary directory is inside a git checkout")
    write_lanes(tmp_path, "2025-12-31")
    result = run("age", "--today", TODAY, cwd=tmp_path)
    assert result.returncode == 3
    assert "cwd (not a git checkout)" in result.stdout.splitlines()[0]


# --- stamp --------------------------------------------------------------------


def stamp(root: Path) -> tuple[int, str]:
    result = run("stamp", "--root", str(root), "--today", TODAY)
    return result.returncode, result.stdout.strip().splitlines()[-1]


def test_stamp_replaces_the_date_and_nothing_else(tmp_path: Path) -> None:
    path = write_lanes(tmp_path, "2025-01-01")
    code, line = stamp(tmp_path)
    assert (code, line) == (0, "LANE_FILE_STAMP: stamped 2026-03-02 (was 2025-01-01)")
    assert path.read_text(encoding="utf-8") == lane_text("2026-03-02")
    assert age(tmp_path)[0] == 0


def test_stamp_adds_a_date_to_an_undated_file(tmp_path: Path) -> None:
    path = write_lanes(tmp_path, None)
    assert stamp(tmp_path) == (0, "LANE_FILE_STAMP: stamped 2026-03-02 (was none)")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Lanes\n\nReviewed: 2026-03-02\n")
    assert BODY in text


def test_stamp_collapses_disagreeing_dates_to_one(tmp_path: Path) -> None:
    path = write_lanes(tmp_path, "2025-01-01")
    path.write_text(path.read_text(encoding="utf-8") + "\nReviewed: 2020-01-01\n", encoding="utf-8")
    assert stamp(tmp_path)[0] == 0
    assert path.read_text(encoding="utf-8").count("Reviewed:") == 1
    assert age(tmp_path)[0] == 0


def test_stamp_keeps_the_files_mode(tmp_path: Path) -> None:
    path = write_lanes(tmp_path, "2025-01-01")
    path.chmod(0o640)
    assert stamp(tmp_path)[0] == 0
    assert path.stat().st_mode & 0o777 == 0o640


def test_stamp_refuses_when_there_is_no_lane_file(tmp_path: Path) -> None:
    assert not (tmp_path / ".claude").exists()  # the negative precondition
    code, line = stamp(tmp_path)
    assert code == 3
    assert line.startswith("LANE_FILE_STAMP: refused - there is no")
    assert not (tmp_path / ".claude").exists(), "a refused stamp created something"


def test_stamp_refuses_a_directory_and_a_symlink(tmp_path: Path) -> None:
    one = tmp_path / "one"
    (one / ".claude" / "lanes.md").mkdir(parents=True)
    assert stamp(one)[0] == 3
    two = tmp_path / "two"
    real = tmp_path / "real.md"
    real.write_text(lane_text("2025-01-01"), encoding="utf-8")
    (two / ".claude").mkdir(parents=True)
    (two / ".claude" / "lanes.md").symlink_to(real)
    code, line = stamp(two)
    assert code == 3 and "symlink" in line
    assert real.read_text(encoding="utf-8") == lane_text("2025-01-01")


def test_stamp_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    write_lanes(tmp_path, "2025-01-01")
    assert stamp(tmp_path)[0] == 0
    assert sorted(p.name for p in (tmp_path / ".claude").iterdir()) == ["lanes.md"]


# --- this repository's own file, and the routing ------------------------------


def test_this_repositorys_lane_file_has_a_readable_date() -> None:
    result = run("age", "--root", str(REPO), "--threshold-days", "100000")
    assert result.returncode == 0, result.stdout
    assert result.stdout.strip().splitlines()[-1].startswith("LANE_FILE_AGE: fresh - ")


COMMANDS = REPO / ".claude" / "commands"


def read(rel: str) -> str:
    return (COMMANDS / rel).read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.split())


def test_create_refuses_to_overwrite_and_shows_the_draft_first() -> None:
    text = normalized(read("lane/create.md"))
    assert "lane-file.py age" in text
    assert "/lane:update" in text
    assert "Show the draft" in text and "before writing" in text
    assert "lane-file.py stamp" in text


def test_update_stamps_even_when_nothing_changed() -> None:
    text = normalized(read("lane/update.md"))
    assert "lane-file.py stamp" in text
    assert "even when no row changed" in text
    assert "only what the owner accepts" in text


@pytest.mark.parametrize("rel", ["lane/create.md", "lane/update.md"])
def test_the_survey_is_a_checklist_whose_rows_cite_evidence(rel: str) -> None:
    text = normalized(read(rel))
    assert re.search(r"cites? (its|the) evidence", text), f"{rel} no longer asks each row for its evidence"
    assert "no trace in the repository" in text, f"{rel} no longer states the survey's limit"


@pytest.mark.parametrize("rel", ["lane/create.md", "lane/update.md", "lane/help.md"])
def test_the_lane_commands_route_to_the_reference(rel: str) -> None:
    assert "docs/agents/lanes.md" in read(rel)


def test_no_lane_command_files_issues() -> None:
    """`tests/test_issue_contract_routing.py` treats the raw call as an issue-filing surface."""
    for rel in ("lane/create.md", "lane/update.md", "lane/help.md"):
        assert "gh issue create" not in read(rel)


def test_the_plan_step_relays_the_advisory_and_continues() -> None:
    text = read("flow/eli5.md")
    pointer = normalized(text[text.index("CPP integration: lanes and readers") :])
    assert "lane-file.py age" in pointer
    assert "LANE_FILE_AGE:" in pointer
    assert "never a stop" in pointer, "the plan step no longer says the advisory cannot stop a plan"


def test_project_init_creates_the_lane_file_after_ci_providers_are_recorded() -> None:
    text = read("project/init.md")
    step = text.index("### 4a.2: Lane file")
    assert text.index("### 4a.1: Record CI providers") < step < text.index("### 4b: CPP Init")
    body = normalized(text[step : text.index("### 4b: CPP Init")])
    assert "`/lane:create`" in body
    assert "the owner reads the draft before it is written" in body
    assert "One lane still gets a one-row file." in body
    assert "warn and continue" in body


@pytest.mark.parametrize("rel", ["lane/create.md", "lane/update.md"])
def test_a_named_project_binds_every_step(rel: str) -> None:
    """Reviewing one project and stamping another records a review nobody did."""
    text = normalized(read(rel))
    assert "Resolve the target once and use it for every step." in text
    assert "the stamp takes the same `--root <path>` as Step 1" in text


def test_update_binds_the_issue_query_to_the_named_project() -> None:
    text = normalized(read("lane/update.md"))
    assert "the `gh` query runs against that project's repository" in text


def test_update_treats_a_full_page_of_fixes_as_truncated() -> None:
    """A list cut at the limit reads as a complete one, and the stamp then hides the rest."""
    text = normalized(read("lane/update.md"))
    assert "A full page is a truncated list." in text
    assert "until a query returns fewer than its limit" in text


def test_update_does_not_stamp_over_a_listing_that_was_not_read() -> None:
    """One rule, two triggers (#1723): truncated, or not readable at all.

    Before #1723 the unreadable case said only that the list "was not examined"
    and Step 5 stamped anyway, so every later review started after the unread
    interval. The rule is stated ONCE in Step 3 and both triggers sit under it,
    and Step 5 carries the exception for a reader who jumps straight there.
    """
    text = read("lane/update.md")
    step3 = normalized(text[text.index("## Step 3:") : text.index("## Step 4:")])
    step5 = normalized(text[text.index("## Step 5:") :])
    rule = "The review date moves only over a listing that was read in full."
    assert step3.count(rule) == 1
    after_rule = step3[step3.index(rule) :]
    assert "A full page is a truncated list." in after_rule
    assert "An unreadable listing is not an empty one." in after_rule
    assert "skip Step 5" in after_rule
    assert "not recorded as a review" in after_rule
    assert "which period went unread" in after_rule
    assert step3.count("skip Step 5") == 1, "the no-stamp rule is stated twice and can drift"
    assert "Not when Step 3's listing went unread or truncated" in step5
    assert step5.index("Not when Step 3's listing went unread or truncated") < step5.index("lane-file.py stamp")
    assert "leave the date where it was" in step5


def test_update_says_what_to_search_when_the_file_is_undated() -> None:
    text = normalized(read("lane/update.md"))
    assert "With no usable review date" in text
    assert "search the last 90 days" in text
    assert "older fixes were not read" in text


# --- the Harness lane: the generated Codex skills ------------------------------


@pytest.fixture(scope="module")
def codex_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("codex-skills")
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "codex-skill-sync.py"), "--write", "--output-root", str(out)],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out


@pytest.mark.parametrize("skill", ["lane-create", "lane-update", "lane-help"])
def test_the_lane_family_is_generated_as_codex_skills(codex_tree: Path, skill: str) -> None:
    assert (codex_tree / skill / "SKILL.md").is_file()


@pytest.mark.parametrize("skill", ["lane-create", "lane-update", "flow-eli5"])
def test_a_generated_skill_calls_its_own_bundled_helper(codex_tree: Path, skill: str) -> None:
    # A long command is split: its later sections land in reference.md, which is
    # where the plan gate's lane pointer sits. Read the skill as Codex is given it.
    text = "".join(
        (codex_tree / skill / name).read_text(encoding="utf-8")
        for name in ("SKILL.md", "reference.md")
        if (codex_tree / skill / name).is_file()
    )
    assert "/scripts/lane-file.py age" in text
    assert "~/.claude/scripts/lane-file.py" not in text, f"{skill} still points at the Claude install path"
    assert (codex_tree / skill / "scripts" / "lane-file.py").is_file()


def test_the_bundled_helper_gives_the_same_verdict_as_the_source(codex_tree: Path, tmp_path: Path) -> None:
    write_lanes(tmp_path, "2025-12-31")
    bundled = codex_tree / "lane-update" / "scripts" / "lane-file.py"
    assert os.access(bundled, os.X_OK), "the bundled helper is not executable"
    result = subprocess.run(
        [sys.executable, str(bundled), "age", "--root", str(tmp_path), "--today", TODAY],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 3
    assert result.stdout.strip().splitlines()[-1] == age(tmp_path)[1]


def test_the_generated_update_skill_carries_the_no_stamp_rule(codex_tree: Path) -> None:
    """The Harness lane for #1723: a Codex run reads the same rule."""
    text = normalized((codex_tree / "lane-update" / "SKILL.md").read_text(encoding="utf-8"))
    assert "The review date moves only over a listing that was read in full." in text
    assert "Not when Step 3's listing went unread or truncated" in text
