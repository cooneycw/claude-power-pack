"""Tests for scripts/cpp-commands-link.sh (issue #663).

The user-scope command-surface symlinker: per-family links from
~/.claude/commands/<family> into the checkout's .claude/commands/, so the
executed command text follows `git pull` atomically (the reconciliation
property the /plugin cache lacked - #662).

Ownership contract under test: the script may only ever touch SYMLINKS whose
readlink target ends in `/.claude/commands/<family>`. Real files, real dirs,
and symlinks pointing anywhere else are foreign - reported, never modified.

Pure filesystem: the script shells only ln/readlink/mkdir/rm, so no
binary guards are needed (the guarded set is git/docker/gitleaks).
"""

import os
import subprocess
from pathlib import Path

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
    assert result.returncode == 1
    assert "missing  flow" in result.stdout
    assert "CPP_COMMANDS_LINK: drift" in result.stdout


def test_check_is_read_only(tmp_path: Path):
    src = _make_source(tmp_path)
    result = _run(tmp_path, src, "--check")
    assert result.returncode == 1
    assert "CPP_COMMANDS_LINK: drift" in result.stdout
    assert not _target(tmp_path).exists(), "--check must not create anything"


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
