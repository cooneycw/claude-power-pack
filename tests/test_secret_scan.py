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
import secrets
import shutil
import string
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".gitleaks.toml"
GATE = ROOT / "scripts" / "secret-scan-check.sh"
CASES = ROOT / "controls" / "secret-scan" / "cases"
CARVE_OUT = "controls/secret-scan/cases/"
TEMPLATE = ROOT / ".gitleaks-findings.tmpl"

#: CLAUDE.md binary-guard directive: these shell out to gitleaks, including via
#: a repo script. CI stages the PINNED binary into `.ci-bin` from the secret-scan
#: step so it is present in `validate`.
requires_gitleaks = pytest.mark.skipif(
    shutil.which("gitleaks") is None or shutil.which("sh") is None,
    reason="needs gitleaks and sh on PATH (CI stages the pinned gitleaks into .ci-bin)",
)


# --------------------------------------------------------------------------- #
# What a scan is allowed to say about itself (issue #1288)
# --------------------------------------------------------------------------- #
# A scan that FINDS something is the moment its output is most dangerous. These
# helpers used to run gitleaks without `--redact` and hand the raw CompletedProcess
# to the tests, four of which pasted `stdout[:2000]` into their failure message -
# so a real credential in an ignored host-local file was printed, value and all,
# into the transcript of the very check that caught it.
#
# Two layers, because either alone has a gap:
#   - at the scanner boundary, gitleaks renders findings through
#     `.gitleaks-findings.tmpl` - rule, file, line - instead of `--verbose`.
#     `--redact` alone was NOT enough on the pinned v8.30.1 (counter-model
#     review, both reproduced): it masks each finding's OWN secret, so a value
#     inside ANOTHER rule's match printed in full, and colour mode printed the
#     surrounding source line besides;
#   - the tests only ever see a ScanResult parsed down to rule/file/line, so a
#     failure message - or pytest's own introspection of an assertion, which
#     prints the repr of every intermediate value - has nothing unsafe to show
#     even if a future gitleaks, or a future edit, drops the redaction.
@dataclass(frozen=True)
class Finding:
    rule: str
    file: str
    line: str


@dataclass(frozen=True)
class ScanResult:
    returncode: int
    findings: tuple[Finding, ...]
    config_load_failed: bool


def _parse(proc: subprocess.CompletedProcess) -> ScanResult:
    """Keep only metadata that cannot carry a secret; drop the raw streams.

    Findings are keyed on `RuleID:` lines, NOT the exit status: gitleaks exits 1
    for findings AND 1 for a config-load failure, so the exit code alone cannot
    tell "I caught something" from "I never started". See
    `test_a_malformed_config_is_not_a_detection`.
    """
    findings = []
    for block in re.split(r"\n\s*\n", proc.stdout):
        fields = dict(re.findall(r"^(RuleID|File|Line):\s*(.*?)\s*$", block, re.M))
        if "RuleID" in fields:
            findings.append(Finding(fields["RuleID"], fields.get("File", "?"),
                                    fields.get("Line", "?")))
    return ScanResult(proc.returncode, tuple(findings),
                      "Failed to load config" in proc.stderr)


def _scan_raw(source: Path, config: Path) -> subprocess.CompletedProcess:
    """The raw streams, for the tests that assert what they do NOT contain."""
    return subprocess.run(
        ["gitleaks", "detect", "--source", str(source), "--config", str(config),
         "--no-git", "--redact", "--report-format", "template",
         "--report-template", str(TEMPLATE), "--report-path", "-"],
        capture_output=True, text=True, timeout=300, cwd=ROOT,
    )


def _scan(source: Path, config: Path) -> ScanResult:
    return _parse(_scan_raw(source, config))


def _gate_raw(case_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", str(GATE), "--root", str(case_dir)],
                          capture_output=True, text=True, timeout=300, cwd=ROOT)


def _findings(result: ScanResult) -> int:
    return len(result.findings)


def _summary(result: ScanResult) -> str:
    """A failure message built from safe metadata only - never the raw output."""
    where = "; ".join(f"{f.rule} at {f.file}:{f.line}" for f in result.findings)
    return (f"exit={result.returncode} findings={len(result.findings)} "
            f"config_load_failed={result.config_load_failed}: {where or 'none'}")


def _synthetic_token() -> str:
    """A GitHub-PAT-SHAPED value made fresh per run, so no committed file holds
    it. Random characters fail GitHub's embedded checksum, so it is no credential."""
    alphabet = string.ascii_letters + string.digits
    return "ghp_" + "".join(secrets.choice(alphabet) for _ in range(36))


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
    assert _findings(result) == 0, _summary(result)
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
        f"removing the carve-out must expose the fixture: {_summary(result)}"
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
        f"the same bytes off the exempt path must be caught: {_summary(relocated)}"
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
    result = _parse(_gate_raw(CASES / case))
    assert _findings(result) == expected, _summary(result)
    # Zero findings alone would also accept a scan that never ran: the gate
    # refusing (exit 3) or a config that failed to load (exit 1, no RuleID).
    assert result.returncode == (1 if expected else 0), _summary(result)
    assert not result.config_load_failed, _summary(result)


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
        f"RuleID, the gate can report success while scanning nothing: {_summary(result)}"
    )
    assert result.config_load_failed


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


