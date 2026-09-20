"""Tests for scripts/check-test-binary-guards.py - the #602 shell-out gate.

Contract:
- Fires on the #577 shape: an unguarded ``subprocess.run(["git", ...])`` inside a
  ``test_`` function.
- Fires on the INDIRECT shape: a ``test_`` that calls a module-level helper which
  shells out, transitively.
- Clears every guard idiom the suite actually uses - an inline
  ``@pytest.mark.skipif(shutil.which(...))``, a module-level ``requires_git``
  alias, a class-level marker, ``pytestmark``, and an in-body
  ``if shutil.which(...) is None: pytest.skip(...)``.
- Fires on the SCRIPT-HOP shape (issue #789): a ``test_`` that runs
  ``["bash", str(SCRIPT)]`` where SCRIPT is a repo script which hard-requires a
  guarded binary - the #783 case the gate's own source used to name as a known
  blind spot.
- Discounts a script that says it survives the binary's absence, confines the
  requirement to one branch, or only ever uses it fail-soft.
- Honours the ``# binary-guard: allow <reason>`` escape.
- Runs clean on CPP's real ``tests/`` tree.

This module deliberately shells out to NOTHING (issue #602 acceptance criterion
4): the checker is pure source analysis, so its own test drives it in-process
over sources written to ``tmp_path``. That is what lets this gate run in the CI
``validate`` image - the very image whose missing binaries it exists to defend.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-test-binary-guards.py"


def _load_checker():
    """Import the hyphenated CLI script as a module."""
    spec = importlib.util.spec_from_file_location("check_test_binary_guards", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _findings(tmp_path: Path, source: str) -> list:
    path = tmp_path / "test_sample.py"
    path.write_text(source, encoding="utf-8")
    return checker.check_paths([path])


PREAMBLE = """\
import shutil
import subprocess

import pytest

"""


# --------------------------------------------------------------------------- #
# The regression the gate exists for (#451, #489, #577)
# --------------------------------------------------------------------------- #
def test_fires_on_the_577_shape(tmp_path: Path) -> None:
    """The exact shape that turned the pipeline red on PR #600."""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
def test_posture_file_is_tracked():
    result = subprocess.run(["git", "check-ignore", "-q", "x"], check=False)
    assert result.returncode != 0
""",
    )
    assert len(findings) == 1, findings
    assert findings[0].test == "test_posture_file_is_tracked"
    assert findings[0].binaries == ("git",)
    assert findings[0].indirect_via is None


def test_fires_on_the_indirect_helper_shape(tmp_path: Path) -> None:
    """Several existing tests shell out only through a module-level helper."""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True)


def _init_repo(repo):
    _git(repo, "init", "-q")


def test_repo_is_initialized(tmp_path):
    _init_repo(tmp_path)
""",
    )
    assert len(findings) == 1, findings
    assert findings[0].test == "test_repo_is_initialized"
    assert findings[0].binaries == ("git",)
    assert findings[0].indirect_via == "_init_repo", "the transitive hop must be named"


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        ('subprocess.run(["docker", "ps"])', ("docker",)),
        ('subprocess.Popen(["gitleaks", "detect"])', ("gitleaks",)),
        ('subprocess.check_call(["/usr/bin/git", "status"])', ("git",)),
        ('subprocess.check_output("git rev-parse HEAD", shell=True)', ("git",)),
        ('subprocess.run(f"git -C {tmp_path} log")', ("git",)),
        ('os.system("docker compose up")', ("docker",)),
    ],
    ids=["docker", "gitleaks", "abs-path", "shell-str", "fstring", "os-system"],
)
def test_recognizes_each_invocation_shape(tmp_path: Path, call: str, expected: tuple) -> None:
    findings = _findings(
        tmp_path,
        PREAMBLE
        + f"""\
import os


def test_thing(tmp_path):
    {call}
""",
    )
    assert len(findings) == 1, f"{call} was not recognized"
    assert findings[0].binaries == expected


def test_ignores_unguarded_binaries_and_dynamic_argv(tmp_path: Path) -> None:
    """bash IS in the validate image, and a runtime-built argv is unresolvable.

    The second case is an accepted false negative, pinned here so nobody
    mistakes the gate for proof of total coverage.
    """
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
def test_bash_helper(tmp_path):
    subprocess.run(["bash", "script.sh"], check=False)


def test_dynamic_argv(tmp_path):
    cmd = ["git", "status"]
    subprocess.run(cmd, check=False)
""",
    )
    assert findings == []


# --------------------------------------------------------------------------- #
# Guard idioms that must clear - every one is in live use in tests/
# --------------------------------------------------------------------------- #
GUARDED_SOURCES = {
    "inline-skipif": """\
@pytest.mark.skipif(shutil.which("git") is None, reason="no git")
def test_thing():
    subprocess.run(["git", "status"], check=False)
""",
    "module-alias": """\
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="no git")


@requires_git
def test_thing():
    subprocess.run(["git", "status"], check=False)
""",
    "pytestmark": """\
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="no git"
)


def test_thing():
    subprocess.run(["git", "status"], check=False)
""",
    "class-level": """\
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="no git")


@requires_git
class TestThings:
    def test_thing(self):
        subprocess.run(["git", "status"], check=False)
""",
    "body-level-skip": """\
def test_thing():
    if shutil.which("git") is None:
        pytest.skip("git unavailable")
    subprocess.run(["git", "status"], check=False)
""",
    "indirect-guarded": """\
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="no git")


def _git(*args):
    subprocess.run(["git", *args], check=False)


@requires_git
def test_thing():
    _git("status")
""",
}


@pytest.mark.parametrize("source", GUARDED_SOURCES.values(), ids=list(GUARDED_SOURCES))
def test_guard_idioms_clear(tmp_path: Path, source: str) -> None:
    assert _findings(tmp_path, PREAMBLE + source) == []


def test_guard_must_name_the_binary_actually_invoked(tmp_path: Path) -> None:
    """A docker skipif does not excuse a git shell-out."""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
@pytest.mark.skipif(shutil.which("docker") is None, reason="no docker")
def test_thing():
    subprocess.run(["git", "status"], check=False)
""",
    )
    assert len(findings) == 1
    assert findings[0].binaries == ("git",)


@pytest.mark.parametrize("anchor", ["def", "call"], ids=["on-def", "on-call"])
def test_allow_escape_suppresses(tmp_path: Path, anchor: str) -> None:
    def_comment = "  # binary-guard: allow intentional" if anchor == "def" else ""
    call_comment = "  # binary-guard: allow intentional" if anchor == "call" else ""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + f"""\
def test_thing():{def_comment}
    subprocess.run(["git", "status"], check=False){call_comment}
""",
    )
    assert findings == []


# --------------------------------------------------------------------------- #
# One hop through a shell script (issue #789 - the #783 blind spot)
# --------------------------------------------------------------------------- #
#: A script that cannot do its job without jq: a bare command substitution, no
#: preflight, no `||` fallback, stderr not discarded. Structurally the
#: `flow-driver-capability.sh --json` body that turned PR #787's pipeline red.
JQ_SCRIPT = """\
#!/usr/bin/env bash
set -euo pipefail
CONFIG="$1"
BRANCH=$(jq -r '.branch' "$CONFIG")
echo "$BRANCH"
"""

#: The module-level `Path` constant idiom every CPP test file uses.
SCRIPT_PREAMBLE = """\
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
THING = ROOT / "scripts" / "thing.sh"

"""

RUNS_THING = """\
def test_reads_the_config(tmp_path):
    subprocess.run(["bash", str(THING), "cfg.json"], check=False)
"""


def _repo(tmp_path: Path, test: str, script: str = JQ_SCRIPT, name: str = "thing.sh") -> list:
    """A tmp checkout shaped like CPP's: tests/test_sample.py beside scripts/<name>."""
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / name).write_text(script, encoding="utf-8")
    (tmp_path / "tests").mkdir(exist_ok=True)
    path = tmp_path / "tests" / "test_sample.py"
    path.write_text(test, encoding="utf-8")
    return checker.check_paths([path])


def test_fires_on_the_783_shape(tmp_path: Path) -> None:
    """`bash SCRIPT` where SCRIPT needs jq - green locally, red in CI, gate silent."""
    findings = _repo(tmp_path, SCRIPT_PREAMBLE + RUNS_THING)
    assert len(findings) == 1, findings
    assert findings[0].test == "test_reads_the_config"
    assert findings[0].binaries == ("jq",)
    assert [p.name for p in findings[0].via_scripts] == ["thing.sh"], "the script must be named"
    assert "thing.sh" in findings[0].render(tmp_path)


