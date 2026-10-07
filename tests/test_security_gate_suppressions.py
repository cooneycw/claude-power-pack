"""The finish gate's suppressions, end to end through the CLI (issue #1299).

A repository that plants fake keys as negative controls was blocked on every
finish run: CPP's native scan does not read `.gitleaks.toml`, and the mechanism
it does honour - `.claude/security.yml` `suppressions:` - was invisible and could
silently vanish. Measured: the same planted key and the same suppression gave
FAIL under a system `python3` without PyYAML (the config fell back to defaults
with no message) and PASS under the venv's python.

Every case runs `python -m lib.security gate flow_finish` on a real temporary
repository, because the defect lived in which config the command actually
applied, and a unit test of `Suppression.matches` cannot see that.

  NEGATIVE CONTROL  a planted key OUTSIDE the suppression still blocks, and one
                    INSIDE passes. With `secret:`, a DIFFERENT value of the same
                    rule in the SAME file still blocks.
  REFUSAL           an unreadable `.claude/security.yml` is UNKNOWN, exit 2 -
                    never a verdict computed from defaults.

Fake keys are assembled at run time so that no literal key sits in this file for
the repository's own scanners to find.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from lib.security.models import Finding, ScanResult, Severity, Suppression
from lib.security.output.json_output import format_results

ROOT = Path(__file__).resolve().parents[1]

#: Two distinct values of the same AWS rule, built so no literal key is committed.
CANARY = "AKIA" + "ABCDEFGHIJKLMNOP"
OTHER = "AKIA" + "ZYXWVUTSRQPONMLK"

#: Blocks `import yaml`, exactly as a system python3 without PyYAML does.
NO_YAML = (
    "import sys\n"
    "class _Block:\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name == 'yaml' or name.startswith('yaml.'):\n"
    "            raise ImportError('No module named yaml (blocked by test)')\n"
    "sys.meta_path.insert(0, _Block())\n"
    "import runpy\n"
    "sys.argv = ['lib.security', *sys.argv[1:]]\n"
    "runpy.run_module('lib.security', run_name='__main__')\n"
)


def _repo(tmp_path: Path, files: dict[str, str], config: str | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    for rel, text in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    if config is not None:
        (repo / ".claude").mkdir(exist_ok=True)
        (repo / ".claude" / "security.yml").write_text(config, encoding="utf-8")
    return repo


def _gate(
    repo: Path, *, without_yaml: bool = False, gate_name: str = "flow_finish"
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    argv = ["gate", gate_name, "--path", str(repo)]
    cmd = [sys.executable, "-c", NO_YAML, *argv] if without_yaml else [sys.executable, "-m", "lib.security", *argv]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT)


def _line(result: subprocess.CompletedProcess[str]) -> str:
    lines = [ln for ln in result.stdout.splitlines() if ln.startswith("SECURITY_GATE: ")]
    assert len(lines) == 1, result.stdout + result.stderr
    return lines[0]


PATH_ONLY = """suppressions:
  - id: AWS_ACCESS_KEY
    path: '^tests/fixture\\.py$'
    reason: planted negative-control fixture
"""


def test_a_key_outside_the_suppression_still_blocks(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"src/app.py": f'KEY = "{CANARY}"\n'}, PATH_ONLY)
    result = _gate(repo)
    assert " FAIL " in _line(result)
    assert result.returncode == 1


def test_a_key_inside_the_suppression_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"tests/fixture.py": f'KEY = "{CANARY}"\n'}, PATH_ONLY)
    unsuppressed = _repo(tmp_path / "control", {"tests/fixture.py": f'KEY = "{CANARY}"\n'})
    # Precondition: without the suppression this exact file blocks.
    assert _gate(unsuppressed).returncode == 1
    result = _gate(repo)
    assert " PASS " in _line(result), result.stdout
    assert result.returncode == 0


EXACT = f"""suppressions:
  - id: AWS_ACCESS_KEY
    path: '^tests/fixture\\.py$'
    secret: '{CANARY}'
    reason: planted negative-control fixture
