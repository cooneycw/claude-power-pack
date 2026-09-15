"""The secret gate's negative control, and the guards that keep it honest (issue #935).

`gitleaks` is the repository's ONLY secret scanner and a hard gate - `validate`
has `depends_on: [secret-scan]`, so every merge is cleared by it. Nothing planted
a known-bad credential and asserted it fired, which means "we have never had a
leak" and "the scanner has never fired" were indistinguishable.

The fixture lives at an allowlisted path so the repo-wide scan stays green, and
`scripts/secret-scan-check.sh` relocates the SAME BYTES off that path to prove
the gate still catches them. That pair proves more than a removal check alone:
the carve-out is real AND it is narrowly scoped rather than blinding the gate.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".gitleaks.toml"
GATE = ROOT / "scripts" / "secret-scan-check.sh"
CASES = ROOT / "controls" / "secret-scan" / "cases"
CARVE_OUT = "controls/secret-scan/cases/"

#: CLAUDE.md binary-guard directive: these shell out to gitleaks, including via
#: a repo script. CI stages the PINNED binary into `.ci-bin` from the secret-scan
#: step so it is present in `validate`.
requires_gitleaks = pytest.mark.skipif(
    shutil.which("gitleaks") is None or shutil.which("sh") is None,
    reason="needs gitleaks and sh on PATH (CI stages the pinned gitleaks into .ci-bin)",
)


def _scan(source: Path, config: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gitleaks", "detect", "--source", str(source), "--config", str(config),
         "--no-git", "--verbose"],
        capture_output=True, text=True, timeout=300, cwd=ROOT,
    )


def _findings(result: subprocess.CompletedProcess) -> int:
    """Count RuleID lines, NOT the exit status.

    gitleaks exits 1 for findings AND 1 for a config-load failure, so the exit
    code alone cannot tell "I caught something" from "I never started". See
    `test_a_malformed_config_is_not_a_detection`.
    """
    return len(re.findall(r"^RuleID:", result.stdout, re.M))


# --------------------------------------------------------------------------- #
# The fixture is not a credential
# --------------------------------------------------------------------------- #
def test_the_fixture_is_provably_not_a_key() -> None:
    """A real-looking string that is actually live would make this control the
    incident it exists to prevent."""
    body = (CASES / "bad-private-key" / "leaked.txt").read_text()
    inner = body.split("-----BEGIN RSA PRIVATE KEY-----")[1].split("-----END")[0].strip()
    assert inner.startswith("NOT-A-KEY"), inner
    # Plain ASCII prose with hyphens: not base64, so it decodes to no key at all.
    assert not re.fullmatch(r"[A-Za-z0-9+/=\s]+", inner), (
        "the body must be visibly NOT base64, or a later reader cannot tell it "
        f"from a real key by eye: {inner!r}"
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="shells out to git")
def test_the_fixture_filename_is_not_gitignored() -> None:
    """Every filename that LOOKS right for a planted credential is ignored here.

    `.gitignore` carries `*.key`, `*.pem`, `*.env` and `*.json`. The first draft
    of this fixture was `leaked.key`, `git status` reported a clean tree, and the
    control would have discriminated locally, reported PASS, and NOT EXISTED in a
    clean clone (#978). The safer the name looks, the more likely it is swallowed.
    """
    for path in sorted(CASES.rglob("*")):
        if not path.is_file():
            continue
        r = subprocess.run(["git", "check-ignore", "-v", str(path)],
                           capture_output=True, text=True, cwd=ROOT, timeout=60)
        assert r.returncode != 0, f"{path.relative_to(ROOT)} is gitignored: {r.stdout.strip()}"


# --------------------------------------------------------------------------- #
# The carve-out is real, narrowly scoped, and load-bearing
# --------------------------------------------------------------------------- #
@requires_gitleaks
def test_the_repo_wide_scan_is_clean_with_the_fixture_committed() -> None:
    """Guard 3: the carve-out does its job."""
    result = _scan(ROOT, CONFIG)
    assert _findings(result) == 0, result.stdout[:2000]
    assert result.returncode == 0


@requires_gitleaks
def test_removing_the_carve_out_turns_the_repo_scan_red(tmp_path: Path) -> None:
    """Guard 1, and it is what makes the entry a guard rather than a comment.

    An allowlist entry that changes nothing when removed is decoration. This one
    is load-bearing: take it out and the shipped scan fails on the fixture.
    """
    text = CONFIG.read_text()
    assert CARVE_OUT in text, "the carve-out must be present to be removed"
    stripped = "\n".join(line for line in text.splitlines() if CARVE_OUT not in line)
    cfg = tmp_path / "no-carve-out.toml"
    cfg.write_text(stripped)

    result = _scan(ROOT, cfg)
    assert _findings(result) >= 1, (
        f"removing the carve-out must expose the fixture: {result.stdout[:2000]}"
    )


@requires_gitleaks
def test_the_same_bytes_are_detected_off_the_exempt_path(tmp_path: Path) -> None:
    """Guard 2: the entry is PATH-scoped, not a blindfold on the gate.

    Same bytes, same shipped config, different path. If this ever goes quiet, the
    carve-out has stopped being narrow and the gate is blind somewhere it should
    not be.
    """
    src = CASES / "bad-private-key" / "leaked.txt"
    dst = tmp_path / "relocated.txt"
    dst.write_bytes(src.read_bytes())
    assert dst.read_bytes() == src.read_bytes()

    at_home = _scan(src.parent, CONFIG)
    relocated = _scan(tmp_path, CONFIG)
    assert _findings(at_home) == 0, "at its exempt path the fixture must be allowed"
    assert _findings(relocated) == 1, (
        f"the same bytes off the exempt path must be caught: {relocated.stdout[:2000]}"
    )


def test_only_one_allowlist_entry_points_into_controls() -> None:
    """The #936 reversal trigger, executed rather than described.

    A SECOND entry pointing into `controls/` means the carve-out has stopped
    being constitutive and become a habit. Checkable by reading the file, which
    is the point - a trigger that only fires when somebody notices and reports
    it never fires at all.
    """
    # Each match is asserted rather than chained: a None here means the
    # DERIVATION broke, and an unchecked .group(1) would surface that as an
    # AttributeError reading like a bug in the test rather than as 'this check
    # can no longer see its own subject'. mypy asked for the same thing.
    block_m = re.search(r"\[allowlist\](.*?)(?=\n\[|\Z)", CONFIG.read_text(), re.S)
    assert block_m is not None, "no [allowlist] block found - the derivation is blind"
    paths_m = re.search(r"paths\s*=\s*\[(.*?)\]", block_m.group(1), re.S)
    assert paths_m is not None, "no paths list found - the derivation is blind"
    entries = re.findall(r"'''(.*?)'''", paths_m.group(1))
    assert len(entries) >= 15, f"derivation looks broken, found {len(entries)} entries"
    into_controls = [e for e in entries if "controls/" in e]
    assert into_controls == [CARVE_OUT], (
        f"exactly one allowlist entry may point into controls/: {into_controls}"
    )


# --------------------------------------------------------------------------- #
# Both directions, and the shape that is not a detection
# --------------------------------------------------------------------------- #
@requires_gitleaks
@pytest.mark.parametrize("case,expected", [
    ("bad-private-key", 1),
    ("good-short-body", 0),
    ("good-clean", 0),
])
def test_the_gate_discriminates_in_both_directions(case: str, expected: int) -> None:
    """A scanner wedged at "findings" is as useless as one wedged at "clean".

    `good-short-body` is the same shape as the bad case with a SHORT body:
    gitleaks private-key detection is length-sensitive, measured on v8.30.1, and
    this is what makes shortening the fixture a failing case rather than a silent
    disarm.
    """
    result = subprocess.run(["sh", str(GATE), "--root", str(CASES / case)],
                            capture_output=True, text=True, timeout=300, cwd=ROOT)
    assert len(re.findall(r"^RuleID:", result.stdout, re.M)) == expected, result.stdout[:2000]


@requires_gitleaks
def test_a_malformed_config_is_not_a_detection(tmp_path: Path) -> None:
    """gitleaks exits 1 for FINDINGS and 1 for CONFIG-LOAD FAILURE.

    So a broken `.gitleaks.toml` would report a successful catch while scanning
    nothing - #946's "a crash is not a detection", arriving on the secret gate.
    The control keys on the finding TEXT for exactly this reason, and this pins
    that a config failure produces no such text.
    """
    cfg = tmp_path / "broken.toml"
    cfg.write_text("[allowlist]\n  paths = [\n  ]\n")
    result = _scan(CASES / "bad-private-key", cfg)

    assert result.returncode == 1, "the failure mode under test is an exit of 1"
    assert _findings(result) == 0, (
        "a config failure must not look like a detection - if this ever reports a "
        f"RuleID, the gate can report success while scanning nothing: {result.stdout[:800]}"
    )
    assert "Failed to load config" in result.stderr


def test_the_gate_refuses_rather_than_passing_when_gitleaks_is_absent(tmp_path: Path) -> None:
    """`good_exit` is 0, so a missing scanner must NOT exit 0.

    NOT guarded on gitleaks, deliberately, and the escape hatch rather than a
    `skipif` is the point: a guard would SKIP this on an image that genuinely
    lacks gitleaks, which is the one image where it is worth running. It needs no
    gitleaks to do its job - it asserts the refusal.

    Otherwise "we could not look" renders identically to "we looked and it was
    clean" - the empty-population failure, on the instrument that gates merges.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for tool in ("sh", "mktemp", "cp", "sha256sum", "cut", "basename", "dirname", "rm", "command"):
        real = shutil.which(tool)
        if real:
            (bindir / tool).symlink_to(real)
    assert shutil.which("gitleaks", path=str(bindir)) is None, "fixture must lack gitleaks"

    result = subprocess.run(  # binary-guard: allow gitleaks absence IS the subject
        ["sh", str(GATE), "--root", str(CASES / "bad-private-key")],
        capture_output=True, text=True, timeout=120, cwd=ROOT,
        env={"PATH": str(bindir), "HOME": str(tmp_path)},
    )
    assert result.returncode != 0, "an unperformed scan must not read as clean"
    assert "unchecked, not clean" in result.stderr, result.stderr
