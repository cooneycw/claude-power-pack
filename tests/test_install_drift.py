"""Regression tests for the surviving install-drift jobs (#622/#662).

The marketplace clone/cache parity walk retired with that distribution lane,
but installed helpers remain byte-compared with checkout helpers through the
symlink restoration in #663. Retired marketplace state is still reported as a
non-failing migration finding. All cases run on hermetic HOME/checkout trees.
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
HELPER = "flow-start-resolve.sh"
HELPER_BODY = "#!/usr/bin/env bash\necho resolve\n"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)


def _make_checkout(root: Path) -> Path:
    """A post-#662 checkout deliberately has no plugins/ directory."""
    (root / ".claude" / "commands" / "flow").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "CLAUDE.md").write_text("# fake CPP\n", encoding="utf-8")
    (root / ".claude" / "commands" / "flow" / "auto.md").write_text(
        "# auto\n", encoding="utf-8"
    )
    (root / "scripts" / HELPER).write_text(HELPER_BODY, encoding="utf-8")
    return root


def _make_cache(home: Path, *families: str) -> Path:
    cache = home / ".claude" / "plugins" / "cache" / "cpp"
    for family in families:
        commands = cache / family / "1.1.0" / "commands"
        commands.mkdir(parents=True)
        (commands / "help.md").write_text("# stale snapshot\n", encoding="utf-8")
    return cache


def _make_helpers(home: Path) -> Path:
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / HELPER).write_text(HELPER_BODY, encoding="utf-8")
    return scripts


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