"""


def test_secret_pins_the_suppression_to_one_value(tmp_path: Path) -> None:
    """A real key committed beside the canary must still block (orchestrator ruling)."""
    canary_only = _repo(tmp_path / "a", {"tests/fixture.py": f'KEY = "{CANARY}"\n'}, EXACT)
    assert _gate(canary_only).returncode == 0

    both = _repo(tmp_path / "b", {"tests/fixture.py": f'KEY = "{CANARY}"\nREAL = "{OTHER}"\n'}, EXACT)
    result = _gate(both)
    assert " FAIL " in _line(result)
    assert "tests/fixture.py:2" in result.stdout, "the OTHER value, on line 2, is what blocks"
    assert "tests/fixture.py:1" not in result.stdout


def test_an_unreadable_config_is_unknown_never_defaults(tmp_path: Path) -> None:
    """RED pre-fix: without PyYAML the file was dropped and defaults gave a FAIL."""
    repo = _repo(tmp_path, {"tests/fixture.py": f'KEY = "{CANARY}"\n'}, PATH_ONLY)
    result = _gate(repo, without_yaml=True)
    line = _line(result)
    assert " UNKNOWN (config unreadable:" in line
    assert "PyYAML is not importable by" in line and sys.executable in line
    assert "NOT applied" in line
    assert result.returncode == 2


@pytest.mark.parametrize(
    "config, cause",
    [
        ("suppressions: [\n", "ParserError"),
        ("- just\n- a list\n", "top level is a list, not a mapping"),
        ("suppressions:\n  - id: AWS_ACCESS_KEY\n    secrets: 'x'\n", "unknown key(s) ['secrets']"),
        ("suppressions:\n  - path: 'x'\n", "needs a non-empty string `id`"),
        ("suppressions:\n  - id: AWS_ACCESS_KEY\n    secret: '(unclosed'\n", "not a valid regex at position 0"),
        (
            "suppressions:\n  - id: AWS_ACCESS_KEY\n    1: x\n    unexpected: y\n",
            "unknown key(s) ['<int not shown>', 'unexpected']",
        ),
        ("gates:\n  flow_finish:\n    block_on: [NOPE]\n", "names an unknown severity"),
        # Counter-model review: falsey and wrong-type shapes used to default or crash.
        ("false\n", "top level is a bool, not a mapping"),
        ("0\n", "top level is a int, not a mapping"),
        ("[]\n", "top level is a list, not a mapping"),
        ("suppressions: false\n", "`suppressions` is a bool, not a list"),
        ("suppressions: 1\n", "`suppressions` is a int, not a list"),
        ("gates: false\n", "`gates` is a bool, not a dict"),
        ("gates:\n  flow_finish: 3\n", "gates.flow_finish is not a mapping"),
        ("gates:\n  flow_finish:\n    block_on: critical\n", "gates.flow_finish.block_on is not a list"),
    ],
)
def test_a_malformed_config_is_unknown(tmp_path: Path, config: str, cause: str) -> None:
    repo = _repo(tmp_path, {"README.md": "clean\n"}, config)
    result = _gate(repo)
    line = _line(result)
    assert " UNKNOWN (config unreadable:" in line and cause in line, line
    assert line == result.stdout.strip(), "the refusal is exactly one line"
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_no_config_file_still_means_defaults(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"README.md": "clean\n"})
    result = _gate(repo)
    assert " PASS " in _line(result)
    assert result.returncode == 0


def test_the_gitleaks_hint_names_the_way_out_without_the_secret(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"tests/fixture.py": f'KEY = "{CANARY}"\n', ".gitleaks.toml": "# allowlist\n"})
    result = _gate(repo)
    assert result.returncode == 1
    assert "HINT: this repository has a .gitleaks.toml, which this gate does NOT read." in result.stdout
    assert "- id: AWS_ACCESS_KEY" in result.stdout
    assert "path: '^tests/fixture\\.py$'" in result.stdout
    assert "secret: '<the exact planted value, regex-escaped>'" in result.stdout
    assert CANARY not in result.stdout + result.stderr, "the hint must never print the value"


@pytest.mark.parametrize("variant", ["no-gitleaks-toml", "has-suppressions", "passes"])
def test_the_hint_appears_only_in_its_case(tmp_path: Path, variant: str) -> None:
    files = {"tests/fixture.py": f'KEY = "{CANARY}"\n', ".gitleaks.toml": "# allowlist\n"}
    config = None
    if variant == "no-gitleaks-toml":
        del files[".gitleaks.toml"]
    elif variant == "has-suppressions":
        files["src/app.py"] = f'KEY = "{OTHER}"\n'  # still blocks, but the repo HAS suppressions
        config = PATH_ONLY
    else:
        config = PATH_ONLY
    result = _gate(_repo(tmp_path, files, config))
    assert "HINT:" not in result.stdout


def _finding(value: str | None) -> Finding:
    return Finding(
        id="AWS_ACCESS_KEY",
        severity=Severity.CRITICAL,
        title="t",
        file_path="tests/fixture.py",
        raw_match="AKIA****",
        secret_value=value,
    )


def test_a_secret_suppression_fails_closed_on_a_finding_without_a_value() -> None:
    supp = Suppression(id="AWS_ACCESS_KEY", path=r"^tests/", secret=CANARY)
    assert supp.matches(_finding(CANARY))
    assert not supp.matches(_finding(OTHER))
    assert not supp.matches(_finding(None)), "no value to compare is not a match"
    assert not supp.matches(_finding(CANARY + "X")), "fullmatch, not a prefix search"


def test_the_full_value_never_reaches_output() -> None:
    finding = _finding(CANARY)
    assert CANARY not in repr(finding)
    result = ScanResult()
    result.findings.append(finding)
    assert CANARY not in format_results(result)


def test_the_declared_value_in_the_config_file_is_not_itself_a_block(tmp_path: Path) -> None:
    """Writing `secret:` puts the value in security.yml, which is scanned too."""
    repo = _repo(tmp_path, {"tests/fixture.py": f'KEY = "{CANARY}"\n'}, EXACT)
    assert CANARY in (repo / ".claude" / "security.yml").read_text(encoding="utf-8")
    assert _gate(repo).returncode == 0

    pasted = EXACT.replace("reason: planted negative-control fixture", f"reason: see {OTHER}")
    repo2 = _repo(tmp_path / "pasted", {"tests/fixture.py": f'KEY = "{CANARY}"\n'}, pasted)
    result = _gate(repo2)
    assert result.returncode == 1, "a DIFFERENT key pasted into the config file still blocks"
    assert ".claude/security.yml:" in result.stdout


def test_a_malformed_config_never_prints_its_source(tmp_path: Path) -> None:
    """Counter-model review (HIGH): PyYAML's message quotes the offending line."""
    config = f"suppressions:\n  - id: AWS_ACCESS_KEY\n    secret: '{CANARY}\n"  # unterminated
    repo = _repo(tmp_path, {"README.md": "clean\n"}, config)
    result = _gate(repo)
    assert result.returncode == 2
    assert " UNKNOWN (config unreadable:" in _line(result)
    assert "at line" in _line(result), "the position is reported instead of the text"
    assert CANARY not in result.stdout + result.stderr
    assert CANARY[4:] not in result.stdout + result.stderr


