"""No tracked file names a host account in a home path (issue #1689).

The literals below are assembled from parts on purpose: this file is tracked,
so a worked example written out whole would be reported by the very check it
tests.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "controls" / "host-account-paths" / "cases"


def _load(name: str, rel: str):
    spec = spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hap = _load("check_host_account_paths", "scripts/check-host-account-paths.py")

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

PLAIN = "/ho" + "me/"
ENCODED = "-ho" + "me-"
MAC = "/Us" + "ers/"
ACCOUNT = "host" + "acct"


@pytest.mark.parametrize(
    "text",
    [
        PLAIN + ACCOUNT + "/Projects/widget",
        "see " + PLAIN + ACCOUNT + ".",
        '"worktree": "' + PLAIN + ACCOUNT + '"',
        MAC + ACCOUNT + "/Projects",
        ENCODED + ACCOUNT + "-Projects/0000.jsonl",
        '"' + ENCODED + ACCOUNT + '"',
        "-Us" + "ers-" + ACCOUNT + "-Projects/0000.jsonl",
    ],
)
def test_an_account_in_a_home_path_is_reported(text):
    assert [account for _, account in hap.findings_in(text)] == [ACCOUNT]


@pytest.mark.parametrize(
    ("text", "account"),
    [
        # Dots and dashes are legal in account names. A placeholder that is only
        # a PREFIX of the component excuses nothing (counter-model review).
        (PLAIN + "jane.doe/Projects/widget", "jane.doe"),
        (PLAIN + "test-person/Projects/widget", "test-person"),
        (PLAIN + "user.name/x", "user.name"),
        ("ends a sentence at " + PLAIN + "jane.doe.", "jane.doe"),
        # Encoded: only `user` and `clean`, as whole tokens, are placeholders.
        (ENCODED + "test-person-Projects/a.jsonl", "test"),
        (ENCODED + "alice-Projects/a.jsonl", "alice"),
    ],
)
def test_dotted_dashed_and_prefix_accounts_are_reported(text, account):
    assert [found for _, found in hap.findings_in(text)] == [account]


@pytest.mark.parametrize(
    "text",
    [
        PLAIN + "user/Projects/widget",
        PLAIN + "clean/work",
        ENCODED + "user-Projects/0000.jsonl",
        PLAIN + "AGENTS.md",  # a file directly in the homes directory
        PLAIN + "<name>/x",
        "$HOME/x and ~/x",
        "notes" + ENCODED + ACCOUNT + "-x",  # inside a longer word, not a component start
        "the home directory",
    ],
)
def test_placeholders_and_account_free_forms_are_not_reported(text):
    assert hap.findings_in(text) == []


@requires_git
@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("bad-plain-home-path", 1),
        ("bad-encoded-transcript-dir", 1),
        ("bad-dotted-and-dashed-accounts", 1),
        ("good-placeholders", 0),
    ],
)
def test_the_committed_cases_discriminate(case, expected):
    assert hap.main(["--root", str(CASES / case)]) == expected


@requires_git
def test_the_real_tree_is_clean_and_was_actually_read(capsys):
    assert hap.main(["--root", str(ROOT)]) == 0
    out = capsys.readouterr().out
    examined = int(out.split("HOST_ACCOUNT_PATHS_EXAMINED: ")[1].split()[0])
    assert examined > 1000, f"only {examined} file(s) examined - the tree is not being read"


@requires_git
def test_a_tree_git_cannot_list_is_unknown_not_clean(tmp_path, monkeypatch, capsys):
    """Outside any repository `git ls-files` fails; that is not a clean tree."""
    (tmp_path / "a.txt").write_text(PLAIN + ACCOUNT + "/x\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert hap.tracked_files(tmp_path) is None, "precondition: git cannot list this directory"
    assert hap.main(["--root", str(tmp_path)]) == 2
    assert "UNKNOWN" in capsys.readouterr().err


def _tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], cwd=repo, check=True, capture_output=True)
    (repo / "clean.txt").write_text("nothing here\n", encoding="utf-8")
    (repo / "record.json").write_text(PLAIN + ACCOUNT + "/x\n", encoding="utf-8")
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True, capture_output=True)
    return repo


@requires_git
def test_a_tracked_file_missing_from_the_working_tree_is_read_from_the_index(tmp_path, capsys):
    """An unstaged deletion or a sparse checkout leaves the file in the index,
    where a commit would still publish it. Skipping it let one readable clean
    file certify the tree (counter-model review)."""
    repo = _tiny_repo(tmp_path)
    assert hap.main(["--root", str(repo)]) == 1, "precondition: the file is reported while present"
    (repo / "record.json").unlink()
    capsys.readouterr()
    assert hap.main(["--root", str(repo)]) == 1
    assert "record.json:1" in capsys.readouterr().out


@requires_git
def test_a_symlink_whose_target_names_an_account_is_reported(tmp_path, capsys):
    repo = _tiny_repo(tmp_path)
    (repo / "record.json").unlink()
    (repo / "record.json").write_text("fine\n", encoding="utf-8")
    (repo / "link").symlink_to(PLAIN + ACCOUNT + "/elsewhere")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    assert hap.main(["--root", str(repo)]) == 1
    assert "link:1" in capsys.readouterr().out


# --- the writers (the sources of new occurrences) ---------------------------

receipt = _load("counter_model_receipt_for_1689", "scripts/counter-model-receipt.py")


@pytest.mark.parametrize(
    ("home", "recorded", "expected"),
    [
        (PLAIN + ACCOUNT, ENCODED + ACCOUNT + "-Projects/abc.jsonl", ENCODED + "user-Projects/abc.jsonl"),
        (PLAIN + ACCOUNT, ENCODED + ACCOUNT + "/abc.jsonl", ENCODED + "user/abc.jsonl"),
        (MAC + ACCOUNT, "-Us" + "ers-" + ACCOUNT + "-Projects/abc.jsonl", "-Us" + "ers-user-Projects/abc.jsonl"),
        (PLAIN + ACCOUNT, PLAIN + ACCOUNT + "/x/y.jsonl", PLAIN + "user/x/y.jsonl"),
        # Claude turns EVERY non-alphanumeric character into a dash, so a dotted
        # or underscored account is encoded with dashes (counter-model review).
        (PLAIN + "jane.doe", ENCODED + "jane-doe-Projects/abc.jsonl", ENCODED + "user-Projects/abc.jsonl"),
        (PLAIN + "jane_doe", ENCODED + "jane-doe-Projects/abc.jsonl", ENCODED + "user-Projects/abc.jsonl"),
        (PLAIN + "user.name", ENCODED + "user-name-Projects/abc.jsonl", ENCODED + "user-Projects/abc.jsonl"),
        # a different account that merely shares a prefix is someone else's name
        (PLAIN + ACCOUNT, ENCODED + ACCOUNT + "x-Projects/a.jsonl", ENCODED + ACCOUNT + "x-Projects/a.jsonl"),
        # Codex rollouts are date paths and carry no account
        (PLAIN + ACCOUNT, "2026/11/11/rollout-x.jsonl", "2026/11/11/rollout-x.jsonl"),
    ],
)
def test_the_receipt_writer_redacts_only_the_home_directory(home, recorded, expected):
    assert receipt._redact_home_account(recorded, Path(home)) == expected


def test_a_redacted_receipt_path_passes_the_tripwire():
    recorded = receipt._redact_home_account(ENCODED + ACCOUNT + "-Projects/abc.jsonl", Path(PLAIN + ACCOUNT))
    assert hap.findings_in(recorded) == []
    # and the unredacted form is what the tripwire exists to catch
    assert hap.findings_in(ENCODED + ACCOUNT + "-Projects/abc.jsonl")


def test_execution_evidence_records_home_paths_relative_to_home():
    from lib.cicd import evidence

    home = Path(PLAIN + ACCOUNT)
    assert evidence.home_relative(PLAIN + ACCOUNT + "/Projects/widget", home) == "~/Projects/widget"
    assert evidence.home_relative(PLAIN + ACCOUNT, home) == "~"
    assert evidence.home_relative("/srv/widget", home) == "/srv/widget"
    assert evidence.home_relative(PLAIN + ACCOUNT + "x/y", home) == PLAIN + ACCOUNT + "x/y"
    assert evidence.home_relative(None, home) is None
