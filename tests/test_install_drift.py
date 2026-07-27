"""Regression tests for installed-plugin-vs-checkout drift detection (issue #622).

`scripts/install-drift.sh` answers a question nothing else in CPP asked: is the
command text a session is EXECUTING the same text the repo maintains? The copy
the Skill tool loads lives under `~/.claude/plugins/`, snapshotted at install
time, while the checkout moves on every pull - and on flow:auto #65 the gap was
15 commits, so the session re-diagnosed an already-fixed bug and nearly filed a
duplicate issue for it.

These tests pin the behaviours that make the check trustworthy enough to run in
a SessionStart hook: content parity per command file, the SPLIT case (helpers
current, markdown stale) named explicitly, `skipped` as a non-failing answer for
marketplace-only and checkout-only hosts, `--quiet` being exactly one line and
never non-zero, and the check never writing anything.

Driven entirely through the `CPP_INSTALL_DRIFT_HOME` / `CPP_INSTALL_DRIFT_CHECKOUT`
seams on hermetic tmp trees, so only bash is required; the one commit-distance
test is guarded on git being present and is skipped in the git-less CI validate
container.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-drift.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)

FAMILY = "flow"
COMMANDS = {"auto.md": "# auto\ncurrent text\n", "help.md": "# help\n"}
HELPERS = {"flow-start-resolve.sh": "#!/usr/bin/env bash\necho resolve\n"}


def _make_checkout(root: Path) -> Path:
    """A minimal tree that satisfies the checkout probe (CLAUDE.md + commands + plugins)."""
    (root / ".claude" / "commands" / FAMILY).mkdir(parents=True)
    (root / "plugins" / FAMILY / "commands").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "CLAUDE.md").write_text("# fake CPP\n", encoding="utf-8")
    for name, body in COMMANDS.items():
        (root / ".claude" / "commands" / FAMILY / name).write_text(body, encoding="utf-8")
        (root / "plugins" / FAMILY / "commands" / name).write_text(body, encoding="utf-8")
    for name, body in HELPERS.items():
        (root / "scripts" / name).write_text(body, encoding="utf-8")
    return root


def _make_install(home: Path, *, version: str = "1.0.0") -> Path:
    """The installed halves: the version-stamped plugin cache plus host helpers."""
    cache = home / ".claude" / "plugins" / "cache" / "cpp" / FAMILY / version / "commands"
    cache.mkdir(parents=True)
    for name, body in COMMANDS.items():
        (cache / name).write_text(body, encoding="utf-8")
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    for name, body in HELPERS.items():
        (scripts / name).write_text(body, encoding="utf-8")
    return cache


def _run(checkout: Path, home: Path, *args: str, script: Path | None = None):
    return subprocess.run(
        ["bash", str(script or SCRIPT), *args],
        env={
            "CPP_INSTALL_DRIFT_CHECKOUT": str(checkout),
            "CPP_INSTALL_DRIFT_HOME": str(home),
            "PATH": os.environ.get("PATH", ""),
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def tree(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    cache = _make_install(home)
    return checkout, home, cache


def test_in_sync_install_reports_ok(tree):
    checkout, home, _ = tree
    r = _run(checkout, home)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "INSTALL_DRIFT: ok" in r.stdout
    assert "0 of 2 command file(s) differ" in r.stdout


def test_changed_command_file_is_reported_by_name(tree):
    checkout, home, cache = tree
    (cache / "auto.md").write_text("# auto\nWEEK OLD TEXT\n", encoding="utf-8")
    r = _run(checkout, home)
    assert r.returncode == 1
    assert "INSTALL_DRIFT: drift" in r.stdout
    assert "flow/auto.md - differs" in r.stdout
    assert "1 of 2 command file(s) differ" in r.stdout


def test_command_missing_from_install_is_drift(tree):
    checkout, home, cache = tree
    (cache / "help.md").unlink()
    r = _run(checkout, home)
    assert r.returncode == 1
    assert "flow/help.md - missing from install" in r.stdout


def test_command_retired_upstream_but_still_installed_is_drift(tree):
    checkout, home, cache = tree
    (cache / "gone.md").write_text("# a command the repo dropped\n", encoding="utf-8")
    r = _run(checkout, home)
    assert r.returncode == 1
    assert "flow/gone.md - retired upstream, still installed" in r.stdout


def test_split_install_is_named_explicitly(tree):
    # The #622 signature: helper half current, markdown half stale. The symptom
    # reads as a helper bug unless the check says otherwise.
    checkout, home, cache = tree
    (cache / "auto.md").write_text("# auto\nold\n", encoding="utf-8")
    r = _run(checkout, home)
    assert "SPLIT INSTALL" in r.stdout, r.stdout
    assert "1 current, 0 stale" in r.stdout


def test_stale_helper_is_reported_and_is_not_a_split(tree):
    checkout, home, _ = tree
    (home / ".claude" / "scripts" / "flow-start-resolve.sh").write_text(
        "#!/usr/bin/env bash\necho OLD\n", encoding="utf-8"
    )
    r = _run(checkout, home)
    assert r.returncode == 1
    assert "0 current, 1 stale" in r.stdout
    assert "Stale helpers: flow-start-resolve.sh" in r.stdout
    # Both halves stale is ordinary staleness, not the split this issue is about.
    assert "SPLIT INSTALL" not in r.stdout


def test_host_only_scripts_are_not_judged(tree):
    # A script the user put in ~/.claude/scripts that CPP does not ship is none
    # of this check's business - flagging it would make the check cry wolf.
    checkout, home, _ = tree
    (home / ".claude" / "scripts" / "my-own-tool.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    r = _run(checkout, home)
    assert r.returncode == 0
    assert "1 current, 0 stale" in r.stdout


def test_uninstalled_family_is_not_drift(tmp_path: Path):
    # Not installing a family is a choice, not staleness.
    checkout = _make_checkout(tmp_path / "checkout")
    (checkout / "plugins" / "security" / "commands").mkdir(parents=True)
    (checkout / "plugins" / "security" / "commands" / "scan.md").write_text("# scan\n", encoding="utf-8")
    home = tmp_path / "home"
    _make_install(home)
    r = _run(checkout, home)
    assert r.returncode == 0, r.stdout
    assert "INSTALL_DRIFT: ok" in r.stdout


def test_no_plugin_install_is_skipped_not_failed(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    home.mkdir()
    r = _run(checkout, home)
    assert r.returncode == 0
    assert "INSTALL_DRIFT: skipped" in r.stdout


def test_no_checkout_is_skipped_not_failed(tmp_path: Path):
    # The marketplace-only user: a plugin install and no repo to compare against.
    # Run a COPY of the script from a dir whose parent is not a checkout, so
    # self-location cannot find one either.
    home = tmp_path / "home"
    _make_install(home)
    bin_dir = tmp_path / "elsewhere" / "bin"
    bin_dir.mkdir(parents=True)
    copy = bin_dir / "install-drift.sh"
    shutil.copy(SCRIPT, copy)
    r = subprocess.run(
        ["bash", str(copy)],
        env={"CPP_INSTALL_DRIFT_HOME": str(home), "PATH": os.environ.get("PATH", "")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "INSTALL_DRIFT: skipped" in r.stdout
    assert "no CPP checkout" in r.stdout


def test_bad_checkout_override_is_an_error_not_a_silent_fallthrough(tmp_path: Path):
    home = tmp_path / "home"
    _make_install(home)
    r = _run(tmp_path / "not-a-checkout", home)
    assert r.returncode == 2
    assert "INSTALL_DRIFT: error" in r.stdout


def test_quiet_is_one_line_on_drift_and_always_exit_zero(tree):
    checkout, home, cache = tree
    (cache / "auto.md").write_text("# auto\nold\n", encoding="utf-8")
    r = _run(checkout, home, "--quiet")
    assert r.returncode == 0, "a session-start hook must never fail the session"
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, r.stdout
    assert lines[0].startswith("CPP install:")
    assert "/cpp:update" in lines[0]
    assert "1 command file(s) stale" in lines[0]


def test_quiet_is_silent_when_in_sync(tree):
    checkout, home, _ = tree
    r = _run(checkout, home, "--quiet")
    assert r.returncode == 0
    assert r.stdout.strip() == "", "no drift -> nothing in the session's context"


def test_quiet_is_silent_when_skipped(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    home.mkdir()
    r = _run(checkout, home, "--quiet")
    assert r.returncode == 0
    assert r.stdout.strip() == "", "a skip is not news; the verdict line must stay out"


def test_list_shows_every_stale_file(tree):
    checkout, home, cache = tree
    for i in range(12):
        (cache / f"extra{i}.md").write_text("# orphan\n", encoding="utf-8")
    sampled = _run(checkout, home).stdout
    assert "more - re-run with --list" in sampled
    full = _run(checkout, home, "--list").stdout
    assert "more - re-run with --list" not in full
    for i in range(12):
        assert f"flow/extra{i}.md" in full


def test_json_shape(tree):
    checkout, home, cache = tree
    (cache / "auto.md").write_text("# auto\nold\n", encoding="utf-8")
    r = _run(checkout, home, "--json")
    assert r.returncode == 1
    payload = json.loads(r.stdout)
    assert payload["verdict"] == "drift"
    assert payload["commands_stale"] == 1
    assert payload["commands_total"] == 2
    assert payload["helpers_current"] == 1
    assert payload["helpers_stale"] == 0
    assert payload["split"] is True


def test_check_never_writes(tree):
    checkout, home, cache = tree
    (cache / "auto.md").write_text("# auto\nold\n", encoding="utf-8")

    def snapshot(root: Path):
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    before = (snapshot(checkout), snapshot(home))
    _run(checkout, home)
    assert (snapshot(checkout), snapshot(home)) == before, "the check must be read-only"


@pytest.mark.skipif(shutil.which("git") is None, reason="requires git on PATH")
def test_marketplace_commit_distance_is_measured_in_the_checkout(tmp_path: Path):
    # The clone was fetched at install time and does not have the commits that
    # landed since, so the range must be resolved in the CHECKOUT, which has both.
    checkout = _make_checkout(tmp_path / "checkout")
    git_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "no-such-gitconfig"),
        "GIT_CONFIG_SYSTEM": str(tmp_path / "no-such-gitconfig"),
    }

    def git(*args: str, cwd: Path = checkout):
        return subprocess.run(
            ["git", "-C", str(cwd), *args], env=git_env, capture_output=True, text=True, check=True
        )

    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-qm", "one")
    (checkout / "plugins" / FAMILY / "commands" / "auto.md").write_text(
        "# auto\nnewer text\n", encoding="utf-8"
    )
    git("add", "-A")
    git("commit", "-qm", "two")

    home = tmp_path / "home"
    _make_install(home)
    mkt = home / ".claude" / "plugins" / "marketplaces" / "cpp"
    mkt.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "-q", str(checkout), str(mkt)], env=git_env, capture_output=True, check=True
    )
    git("reset", "-q", "--hard", "HEAD~1", cwd=mkt)

    r = _run(checkout, home, "--json")
    payload = json.loads(r.stdout)
    assert payload["commit_state"] == "resolved"
    assert payload["behind"] == 1
    assert payload["ahead"] == 0
    assert payload["verdict"] == "drift"

    report = _run(checkout, home).stdout
    assert "1 commit(s) behind the checkout" in report