def test_a_config_that_is_not_utf8_is_unknown(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"README.md": "clean\n"})
    (repo / ".claude").mkdir()
    (repo / ".claude" / "security.yml").write_bytes(b"suppressions:\n  - id: \xff\xfe\n")
    result = _gate(repo)
    assert " UNKNOWN (config unreadable:" in _line(result) and "not valid UTF-8" in _line(result)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_an_empty_config_file_still_means_defaults(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"README.md": "clean\n"}, "")
    assert _gate(repo).returncode == 0


@pytest.mark.parametrize(
    "line",
    [
        f"secret: *{CANARY}",  # undefined alias: PyYAML's problem text names it
        f"secret: '(?P={CANARY})'",  # re.error names the unknown group
        f"{CANARY}: x",  # the value pasted where a key goes
    ],
)
def test_no_malformed_config_echoes_a_value(tmp_path: Path, line: str) -> None:
    """Counter-model re-review (HIGH): each of these printed the full value."""
    config = f"suppressions:\n  - id: AWS_ACCESS_KEY\n    {line}\n"
    result = _gate(_repo(tmp_path, {"README.md": "clean\n"}, config))
    assert result.returncode == 2, result.stdout + result.stderr
    assert CANARY[4:] not in result.stdout + result.stderr


def test_a_secret_suppression_also_clears_the_generic_classifier_on_the_same_value(
    tmp_path: Path,
) -> None:
    """Issue #1405 item (b). Writing `secret: '<value>'` into security.yml makes

    that line match TWO native patterns at once: `AKIA[0-9A-Z]{16}` (id
    AWS_ACCESS_KEY, suppressed by the declared id) and the generic
    `(?:secret|...)\\s*[=:]\\s*["']...["']` assignment pattern (id
    HARDCODED_SECRET - the YAML syntax `secret: '...'` is itself a secret-like
    assignment). Pre-fix, only the first was exempt: HARDCODED_SECRET is HIGH,
    which only WARNS on `flow_finish` (so that gate still returned PASS) but
    BLOCKS on `flow_deploy` (which blocks HIGH too) - a suppression that looked
    like it worked on the gate most people watch, and silently still blocked
    the deploy gate on exactly the value it was written to clear.
    """
    # Full .gitignore, matching TestGitignoreScanner's own covering pattern, so
    # the orthogonal GITIGNORE_GAP warnings (also HIGH, also block flow_deploy)
    # don't mask the one finding this test is about.
    full_gitignore = ".env\n.env.*\n*.pem\n*.key\nsecrets.*\n*.p12\n.claude/security.yml\n"
    repo = _repo(tmp_path, {"README.md": "clean\n", ".gitignore": full_gitignore}, EXACT)
    finish = _gate(repo, gate_name="flow_finish")
    assert " PASS " in _line(finish)
    assert "[HARDCODED_SECRET]" not in finish.stdout, "RED pre-fix: HARDCODED_SECRET warned here"

    deploy = _gate(repo, gate_name="flow_deploy")
    assert " PASS " in _line(deploy), deploy.stdout
    assert "[HARDCODED_SECRET]" not in deploy.stdout
    assert ".claude/security.yml" not in deploy.stdout


