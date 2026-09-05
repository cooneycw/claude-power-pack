"""Tests for scripts/cpp-commands-link.sh (issue #663).

The user-scope command-surface symlinker: per-family links from
~/.claude/commands/<family> into the checkout's .claude/commands/, so the
executed command text follows `git pull` atomically (the reconciliation
property the /plugin cache lacked - #662).

Ownership contract under test: the script may only ever touch SYMLINKS whose
readlink target ends in `/.claude/commands/<family>`. Real files, real dirs,
and symlinks pointing anywhere else are foreign - reported, never modified.

Mostly pure filesystem: the script shells ln/readlink/mkdir/rm for its real
work. Since #685 `--check` ALSO shells `git` for a fail-open content advisory,
so the tests that exercise that path carry the required `shutil.which("git")`
guard; the rest need none (the guarded set is git/docker/gitleaks).
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "cpp-commands-link.sh"


def _make_source(tmp_path: Path, families=("flow", "cicd", "cpp")) -> Path:
    """A fake checkout with a .claude/commands/<family>/ tree."""
    src = tmp_path / "checkout" / ".claude" / "commands"
    for fam in families:
        (src / fam).mkdir(parents=True)
        (src / fam / f"{fam}-cmd.md").write_text(f"# {fam}\n")
    return src


def _run(tmp_path: Path, src: Path, *args) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CPP_COMMANDS_LINK_HOME"] = str(tmp_path / "home")
    return subprocess.run(
        ["bash", str(SCRIPT), "--source", str(src), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _target(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".claude" / "commands"


def test_script_is_executable():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK), "cpp-commands-link.sh must be executable"


def test_fresh_install_links_every_family(tmp_path: Path):
    src = _make_source(tmp_path)
    result = _run(tmp_path, src)
    assert result.returncode == 0, result.stderr
    assert "CPP_COMMANDS_LINK: installed" in result.stdout
    for fam in ("flow", "cicd", "cpp"):
        link = _target(tmp_path) / fam
        assert link.is_symlink(), f"{fam} not linked"
        assert os.readlink(link) == str(src / fam)


def test_second_run_is_idempotent(tmp_path: Path):
    src = _make_source(tmp_path)
    _run(tmp_path, src)
    result = _run(tmp_path, src)
    assert result.returncode == 0, result.stderr
    assert "CPP_COMMANDS_LINK: ok" in result.stdout
    assert "changed: 0" in result.stdout


def test_foreign_real_dir_is_preserved(tmp_path: Path):
    # A user's own flow/ directory blocks the link and is never modified.
    src = _make_source(tmp_path)
    user_dir = _target(tmp_path) / "flow"
    user_dir.mkdir(parents=True)
    (user_dir / "my-own.md").write_text("mine\n")

    result = _run(tmp_path, src)
    assert result.returncode == 0, result.stderr
    assert "foreign  flow" in result.stdout
    assert not user_dir.is_symlink()
    assert (user_dir / "my-own.md").read_text() == "mine\n"


def test_foreign_symlink_is_preserved(tmp_path: Path):
    # A user symlink pointing somewhere that is NOT a .claude/commands family
    # shape is foreign - reported, not replaced.
    src = _make_source(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = _target(tmp_path)
    target.mkdir(parents=True)
    (target / "cicd").symlink_to(elsewhere)

    result = _run(tmp_path, src)
    assert result.returncode == 0, result.stderr
    assert "foreign  cicd" in result.stdout
    assert os.readlink(target / "cicd") == str(elsewhere)


def test_user_regular_file_is_untouched(tmp_path: Path):
    # A loose user command file (e.g. project-next.md) is not a family name
    # collision and must survive install + prune untouched.
    src = _make_source(tmp_path)
    target = _target(tmp_path)
    target.mkdir(parents=True)
    (target / "project-next.md").write_text("standalone\n")

    result = _run(tmp_path, src)
    assert result.returncode == 0, result.stderr
    assert (target / "project-next.md").read_text() == "standalone\n"


def test_stale_owned_link_is_repointed(tmp_path: Path):
    # An owned link into ANOTHER checkout (same /.claude/commands/<fam> shape)
    # is stale and gets repointed on install.
    src = _make_source(tmp_path)
    other = tmp_path / "other-checkout" / ".claude" / "commands" / "flow"
    other.mkdir(parents=True)
    target = _target(tmp_path)
    target.mkdir(parents=True)
    (target / "flow").symlink_to(other)

    result = _run(tmp_path, src)
    assert result.returncode == 0, result.stderr
    assert "updated  flow" in result.stdout
    assert os.readlink(target / "flow") == str(src / "flow")


def test_owned_orphan_is_pruned(tmp_path: Path):
    # An owned-shape link for a family the source no longer ships is pruned.
    src = _make_source(tmp_path)
    gone = tmp_path / "old-checkout" / ".claude" / "commands" / "retiredfam"
    gone.mkdir(parents=True)
    target = _target(tmp_path)
    target.mkdir(parents=True)
    (target / "retiredfam").symlink_to(gone)

    result = _run(tmp_path, src)
    assert result.returncode == 0, result.stderr
    assert "pruned   retiredfam" in result.stdout
    assert not (target / "retiredfam").exists()
    assert not (target / "retiredfam").is_symlink()


def test_check_reports_ok_after_install(tmp_path: Path):
    src = _make_source(tmp_path)
    _run(tmp_path, src)
    result = _run(tmp_path, src, "--check")
    assert result.returncode == 0, result.stdout
    assert "CPP_COMMANDS_LINK: ok" in result.stdout


def test_check_reports_drift_when_missing(tmp_path: Path):
    src = _make_source(tmp_path)
    _run(tmp_path, src)
    (_target(tmp_path) / "flow").unlink()
    result = _run(tmp_path, src, "--check")
    assert result.returncode == 3
    assert "missing  flow" in result.stdout
    assert result.stdout.splitlines()[-1] == "CPP_COMMANDS_LINK: drift-missing"


def test_check_is_read_only(tmp_path: Path):
    src = _make_source(tmp_path)
    result = _run(tmp_path, src, "--check")
    assert result.returncode == 3
    assert result.stdout.splitlines()[-1] == "CPP_COMMANDS_LINK: drift-missing"
    assert not _target(tmp_path).exists(), "--check must not create anything"


def test_check_reports_drift_when_stale(tmp_path: Path):
    # A link aimed at another checkout may be an intentional user choice, so
    # stale-only drift keeps the human-gated exit 1 verdict.
    src = _make_source(tmp_path)
    _run(tmp_path, src)
    other = tmp_path / "other-checkout" / ".claude" / "commands" / "flow"
    other.mkdir(parents=True)
    link = _target(tmp_path) / "flow"
    link.unlink()
    link.symlink_to(other)

    result = _run(tmp_path, src, "--check")
    assert result.returncode == 1
    assert "stale    flow" in result.stdout
    assert result.stdout.splitlines()[-1] == "CPP_COMMANDS_LINK: drift"


def test_check_reports_drift_when_missing_and_stale(tmp_path: Path):
    # Missing links are safe to add, but one stale link makes the combined
    # state ambiguous. Stale wins so the install still waits for a human.
    src = _make_source(tmp_path)
    _run(tmp_path, src)
    target = _target(tmp_path)
    (target / "flow").unlink()
    other = tmp_path / "other-checkout" / ".claude" / "commands" / "cicd"
    other.mkdir(parents=True)
    (target / "cicd").unlink()
    (target / "cicd").symlink_to(other)

    result = _run(tmp_path, src, "--check")
    assert result.returncode == 1
    assert "missing  flow" in result.stdout
    assert "stale    cicd" in result.stdout
    assert result.stdout.splitlines()[-1] == "CPP_COMMANDS_LINK: drift"


def test_check_reports_drift_for_owned_orphan(tmp_path: Path):
    # Removing a retired family changes the visible command surface, so an
    # owned orphan remains stale and must not use the missing-only verdict.
    src = _make_source(tmp_path)
    _run(tmp_path, src)
    gone = tmp_path / "old-checkout" / ".claude" / "commands" / "retiredfam"
    gone.mkdir(parents=True)
    (_target(tmp_path) / "retiredfam").symlink_to(gone)

    result = _run(tmp_path, src, "--check")
    assert result.returncode == 1
    assert "orphan   retiredfam" in result.stdout
    assert result.stdout.splitlines()[-1] == "CPP_COMMANDS_LINK: drift"


def test_foreign_is_not_drift_in_check(tmp_path: Path):
    # The user's own content for a family name is a choice, not drift:
    # --check reports it but exits 0 when everything else is current.
    src = _make_source(tmp_path)
    _run(tmp_path, src)
    target = _target(tmp_path)
    (target / "flow").unlink()
    (target / "flow").mkdir()

    result = _run(tmp_path, src, "--check")
    assert result.returncode == 0, result.stdout
    assert "foreign  flow" in result.stdout
    assert "CPP_COMMANDS_LINK: ok" in result.stdout


def test_unknown_argument_errors(tmp_path: Path):
    src = _make_source(tmp_path)
    result = _run(tmp_path, src, "--bogus")
    assert result.returncode == 2
    assert "CPP_COMMANDS_LINK: error" in result.stdout


# --------------------------------------------------------------------------- #
# Content advisory: `ok` is topology, not health (issue #685)
#
# A restore-over-clone accident left 106 files reverted and 111 upstream-deleted
# files resurrected, HEAD untouched. Every link resolved, `--check` said ok, and
# `git pull` said "Already up to date" - three green signals on a corrupted
# install. The advisory does not fix that (dirtiness is not staleness and this
# cannot tell a mid-edit maintainer from a corrupted restore); it stops the
# second question from being SILENT while the first answers ok.
# --------------------------------------------------------------------------- #
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

ADVISORY = "content not verified"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


def _git_source(tmp_path: Path) -> Path:
    """A fake checkout that is a real git repo with everything committed."""
    src = _make_source(tmp_path)
    repo = tmp_path / "checkout"
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "initial")
    return src


@needs_git
def test_clean_checkout_prints_no_advisory(tmp_path: Path) -> None:
    """The line must not fire on a healthy checkout - a warning that appears on
    every box trains everyone to ignore it, which is the antipattern this whole
    advisory is meant to avoid rather than join."""
    src = _git_source(tmp_path)
    _run(tmp_path, src)
    res = _run(tmp_path, src, "--check")
    assert ADVISORY not in res.stdout
    assert "CPP_COMMANDS_LINK: ok" in res.stdout
    assert res.returncode == 0


@needs_git
def test_dirty_checkout_reports_split_counts(tmp_path: Path) -> None:
    """Tracked and untracked are reported SEPARATELY, which is what makes the
    line diagnostic: a maintainer mid-edit reads `1 tracked, 1 untracked`, the
    #685 corruption read 106 and 111. One merged total makes those identical."""
    src = _git_source(tmp_path)
    _run(tmp_path, src)
    (src / "flow" / "flow-cmd.md").write_text("# tampered\n")   # tracked change
    (src / "flow" / "resurrected.md").write_text("# zombie\n")  # untracked add

    res = _run(tmp_path, src, "--check")
    assert "checkout: 1 tracked modified, 1 untracked (-uall)" in res.stdout