# --------------------------------------------------------------------------- #
# A detection never prints the value it detected (issue #1288)
# --------------------------------------------------------------------------- #
# Synthetic data only, generated per run. Never demonstrate this over a real host
# file: a check that leaks is not re-run on real credentials to prove it leaks.
def _plant(tmp_path: Path) -> tuple[str, Path]:
    token = _synthetic_token()
    case = tmp_path / "planted"
    case.mkdir()
    (case / "config.txt").write_text(f'token = "{token}"\n')
    return token, case


@requires_gitleaks
def test_a_detection_withholds_the_value_from_both_streams(tmp_path: Path) -> None:
    """Still caught, still nonzero - and the value is in neither stream.

    Membership is computed into a bool BEFORE asserting on it: `assert token not
    in proc.stdout` would make pytest's introspection print the very stdout it
    is checking, which is the leak this test exists to rule out.
    """
    token, case = _plant(tmp_path)
    proc = _scan_raw(case, CONFIG)
    result = _parse(proc)
    assert result.returncode == 1, _summary(result)
    assert [f.rule for f in result.findings] == ["github-pat"], _summary(result)
    assert result.findings[0].line == "1", _summary(result)
    in_stdout, in_stderr = token in proc.stdout, token in proc.stderr
    assert not in_stdout, "the synthetic value appeared in scanner stdout"
    assert not in_stderr, "the synthetic value appeared in scanner stderr"


def _windows(value: str, width: int = 8) -> list[str]:
    return [value[i:i + width] for i in range(len(value) - width + 1)]


@requires_gitleaks
def test_a_neighbouring_value_on_the_same_line_is_not_printed_as_context(
    tmp_path: Path,
) -> None:
    """Under `--verbose --redact`, colour mode printed the surrounding source
    line with only the match masked, so text beside it - here a short key no
    rule claims - reached the transcript by its tail. Checked by 8-char windows,
    because what leaked was a fragment, not the whole value."""
    token = _synthetic_token()
    neighbour = _synthetic_token()[4:16]
    case = tmp_path / "same-line"
    case.mkdir()
    (case / "config.txt").write_text(f'api_key = "{neighbour}" token = "{token}"\n')
    for proc in (_scan_raw(case, CONFIG), _gate_raw(case)):
        result = _parse(proc)
        assert "github-pat" in [f.rule for f in result.findings], _summary(result)
        out = proc.stdout + proc.stderr
        leaked = [w for w in _windows(neighbour) + _windows(token) if w in out]
        assert not leaked, f"{len(leaked)} fragment(s) of a same-line value were printed"


@requires_gitleaks
def test_a_secret_inside_another_rules_match_is_not_printed(tmp_path: Path) -> None:
    """The case `--redact` cannot handle: `curl-auth-header` matches a span that
    CONTAINS the GitHub PAT, and redaction masks only that finding's own secret
    (the bearer value) - so the PAT printed in full under `--verbose --redact`.
    Both findings must still be reported."""
    token = _synthetic_token()
    bearer = _synthetic_token()[4:]
    case = tmp_path / "overlap"
    case.mkdir()
    (case / "run.sh").write_text(
        f'curl "https://example.invalid/?token={token}" -H "Authorization: Bearer {bearer}"\n'
    )
    for proc in (_scan_raw(case, CONFIG), _gate_raw(case)):
        result = _parse(proc)
        rules = sorted(f.rule for f in result.findings)
        assert rules == ["curl-auth-header", "github-pat"], _summary(result)
        out = proc.stdout + proc.stderr
        leaked = [w for w in _windows(token) + _windows(bearer) if w in out]
        assert not leaked, f"{len(leaked)} fragment(s) of an overlapping value were printed"


@requires_gitleaks
def test_the_gate_script_withholds_the_value_too(tmp_path: Path) -> None:
    """`secret-scan-check.sh` is the other path to the scanner, and a registered
    negative control whose output lands in CI logs."""
    token, case = _plant(tmp_path)
    proc = _gate_raw(case)
    result = _parse(proc)
    assert result.returncode == 1, _summary(result)
    assert _findings(result) == 1, _summary(result)
    in_stdout, in_stderr = token in proc.stdout, token in proc.stderr
    assert not in_stdout, "the synthetic value appeared in the gate's stdout"
    assert not in_stderr, "the synthetic value appeared in the gate's stderr"


@requires_gitleaks
def test_a_failing_assertion_on_a_detection_reports_where_not_what(
    pytester: pytest.Pytester, tmp_path: Path,
) -> None:
    """The whole failure report of a test that trips on a detection, read as a
    reader of the transcript would read it: `-vv` for full assertion
    introspection and `-l` for every local in the traceback.

    It must name the rule, the file, the line and the count, and must not
    contain the value. Against the pre-fix helper (no `--redact`, raw
    CompletedProcess, `stdout[:2000]` as the message) this report carried the
    synthetic value verbatim.
    """
    token, case = _plant(tmp_path)
    pytester.makepyfile(test_inner=f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from tests.test_secret_scan import CONFIG, _findings, _scan, _summary

        def test_trips_on_the_planted_value():
            result = _scan(Path({str(case)!r}), CONFIG)
            assert _findings(result) == 0, _summary(result)
    """)
    run = pytester.runpytest_subprocess("-vv", "-l", "-p", "no:cacheprovider")
    report = "\n".join(run.outlines + run.errlines)

    run.assert_outcomes(failed=1)
    assert "github-pat" in report
    assert "config.txt:1" in report
    assert "findings=1" in report
    leaked = token in report
    assert not leaked, "the synthetic value appeared in the pytest failure report"