def test_stale_helper_is_real_drift_in_every_output_mode(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    scripts = _make_helpers(home)
    (scripts / HELPER).write_text(
        "#!/usr/bin/env bash\necho OLD\n", encoding="utf-8"
    )

    report = _run(checkout, home)
    quiet = _run(checkout, home, "--quiet")
    json_result = _run(checkout, home, "--json")
    payload = json.loads(json_result.stdout)

    assert report.returncode == 0, report.stdout + report.stderr
    assert "0 current, 1 stale" in report.stdout
    assert f"Stale helpers: {HELPER}" in report.stdout
    assert "INSTALL_DRIFT: drift" in report.stdout
    assert quiet.returncode == 0
    assert quiet.stdout.splitlines() == [
        "CPP install: 1 helper(s) stale - run /cpp:update"
    ]
    assert json_result.returncode == 0
    assert payload["verdict"] == "drift"
    assert payload["helpers_stale"] == 1
    assert payload["stale_helpers"] == [HELPER]


def test_host_only_scripts_are_not_judged(tmp_path: Path):
    # A script the user put in ~/.claude/scripts that CPP does not ship is none
    # of this check's business - flagging it would make the check cry wolf.
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    scripts = _make_helpers(home)
    (scripts / "my-own-tool.sh").write_text("#!/bin/sh\necho host\n", encoding="utf-8")

    result = _run(checkout, home)

    assert result.returncode == 0
    assert "1 current, 0 stale" in result.stdout
    assert "my-own-tool.sh" not in result.stdout
    assert "INSTALL_DRIFT: ok" in result.stdout


def test_split_install_is_named_with_current_helpers_and_retired_cache(tmp_path: Path):
    # The two independently installed halves from #622 remain visible during
    # migration: helpers can match the checkout while the old command cache is
    # still present. Cache contents are no longer judged after #662.
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    _make_helpers(home)
    _make_cache(home, "flow")

    report = _run(checkout, home)
    payload = json.loads(_run(checkout, home, "--json").stdout)

    assert report.returncode == 0
    assert "SPLIT INSTALL" in report.stdout
    assert "1 current, 0 stale" in report.stdout
    assert "INSTALL_DRIFT: skipped" in report.stdout
    assert payload["split"] is True


def test_stale_helpers_and_retired_cache_coexist_with_drift_dominant(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    scripts = _make_helpers(home)
    (scripts / HELPER).write_text("#!/bin/sh\necho stale\n", encoding="utf-8")
    _make_cache(home, "flow")

    report = _run(checkout, home)
    quiet = _run(checkout, home, "--quiet")
    payload = json.loads(_run(checkout, home, "--json").stdout)

    assert "Stale helpers" in report.stdout
    assert "/plugin uninstall flow@cpp" in report.stdout
    assert "INSTALL_DRIFT: drift" in report.stdout
    assert len(quiet.stdout.splitlines()) == 1
    assert "1 helper(s) stale" in quiet.stdout
    assert "retired marketplace surface" in quiet.stdout
    assert payload["verdict"] == "drift"
    assert payload["cache_families"] == ["flow"]


def test_plugins_less_checkout_with_lingering_cache_is_retired_info(tmp_path: Path):
    """The #662 regression: removed checkout sources must not crash the walk."""
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    _make_cache(home, "flow")

    result = _run(checkout, home)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "retired CPP marketplace surface" in result.stdout
    assert "/plugin uninstall flow@cpp" in result.stdout
    assert "INSTALL_DRIFT: skipped" in result.stdout
    assert "drift" not in result.stderr.lower()


def test_multiple_cached_families_are_named(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    _make_cache(home, "flow", "security")

    result = _run(checkout, home)

    assert result.returncode == 0
    assert "installed families flow security" in result.stdout
    assert "/plugin uninstall flow@cpp" in result.stdout
    assert "/plugin uninstall security@cpp" in result.stdout


def test_quiet_retired_cache_is_one_non_failing_line(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    _make_cache(home, "flow", "security")

    result = _run(checkout, home, "--quiet")

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines == [
        "CPP install: retired marketplace surface pending uninstall (#662/#663): flow,security"
    ]


def test_no_retired_surface_is_skipped_silently_in_quiet_mode(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    home.mkdir()

    report = _run(checkout, home)
    quiet = _run(checkout, home, "--quiet")

    assert report.returncode == 0
    assert "INSTALL_DRIFT: skipped" in report.stdout
    assert quiet.returncode == 0
    assert quiet.stdout == ""


def test_marketplace_clone_is_reported_without_cache(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    (home / ".claude" / "plugins" / "marketplaces" / "cpp").mkdir(parents=True)

    report = _run(checkout, home)
    quiet = _run(checkout, home, "--quiet")

    assert report.returncode == 0
    assert "marketplace clone" in report.stdout
    assert "(retired)" in report.stdout
    assert quiet.stdout.count("\n") == 1
    assert "retired marketplace clone" in quiet.stdout


def test_json_reports_skipped_retired_surface(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    _make_cache(home, "flow")

    result = _run(checkout, home, "--json")
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["verdict"] == "skipped"
    assert payload["reason"] == "retired marketplace surface"
    assert payload["cache_families"] == ["flow"]


def test_no_checkout_is_skipped_not_failed(tmp_path: Path):
    home = tmp_path / "home"
    _make_cache(home, "flow")
    bin_dir = tmp_path / "elsewhere" / "bin"
    bin_dir.mkdir(parents=True)
    copied_script = bin_dir / "install-drift.sh"
    shutil.copy(SCRIPT, copied_script)

    result = subprocess.run(
        ["bash", str(copied_script)],
        env={"CPP_INSTALL_DRIFT_HOME": str(home), "PATH": os.environ.get("PATH", "")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "no CPP checkout" in result.stdout
    assert "INSTALL_DRIFT: skipped" in result.stdout


def test_bad_checkout_override_is_an_error(tmp_path: Path):
    home = tmp_path / "home"
    _make_cache(home, "flow")

    result = _run(tmp_path / "not-a-checkout", home)

    assert result.returncode == 2
    assert "INSTALL_DRIFT: error" in result.stdout


def test_check_never_writes(tmp_path: Path):
    checkout = _make_checkout(tmp_path / "checkout")
    home = tmp_path / "home"
    _make_cache(home, "flow")

    def snapshot(root: Path):
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    before = snapshot(checkout), snapshot(home)
    _run(checkout, home)
    assert (snapshot(checkout), snapshot(home)) == before