def test_the_value_match_does_not_leak_outside_the_config_file(tmp_path: Path) -> None:
    """Same declared value, but the finding is in a DIFFERENT file: still blocks

    under every id, regardless of what security.yml declares (issue #1405).
    The widening in `_is_declared_in_config` is gated on `file_path ==
    CONFIG_REL`; this is the case that gate must keep refusing.
    """
    full_gitignore = ".env\n.env.*\n*.pem\n*.key\nsecrets.*\n*.p12\n.claude/security.yml\n"
    repo = _repo(
        tmp_path, {"src/other.py": f'api_key = "{CANARY}"\n', ".gitignore": full_gitignore}, EXACT
    )
    result = _gate(repo, gate_name="flow_deploy")
    assert " FAIL " in _line(result), result.stdout
    assert "src/other.py" in result.stdout
    assert "[HARDCODED_SECRET]" in result.stdout, result.stdout


def test_the_value_match_is_bound_to_the_declared_value_not_the_whole_file(
    tmp_path: Path,
) -> None:
    """A DIFFERENT, undeclared secret-shaped value also written into

    security.yml - e.g. pasted into a `reason:` - must still be flagged: the
    widening exempts one declared VALUE, not every finding in that file
    (issue #1405).
    """
    full_gitignore = ".env\n.env.*\n*.pem\n*.key\nsecrets.*\n*.p12\n.claude/security.yml\n"
    config = EXACT.replace(
        "reason: planted negative-control fixture",
        f"reason: api_key = '{OTHER}'",
    )
    repo = _repo(tmp_path, {"README.md": "clean\n", ".gitignore": full_gitignore}, config)
    result = _gate(repo, gate_name="flow_deploy")
    assert " FAIL " in _line(result), result.stdout
    assert ".claude/security.yml" in result.stdout
    assert "[HARDCODED_SECRET]" in result.stdout, result.stdout
    assert OTHER not in result.stdout + result.stderr


GITLEAKS_ALLOWLIST = f"""[extend]
useDefault = true

[allowlist]
  regexes = [
    '''{CANARY}''',
  ]
"""


def test_a_canary_declared_in_gitleaks_own_allowlist_is_exempt_there(tmp_path: Path) -> None:
    """Issue #1405 item (d), RED pre-fix.

    `.gitleaks.toml` is a security-policy file in the same class as
    `.claude/security.yml`: a repository that plants a value as gitleaks'
    OWN allowlisted canary (a literal regex entry that happens to look like a
    secret) had no way to tell CPP's native scanner that fact, so the same
    canary blocked `lib.security gate` even though gitleaks itself was told
    to ignore it.
    """
    repo = _repo(tmp_path, {".gitleaks.toml": GITLEAKS_ALLOWLIST})
    result = _gate(repo, gate_name="flow_finish")
    assert " PASS " in _line(result), result.stdout
    assert "AWS_ACCESS_KEY" not in result.stdout