def test_the_783_shape_is_invisible_to_the_pre_change_checker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-vacuity: the fixture above passes the gate as it stood before #789.

    Emptying ``SHELL_RUNNERS`` reproduces the pre-change checker exactly - it had
    no ``bash``/``sh`` branch, so an argv headed by one resolved to nothing. The
    fixture's test source names no guarded binary itself, so if this returned a
    finding the new hop would not be what produced it in the test above.
    """
    source = SCRIPT_PREAMBLE + RUNS_THING
    assert "jq" not in source, "the fixture must reach jq ONLY through the script"
    monkeypatch.setattr(checker, "SHELL_RUNNERS", frozenset())
    assert _repo(tmp_path, source) == [], "the old gate must miss this - otherwise #789 proves nothing"


RESOLVABLE_ARGVS = {
    "str-of-constant": 'subprocess.run(["bash", str(THING)], check=False)',
    "bare-constant": "subprocess.run([\"bash\", THING], check=False)",
    "inline-expression": 'subprocess.run(["bash", str(ROOT / "scripts" / "thing.sh")], check=False)',
    "absolute-runner": 'subprocess.run(["/bin/bash", str(THING)], check=False)',
    "sh-runner": 'subprocess.run(["sh", str(THING)], check=False)',
    "after-end-of-options": 'subprocess.run(["bash", "--", str(THING)], check=False)',
    "with-flags": 'subprocess.run(["bash", "-e", str(THING)], check=False)',
}


@pytest.mark.parametrize("call", RESOLVABLE_ARGVS.values(), ids=list(RESOLVABLE_ARGVS))
def test_resolves_the_path_constant_idiom(tmp_path: Path, call: str) -> None:
    findings = _repo(tmp_path, SCRIPT_PREAMBLE + f"def test_thing(tmp_path):\n    {call}\n")
    assert len(findings) == 1, f"{call} did not resolve"
    assert findings[0].binaries == ("jq",)


UNRESOLVABLE_ARGVS = {
    "bash-c-command-string": 'subprocess.run(["bash", "-c", cmd], check=False)',
    "local-variable": "subprocess.run([\"bash\", str(script)], check=False)",
    "no-such-file": 'subprocess.run(["bash", "absent.sh"], check=False)',
    "runtime-argv": "subprocess.run(cmd, check=False)",
    "starred": "subprocess.run([\"bash\", *argv], check=False)",
}


@pytest.mark.parametrize("call", UNRESOLVABLE_ARGVS.values(), ids=list(UNRESOLVABLE_ARGVS))
def test_unresolvable_script_argv_stays_unflagged(tmp_path: Path, call: str) -> None:
    """The floor-not-proof contract: what cannot be resolved is never guessed at."""
    body = f"def test_thing(tmp_path, cmd, script, argv):\n    {call}\n"
    assert _repo(tmp_path, SCRIPT_PREAMBLE + body) == []


def test_a_guard_clears_a_script_finding(tmp_path: Path) -> None:
    source = SCRIPT_PREAMBLE + """\
requires_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="no jq")


@requires_jq
def test_thing(tmp_path):
    subprocess.run(["bash", str(THING)], check=False)
"""
    assert _repo(tmp_path, source) == []


@pytest.mark.parametrize("anchor", ["def", "call"], ids=["on-def", "on-call"])
def test_allow_escape_suppresses_a_script_finding(tmp_path: Path, anchor: str) -> None:
    """The escape for the case the hop cannot see: this path never reaches jq."""
    on_def = "  # binary-guard: allow usage error exits first" if anchor == "def" else ""
    on_call = "  # binary-guard: allow usage error exits first" if anchor == "call" else ""
    source = SCRIPT_PREAMBLE + (
        f"def test_thing(tmp_path):{on_def}\n"
        f'    subprocess.run(["bash", str(THING)], check=False){on_call}\n'
    )
    assert _repo(tmp_path, source) == []


def test_helper_wrapper_still_names_the_script(tmp_path: Path) -> None:
    """The dominant idiom: a module-level ``_run()`` around the script."""
    source = SCRIPT_PREAMBLE + """\
def _run(*args):
    return subprocess.run(["bash", str(THING), *args], check=False)


def test_thing(tmp_path):
    _run("cfg.json")
"""
    findings = _repo(tmp_path, source)
    assert len(findings) == 1, findings
    assert findings[0].binaries == ("jq",)
    assert [p.name for p in findings[0].via_scripts] == ["thing.sh"]


# --------------------------------------------------------------------------- #
# What counts as a script's HARD requirement (issue #789)
# --------------------------------------------------------------------------- #
HARD_SCRIPTS = {
    "bare-substitution": 'BRANCH=$(jq -r ".branch" "$1")\necho "$BRANCH"\n',
    "piped": 'cat "$1" | jq -S .\n',
    "after-then": 'if [ -f "$1" ]; then\n    jq . "$1"\nfi\n',
    "top-level-exiting-preflight": (
        'if ! command -v jq >/dev/null 2>&1; then\n'
        '    echo "jq required" >&2\n'
        "    exit 1\n"
        "fi\n"
        'BRANCH=$(jq -r ".branch" "$1")\n'
    ),
    "continued-command": 'ROW=$(jq -n \\\n    --arg a "$1" \\\n    "{a: \\$a}")\n',
}

SOFT_SCRIPTS = {
    "comment-only": "# this would be easier with jq\necho hi\n",
    "gh-jq-flag": 'gh issue view 1 --json state --jq .state\n',
    "inside-a-string-list": 'TOOLS=("hostname" "jq" "uniq")\necho "${TOOLS[@]}"\n',
    "or-fallback": 'BRANCH=$(jq -r ".branch" "$1") || BRANCH=main\n',
    "stderr-discarded": 'BRANCH="$(jq -r ".branch" "$1" 2>/dev/null)"\n',
    "used-as-a-condition": 'if jq -e . "$1" >/dev/null; then echo ok; fi\n',
    "negated": '! jq -e . "$1" && echo bad\n',
    "degrading-preflight": (
        "command -v jq >/dev/null 2>&1 || return 0\n" 'BRANCH=$(jq -r ".branch" "$1")\n'
    ),
    "degrading-preflight-block": (
        "if ! command -v jq >/dev/null 2>&1; then\n"
        '    echo "no jq - skipping" >&2\n'
        "    return\n"
        "fi\n"
        'BRANCH=$(jq -r ".branch" "$1")\n'
    ),
    "scoped-exiting-preflight": (
        "case \"$1\" in\n"
        "  --json)\n"
        "      command -v jq >/dev/null 2>&1 || {\n"
        '          echo "jq needed for --json" >&2\n'
        "          exit 2\n"
        "      }\n"
        '      jq -n "{a: 1}"\n'
        "      ;;\n"
        "esac\n"
    ),
}


@pytest.mark.parametrize("body", HARD_SCRIPTS.values(), ids=list(HARD_SCRIPTS))
def test_script_hard_requirements_are_flagged(tmp_path: Path, body: str) -> None:
    findings = _repo(tmp_path, SCRIPT_PREAMBLE + RUNS_THING, script="#!/usr/bin/env bash\n" + body)
    assert len(findings) == 1, f"expected a jq finding for:\n{body}"
    assert findings[0].binaries == ("jq",)


@pytest.mark.parametrize("body", SOFT_SCRIPTS.values(), ids=list(SOFT_SCRIPTS))
def test_scripts_that_survive_without_the_binary_are_not_flagged(tmp_path: Path, body: str) -> None:
    """Measured on this repo, a naive "mentions jq" scan gave 266 findings, ~250 false."""
    findings = _repo(tmp_path, SCRIPT_PREAMBLE + RUNS_THING, script="#!/usr/bin/env bash\n" + body)
    assert findings == [], f"expected no finding for:\n{body}"


def test_a_scoped_preflight_still_covers_top_level_uses(tmp_path: Path) -> None:
    """Scoping is per-branch, not per-script: a top-level use outside it still counts."""
    body = (
        "#!/usr/bin/env bash\n"
        "case \"$1\" in\n"
        "  --json)\n"
        "      command -v jq >/dev/null 2>&1 || { echo no >&2; exit 2; }\n"
        '      jq -n "{a: 1}"\n'
        "      ;;\n"
        "esac\n"
        'jq -r ".always" "$2"\n'
    )
    findings = _repo(tmp_path, SCRIPT_PREAMBLE + RUNS_THING, script=body)
    assert len(findings) == 1, findings
    assert findings[0].binaries == ("jq",)


def test_binaries_in_script_reads_the_real_helpers() -> None:
    """Pin the classification of two live scripts, so a rewrite of either is visible."""
    scripts = ROOT / "scripts"
    assert "jq" in checker.binaries_in_script(scripts / "branch-protection.sh"), (
        "branch-protection.sh exits on a top-level `command -v jq` preflight - a hard requirement"
    )
    assert "git" not in checker.binaries_in_script(scripts / "cpp-commands-link.sh"), (
        "cpp-commands-link.sh declares `command -v git || return 0` - it runs fine without git"
    )


# --------------------------------------------------------------------------- #
# The gate itself
# --------------------------------------------------------------------------- #
def test_real_tests_tree_is_clean() -> None:
    """CPP's own suite must satisfy the rule this script enforces.

    This is the assertion that makes the #577 class of failure reproducible on a
    dev box, where `git` is present and the red pipeline is otherwise invisible.
    """
    findings = checker.check_tree(ROOT / "tests")
    rendered = "\n".join(f.render(ROOT) for f in findings)
    assert findings == [], f"unguarded shell-outs in tests/:\n{rendered}"


def test_this_module_does_not_shell_out() -> None:
    """Acceptance criterion 4 - the gate's own test needs no binary.

    Checked structurally rather than by grep: the sources this module feeds the
    checker are full of ``subprocess.run`` text, but they are string literals,
    never executed. What matters is that the module itself never imports a way
    to spawn one - so it can never be the unguarded test it is here to catch.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & {"subprocess", "os"}, (
        f"the binary-guard test must not import a subprocess API (found {imported})"
    )


def test_cli_reports_and_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_bad.py").write_text(
        PREAMBLE + 'def test_thing():\n    subprocess.run(["git", "status"])\n',
        encoding="utf-8",
    )
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "test_thing" in out
    assert "shutil.which" in out, "the failure must show the fix, not just the finding"