@needs_git
def test_advisory_never_changes_the_verdict_or_exit_code(tmp_path: Path) -> None:
    """THE #685 THESIS, as a test: a corrupted working tree still reports `ok`,
    because topology really is fine. The advisory is an observation printed
    alongside the verdict - it must never become the verdict."""
    src = _git_source(tmp_path)
    _run(tmp_path, src)
    (src / "cicd" / "cicd-cmd.md").write_text("# month-old content\n")

    res = _run(tmp_path, src, "--check")
    assert ADVISORY in res.stdout                      # the silence is broken
    assert "CPP_COMMANDS_LINK: ok" in res.stdout       # ...but ok still means ok
    assert "CPP_COMMANDS_LINK: drift" not in res.stdout
    assert res.returncode == 0
    assert "WARNING" not in res.stdout


@needs_git
def test_advisory_is_suppressible(tmp_path: Path) -> None:
    src = _git_source(tmp_path)
    _run(tmp_path, src)
    (src / "flow" / "flow-cmd.md").write_text("# tampered\n")

    env = dict(os.environ)
    env["CPP_COMMANDS_LINK_HOME"] = str(tmp_path / "home")
    env["CPP_COMMANDS_LINK_NO_PROBE"] = "1"
    res = subprocess.run(
        ["bash", str(SCRIPT), "--source", str(src), "--check"],
        capture_output=True, text=True, env=env,
    )
    assert ADVISORY not in res.stdout
    assert "CPP_COMMANDS_LINK: ok" in res.stdout