def test_the_gitleaks_exemption_does_not_leak_to_other_files(tmp_path: Path) -> None:
    """NEGATIVE CONTROL: the same canary in an ORDINARY source file still

    blocks (issue #1405 orchestrator ruling). The exemption is bound to
    findings located IN `.gitleaks.toml` itself.
    """
    repo = _repo(
        tmp_path,
        {
            ".gitleaks.toml": GITLEAKS_ALLOWLIST,
            "src/app.py": f'KEY = "{CANARY}"\n',
        },
    )
    result = _gate(repo, gate_name="flow_finish")
    assert " FAIL " in _line(result), result.stdout
    assert "src/app.py" in result.stdout
    assert "[AWS_ACCESS_KEY]" in result.stdout


def test_the_gitleaks_exemption_is_bound_to_declared_literals(tmp_path: Path) -> None:
    """A DIFFERENT, undeclared secret-shaped value elsewhere in the SAME

    `.gitleaks.toml` - not inside an allowlist array - must still block: the
    widening exempts declared literal text, not the whole file (issue #1405).
    """
    toml_text = GITLEAKS_ALLOWLIST + f'  description = "see {OTHER}"\n'
    repo = _repo(tmp_path, {".gitleaks.toml": toml_text})
    result = _gate(repo, gate_name="flow_finish")
    assert " FAIL " in _line(result), result.stdout
    assert ".gitleaks.toml" in result.stdout
    assert "[AWS_ACCESS_KEY]" in result.stdout
    assert OTHER not in result.stdout + result.stderr


def test_a_malformed_gitleaks_toml_fails_closed(tmp_path: Path) -> None:
    """An unparsable `.gitleaks.toml` exempts nothing - fails closed, same as

    a missing `.claude/security.yml` leaves nothing to exempt (issue #1405).
    Never a crash, never a silent pass.
    """
    malformed = "[allowlist\n  regexes = [ '''" + CANARY + "''' ]\n"
    repo = _repo(tmp_path, {".gitleaks.toml": malformed})
    result = _gate(repo, gate_name="flow_finish")
    assert " FAIL " in _line(result), result.stdout
    assert "[AWS_ACCESS_KEY]" in result.stdout


def test_a_gitleaks_toml_with_an_oversized_integer_fails_closed(tmp_path: Path) -> None:
    """Counter-model review (codex): a decimal integer literal past Python's

    int-to-str conversion limit makes `tomllib.loads` raise `ValueError`, not
    `tomllib.TOMLDecodeError` - an exception class the original except clause
    did not list, which crashed the whole security scan over one unrelated
    TOML value instead of failing closed (issue #1405).
    """
    toml_text = "x = " + "9" * 5000 + "\n"
    repo = _repo(tmp_path, {".gitleaks.toml": toml_text, "src/app.py": f'KEY = "{CANARY}"\n'})
    result = _gate(repo, gate_name="flow_finish")
    assert "Traceback" not in result.stderr, result.stderr
    assert " FAIL " in _line(result), result.stdout
    assert "[AWS_ACCESS_KEY]" in result.stdout


def test_a_gitleaks_toml_with_deeply_nested_arrays_fails_closed(tmp_path: Path) -> None:
    """Counter-model review (codex): arrays nested past the interpreter's

    recursion limit make `tomllib.loads` raise `RecursionError`, also not
    `tomllib.TOMLDecodeError` (issue #1405).
    """
    toml_text = "x = " + "[" * 2000 + "]" * 2000 + "\n"
    repo = _repo(tmp_path, {".gitleaks.toml": toml_text, "src/app.py": f'KEY = "{CANARY}"\n'})
    result = _gate(repo, gate_name="flow_finish")
    assert "Traceback" not in result.stderr, result.stderr
    assert " FAIL " in _line(result), result.stdout
    assert "[AWS_ACCESS_KEY]" in result.stdout


def test_the_hint_yaml_survives_an_apostrophe_in_the_path(tmp_path: Path) -> None:
    import yaml

    repo = _repo(tmp_path, {"tests/o'brien.py": f'KEY = "{CANARY}"\n', ".gitleaks.toml": "#\n"})
    result = _gate(repo)
    example = result.stdout.split("  suppressions:\n", 1)[1]
    parsed = yaml.safe_load("suppressions:\n" + example)
    import re as _re

    assert _re.match(parsed["suppressions"][0]["path"], "tests/o'brien.py")
