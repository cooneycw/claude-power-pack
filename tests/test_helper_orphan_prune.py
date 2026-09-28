"""The prune half of `/cpp:update` Step 5b (issue #1263).

Step 5b linked every executable in `scripts/` into `~/.claude/scripts/` and
removed nothing, so a helper deleted upstream left a dangling link at the stable
path indefinitely. install-drift NAMED it at every session start; nothing acted
on it. Measured live: `project-next-vendor.py`, dangling from af348f8 (#1144)
until someone deleted it by hand.

THE NEGATIVE CONTROL (ADR 0008, as the issue states it): an upstream-deleted
script whose symlink is still installed must be named AND pruned. The first test
is that case end to end - install-drift's own `--json` orphan list drives the
seam, exactly as Step 5b does - and it fails on the pre-fix seam, which had no
`unlink-orphan` and exited 2 with the link still in place.

The refusal cases are the other verdict. A prune that removed whatever it was
handed would pass the first test and delete a user's tool, a live helper, or a
neighbour project's link, so each of those is pinned as surviving.
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
SEAM = ROOT / "scripts" / "cpp-host-write.sh"
DRIFT = ROOT / "scripts" / "install-drift.sh"
UPDATE_DOC = ROOT / ".claude" / "commands" / "cpp" / "update.md"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash on PATH")


#: The seam honours this as a caller's request not to write the named surfaces
#: (a Kyle session container sets it). A test that inherits it measures the
#: environment it runs in, not the code: every removal reads DEFERRED and the
#: suite is red on unmodified main in every container (issue #1343). A test
#: that is ABOUT deferral names the variable explicitly instead.
DEFER_ENV = "CPP_DEFER_SURFACES"


def _host_env(**overrides: str) -> dict[str, str]:
    """The caller's environment minus DEFER_ENV, plus `overrides`."""
    env = {k: v for k, v in os.environ.items() if k != DEFER_ENV}
    env.update(overrides)
    return env


