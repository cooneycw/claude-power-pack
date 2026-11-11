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
    assert "even when nothing changed" in text
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
    pointer = normalized(text[text.index("answer the lane file") :])
    assert "lane-file.py age" in pointer
    assert "LANE_FILE_AGE:" in pointer
    assert "never a stop" in pointer, "the plan step no longer says the advisory cannot stop a plan"