# --- Fail-open: TESTED, not asserted ---------------------------------------
# `--check` had no git dependency before #685. A fail-open that only works when
# someone remembered to write it correctly is not fail-open, so each path gets
# its own test: the check must keep working exactly as it did with no git at
# all, outside a repo, and when git itself errors.
def test_fail_open_when_source_is_not_a_repo(tmp_path: Path) -> None:
    """The pre-#685 fixture: a plain directory. No advisory, unchanged verdict."""
    src = _make_source(tmp_path)
    _run(tmp_path, src)
    res = _run(tmp_path, src, "--check")
    assert ADVISORY not in res.stdout
    assert "CPP_COMMANDS_LINK: ok" in res.stdout
    assert res.returncode == 0


def test_fail_open_when_git_is_absent(tmp_path: Path) -> None:
    """PATH carrying the coreutils the script needs but NO git - the
    CI-container shape (uv:python3.11-slim ships none of git/docker/gitleaks).
    The check must still answer its own question rather than erroring on a
    dependency it never needed before #685.

    The PATH is built from explicit symlinks rather than emptied outright: an
    empty PATH also removes `ln`/`mkdir`/`readlink`, so the script would fail
    for reasons that have nothing to do with git and the test would pass while
    proving nothing.
    """
    src = _make_source(tmp_path)
    stub_path = tmp_path / "nogitbin"
    stub_path.mkdir()
    for tool in ("mkdir", "ln", "rm", "readlink", "basename", "grep", "bash"):
        found = shutil.which(tool)
        if found:
            (stub_path / tool).symlink_to(found)
    assert shutil.which("git", path=str(stub_path)) is None, "fixture must lack git"

    env = dict(os.environ)
    env["CPP_COMMANDS_LINK_HOME"] = str(tmp_path / "home")
    env["PATH"] = str(stub_path)
    for args in ((), ("--check",)):
        res = subprocess.run(
            ["bash", str(SCRIPT), "--source", str(src), *args],
            capture_output=True, text=True, env=env,
        )
        assert ADVISORY not in res.stdout
        assert res.returncode == 0, res.stderr
    assert "CPP_COMMANDS_LINK: ok" in res.stdout