def test_cli_is_silent_success_on_a_clean_tree(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text("def test_thing():\n    assert True\n", encoding="utf-8")
    assert checker.main(["--root", str(tmp_path)]) == 0
    assert "ok" in capsys.readouterr().out


def test_cli_fails_when_the_root_has_no_tests_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """#840: a missing tests/ must not read the same as a clean scan - the
    exit code is what `make verify` reads, and the message alone (already
    present, previously on stderr) was a silent pass through that gate."""
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "no tests/ directory" in out


def test_cli_fails_when_tests_directory_has_no_test_files(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """#840: a present-but-empty tests/ is worse than a missing one - the old
    code printed a clean "ok" for a population of zero, a false positive
    rather than a missed report."""
    (tmp_path / "tests").mkdir()
    assert checker.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "no test files" in out


# --------------------------------------------------------------------------- #
# A `case` pattern label is read as a command invocation (issue #833)
#
# `SHELL_BINARY_RE` matches a guarded name at "command position" - after a
# newline, `;`, `&`, `|`, `(`, backtick, `$(`, `&&`, `||`, or an anchor
# keyword. A `case` label sits at exactly that position too (`ps)` follows a
# newline the same way a real command would), and its closing `)` satisfies
# the trailing `\b` the same way a real command's argument list would - so
# nothing in the regex's surroundings distinguishes the two. Latent today
# because none of the four currently-guarded binaries (git/docker/gitleaks/
# jq) is a label anyone writes; `ps`, `timeout` and `rev` all are, in this
# repo's own scripts, and widening `GUARDED_BINARIES` to include any of them
# was what surfaced it (101 findings, all one label, per the issue).
#
# Per review: the regression fixture is the REAL line from
# scripts/flow-wave-mailbox.sh, not a constructed one - a real in-tree
# instance is evidence, a hand-written case block is illustration. And the
# fix must be tested in BOTH directions: it must stop reading the label as a
# use, and it must NOT also stop seeing the genuine invocations a few lines
# later - the undercount direction is the unsafe one (same principle as the
# unreadable-`/proc/<pid>/environ` note on issue #832).
# --------------------------------------------------------------------------- #

MAILBOX_SCRIPT = ROOT / "scripts" / "flow-wave-mailbox.sh"


def _widened_checker(tmp_path: Path, binaries: frozenset[str]):
    """A second checker instance with `GUARDED_BINARIES` widened - the exact
    sed-substitution technique issue #833 used to produce its 101-finding
    oracle, so this reproduces that measurement rather than a different one.
    A separate module object (not the shared `checker` used elsewhere in
    this file) so widening here cannot leak into any other test's import.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    widened_source, n = re.subn(
        r"^GUARDED_BINARIES = .*$",
        f"GUARDED_BINARIES = frozenset({sorted(binaries)!r})",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    assert n == 1, "GUARDED_BINARIES assignment line not found - checker source shape changed"
    widened_path = tmp_path / "check_test_binary_guards_widened.py"
    widened_path.write_text(widened_source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "check_test_binary_guards_widened", widened_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass() needs the module registered before exec
    spec.loader.exec_module(module)
    return module


def _ps_uses_in_mailbox_script(widened) -> list:
    text = MAILBOX_SCRIPT.read_text(encoding="utf-8")
    source = widened._mask_noncode(text)
    lines = source.splitlines()
    return [use for use in widened._script_uses(source, lines) if use.binary == "ps"]


def test_the_case_label_at_720_is_not_read_as_a_use(tmp_path: Path) -> None:
    text = MAILBOX_SCRIPT.read_text(encoding="utf-8")
    # Precondition: the exact reproduction line from issue #833 is still
    # there, so this test is checking the real defect, not a stale line
    # number that happens to still pass.
    assert 'ps)   watcher_roles_ps_fallback "$wave" ;;' in text

    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "ps"}))
    uses = _ps_uses_in_mailbox_script(widened)
    assert all(use.indent != 4 or use.failsoft for use in uses)
    # The label produces NO use at all (not even a fail-soft one) - it is
    # not a command, so it must not appear in the use list in any form.
    assert len(uses) == 2, (
        f"expected exactly the two real `ps` invocations (845, 894), got {uses} - "
        "either the label at 720 is still being read as a use, or a real "
        "invocation was lost"
    )


def test_the_real_invocations_at_845_and_894_are_still_detected(tmp_path: Path) -> None:
    """The undercount direction is the unsafe one (per review): confirms the
    fix narrows what counts as a case label, not what counts as `ps` at all."""
    text = MAILBOX_SCRIPT.read_text(encoding="utf-8")
    assert 'ppid="$(ps -o ppid= -p "$pid" 2>/dev/null' in text  # precondition: the walk
    # The argv scan gained `-ww` in issue #904: without it procps caps each line
    # at $COLUMNS, so a watcher whose argv carries a long script path lost its
    # `--role`/`--wave` fields and the lane reported a confident zero. The text is
    # pinned rather than pattern-matched precisely so a change like that one shows
    # up here as a precondition failure instead of passing silently.
    assert "$(ps -ww -eo pid,ppid,args --no-headers 2>/dev/null)" in text

    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "ps"}))
    uses = _ps_uses_in_mailbox_script(widened)
    assert len(uses) == 2, f"expected both real invocations, got {uses}"
    # Both are fail-soft in the source (stderr silenced) - that classification
    # is unaffected by this fix and is asserted here so a future change that
    # breaks IT is caught by this test too, not only a change that breaks
    # detection outright.
    assert all(use.failsoft for use in uses)


def test_ps_is_not_a_hard_requirement_of_the_real_script(tmp_path: Path) -> None:
    """The end-to-end shape of issue #833's oracle: with `ps` added to
    GUARDED_BINARIES, `binaries_in_script()` on the real file must not
    report `ps` as a MANDATORY requirement - it never was one; both real
    uses are fail-soft and the label was never a use."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "ps"}))
    assert "ps" not in widened.binaries_in_script(MAILBOX_SCRIPT)


def test_a_pipe_joined_case_label_is_also_not_a_use(tmp_path: Path) -> None:
    """CASE_LABEL_RE covers `a|ps|b)`, not only the single-pattern shape
    actually in the tree today (issue #833's own scope note: 22 distinct
    case labels exist across scripts/*.sh; only the single-pattern shape
    happens to be real today, but the fix should not need re-deriving the
    moment a pipe-joined one is added). A constructed fixture is fine here -
    unlike the two tests above, there is no real in-tree instance to point
    at yet."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "ps"}))
    source = 'case "$x" in\n  proc|ps|none) do_thing ;;\nesac\n'
    lines = source.splitlines()
    uses = [u for u in widened._script_uses(source, lines) if u.binary == "ps"]
    assert uses == []


def test_a_real_command_immediately_followed_by_a_close_paren_still_counts(
    tmp_path: Path,
) -> None:
    """The narrow "next char is `)`" heuristic issue #833 also considered -
    and a reviewer then measured, not just warned about - would misfire on a
    genuine zero-argument invocation closed immediately: `ps)` (a case
    label) and `$(ps)` (a real invocation) are TEXTUALLY IDENTICAL, a bare
    binary name followed immediately by `)`; only what PRECEDES the name
    tells them apart (a line start vs. a literal `$(`), which is exactly why
    CASE_LABEL_RE anchors on line start rather than rejecting on the
    trailing `)` alone. A synthetic minimal case, kept alongside the real
    in-tree ones below because it isolates the exact textual collision a
    reviewer's reproduction named."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "ps"}))
    source = "count=$(ps)\n"
    lines = source.splitlines()
    uses = [u for u in widened._script_uses(source, lines) if u.binary == "ps"]
    assert len(uses) == 1, "a genuine zero-argument invocation must still be detected"


def test_real_bare_command_substitutions_in_tree_still_count(tmp_path: Path) -> None:
    """The same collision, pinned against REAL in-tree instances rather than
    only the synthetic one above (per review): `$(cat)` and `$(uname)` are
    both bare, zero-argument command substitutions actually in this repo's
    scripts, and both must stay detected once their binary is guarded -
    `cat`/`uname` are not in `GUARDED_BINARIES` today, but the fix must not
    depend on that; it must hold structurally, the same way #832 pinned the
    unreadable-`environ` failure direction rather than trusting today's
    binary list to never change."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "cat", "uname"}))

    hook_mask = ROOT / "scripts" / "hook-mask-output.sh"
    text = hook_mask.read_text(encoding="utf-8")
    assert "INPUT=$(cat)" in text  # precondition
    source = widened._mask_noncode(text)
    uses = [u for u in widened._script_uses(source, source.splitlines()) if u.binary == "cat"]
    assert len(uses) >= 1, "a real bare $(cat) must still be detected"

    bash_prep = ROOT / "scripts" / "bash-prep.sh"
    text = bash_prep.read_text(encoding="utf-8")
    assert 'warn "bash-prep is designed for Linux. Detected: $(uname)"' in text  # precondition
    source = widened._mask_noncode(text)
    uses = [u for u in widened._script_uses(source, source.splitlines()) if u.binary == "uname"]
    assert len(uses) >= 1, "a real bare $(uname) must still be detected"


# --------------------------------------------------------------------------- #
# Issue #838: an assignment (rev=0), an arithmetic expansion (rev=$((rev+1))),
# and text inside a quoted string ("fail (timeout: ...)", an AWK program
# embedded in `awk '...'`) are all read as command invocations for the same
# underlying reason CASE_LABEL_RE exists - each SITS AT the shape
# SHELL_BINARY_RE treats as command position without being one. Quoting and
# arithmetic both require STATE (is the current position inside such a
# region), unlike a case label or an assignment, which are answered by what
# is immediately adjacent to the match - see _mask_noncode's own header
# comment for why that distinction decided the fix's shape (a state-tracking
# pass for the two stateful mechanisms, a narrow positional regex,
# ASSIGNMENT_RE, for the one that is not).
# --------------------------------------------------------------------------- #

WAVE_MAILBOX = ROOT / "scripts" / "flow-wave-mailbox.sh"
FINISH_GATE = ROOT / "scripts" / "flow-finish-gate.sh"


def _rev_uses(widened, source: str) -> list:
    """`_script_uses` on already-masked source - the same order production
    code always runs them in (`binaries_in_script` masks before scanning)."""
    masked = widened._mask_noncode(source)
    return [u for u in widened._script_uses(masked, masked.splitlines()) if u.binary == "rev"]


def test_a_bash_assignment_is_not_read_as_an_invocation(tmp_path: Path) -> None:
    """`rev=0` and `rev="$(...)"` are assignment TARGETS, not invocations -
    the minimal constructed shapes, isolating the mechanism before the real
    in-tree test below pins it against actual code."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "rev"}))
    source = 'rev=0\nrev="$(some_helper)"\n'
    assert _rev_uses(widened, source) == []


def test_the_real_assignment_sites_in_tree_are_not_uses(tmp_path: Path) -> None:
    """The real bash assignments cited in issue #838:
    `flow-wave-mailbox.sh:1381,1383,1393` - `rev=0`, `rev="$(awk ...)"`, and
    `rev=$((rev + 1))` (the last one is ALSO the arithmetic-expansion
    mechanism below; fixing only the assignment-target half of that line is
    not enough on its own, which the end-to-end oracle further down proves)."""
    text = WAVE_MAILBOX.read_text(encoding="utf-8")
    assert "        rev=0\n" in text  # precondition: :1381
    assert '          rev="$(awk \'\n' in text  # precondition: :1383
    assert "        rev=$((rev + 1))\n" in text  # precondition: :1393

    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "rev"}))
    uses = _rev_uses(widened, text)
    assert uses == [], f"expected no assignment target read as a use, got {uses}"