def _checkout(root: Path) -> Path:
    (root / ".claude" / "commands").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "CLAUDE.md").write_text("# fake CPP\n", encoding="utf-8")
    # The seam itself: what distinguishes a CPP checkout from any Claude project.
    (root / "scripts" / "cpp-host-write.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    return root


def _script(checkout: Path, name: str) -> Path:
    path = checkout / "scripts" / name
    path.write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _seam(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SEAM), *args],
        env={"HOME": str(home), "PATH": os.environ.get("PATH", "")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


def _orphans(checkout: Path, home: Path) -> list[str]:
    result = subprocess.run(
        ["bash", str(DRIFT), "--json"],
        env={
            "CPP_INSTALL_DRIFT_CHECKOUT": str(checkout),
            "CPP_INSTALL_DRIFT_HOME": str(home),
            "PATH": os.environ.get("PATH", ""),
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return list(json.loads(result.stdout)["orphaned_helpers"])


def test_an_upstream_deleted_helper_is_named_AND_pruned(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path / "cpp")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    kept = _script(checkout, "kept.sh")
    gone = _script(checkout, "retired-vendor.py")
    (scripts / "kept.sh").symlink_to(kept)
    (scripts / "retired-vendor.py").symlink_to(gone)
    gone.unlink()  # deleted upstream; the installed link now dangles

    named = _orphans(checkout, home)
    assert named == ["retired-vendor.py"], named

    # Step 5b's prune loop: install-drift's list, one seam call per name.
    for name in named:
        result = _seam(home, "unlink-orphan", str(scripts), name)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "orphan removed" in result.stdout

    assert not (scripts / "retired-vendor.py").is_symlink(), "the orphan must be gone"
    assert (scripts / "kept.sh").resolve() == kept, "a live helper must survive"
    assert _orphans(checkout, home) == []


@pytest.mark.parametrize(
    "case", ["live", "host-file", "neighbour", "claude-project", "not-install-shape"]
)
def test_anything_that_is_not_our_dangling_link_is_refused(tmp_path: Path, case: str) -> None:
    checkout = _checkout(tmp_path / "cpp")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    entry = scripts / "tool.sh"
    if case == "live":
        entry.symlink_to(_script(checkout, "tool.sh"))
    elif case == "host-file":
        entry.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    elif case == "neighbour":
        # Same install SHAPE, but the root is not a CPP checkout.
        other = tmp_path / "other-project"
        (other / "scripts").mkdir(parents=True)
        entry.symlink_to(other / "scripts" / "tool.sh")
    elif case == "claude-project":
        # A neighbour that IS a Claude project - CLAUDE.md and .claude/commands -
        # but not CPP. The first cut accepted these two generic markers as
        # proof of ownership and deleted the link (counter-model review).
        other = tmp_path / "other-claude-project"
        (other / ".claude" / "commands").mkdir(parents=True)
        (other / "scripts").mkdir()
        (other / "CLAUDE.md").write_text("# someone else\n", encoding="utf-8")
        entry.symlink_to(other / "scripts" / "tool.sh")
        assert not entry.exists(), "fixture must dangle"
    else:
        # Dangling, into the CPP checkout, but not `<root>/scripts/<own name>`.
        entry.symlink_to(checkout / "scripts" / "renamed.sh")

    result = _seam(home, "unlink-orphan", str(scripts), "tool.sh")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "REFUSED" in result.stderr
    assert entry.is_symlink() or entry.exists(), f"{case}: the entry must survive"


def test_a_deferred_scripts_dir_is_not_pruned(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path / "cpp")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "gone.sh").symlink_to(checkout / "scripts" / "gone.sh")

    result = _seam(home, "unlink-orphan", str(scripts), "gone.sh", "--defer", "~/.claude/scripts")

    assert result.returncode == 3, result.stdout + result.stderr
    assert "DEFERRED" in result.stdout
    assert (scripts / "gone.sh").is_symlink()


def test_a_name_with_a_path_separator_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude" / "scripts").mkdir(parents=True)
    result = _seam(home, "unlink-orphan", str(home / ".claude" / "scripts"), "../settings.json")
    assert result.returncode == 1


def test_update_step_5b_wires_the_prune_to_install_drifts_orphan_list() -> None:
    """The seam is only half the fix; the command must call it.

    Red on the pre-fix document, whose Step 5b only ever called `link-into`.
    """
    text = UPDATE_DOC.read_text(encoding="utf-8")
    start = text.index("## Step 5b: Script Symlink Refresh")
    end = text.index("## Step 5b.1:")
    step = text[start:end]
    assert "orphaned_helpers" in step
    assert "cpp-host-write.sh unlink-orphan" in step


def _listing_block() -> str:
    text = UPDATE_DOC.read_text(encoding="utf-8")
    step = text[text.index("## Step 5b: Script Symlink Refresh") : text.index("## Step 5b.1:")]
    blocks = [b for b in re.findall(r"```bash\n(.*?)```", step, re.S) if "ORPHAN_SCAN" in b]
    assert len(blocks) == 1, "Step 5b must carry exactly one orphan-listing block"
    return blocks[0]


def _run_listing(checkout: Path, home: Path) -> str:
    return subprocess.run(
        ["bash", "-c", _listing_block()],
        env=_host_env(HOME=str(home), CPP_DIR=str(checkout)),
        capture_output=True,
        text=True,
    ).stdout


@pytest.mark.skipif(shutil.which("jq") is None, reason="the listing block uses jq")
def test_the_step_5b_listing_names_an_orphan_the_scan_found(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path / "cpp")
    shutil.copy2(DRIFT, checkout / "scripts" / "install-drift.sh")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "gone.sh").symlink_to(checkout / "scripts" / "gone.sh")
    assert not (scripts / "gone.sh").exists(), "fixture must dangle"

    out = _run_listing(checkout, home)
    assert "gone.sh" in out, out
    assert "No orphaned helper links" not in out, out


@pytest.mark.skipif(shutil.which("jq") is None, reason="the listing block uses jq")
def test_a_scan_that_did_not_run_is_not_reported_clean(tmp_path: Path) -> None:
    """No install-drift.sh in the checkout: the scan cannot run.

    The first cut printed "No orphaned helper links" here - the same words as a
    scan that looked and found nothing (counter-model review).
    """
    checkout = _checkout(tmp_path / "cpp")
    assert not (checkout / "scripts" / "install-drift.sh").exists(), "fixture must lack the scanner"
    home = tmp_path / "home"
    (home / ".claude" / "scripts").mkdir(parents=True)

    out = _run_listing(checkout, home)
    assert "No orphaned helper links" not in out, out
    assert "NOT run" in out, out


def _prune_block() -> str:
    text = UPDATE_DOC.read_text(encoding="utf-8")
    step = text[text.index("## Step 5b: Script Symlink Refresh") : text.index("## Step 5b.1:")]
    blocks = [b for b in re.findall(r"```bash\n(.*?)```", step, re.S) if "PRUNE_CONFIRMED" in b]
    assert len(blocks) == 1, "Step 5b must carry exactly one prune block"
    return blocks[0]


def _prune_fixture(tmp_path: Path) -> tuple[Path, str]:
    """One dangling link of ours and one listed orphan that is already gone."""
    checkout = _checkout(tmp_path / "cpp")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "gone.sh").symlink_to(checkout / "scripts" / "gone.sh")
    assert not (scripts / "vanished.sh").exists(), "fixture: one listed orphan is already gone"
    # The block calls the stable path; point it at the seam under test.
    (scripts / "cpp-host-write.sh").symlink_to(SEAM)
    return home, _prune_block().replace("<the listed names>", "gone.sh vanished.sh")