def test_fail_open_when_git_errors(tmp_path: Path) -> None:
    """A git on PATH that fails every invocation (broken install, bad config).
    Errors must be swallowed - no advisory, no stderr leakage into the verdict,
    no exit-code change."""
    src = _make_source(tmp_path)
    stub_path = tmp_path / "brokenbin"
    stub_path.mkdir()
    stub = stub_path / "git"
    stub.write_text("#!/usr/bin/env bash\necho 'fatal: broken' >&2\nexit 128\n")
    stub.chmod(0o755)

    env = dict(os.environ)
    env["CPP_COMMANDS_LINK_HOME"] = str(tmp_path / "home")
    env["PATH"] = f"{stub_path}:{env['PATH']}"
    subprocess.run(["bash", str(SCRIPT), "--source", str(src)],
                   capture_output=True, text=True, env=env)
    res = subprocess.run(
        ["bash", str(SCRIPT), "--source", str(src), "--check"],
        capture_output=True, text=True, env=env,
    )
    assert ADVISORY not in res.stdout
    assert "CPP_COMMANDS_LINK: ok" in res.stdout
    assert res.returncode == 0


def test_header_states_ok_is_topology_not_health() -> None:
    """The claim-shaped half of #685. The old header concluded that command
    drift was 'structurally impossible' - true of CACHE drift, false of
    working-tree corruption, and that inference is what made `ok` read as a
    health verdict.

    Asserted POSITIVELY, on the corrective claims being present. The obvious
    negative check - that the phrase 'structurally impossible' is absent - is
    wrong here and this test failed on it first: the header now QUOTES the old
    conclusion in order to correct it, which is exactly the shape a reader needs
    and a substring ban forbids. Banning a phrase bans its retraction too.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    assert "TOPOLOGY VERDICT, NOT A HEALTH VERDICT" in text, (
        "the --check contract no longer says `ok` is topology-only (issue #685)"
    )
    assert "cannot follow the checkout's CONTENT" in text, (
        "the header no longer explains WHY topology and content differ - a link "
        "follows the ref, not the working tree (issue #685)"
    )