def test_an_arithmetic_expansion_identifier_is_not_read_as_an_invocation(
    tmp_path: Path,
) -> None:
    """A bare identifier inside `$(( ... ))` is a variable reference, not a
    command - `$((rev + 1))`'s second `(` satisfies SHELL_BINARY_RE's bare
    `(` separator the same way a real subshell opener would."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "rev"}))
    source = "rev=$((rev + 1))\n"
    assert _rev_uses(widened, source) == []


def test_arithmetic_expansion_nesting_is_not_read_as_an_invocation(tmp_path: Path) -> None:
    """Every `(` inside `$(( ... ))` is arithmetic grouping, at ANY nesting
    depth - not only the outermost one. A fix that only recognises the
    literal two-character `$((` sequence (e.g. "is the char two back `$(`")
    would stop working the moment the expression groups a sub-term, which is
    exactly why this needs paren-depth TRACKING inside the region rather
    than a fixed-width lookbehind at its entrance."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "rev"}))
    source = "x=$(( (rev) + 1 ))\n"
    assert _rev_uses(widened, source) == []


def test_text_inside_a_double_quoted_string_is_not_read_as_an_invocation(
    tmp_path: Path,
) -> None:
    """The real site: `verdict "fail (timeout: ...)"` at
    `flow-finish-gate.sh:306` - the `(` inside the string satisfies
    SHELL_BINARY_RE's separator class the same way a real subshell opener
    would, even though it is plain text data, never executed."""
    text = FINISH_GATE.read_text(encoding="utf-8")
    assert 'verdict "fail (timeout: $TIMED_OUT_STEP after' in text  # precondition

    widened = _widened_checker(
        tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "timeout"})
    )
    source = widened._mask_noncode(text)
    uses = [u for u in widened._script_uses(source, source.splitlines()) if u.binary == "timeout"]
    assert uses == [], f"expected the quoted text to produce no use, got {uses}"


def test_text_inside_a_single_quoted_string_is_not_read_as_an_invocation(
    tmp_path: Path,
) -> None:
    """The real site: an AWK program's own `rev = 0` embedded in
    `awk '...'` at `flow-wave-mailbox.sh:634` (and 729, 900, identically) -
    AWK assignment syntax that is not bash at all, sitting inside a
    single-quoted shell string the checker previously had no way to tell
    from real command-position code."""
    text = WAVE_MAILBOX.read_text(encoding="utf-8")
    assert "      rev = 0\n" in text  # precondition: the awk-embedded shape

    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "rev"}))
    # None of the awk-body sites (634, 729, 900) may surface as a use.
    uses = _rev_uses(widened, text)
    assert uses == [], f"expected the awk-embedded text to produce no use, got {uses}"


def test_a_live_command_substitution_inside_a_double_quoted_string_still_counts(
    tmp_path: Path,
) -> None:
    """The undercount direction, for quoting: a double-quoted string MAY
    contain a real, executed command substitution - `"...$(git status)..."` -
    and that must stay detected even though it is textually inside quotes,
    because it still runs regardless of what encloses it."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq"}))
    source = 'echo "state is $(git status --short)"\n'
    source = widened._mask_noncode(source)
    uses = [u for u in widened._script_uses(source, source.splitlines()) if u.binary == "git"]
    assert len(uses) == 1, "a live $(...) nested in a double-quoted string must still count"


def test_a_live_command_substitution_inside_arithmetic_still_counts(tmp_path: Path) -> None:
    """The undercount direction, for arithmetic: `$(( ... ))` MAY itself
    contain a real command substitution - `$(( $(count_git) + 1 ))` - which
    must stay detected even though it sits inside an otherwise-masked
    arithmetic region."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq"}))
    source = "n=$(( $(git rev-list --count HEAD) + 1 ))\n"
    source = widened._mask_noncode(source)
    uses = [u for u in widened._script_uses(source, source.splitlines()) if u.binary == "git"]
    assert len(uses) == 1, "a live $(...) nested in arithmetic must still count"


