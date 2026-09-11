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
    source = widened.SHELL_COMMENT_RE.sub("", text)
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
    assert 'ppid="$(ps -o ppid= -p "$pid" 2>/dev/null' in text  # precondition: :845
    assert "$(ps -eo pid,ppid,args --no-headers 2>/dev/null)" in text  # precondition: :894

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
    source = widened.SHELL_COMMENT_RE.sub("", text)
    uses = [u for u in widened._script_uses(source, source.splitlines()) if u.binary == "cat"]
    assert len(uses) >= 1, "a real bare $(cat) must still be detected"

    bash_prep = ROOT / "scripts" / "bash-prep.sh"
    text = bash_prep.read_text(encoding="utf-8")
    assert 'warn "bash-prep is designed for Linux. Detected: $(uname)"' in text  # precondition
    source = widened.SHELL_COMMENT_RE.sub("", text)
    uses = [u for u in widened._script_uses(source, source.splitlines()) if u.binary == "uname"]
    assert len(uses) >= 1, "a real bare $(uname) must still be detected"