def test_the_prune_tally_does_not_count_an_already_absent_entry_as_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit 0 means removed OR already absent; only the first is this run's work.

    The ambient deferral is set ON PURPOSE (issue #1343): this test must hold in
    a Kyle container, which sets it, and not only on a host that does not. Red
    on the pre-fix env, which inherited it and read `0 removed, ... 2 refused
    or deferred` - on every host, because the variable comes from here.
    """
    monkeypatch.setenv(DEFER_ENV, "~/.claude/scripts")
    home, block = _prune_fixture(tmp_path)
    scripts = home / ".claude" / "scripts"

    out = subprocess.run(
        ["bash", "-c", block],
        env=_host_env(HOME=str(home), PRUNE_CONFIRMED="yes"),
        capture_output=True,
        text=True,
    ).stdout
    assert "1 removed, 1 already absent, 0 refused" in out, out
    assert not (scripts / "gone.sh").is_symlink()


def test_a_deferral_the_caller_names_is_honoured_and_tallied(tmp_path: Path) -> None:
    """The other verdict: a deferral that IS the caller's request removes nothing.

    Stripping the ambient variable must not cost the deferral path its coverage.
    """
    home, block = _prune_fixture(tmp_path)
    scripts = home / ".claude" / "scripts"

    out = subprocess.run(
        ["bash", "-c", block],
        env=_host_env(HOME=str(home), PRUNE_CONFIRMED="yes", **{DEFER_ENV: "~/.claude/scripts"}),
        capture_output=True,
        text=True,
    ).stdout
    assert "0 removed, 0 already absent, 2 refused or deferred" in out, out
    assert (scripts / "gone.sh").is_symlink(), "a deferred surface must not be written"


def test_an_unconfirmed_prune_removes_nothing(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path / "cpp")
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "gone.sh").symlink_to(checkout / "scripts" / "gone.sh")
    (scripts / "cpp-host-write.sh").symlink_to(SEAM)
    block = _prune_block().replace("<the listed names>", "gone.sh")
    # No DEFER_ENV either: a deferral also removes nothing, so under an inherited
    # one this test passed whatever the confirmation check did (issue #1343).
    env = {k: v for k, v in _host_env(HOME=str(home)).items() if k != "PRUNE_CONFIRMED"}

    subprocess.run(["bash", "-c", block], env=env, capture_output=True, text=True)
    assert (scripts / "gone.sh").is_symlink(), "no confirmation, no delete"