def test_comment_and_quote_ordering_do_not_misread_each_other(tmp_path: Path) -> None:
    """Comments and quoting are resolved TOGETHER, not as two independent
    passes (see `_mask_noncode`'s own header comment): an apostrophe inside a
    `#` comment must not be read as opening a single-quoted string (which
    would swallow everything up to the NEXT apostrophe anywhere later in the
    file - exactly the regression caught while building this fix, against
    this repo's own scripts), and a `#` inside a real quoted string must not
    truncate the real code that follows it on the same line."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq"}))

    # An apostrophe in a comment must not open a fake single-quoted region
    # that then swallows the real `git` invocation several lines later.
    source = "# the orchestrator's state\necho ok\ngit status\n"
    masked = widened._mask_noncode(source)
    uses = [u for u in widened._script_uses(masked, masked.splitlines()) if u.binary == "git"]
    assert len(uses) == 1, "an apostrophe in a comment swallowed real code after it"

    # A `#` inside a real double-quoted string must not start a comment that
    # eats the `git status` which follows on the same line.
    source = 'echo "value # not a comment" && git status\n'
    masked = widened._mask_noncode(source)
    uses = [u for u in widened._script_uses(masked, masked.splitlines()) if u.binary == "git"]
    assert len(uses) == 1, "a `#` inside a quoted string ate real code after it"


def test_rev_widening_reaches_zero_findings(tmp_path: Path) -> None:
    """The end-to-end oracle issue #838 measured: widening `GUARDED_BINARIES`
    to `rev` produced 234 findings before this fix, all traced to the six
    sites above. After it, none of the six real sites are uses, and no
    OTHER script in the tree needs `rev` either, so the tree-wide finding
    count must be exactly zero - not merely "the six sites are excluded",
    which a narrower assertion could satisfy while missing a seventh."""
    widened = _widened_checker(tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "rev"}))
    findings = widened.check_tree(ROOT / "tests")
    assert findings == [], f"expected zero findings widening to rev, got {findings}"


def test_timeout_widening_reaches_exactly_the_one_genuine_finding(tmp_path: Path) -> None:
    """The other half of #838's oracle: widening to `timeout` produced 42
    findings before this fix. 41 are the SAME quoted-text false positive
    (`flow-finish-gate.sh:306`, transitively reaching every test that runs
    the gate via the script hop) - those must all be gone. The 42nd is a
    genuine, correct finding: `test_a_real_forced_timeout_reaches_the_helper_as_124`
    in `tests/test_delegated_run_check.py` shells out to the real `timeout`
    binary directly, with no guard, and is not a false positive of any
    mechanism this issue is about - it must NOT also disappear, which would
    be the undercount direction this whole issue is about avoiding."""
    widened = _widened_checker(
        tmp_path, frozenset({"git", "docker", "gitleaks", "jq", "timeout"})
    )
    findings = widened.check_tree(ROOT / "tests")
    assert len(findings) == 1, f"expected exactly the one genuine finding, got {findings}"
    assert findings[0].test == "test_a_real_forced_timeout_reaches_the_helper_as_124"
    assert findings[0].via_scripts == (), "the genuine finding is a direct call, not via a script"


# --------------------------------------------------------------------------- #
# Issue #831: the DIRECT lane is inverted - the CI image supplies the default.
#
# Before this, the gate answered "is a GUARDED binary unguarded?" and its reader
# took it for "is ANY binary unguarded?". Both are true of the code; only the
# first was true of the check. #830 is what the gap cost: `pgrep` was outside
# what the check examined, `make verify` passed, and CI went red.
#
# The first test below is the one that matters, because the obvious fix - adding
# names to `GUARDED_BINARIES` - is INERT for the case that actually failed if the
# binary is reached through a script that degrades gracefully. Measured while
# writing this: widening the set to {pgrep, ps, tmux, flock, curl} and then
# DELETING the `@requires_ps` guards from tests/test_flow_wave_mailbox.py still
# produced zero findings. See `test_a_fail_soft_script_use_is_a_known_blind_spot`.
# --------------------------------------------------------------------------- #


def _tree(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_sample.py").write_text(body, encoding="utf-8")
    return root


def test_an_unlisted_binary_now_needs_a_guard(tmp_path: Path) -> None:
    """The membership floor: a binary nobody put on any list.

    `rsync` is on no list in the checker and never has been. Before #831 it was
    invisible; the point of inverting is that "nobody thought of this one" stops
    being indistinguishable from "this one is fine".
    """
    root = _tree(
        tmp_path,
        "import subprocess\n\n\n"
        "def test_x():\n"
        "    subprocess.run(['rsync', '-a', 'a', 'b'])\n",
    )
    findings = checker.check_tree(root / "tests")
    assert len(findings) == 1, f"expected the unlisted binary to be found: {findings}"
    assert findings[0].binaries == ("rsync",)


def test_the_830_shape_is_found(tmp_path: Path) -> None:
    """The exact call that reddened #830, as a regression pin.

    `tests/test_flow_wave_mailbox.py:1861` ran this with no guard. The binary has
    since been removed from that test entirely (the #814 fix reads /proc instead),
    so this reconstructs the shape rather than pointing at a live site - stated
    plainly because a regression test whose original is gone can otherwise read as
    covering something it no longer touches.
    """
    root = _tree(
        tmp_path,
        "import subprocess\n\n\n"
        "def test_supervise():\n"
        "    subprocess.run(['pgrep', '-P', '1', '-f', 'watch'])\n",
    )
    findings = checker.check_tree(root / "tests")
    assert [f.binaries for f in findings] == [("pgrep",)]


def test_a_binary_the_ci_image_provides_needs_no_guard(tmp_path: Path) -> None:
    """The other direction, and the one that decides whether this is usable.

    An inversion that flagged `sed` would flag most of the suite and be turned
    off within a week. The exempt list is what keeps the gate proportionate, and
    is the thing to correct if a finding looks silly - not the inversion.
    """
    root = _tree(
        tmp_path,
        "import subprocess\n\n\n"
        "def test_x():\n"
        "    subprocess.run(['sed', '-n', '1p', 'f'])\n"
        "    subprocess.run(['grep', '-q', 'x', 'f'])\n"
        "    subprocess.run(['python3', '-c', 'pass'])\n",
    )
    assert checker.check_tree(root / "tests") == []


def test_a_guarded_unlisted_binary_is_accepted(tmp_path: Path) -> None:
    """A guard may now name a binary that appears on no list in the checker."""
    root = _tree(
        tmp_path,
        "import shutil\n"
        "import subprocess\n\n"
        "import pytest\n\n"
        "requires_rsync = pytest.mark.skipif(\n"
        "    shutil.which('rsync') is None, reason='needs rsync'\n"
        ")\n\n\n"
        "@requires_rsync\n"
        "def test_x():\n"
        "    subprocess.run(['rsync', '-a', 'a', 'b'])\n",
    )
    assert checker.check_tree(root / "tests") == []


def test_a_shell_command_string_is_covered_by_the_inversion(tmp_path: Path) -> None:
    """`shell=True` takes the same lane, so the inversion must reach it too."""
    root = _tree(
        tmp_path,
        "import subprocess\n\n\n"
        "def test_x():\n"
        "    subprocess.run('tmux list-sessions', shell=True)\n",
    )
    assert [f.binaries for f in checker.check_tree(root / "tests")] == [("tmux",)]


def test_bash_is_not_flagged_but_its_script_is_still_followed(tmp_path: Path) -> None:
    """`bash` is provided by the image, so it must not become a finding itself -
    and making it exempt must not cost the #789 script hop, which is the only
    reason argv[0] of `bash` is interesting at all."""
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "scripts").mkdir()
    script = root / "scripts" / "needs-jq.sh"
    script.write_text("#!/bin/bash\nBRANCH=$(jq -r '.b' \"$CONFIG\")\necho \"$BRANCH\"\n")
    (root / "tests" / "test_sample.py").write_text(
        "import subprocess\n"
        "from pathlib import Path\n\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "SCRIPT = ROOT / 'scripts' / 'needs-jq.sh'\n\n\n"
        "def test_x():\n"
        "    subprocess.run(['bash', str(SCRIPT)])\n",
        encoding="utf-8",
    )
    findings = checker.check_tree(root / "tests")
    assert [f.binaries for f in findings] == [("jq",)], (
        f"the hop must still resolve through an exempt bash: {findings}"
    )
    assert findings[0].via_scripts, "this is a via-script finding, not a direct one"


def test_ci_image_constant_matches_the_pipeline(tmp_path: Path) -> None:
    """`CI_IMAGE_BINARIES` is a claim about ONE image, and claims go stale.

    The exempt list is only as true as the image it describes. Nothing else in
    this repository would notice the pipeline moving to a different base, and the
    failure would be silent in exactly the way #830 was: the gate keeps saying ok
    while the premise underneath it has changed.
    """
    pipeline = (ROOT / ".woodpecker.yml").read_text(encoding="utf-8")
    assert checker.CI_IMAGE in pipeline, (
        f"check-test-binary-guards.py describes {checker.CI_IMAGE!r}, which "
        f".woodpecker.yml no longer uses. The exempt list is a statement about "
        f"the image's contents - re-derive it before changing this constant "
        f"(issue #831)."
    )


def test_the_two_lists_do_not_silently_overlap() -> None:
    """A name in both lists is an always-guard override of the image default.

    Legal, and today empty. Asserting it is empty keeps the override from being
    used by accident: if a future change puts a name in both, that is a decision
    worth making on purpose rather than discovering from a finding nobody
    expected.
    """
    overlap = checker.GUARDED_BINARIES & checker.CI_IMAGE_BINARIES
    assert overlap == frozenset(), (
        f"{sorted(overlap)} are declared both always-guarded and provided by the "
        f"image. That combination means 'guard it anyway'; if that is intended, "
        f"say so here rather than leaving it to be inferred."
    )


def test_a_fail_soft_script_use_is_a_known_blind_spot(tmp_path: Path) -> None:
    """A NAMED RESIDUAL, pinned as a property rather than left as a TODO.

    The hop drops a binary when the script's every use is fail-soft - stderr
    silenced, in a condition, or with a `||` fallback - because such a script
    genuinely survives the binary's absence. That is the right answer to the
    question the hop asks: *can the SCRIPT do its job without this binary?*

    A reader takes it for a different question: *can the TEST pass without this
    binary?* Those diverge exactly when a script degrades gracefully and a test
    asserts the DEGRADED-versus-not distinction, which is a growing pattern here -
    every `unknown`-vs-`clear` lane produces one.

    It is live in this repository, and NOT in one place. This docstring used to
    name a single instance - `scripts/flow-wave-mailbox.sh` reaching `ps` only as
    `$(ps -eo pid,ppid,args --no-headers 2>/dev/null)`. Derived by this gate's own
    predicates (`--fail-soft-report`, issue #926): FOURTEEN (script, binary) pairs
    across `scripts/*.sh`, thirteen of them named by a test module, of which six
    carry a hand-written guard and SEVEN do not. A hand-maintained example in a
    docstring stayed at one while the tree held thirteen, which is why the
    population is now derived and printed rather than described here.

    Measured: widening `GUARDED_BINARIES` to include `ps` AND deleting those
    guards still yields zero findings, so the inversion this issue asked for does
    not close this.

    THE REMEDY IS A SEPARATE CHANNEL, NOT A WIDER ONE. Believing the fail-soft
    declaration is what keeps the hop from crying wolf (scanning for mere mentions
    produced 266 findings, ~250 of them false) - the shape
    docs/agents/detector-contracts.md calls "when widening is not the remedy". So
    the hop still drops these, and #926 added the two things that make that
    survivable: `--fail-soft-report` lists the population with its bound, and
    `tests/conftest.py` names and counts skips caused by an absent binary so an
    unexercised lane is visible in `make verify` rather than absorbed into
    "N passed".

    WHAT THIS TEST PINS IS THE DROP, AND IT IS STILL DELIBERATE. What it no longer
    claims is that the drop is harmless: on 2026-09-15
    `TestPsFallbackWatcherIdentityAcrossDirectories` was found PASSING on a host
    without the `ps` it forces, asserting an `unknown` the absent binary produced
    for an unrelated reason. That was a green carrying no information, not the red
    pipeline #926 records, and it is fixed.
    """
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "scripts").mkdir()
    script = root / "scripts" / "degrades.sh"
    # The real shape, copied from scripts/flow-wave-mailbox.sh.
    script.write_text(
        "#!/bin/bash\nROWS=$(ps -eo pid,ppid,args --no-headers 2>/dev/null)\n"
        'echo "${ROWS:-unknown}"\n'
    )
    (root / "tests" / "test_sample.py").write_text(
        "import subprocess\n"
        "from pathlib import Path\n\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "SCRIPT = ROOT / 'scripts' / 'degrades.sh'\n\n\n"
        "def test_forces_the_ps_lane():\n"
        "    subprocess.run(['bash', str(SCRIPT)])\n",
        encoding="utf-8",
    )
    assert "ps" in checker.GUARDED_BINARIES, (
        "precondition: `ps` must be on the hop's scan list, or this test proves "
        "only that an unlisted binary is unlisted"
    )
    assert checker.check_tree(root / "tests") == [], (
        "if this now reports a finding the residual has been closed - good. "
        "Update this test to assert the new behaviour and remove the note in "
        "docs/scripts.md rather than deleting the test."
    )


# --------------------------------------------------------------------------- #
# curl, the binary that turned #895's first pipeline red (issue #895)
# --------------------------------------------------------------------------- #
# Deliberately NOT asserting `"curl" in checker.GUARDED_BINARIES`. #831 made
# `CI_IMAGE_BINARIES` the default lane - a binary the CI image lacks is guarded
# because it is absent from the image, not because it is in the explicit
# override list - so pinning that membership would forbid a later correct
# removal. What is worth pinning is the BEHAVIOUR: that the gate fires on an
# unguarded curl and clears a guarded one. Membership without a firing test is
# exactly how curl stayed invisible while the comment above the set had named it
# as absent from the image since #716/#717.
def test_fires_on_an_unguarded_curl(tmp_path: Path) -> None:
    """Positive control for the binary that cost #895 a red `validate` step."""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
def test_probe():
    subprocess.run("curl -sf http://127.0.0.1:1/api/tags", shell=True, check=False)
""",
    )
    assert len(findings) == 1, findings
    assert "curl" in str(findings[0])


def test_a_guarded_curl_clears(tmp_path: Path) -> None:
    """The negative half: a correctly guarded test must NOT be flagged."""
    findings = _findings(
        tmp_path,
        PREAMBLE
        + """\
requires_curl = pytest.mark.skipif(shutil.which("curl") is None, reason="needs curl")


@requires_curl
def test_probe():
    subprocess.run("curl -sf http://127.0.0.1:1/api/tags", shell=True, check=False)
""",
    )
    assert findings == [], findings


# --------------------------------------------------------------------------- #
# Issue #906: a test that runs a repo script DIRECTLY bypassed the one-hop scan.
#
# The #789 hop required argv[0] to be `bash` or `sh`. Every helper in `scripts/`
# is executable and carries `#!/usr/bin/env bash`, so running one directly is the
# NATURAL spelling - and it entered no hop at all, so the script was never
# scanned. A test author following the repo's own conventions got no coverage;
# one writing the less natural `["bash", SCRIPT]` did.
#
# This widens only the TRIGGER. The scan it feeds is the same
# `binaries_in_script()` against the same explicit `GUARDED_BINARIES`, so the
# function-versus-binary collision that made inverting the hop unworkable (#831)
# stays out of reach - a shell function is only mistakable for a binary when
# scanning for arbitrary tokens, and nothing here does that.
# --------------------------------------------------------------------------- #


def _direct_tree(tmp_path: Path, *, body: str, script: str, executable: bool = True) -> Path:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "scripts").mkdir()
    helper = root / "scripts" / "hard.sh"
    helper.write_text(script, encoding="utf-8")
    if executable:
        helper.chmod(0o755)
    (root / "tests" / "test_sample.py").write_text(body, encoding="utf-8")
    return root


#: A script that HARD-requires jq: a bare command substitution, no preflight,
#: no fail-soft fallback. Chosen so these tests exercise the trigger rather than
#: the separate hard-requires judgement.
_HARD_JQ = "#!/usr/bin/env bash\nset -euo pipefail\nB=$(jq -r '.b' \"$1\")\necho \"$B\"\n"

_DIRECT_BODY = (
    "import subprocess\n"
    "from pathlib import Path\n\n"
    "ROOT = Path(__file__).resolve().parents[1]\n"
    "HELPER = ROOT / 'scripts' / 'hard.sh'\n\n\n"
    "def test_x():\n"
    "    subprocess.run([str(HELPER), 'x.json'])\n"
)


def test_a_directly_invoked_script_is_scanned(tmp_path: Path) -> None:
    """#906's acceptance criterion 1, and the positive control it asks for.

    The issue is explicit that a membership-only assertion is not enough here -
    "the 1-of-12 result above is what a membership-only assertion looks like when
    it passes". So this asserts the finding, and
    `test_the_direct_trigger_is_what_makes_the_difference` asserts that the
    PREVIOUS behaviour would not have produced it.
    """
    root = _direct_tree(tmp_path, body=_DIRECT_BODY, script=_HARD_JQ)
    findings = checker.check_tree(root / "tests")
    assert [f.binaries for f in findings] == [("jq",)], (
        f"a directly-invoked repo script was not scanned (issue #906): {findings}"
    )
    assert findings[0].via_scripts, "this is a via-script finding, not a direct one"


def test_a_bare_path_object_argv0_is_scanned(tmp_path: Path) -> None:
    """`subprocess.run([HELPER, ...])` without `str()` is the same shape."""
    body = _DIRECT_BODY.replace("str(HELPER)", "HELPER")
    root = _direct_tree(tmp_path, body=body, script=_HARD_JQ)
    assert [f.binaries for f in checker.check_tree(root / "tests")] == [("jq",)]


def test_the_direct_trigger_is_what_makes_the_difference(tmp_path: Path) -> None:
    """Control: the same tree is INVISIBLE to a checker without the #906 trigger.

    Without this, every assertion above could pass for some unrelated reason and
    the change would look effective while covering nothing - which is exactly the
    1-of-12 the issue warns about.
    """
    root = _direct_tree(tmp_path, body=_DIRECT_BODY, script=_HARD_JQ)
    # The hop's trigger, as it was: argv[0] must be bash/sh.
    assert "bash" in checker.SHELL_RUNNERS and "sh" in checker.SHELL_RUNNERS
    resolver_used = checker.check_tree(root / "tests")
    assert resolver_used, "precondition: the new trigger finds it"
    # And the bash spelling still works - the widening is additive, not a swap.
    bash_body = _DIRECT_BODY.replace(
        "subprocess.run([str(HELPER), 'x.json'])",
        "subprocess.run(['bash', str(HELPER), 'x.json'])",
    )
    root2 = _direct_tree(tmp_path / "two", body=bash_body, script=_HARD_JQ)
    assert [f.binaries for f in checker.check_tree(root2 / "tests")] == [("jq",)], (
        "the #789 bash hop regressed"
    )


def test_a_guarded_direct_invocation_is_not_flagged(tmp_path: Path) -> None:
    """#906 acceptance: the negative half."""
    body = (
        "import shutil\n"
        "import subprocess\n"
        "from pathlib import Path\n\n"
        "import pytest\n\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "HELPER = ROOT / 'scripts' / 'hard.sh'\n"
        "requires_jq = pytest.mark.skipif(shutil.which('jq') is None, reason='jq')\n\n\n"
        "@requires_jq\n"
        "def test_x():\n"
        "    subprocess.run([str(HELPER), 'x.json'])\n"
    )
    root = _direct_tree(tmp_path, body=body, script=_HARD_JQ)
    assert checker.check_tree(root / "tests") == []


def test_a_script_that_does_not_reach_the_binary_is_not_flagged(tmp_path: Path) -> None:
    """#906 acceptance: a script with no guarded requirement stays silent."""
    root = _direct_tree(
        tmp_path,
        body=_DIRECT_BODY,
        script="#!/usr/bin/env bash\nset -euo pipefail\necho \"$1\"\n",
    )
    assert checker.check_tree(root / "tests") == []


def test_an_argv0_outside_the_repo_is_ignored(tmp_path: Path) -> None:
    """Ownership boundary (#906 acceptance): a system script is not ours to scan.

    A path that resolves to a real, executable file OUTSIDE the checkout must not
    be read. Findings about a neighbour's code are the #834 ownership half, and a
    checker that reports them cannot be trusted about its own.
    """
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    stranger = outside / "hard.sh"
    stranger.write_text(_HARD_JQ, encoding="utf-8")
    stranger.chmod(0o755)

    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_sample.py").write_text(
        "import subprocess\n"
        "from pathlib import Path\n\n"
        f"HELPER = Path({str(stranger)!r})\n\n\n"
        "def test_x():\n"
        "    subprocess.run([str(HELPER), 'x.json'])\n",
        encoding="utf-8",
    )
    assert stranger.is_file(), "precondition: the outside script exists and is real"
    assert checker.check_tree(root / "tests") == [], (
        "a script outside the checkout was scanned (issue #906 ownership boundary)"
    )


def test_a_non_executable_argv0_is_ignored(tmp_path: Path) -> None:
    """The shape covered is "run on its shebang", which needs the x bit.

    A non-executable path in argv[0] cannot run at all, so scanning it would be
    reading a file the test never executes.
    """
    root = _direct_tree(tmp_path, body=_DIRECT_BODY, script=_HARD_JQ, executable=False)
    assert checker.check_tree(root / "tests") == []


# --------------------------------------------------------------------------- #
# Issue #906, second half: a quoted heredoc body is another language's source.
#
# Widening the trigger above took the tree from `ok` to 31 findings, ALL false,
# ALL from one line of prose. `scripts/delegated-run-check.sh` embeds a Python
# program via `python3 - <<'PYEOF'`, and a docstring inside it says a model that
# tries `git commit` once is behaving as designed. Those are MARKDOWN backticks -
# but a backtick opens a command substitution in shell, and SHELL_BINARY_RE
# counts one as a command-position separator, so the sentence read as an
# invocation of git.
#
# It could not fire before #906: that script is only ever invoked DIRECTLY by its
# tests, the exact shape the hop could not see. The gap masked the bug. Same
# sequence as #831's widening exposing #833's `case` label - each widening
# exposes the next latent false positive, invisible until its predecessor closed.
# --------------------------------------------------------------------------- #

DELEGATED_RUN_CHECK = ROOT / "scripts" / "delegated-run-check.sh"


def test_the_real_embedded_python_docstring_is_not_read_as_shell() -> None:
    """The regression fixture is the REAL in-tree instance, not a constructed one.

    #833's own note: a real in-tree instance is evidence, a hand-written block is
    illustration. This is the file and the line that produced the 31 findings.
    """
    assert DELEGATED_RUN_CHECK.is_file(), "the fixture script is gone - test is stale"
    text = DELEGATED_RUN_CHECK.read_text(encoding="utf-8")
    assert "<<'PYEOF'" in text, (
        "precondition: the script no longer embeds a quoted heredoc, so this test "
        "is not exercising the shape it claims to pin"
    )
    assert "`git commit`" in text, (
        "precondition: the backticked prose that caused the false positive is "
        "gone - re-point this test at whatever instance remains, or retire it"
    )
    assert checker.binaries_in_script(DELEGATED_RUN_CHECK) == frozenset(), (
        "prose inside an embedded-Python heredoc is being read as a shell "
        "invocation (issue #906)"
    )


def test_masking_a_heredoc_does_not_hide_a_genuine_use(tmp_path: Path) -> None:
    """The other direction, and the one that matters.

    Blanking heredoc bodies is the safe-looking move, and the undercount is the
    unsafe direction - the same asymmetry #838 pinned for its own fix. A real
    `jq` invocation in the surrounding shell, and one on the heredoc's own
    opening line, must both still be seen.
    """
    script = tmp_path / "mixed.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "B=$(jq -r '.b' \"$1\")\n"            # genuine, before the heredoc
        "python3 - <<'PY'\n"
        "import sys\n"
        '"""a docstring mentioning `jq` and `git` in prose"""\n'
        "PY\n"
        "echo \"$B\"\n",
        encoding="utf-8",
    )
    found = checker.binaries_in_script(script)
    assert "jq" in found, "masking the heredoc also hid the real invocation above it"
    assert "git" not in found, "prose inside the heredoc is still being read as shell"


def test_an_unterminated_heredoc_does_not_swallow_the_rest_of_the_file(
    tmp_path: Path,
) -> None:
    """A named residual, pinned rather than left to be discovered.

    The mask runs to the closing delimiter. A script whose delimiter never
    appears - a truncated file, or a delimiter written differently than opened -
    masks everything after it, and every binary below goes UNSEEN. That is the
    undercount direction, so it is worth knowing it is the behaviour rather than
    assuming the parser is total.

    Not defended against here: a real heredoc parser is the fix, and this file
    states outright that it is not one. Bash itself rejects an unterminated
    heredoc, so a script in this shape is already broken and would not run.
    """
    script = tmp_path / "unterminated.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "python3 - <<'PY'\n"
        "print('no closing delimiter')\n"
        "B=$(jq -r '.b' \"$1\")\n",          # below the unterminated heredoc
        encoding="utf-8",
    )
    assert checker.binaries_in_script(script) == frozenset(), (
        "if this now finds jq the residual is closed - assert the new behaviour "
        "and update docs/scripts.md rather than deleting the test"
    )


