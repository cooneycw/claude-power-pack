"""Tests for scripts/flow-helpers-install.sh - host helper installation.

Contract:
- Install the flow helper family into $HOME/.claude/scripts/, idempotently.
- SYMLINK when the source is a CPP checkout (follows `git pull`); COPY when the
  source is a legacy plugin cache during the #662/#663 migration.
- `--check` is read-only and reports ok / missing / stale, exit 1 on the latter
  two, so /flow:doctor can call it without mutating the host.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from tests.test_permissions_template_link_parity import installer_helper_names

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "flow-helpers-install.sh"

# DERIVED from the script, never duplicated (issue #677). This list used to be a
# hardcoded 9-entry copy beside a 13-entry array - missing flow-worktree-claim.sh,
# flow-wave-registry.sh, flow-wave-plan.py and flow-finish-gate.sh - so it could
# not detect an omission from the thing it was testing; it only proved the copy
# matched itself, and stayed green while two required helpers were missing from
# the array. Parsing the array is what makes these tests cover the real family.
HELPERS = installer_helper_names()
REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(
    *args: str,
    home: Path,
    source: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["FLOW_HELPERS_HOME"] = str(home)
    if source is not None:
        env["FLOW_HELPERS_SOURCE"] = str(source)
    else:
        env.pop("FLOW_HELPERS_SOURCE", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run(
        [str(INSTALLER), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_HELPERS:")]
    assert lines, f"no verdict line in output:\n{proc.stdout}\n{proc.stderr}"
    return lines[-1].split(":", 1)[1].strip()


@pytest.fixture
def plugin_source(tmp_path: Path) -> Path:
    """A legacy-cache-shaped source: scripts/ with no CLAUDE.md above it."""
    src = tmp_path / "plugin" / "scripts"
    src.mkdir(parents=True)
    for name in HELPERS:
        dest = src / name
        dest.write_bytes((ROOT / "scripts" / name).read_bytes())
        dest.chmod(0o755)
    return src


def test_script_is_executable():
    assert INSTALLER.exists()
    assert os.access(INSTALLER, os.X_OK), "flow-helpers-install.sh must be executable"


def test_installs_the_whole_family(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    proc = _run(home=home, source=plugin_source)
    assert proc.returncode == 0, proc.stderr
    assert _verdict(proc) == "installed"
    for name in HELPERS:
        installed = home / ".claude" / "scripts" / name
        assert installed.is_file(), f"{name} not installed"
        assert installed.stat().st_mode & 0o111, f"{name} installed without exec bit"


def test_install_is_idempotent(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    _run(home=home, source=plugin_source)
    second = _run(home=home, source=plugin_source)
    assert second.returncode == 0
    assert _verdict(second) == "ok", "re-running must be a no-op, not a rewrite"


def test_plugin_source_copies_rather_than_symlinks(tmp_path: Path, plugin_source: Path):
    # A symlink into a version-stamped legacy cache dangles on uninstall; the copy
    # keeps working (and goes "stale", which --check reports).
    home = tmp_path / "home"
    _run(home=home, source=plugin_source)
    installed = home / ".claude" / "scripts" / "flow-start-resolve.sh"
    assert not installed.is_symlink(), "plugin-sourced helpers must be copied, not linked"


def test_checkout_source_symlinks(tmp_path: Path):
    # A checkout-shaped source: CLAUDE.md + .claude/commands one level above scripts/.
    checkout = tmp_path / "cpp"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / ".claude" / "commands").mkdir(parents=True)
    (checkout / "CLAUDE.md").write_text("# CPP\n")
    for name in HELPERS:
        dest = checkout / "scripts" / name
        dest.write_bytes((ROOT / "scripts" / name).read_bytes())
        dest.chmod(0o755)

    home = tmp_path / "home"
    proc = _run(home=home, source=checkout / "scripts")
    assert proc.returncode == 0, proc.stderr
    installed = home / ".claude" / "scripts" / "flow-start-resolve.sh"
    assert installed.is_symlink(), "checkout-sourced helpers must be symlinked to follow git pull"
    assert installed.resolve() == (checkout / "scripts" / "flow-start-resolve.sh").resolve()


def test_check_reports_missing_on_a_fresh_host(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    proc = _run("--check", home=home, source=plugin_source)
    assert proc.returncode == 1
    assert _verdict(proc) == "missing"
    assert not (home / ".claude" / "scripts").exists(), "--check must not write anything"


def test_check_reports_ok_after_install(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    _run(home=home, source=plugin_source)
    proc = _run("--check", home=home, source=plugin_source)
    assert proc.returncode == 0
    assert _verdict(proc) == "ok"


def test_check_detects_stale_legacy_cache_copies(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    _run(home=home, source=plugin_source)
    # Simulate the upgrade: the bundled source moves on, the installed copy does not.
    upgraded = plugin_source / "gh-pr-merge.sh"
    upgraded.write_text(upgraded.read_text() + "\n# v2\n")

    proc = _run("--check", home=home, source=plugin_source)
    assert proc.returncode == 1
    assert _verdict(proc) == "stale"
    assert "STALE gh-pr-merge.sh" in proc.stdout

    # And repair brings it back.
    fixed = _run(home=home, source=plugin_source)
    assert _verdict(fixed) == "installed"
    assert _verdict(_run("--check", home=home, source=plugin_source)) == "ok"


def test_check_treats_a_dangling_symlink_as_missing(tmp_path: Path, plugin_source: Path):
    # The failure mode a naive symlink-into-plugin-cache install would produce.
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "flow-start-resolve.sh").symlink_to(tmp_path / "gone" / "flow-start-resolve.sh")

    proc = _run("--check", home=home, source=plugin_source)
    assert proc.returncode == 1
    assert _verdict(proc) == "missing"
    assert "dangling symlink" in proc.stdout


def test_install_replaces_a_dangling_symlink(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    stale_link = scripts / "flow-start-resolve.sh"
    stale_link.symlink_to(tmp_path / "gone" / "flow-start-resolve.sh")

    proc = _run(home=home, source=plugin_source)
    assert proc.returncode == 0, proc.stderr
    assert not stale_link.is_symlink()
    assert stale_link.is_file() and stale_link.stat().st_mode & 0o111


def test_unknown_argument_is_rejected(tmp_path: Path, plugin_source: Path):
    proc = _run("--nope", home=tmp_path / "home", source=plugin_source)
    assert proc.returncode == 2
    assert "unknown argument" in proc.stderr


def test_help_stops_at_the_doc_block(tmp_path: Path):
    """--help must print the header and nothing after it (issue #686).

    The extractor is a hardcoded `sed -n '2,Np'` range, so it silently drifts
    whenever the header grows or shrinks - it was `2,37p` against a block ending
    at line 28, spilling `set -uo pipefail`, three variable assignments and two
    stray comment lines into user-visible output. Asserting on the CODE that
    must not appear (rather than on an exact line count) survives the header
    being edited, which is the thing that will happen next.
    """
    proc = _run("--help", home=tmp_path / "home")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    # The real help text is present...
    assert "flow-helpers-install.sh - Install the flow helper family" in out
    assert "FLOW_HELPERS_SOURCE" in out, "the last Env entry is the doc block's end"

    # ...and no executable code leaked past it.
    for leaked in ("set -uo pipefail", "SELF_DIR=", "HOME_DIR=", "TARGET_DIR=",
                   "HELPERS=("):
        assert leaked not in out, (
            f"--help leaked {leaked!r} - the sed range extends past the doc "
            f"block, which ends at the last `# Env:` entry (issue #686)"
        )


# --------------------------------------------------------------------------- #
# #927: `unverifiable` is not a lesser `ok`
#
# The installer already DETECTED that no source of truth was reachable - it
# printed "cannot compare" - and then emitted `FLOW_HELPERS: ok`. The honest
# sentence went to a human channel and the machine-readable verdict said
# success, which is the same shape as a refusal that exits 0. These tests pin
# the distinction from BOTH sides: a test that only checks the new word appears
# cannot tell you the old one stopped being emitted.
# --------------------------------------------------------------------------- #


def _stale_installed_copy(home: Path, drop: int = 2) -> Path:
    """An installed installer whose own allowlist is short by `drop` names.

    This is the container shape: `~/.claude/scripts/flow-helpers-install.sh` as
    a COPY rather than a symlink, so it can fall behind. On a host where it is a
    symlink into the checkout it cannot, which is why this is constructed rather
    than observed.
    """
    target = home / ".claude" / "scripts"
    target.mkdir(parents=True, exist_ok=True)
    text = INSTALLER.read_text(encoding="utf-8")
    for name in list(HELPERS)[-drop:]:
        line = f"    {name}\n"
        assert text.count(line) == 1, f"allowlist entry {name!r} appears {text.count(line)}x"
        text = text.replace(line, "")
    copy = target / "flow-helpers-install.sh"
    copy.write_text(text, encoding="utf-8")
    copy.chmod(0o755)
    return copy


def _run_installed(copy: Path, home: Path) -> subprocess.CompletedProcess[str]:
    """Run the INSTALLED copy with nothing else reachable - the container case.

    PRECONDITION ASSERTED (the #697 rule, landed as #933/#995 while this branch
    was open). This fixture's entire premise is that NO upstream is reachable -
    that is what makes it the container case rather than an ordinary run. The
    premise was never checked: had any of the searched locations existed under
    the fake HOME, the installer would have found a checkout and this would have
    been measuring something else while still passing. The absence is the
    fixture, so the absence gets asserted.
    """
    for candidate in ("Projects/claude-power-pack", ".claude-power-pack"):
        assert not (home / candidate).exists(), (
            f"{candidate} exists under the fake HOME, so an upstream IS reachable "
            f"and this is no longer the no-upstream case"
        )
    return subprocess.run(
        ["bash", str(copy)], check=False, capture_output=True, text=True,
        # negative-fixture: allow absence is a missing checkout, asserted above
        env={"HOME": str(home), "PATH": "/usr/bin:/bin",
             "FLOW_HELPERS_HOME": str(home)},
    )


def test_no_reachable_source_reports_unverifiable_and_not_ok(tmp_path: Path) -> None:
    """Both sides of the word, in one assertion pair.

    `unverifiable` must APPEAR and `ok` must be ABSENT. Asserting only the first
    would still pass if the installer emitted both, or if `ok` were left on a
    later line - and "the new word shows up" is not the claim. The claim is that
    this state no longer reports success.
    """
    home = tmp_path / "home"
    proc = _run_installed(_stale_installed_copy(home), home)
    verdicts = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_HELPERS:")]
    assert verdicts == ["FLOW_HELPERS: unverifiable"], (
        f"expected exactly the unverifiable verdict, got {verdicts}\n{proc.stdout}"
    )
    assert proc.returncode == 0, (
        "exit stays 0: a container that cannot reach a checkout is not an error, "
        "and this verdict is read by a person deciding whether to repair rather "
        "than by a gate letting work through"
    )


def test_a_reachable_source_still_reports_ok(tmp_path: Path) -> None:
    """The other side. Without this, an installer wedged at `unverifiable`
    passes the test above and nothing notices that `ok` has stopped existing."""
    home = tmp_path / "home"
    _run(home=home)  # install everything current
    proc = _run(home=home)
    assert _verdict(proc) == "ok", f"a current install must still report ok: {proc.stdout}"


def test_every_verdict_carries_its_allowlist_length(tmp_path: Path) -> None:
    """The denominator (#952) applied to this script's own output.

    `ok` from a 22-entry allowlist and `ok` from a 24-entry one were the same
    line. A verdict that cannot be read against what produced it is the defect
    #927 was measured through.
    """
    home = tmp_path / "home"
    proc = _run(home=home)
    lines = dict(
        ln.split(":", 1) for ln in proc.stdout.splitlines() if ln.startswith("FLOW_HELPERS_")
    )
    assert "FLOW_HELPERS_ALLOWLIST" in lines, f"no allowlist length reported:\n{proc.stdout}"
    assert int(lines["FLOW_HELPERS_ALLOWLIST"].strip()) == len(HELPERS)
    assert "FLOW_HELPERS_INSTALLER" in lines, "the verdict does not say which installer ran"


def test_a_stale_installed_copy_reports_a_SHORTER_allowlist(tmp_path: Path) -> None:
    """The provenance line must actually discriminate, not merely exist.

    This is the positive control on the denominator: a 22 where main has 24 is
    what makes a stale install legible to a reader. Without it, asserting the
    line is present cannot tell a real count from a constant.
    """
    home = tmp_path / "home"
    proc = _run_installed(_stale_installed_copy(home, drop=2), home)
    reported = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_HELPERS_ALLOWLIST")]
    assert reported, f"no allowlist length on the unverifiable path:\n{proc.stdout}"
    assert int(reported[0].split(":", 1)[1]) == len(HELPERS) - 2, (
        f"the stale copy should report {len(HELPERS) - 2}, not {reported[0]}"
    )


def test_an_empty_source_reports_unverifiable_not_ok(tmp_path: Path) -> None:
    """Codex, MEDIUM: scanned nothing, reported clean - inside this change.

    A source directory holding none of the helper names skipped all 24 and
    emitted `ok` with `FLOW_HELPERS_ALLOWLIST: 24`. The allowlist length says
    what the installer KNOWS, not what it COMPARED, and only the first was
    printed. That directly contradicted the guarantee this same change added,
    that `ok` means a comparison happened.
    """
    home = tmp_path / "home"
    src = tmp_path / "src"
    src.mkdir()
    (src / "unrelated.txt").write_text("not a helper\n", encoding="utf-8")
    proc = _run(home=home, source=src)
    assert _verdict(proc) == "unverifiable", proc.stdout
    lines = dict(
        ln.split(":", 1) for ln in proc.stdout.splitlines() if ln.startswith("FLOW_HELPERS_")
    )
    assert int(lines["FLOW_HELPERS_EXAMINED"].strip()) == 0
    assert lines["FLOW_HELPERS_REASON"].strip() == "empty-source"


def test_a_populated_source_reports_a_NONZERO_examined_count(tmp_path: Path) -> None:
    """The other side of the examined denominator.

    Without this, an installer wedged at EXAMINED=0 passes the test above and
    nothing notices that real comparisons stopped happening.
    """
    home = tmp_path / "home"
    proc = _run(home=home)
    lines = dict(
        ln.split(":", 1) for ln in proc.stdout.splitlines() if ln.startswith("FLOW_HELPERS_")
    )
    assert int(lines["FLOW_HELPERS_EXAMINED"].strip()) == len(HELPERS), (
        f"a full source must examine all {len(HELPERS)} helpers: {proc.stdout}"
    )


@pytest.mark.parametrize("verdict_case", ["missing", "error"])
def test_provenance_is_present_on_the_non_success_verdicts(
    verdict_case: str, tmp_path: Path
) -> None:
    """Codex, MEDIUM: `emit_provenance` was defined BELOW the error exit.

    So "provenance on every verdict" held for the paths I was looking at and
    not for the ones I was not - the missing-source error fired before the
    function existed. Both non-success verdicts are checked here rather than
    trusting the claim.
    """
    home = tmp_path / "home"
    if verdict_case == "missing":
        proc = _run("--check", home=home)          # nothing installed yet
    else:
        proc = _run(home=home, source=tmp_path / "does-not-exist")
    assert _verdict(proc) == verdict_case, proc.stdout
    assert "FLOW_HELPERS_INSTALLER" in proc.stdout, (
        f"the {verdict_case} verdict carries no provenance:\n{proc.stdout}"
    )
    assert "FLOW_HELPERS_REASON" in proc.stdout


def test_repair_resolves_a_checkout_by_known_location_not_only_by_cwd() -> None:
    """Codex, MEDIUM: `scripts/...` is cwd-relative.

    Preferring a source of truth only works if one can be FOUND. Invoked from
    any repository other than the CPP checkout, the relative path misses, the
    chain falls through to the installed copy, and the stale installer then
    finds the checkout by its own upstream search and processes it with its own
    shortened allowlist - mechanism B, reproduced through the fix for it.
    """
    text = (REPO_ROOT / ".claude" / "commands" / "flow" / "repair.md").read_text(encoding="utf-8")
    assert "~/Projects/claude-power-pack/scripts/flow-helpers-install.sh" in text, (
        "repair.md resolves a checkout only relative to the cwd"
    )
    # The installed copy must remain LAST - that is the whole ordering fix.
    checkout_at = text.index("scripts/flow-helpers-install.sh")
    installed_at = text.index("~/.claude/scripts/flow-helpers-install.sh\n```")
    assert checkout_at < installed_at, (
        "the installed copy is no longer last in the chain; a repair must not "
        "prefer the artifact it repairs"
    )


def test_every_error_exit_in_the_script_is_preceded_by_provenance() -> None:
    """Codex pass 2: THREE error exits still bypassed it after the first fix.

    Moving `emit_provenance` above the exits made it AVAILABLE everywhere; it
    did not make it CALLED everywhere, and my error-path test exercised only
    the one branch I had looked at. This counts the population instead of
    sampling it, so a new error exit added without provenance fails here
    rather than being found by the next reviewer.
    """
    text = INSTALLER.read_text(encoding="utf-8")
    lines = text.splitlines()
    exits = [i for i, ln in enumerate(lines) if ln.strip() == 'echo "FLOW_HELPERS: error"']
    assert exits, "no error verdict found - this test has stopped measuring anything"
    unguarded = [
        i + 1 for i in exits
        if not any("emit_provenance" in lines[j] for j in range(max(0, i - 3), i))
    ]
    assert not unguarded, (
        f"error verdicts at line(s) {unguarded} emit no provenance, so a reader "
        f"cannot tell which installer failed or what its allowlist was"
    )


def test_repair_lists_every_upstream_location_the_installer_searches() -> None:
    """Codex pass 2: I documented TWO of the installer's three locations.

    And the prose said "the same three locations", so the text asserted a
    completeness it did not deliver. This derives the list from the installer
    rather than restating it, which is the only version that cannot drift.
    """
    installer = INSTALLER.read_text(encoding="utf-8")
    search = [ln for ln in installer.splitlines() if "for dir in" in ln and "claude-power-pack" in ln]
    assert len(search) == 1, f"the upstream search line has moved: {search}"
    locations = re.findall(r'(?:\$HOME_DIR/|/)([A-Za-z0-9_.-]*claude-power-pack)', search[0])
    assert locations, "could not derive the searched locations from the installer"

    repair = (REPO_ROOT / ".claude" / "commands" / "flow" / "repair.md").read_text(encoding="utf-8")
    missing = [loc for loc in locations if loc not in repair]
    assert not missing, (
        f"repair.md does not offer every checkout location the installer itself "
        f"searches: {missing}. A chain that finds fewer checkouts than the stale "
        f"installer does falls through to the stale installer."
    )


# --- Source integrity of a bundled helper (issue #1185) ---------------------
#
# Everything above this line tests INSTALLED-COPY-vs-SOURCE, which is drift.
# These test SOURCE-vs-ITS-RECORDED-DIGEST, which is a different question, and
# the one a Codex host installed from a bundle cannot otherwise answer.
#
# The bound is asserted as prose in `limits` and in the script; what these tests
# pin is narrower and checkable: a source that disagrees with its manifest is
# REFUSED and installs NOTHING, and "cannot verify" never reports as "verified".

MANIFEST_NAME = "SHA256SUMS"


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(scripts_dir: Path) -> None:
    rows = [
        f"{_sha256(f)}  {f.name}\n"
        for f in sorted(scripts_dir.iterdir())
        if f.is_file() and f.name != MANIFEST_NAME
    ]
    (scripts_dir / MANIFEST_NAME).write_text("# generated by the test fixture\n" + "".join(rows))


@pytest.fixture
def bundle_source(tmp_path: Path) -> Path:
    """A Codex-bundle-shaped source: SKILL.md beside scripts/, with a manifest.

    The SKILL.md sibling is what marks this a BUNDLE rather than a legacy plugin
    cache, and the distinction is load-bearing: a bundle with no manifest is
    refused, a legacy cache with no manifest is not.
    """
    bundle = tmp_path / "bundle"
    src = bundle / "scripts"
    src.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("# a generated skill\n")
    for name in HELPERS:
        dest = src / name
        dest.write_bytes((ROOT / "scripts" / name).read_bytes())
        dest.chmod(0o755)
    _write_manifest(src)
    return src


def _manifest_state(proc: subprocess.CompletedProcess[str]) -> str:
    lines = [
        ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_HELPERS_MANIFEST:")
    ]
    assert lines, f"no manifest line in output:\n{proc.stdout}\n{proc.stderr}"
    return lines[-1].split(":", 1)[1].strip()


def _installed(home: Path) -> list[str]:
    target = home / ".claude" / "scripts"
    return sorted(p.name for p in target.iterdir()) if target.is_dir() else []


def test_an_intact_bundle_installs(tmp_path: Path, bundle_source: Path):
    home = tmp_path / "home"
    proc = _run(home=home, source=bundle_source)
    assert _verdict(proc) == "installed"
    assert _manifest_state(proc) == "verified"
    assert proc.returncode == 0
    assert _installed(home), "an intact bundle must still install"


def test_a_tampered_source_is_refused_and_installs_nothing(
    tmp_path: Path, bundle_source: Path
):
    """The issue's own case: before #1185 this installed and reported success."""
    victim = bundle_source / "worktree-remove.sh"
    victim.write_bytes(victim.read_bytes() + b"\n# injected\n")
    home = tmp_path / "home"
    proc = _run(home=home, source=bundle_source)
    assert _verdict(proc) == "tampered"
    assert _manifest_state(proc) == "mismatch"
    assert proc.returncode == 5
    # THE LOAD-BEARING HALF. A refusal that still installed would be a warning.
    assert _installed(home) == []


def test_deleting_the_manifest_is_not_a_way_past_the_check(
    tmp_path: Path, bundle_source: Path
):
    (bundle_source / MANIFEST_NAME).unlink()
    home = tmp_path / "home"
    proc = _run(home=home, source=bundle_source)
    assert _verdict(proc) == "unverifiable-source"
    assert _manifest_state(proc) == "absent-on-bundle"
    assert proc.returncode == 6
    assert _installed(home) == []


def test_a_file_ADDED_to_a_bundle_is_refused(tmp_path: Path, bundle_source: Path):
    """The other direction, which a digest check usually forgets.

    Verifying only the rows the manifest lists is bypassed by ADDING a file
    rather than modifying one - an unlisted script named in HELPERS would be
    installed without ever being compared to anything.
    """
    (bundle_source / "friction-log.sh").unlink(missing_ok=True)
    _write_manifest(bundle_source)
    (bundle_source / "friction-log.sh").write_text("#!/bin/sh\necho added\n")
    home = tmp_path / "home"
    proc = _run(home=home, source=bundle_source)
    assert _verdict(proc) == "tampered"
    assert proc.returncode == 5
    assert _installed(home) == []


def test_a_file_REMOVED_from_a_bundle_is_refused(tmp_path: Path, bundle_source: Path):
    (bundle_source / "worktree-remove.sh").unlink()
    home = tmp_path / "home"
    proc = _run(home=home, source=bundle_source)
    assert _verdict(proc) == "tampered"
    assert proc.returncode == 5
    assert _installed(home) == []


def test_an_empty_manifest_is_not_a_clean_one(tmp_path: Path, bundle_source: Path):
    (bundle_source / MANIFEST_NAME).write_text("# rows removed\n")
    home = tmp_path / "home"
    proc = _run(home=home, source=bundle_source)
    assert _verdict(proc) == "unverifiable-source"
    assert _manifest_state(proc) == "empty"
    assert proc.returncode == 6
    assert _installed(home) == []


def test_tampered_and_unverifiable_source_stay_distinct_through_the_exit_code(
    tmp_path: Path, bundle_source: Path
):
    """Two different facts, never one word.

    `tampered` says the source DISAGREES with its manifest; `unverifiable-source`
    says this run COULD NOT ASK. Collapsing them into one verdict is the failure
    this issue is about one level up - and a caller reading only `$?` must be
    able to tell them apart too, so the distinction goes all the way to the
    exit code rather than living only in the printed word.
    """
    tampered_src = bundle_source
    victim = tampered_src / "worktree-remove.sh"
    victim.write_bytes(victim.read_bytes() + b"\n# injected\n")
    tampered = _run(home=tmp_path / "h1", source=tampered_src)

    unverifiable_src = tmp_path / "b2" / "scripts"
    unverifiable_src.mkdir(parents=True)
    (unverifiable_src.parent / "SKILL.md").write_text("# a generated skill\n")
    for name in HELPERS:
        dest = unverifiable_src / name
        dest.write_bytes((ROOT / "scripts" / name).read_bytes())
        dest.chmod(0o755)
    unverifiable = _run(home=tmp_path / "h2", source=unverifiable_src)

    assert _verdict(tampered) != _verdict(unverifiable)
    assert tampered.returncode != unverifiable.returncode
    assert {tampered.returncode, unverifiable.returncode} == {5, 6}


def test_a_source_with_no_manifest_and_no_bundle_marker_is_unaffected(
    tmp_path: Path, plugin_source: Path
):
    """Risk (b): the legacy CLAUDE_PLUGIN_ROOT cache must not be refused.

    The bundle test is a sibling SKILL.md, NOT `SOURCE_KIND=plugin` - the broader
    test would refuse the legacy migration cache for a reason that has nothing
    to do with it.
    """
    home = tmp_path / "home"
    proc = _run(home=home, source=plugin_source)
    assert _verdict(proc) == "installed"
    assert _manifest_state(proc) == "absent"
    assert proc.returncode == 0
    assert _installed(home)


def test_the_manifest_state_is_reported_on_every_verdict(
    tmp_path: Path, bundle_source: Path
):
    """"No manifest" must be REPORTED, never silently read as verified.

    An absent guard that looks like a guard that passed is the failure shape this
    repository refuses; the provenance line is what makes the two distinguishable
    without reading the script.
    """
    assert _manifest_state(_run(home=tmp_path / "a", source=bundle_source)) == "verified"
    (bundle_source / MANIFEST_NAME).unlink()
    assert (
        _manifest_state(_run(home=tmp_path / "b", source=bundle_source))
        == "absent-on-bundle"
    )


def test_the_GENERATED_manifest_is_accepted_by_the_INSTALLER(tmp_path: Path):
    """Closes the loop between the two halves of this change.

    The fixture above writes its own manifest, so it proves the installer reads
    THAT format. It does not prove codex-skill-sync.py WRITES that format. This
    copies a real generated bundle out of the checkout and installs from it: if
    the generator and the reader ever disagree on the format, every bundled host
    refuses every helper, and only a test spanning both would see it.
    """
    generated = ROOT / "codex" / "skills" / "flow-doctor"
    if not (generated / "scripts" / MANIFEST_NAME).is_file():
        pytest.skip(f"no generated manifest at {generated} - run codex-skill-sync.py --write")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "SKILL.md").write_bytes((generated / "SKILL.md").read_bytes())
    import shutil

    shutil.copytree(generated / "scripts", bundle / "scripts")
    proc = _run(home=tmp_path / "home", source=bundle / "scripts")
    assert _manifest_state(proc) == "verified", (
        "the generated manifest was not accepted by the installer - the writer "
        "and the reader disagree on the format"
    )
    assert _verdict(proc) == "installed"


def test_a_failing_digest_tool_is_UNVERIFIABLE_not_TAMPERED(
    tmp_path: Path, bundle_source: Path
):
    """Counter-model review (codex, MEDIUM), reproduced before fixing.

    `_digest_of` swallowed its exit status, so an unreadable file or a failing
    digest executable produced an empty string, compared unequal to every
    recorded digest, and reported `tampered` with exit 5 over an INTACT bundle.
    That is a false accusation AND the exact collapse this change exists to
    prevent: "the bytes disagree" and "I could not ask" are different facts.
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for tool in ("sha256sum", "shasum"):
        stub = fake_bin / tool
        stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["FLOW_HELPERS_HOME"] = str(tmp_path / "home")
    env["FLOW_HELPERS_SOURCE"] = str(bundle_source)
    proc = subprocess.run(
        [str(INSTALLER)], check=False, capture_output=True, text=True, env=env
    )

    assert _verdict(proc) == "unverifiable-source", proc.stdout + proc.stderr
    assert proc.returncode == 6
    assert _installed(tmp_path / "home") == []


def test_a_truncated_digest_is_not_compared(tmp_path: Path, bundle_source: Path):
    """The other direction of the same fix.

    A tool that succeeds but prints something that is not a digest must not have
    its output compared either - it would differ from the recorded value and
    read as tampering for a reason that is not tampering.
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for tool in ("sha256sum", "shasum"):
        stub = fake_bin / tool
        stub.write_text("#!/bin/sh\necho 'deadbeef  x'\n", encoding="utf-8")
        stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["FLOW_HELPERS_HOME"] = str(tmp_path / "home")
    env["FLOW_HELPERS_SOURCE"] = str(bundle_source)
    proc = subprocess.run(
        [str(INSTALLER)], check=False, capture_output=True, text=True, env=env
    )

    assert _verdict(proc) == "unverifiable-source", proc.stdout + proc.stderr
    assert proc.returncode == 6