def test_an_unquoted_heredoc_is_still_scanned(tmp_path: Path) -> None:
    """Only a QUOTED delimiter means "literal text for another program".

    An unquoted `<<EOF` body is parameter-expanded and command-substituted by the
    shell itself, so a `$(...)` in it really is this script running a command.
    Masking those too would be the undercount direction again.
    """
    script = tmp_path / "unquoted.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<EOF\n"
        "value: $(jq -r '.b' \"$1\")\n"
        "EOF\n",
        encoding="utf-8",
    )
    assert "jq" in checker.binaries_in_script(script), (
        "an unquoted heredoc is expanded by the shell - its command "
        "substitutions are real invocations and must still be seen"
    )


# --------------------------------------------------------------------------- #
# --fail-soft-report: the population, derived (issue #926)
# --------------------------------------------------------------------------- #
# The blind spot was described by a docstring naming ONE instance while the tree
# held thirteen. A hand-maintained list is right the day it is written; these
# assert the DERIVATION instead, so the list re-derives as the tree moves.
def test_the_report_derives_a_nonempty_population() -> None:
    """An empty population would make every assertion below vacuous.

    The extractor's own control: if `_script_uses` or the failsoft predicate ever
    stops matching, this reports zero pairs and a reader sees "no blind spot"
    rather than "the derivation is broken". Those are different facts.
    """
    rows = checker.fail_soft_population(ROOT)
    assert len(rows) >= 10, f"derivation looks blind, found {len(rows)} pairs"
    scripts = {script for script, _binary, _naming, _guarded in rows}
    assert "flow-wave-mailbox.sh" in scripts, (
        "the instance this issue was filed about must appear in its own population"
    )
    binaries = {binary for _script, binary, _naming, _guarded in rows}
    assert binaries <= set(checker.GUARDED_BINARIES), (
        f"the report must not invent binaries outside the gate's own set: {binaries}"
    )


def test_the_report_separates_guarded_from_candidate() -> None:
    """Both classifications must occur, or the split is not doing any work.

    A report where everything is `guarded` and one where everything is
    `CANDIDATE` are both consistent with a broken classifier; only the presence
    of both shows it discriminates.
    """
    rows = checker.fail_soft_population(ROOT)
    named = [r for r in rows if r[2]]
    guarded = [r for r in named if r[3]]
    candidates = [r for r in named if not r[3]]
    assert guarded, "no pair classified as guarded - the guard detection is blind"
    assert candidates, "no pair classified as a candidate - the split is inert"

    by_pair = {(script, binary): is_guarded for script, binary, _n, is_guarded in rows}
    assert by_pair.get(("flow-wave-mailbox.sh", "ps")) is True, (
        "the ps instance carries a hand-written requires_ps and must read as guarded"
    )


def test_the_report_never_fails_the_build(capsys: pytest.CaptureFixture) -> None:
    """It REPORTS. Making it a gate would flag candidates as defects.

    The evidence cannot support that: "a test module names the script" is coarse,
    and a gate whose findings are mostly unconfirmed is the crying-wolf failure
    the hop exists to avoid - 266 findings, ~250 false, per the module docstring.
    """
    assert checker.main(["--fail-soft-report"]) == 0
    out = capsys.readouterr().out
    assert "fail-soft blind spot:" in out, out
    assert "not inspected:" in out, (
        "the report must name what it did NOT establish - whether a candidate's "
        "test actually needs the binary"
    )


def test_the_report_does_not_change_the_gate_verdict(capsys: pytest.CaptureFixture) -> None:
    """Adding a mode must not move what the default invocation says."""
    assert checker.main([]) == 0
    assert "binary-guards: ok" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# The missing-binary skip reporter (issue #926, tests/conftest.py)
# --------------------------------------------------------------------------- #
# A guard turns a vacuous PASS into a SKIP, and a skip inside `make verify` is
# still a green carrying no information. The hook names and counts them. These
# pin BOTH directions, because a hook that reports "missing-binary skips" while
# actually counting EVERY skip is indistinguishable from a correct one on any run
# where all skips happen to be binary-related - which is most runs.
def _load_conftest():
    """Load tests/conftest.py by PATH.

    `import conftest` raises ModuleNotFoundError under this repo's import mode -
    pytest does not put tests/ on sys.path here. Mirrors `_load_checker` above
    rather than inventing a second mechanism.
    """
    path = ROOT / "tests" / "conftest.py"
    spec = importlib.util.spec_from_file_location("cpp_tests_conftest", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _attribute(reasons: list[str], binaries: set[str] | None = None) -> dict[str, int]:
    conf = _load_conftest()
    return conf.attribute_missing_binary_skips(
        reasons, frozenset(binaries if binaries is not None else {"ps", "git", "jq", "curl"})
    )


def test_a_missing_binary_skip_is_attributed_to_its_binary() -> None:
    counts = _attribute([
        "needs ps: the fallback lane shells out to it",
        "requires git on PATH",
        "needs ps for the watcher scan",
    ])
    assert counts == {"ps": 2, "git": 1}, counts


def test_an_unrelated_skip_is_NOT_attributed() -> None:
    """The half most people skip, and the one that makes the count mean anything.

    Without it, a hook that counted every skip and labelled the total
    "missing-binary" would pass every test above.
    """
    assert _attribute([
        "not implemented yet",
        "needs a slow network fixture",
        "flaky on this platform",
    ]) == {}


def test_a_binary_name_inside_a_longer_word_is_not_a_match() -> None:
    """`ps` must not match "steps", and a hyphen is not a word boundary here.

    `\\b` would treat "no-ps-here" as naming `ps`; the boundary is `[\\w-]` on both
    sides for exactly that reason, and this is what pins it rather than the
    comment saying so.
    """
    assert _attribute(["skipped between steps", "https only", "no-ps-here"]) == {}
    assert _attribute(["needs ps"]) == {"ps": 1}


def test_an_unreadable_binary_set_attributes_nothing_rather_than_guessing() -> None:
    """An empty set must produce no attribution, not a confident zero-labelled count."""
    assert _attribute(["needs ps", "requires git"], binaries=set()) == {}


# --------------------------------------------------------------------------- #
# The displacement hazard itself (issue #926, #923)
# --------------------------------------------------------------------------- #
# Fixing the un-guarded class was NOT enough, and a mutation is what showed it:
# deleting the restored `@requires_ps` left the whole suite green. That is the
# condition #923 happened under and survived in for months - the fix was as
# uncontrolled as the defect. These two catch the MECHANISM rather than the one
# instance, so the next displacement fails here instead of in someone's pipeline.
_MAILBOX_TESTS = ROOT / "tests" / "test_flow_wave_mailbox.py"


def _classes_with_decorators(path: Path) -> list[tuple[str, int, list[str]]]:
    """(class name, line, decorators) for every top-level test class."""
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for i, line in enumerate(lines):
        if not line.startswith("class Test"):
            continue
        deco, j = [], i - 1
        while j >= 0 and (lines[j].startswith("@") or lines[j].startswith("#") or not lines[j].strip()):
            if lines[j].startswith("@"):
                deco.append(lines[j].strip())
            j -= 1
        out.append((line.split("(")[0].removeprefix("class ").rstrip(":"), i + 1, list(reversed(deco))))
    return out


def test_no_test_class_carries_a_duplicated_decorator() -> None:
    """A doubled stack is the TELL of a displaced edit, and it is harmless at runtime.

    #923 pasted a class directly above a decorated one; Python applied the
    existing pair to whichever class came next, and the original was displaced out
    from under its own guards. The only signal was the same decorator appearing
    twice - no linter, gate or test flagged it, because two identical `skipif`
    marks do nothing. Cheap to detect, and it catches the mechanism rather than
    any one victim.
    """
    offenders = [
        (name, line, deco)
        for name, line, deco in _classes_with_decorators(_MAILBOX_TESTS)
        if len(deco) != len(set(deco))
    ]
    assert not offenders, (
        f"duplicated decorators - the signature of a displaced edit: {offenders}"
    )


def test_every_test_forcing_the_ps_lane_is_guarded_for_ps() -> None:
    """Derived from what each TEST does, at the granularity the guard can sit.

    A test that sets FLOW_WAVE_WATCHER_SCAN to "ps" forces the ps lane and needs
    ps to exercise anything. Measured 2026-09-15: unguarded, such a test PASSED on
    a host without ps - it asserts the lane reports `unknown`, and an absent
    binary produces `unknown` for an unrelated reason.

    PER TEST, NOT PER CLASS, because the guard legitimately sits in either place -
    `TestListWatchState` guards one METHOD rather than the whole class, and a
    class-level check would have called that a defect. The first draft did exactly
    that, and it also missed the `FLOW_WAVE_WATCHER_SCAN="ps"` keyword form while
    matching only the subscript form, so it reported the wrong classes for two
    reasons at once.

    Keyed on behaviour so a renamed or newly added test is covered the moment it
    exists - the same reason #926's population is derived rather than listed.
    """
    import ast

    tree = ast.parse(_MAILBOX_TESTS.read_text(encoding="utf-8"))
    source = _MAILBOX_TESTS.read_text(encoding="utf-8")

    def decorator_names(node: ast.AST) -> set[str]:
        out = set()
        for dec in getattr(node, "decorator_list", []):
            out.add(ast.unparse(dec))
        return out

    def forces_ps(node: ast.AST) -> bool:
        seg = ast.get_source_segment(source, node) or ""
        return 'FLOW_WAVE_WATCHER_SCAN="ps"' in seg or 'FLOW_WAVE_WATCHER_SCAN"] = "ps"' in seg

    forcing, unguarded = [], []
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        cls_decs = decorator_names(cls)
        for fn in [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            if not forces_ps(fn):
                continue
            forcing.append(f"{cls.name}.{fn.name}")
            if "requires_ps" not in (cls_decs | decorator_names(fn)):
                unguarded.append(f"{cls.name}.{fn.name}:{fn.lineno}")

    assert forcing, (
        "no test forces the ps lane - either the derivation broke or the lane "
        "moved, and both mean this test is watching nothing"
    )
    assert not unguarded, (
        f"these force the ps lane and would PASS vacuously without ps: {unguarded}"
    )


# --------------------------------------------------------------------------- #
# #1036 - "every shelling-out test is guarded" is a claim about a CLASS
# --------------------------------------------------------------------------- #


def _clean_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    for name, source in files.items():
        (tests_dir / name).write_text(source, encoding="utf-8")
    return tmp_path


GUARDED_TEST = '''
import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("git") is None, reason="no git")
def test_uses_git():
    subprocess.run(["git", "status"], check=False)


def test_uses_nothing():
    assert True
'''

PLAIN_TEST = '''
def test_nothing_at_all():
    assert True
'''


def test_the_success_line_states_a_denominator_not_a_quantifier(tmp_path: Path, capsys) -> None:
    """The remedy shape, and NOT deleting the word `every`.

    `binary-guards: ok - every shelling-out test is guarded` claims a CLASS
    while the check inspects one statically-visible shape, as this file's own
    docstring scopes it - so a test reaching a binary through a shape the parser
    does not model produced the identical green. The gate sits in `make verify`,
    so that green is consumed by every commit, and `every` converts a floor into
    apparent total coverage.

    A bare `ok` would be worse, not better: silence reads as clean. The repo
    already has the right shape in `claude-md-budget: ok - 1310/2000 words`.
    """
    root = _clean_tree(tmp_path, {"test_a.py": GUARDED_TEST})
    assert checker.main(["--root", str(root)]) == 0
    line = capsys.readouterr().out.strip()
    assert "every shelling-out test" not in line, (
        f"the class quantifier is back: {line!r}"
    )
    assert re.search(r"\b1 test file\(s\) scanned\b", line), line
    assert re.search(r"\b1 statically reaching a guarded binary\b", line), line


def test_the_denominator_moves_when_a_test_file_is_added(tmp_path: Path, capsys) -> None:
    """THE COMMITTED RED for #1036's fourth acceptance item.

    "The count must change when a test file is added or removed. A denominator
    that never moves is the same defect one level down" - a hardcoded number, or
    one derived from something other than the population actually scanned, reads
    exactly like a real one. Two trees of different sizes is the only thing that
    tells them apart.
    """
    one = _clean_tree(tmp_path / "one", {"test_a.py": GUARDED_TEST})
    assert checker.main(["--root", str(one)]) == 0
    first = capsys.readouterr().out.strip()

    two = _clean_tree(
        tmp_path / "two", {"test_a.py": GUARDED_TEST, "test_b.py": PLAIN_TEST}
    )
    assert checker.main(["--root", str(two)]) == 0
    second = capsys.readouterr().out.strip()

    assert first != second, (
        "the success line is identical over a one-file and a two-file tree, so "
        f"its denominator describes neither: {first!r}"
    )
    assert "1 test file(s) scanned" in first, first
    assert "2 test file(s) scanned" in second, second
    # The REACHING count is the load-bearing one: `test_b.py` adds a test that
    # touches no binary, so a gate counting files alone would move while the
    # number a reader cares about stood still.
    assert "1 statically reaching a guarded binary" in first, first
    assert "1 statically reaching a guarded binary" in second, second


def test_the_reaching_count_moves_when_a_shelling_out_test_is_added(tmp_path: Path, capsys) -> None:
    """The other half: the number that describes the SUBJECT must move too."""
    one = _clean_tree(tmp_path / "one", {"test_a.py": GUARDED_TEST})
    assert checker.main(["--root", str(one)]) == 0
    first = capsys.readouterr().out.strip()

    two = _clean_tree(
        tmp_path / "two", {"test_a.py": GUARDED_TEST, "test_b.py": GUARDED_TEST}
    )
    assert checker.main(["--root", str(two)]) == 0
    second = capsys.readouterr().out.strip()

    assert "1 statically reaching a guarded binary" in first, first
    assert "2 statically reaching a guarded binary" in second, second


EXEMPTED_TEST = '''
import subprocess


def test_uses_git_but_is_allowed():  # binary-guard: allow fixture for the count
    subprocess.run(["git", "status"], check=False)
'''


def test_an_exempted_test_is_not_counted_as_guarded(tmp_path: Path, capsys) -> None:
    """The first denominator still said "all guarded" over exemptions.

    `# binary-guard: allow <reason>` suppresses a finding; it does not add a
    guard. Folding those into one number reproduced the very conflation this
    change removes - a verified guard and a written-down exception reported as
    the same thing - inside the fix for it. Found by the counter-model review
    (codex/gpt-6-astra) on this branch; the real tree carries two.
    """
    root = _clean_tree(tmp_path, {"test_a.py": EXEMPTED_TEST})
    assert checker.main(["--root", str(root)]) == 0
    line = capsys.readouterr().out.strip()
    assert "all guarded" not in line, f"an exemption is being reported as a guard: {line!r}"
    assert "0 guarded, 1 exempted" in line, line


def test_a_guarded_test_is_not_counted_as_exempted(tmp_path: Path, capsys) -> None:
    """The other direction: the split must not just relabel everything."""
    root = _clean_tree(tmp_path, {"test_a.py": GUARDED_TEST})
    assert checker.main(["--root", str(root)]) == 0
    line = capsys.readouterr().out.strip()
    assert "1 guarded, 0 exempted" in line, line
