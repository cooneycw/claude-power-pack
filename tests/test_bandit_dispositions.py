"""The bandit MEDIUM+ residual, kept honest (issue #1113).

#962 adopted bandit at severity >= MEDIUM with an EMPTY skip list, and recorded
the eleven findings it does not fail on as lines in `.bandit-audit-allow`.
#1113 is the bill for that: a written disposition for each. The prose lives in
`docs/security/bandit-finding-dispositions.md`; this module is the part of it
that can fail.

THREE PROPERTIES, and they fail in different directions on purpose:

  THE SHELL SITES ARE ENUMERATED     a SEVENTH `shell=True` call anywhere under
                                     `lib/` fails until someone dispositions
                                     it. The B602 disposition rests entirely on
                                     "these six execute repository-committed
                                     config"; a seventh site executing an HTTP
                                     response would be covered by that sentence
                                     and contradicted by it at once, and
                                     nothing else in the suite would notice.

  THE TRUST BOUNDARY HOLDS           `CICDConfig.load()` reads commands from a
                                     file in the checkout and nowhere else. The
                                     enumeration above says which calls exist;
                                     this says where their strings come from,
                                     which is the half the disposition actually
                                     claims.

  THE REGISTER COVERS THE LEDGER     every line in `.bandit-audit-allow` has a
                                     disposition entry, so a future finding
                                     cannot be suppressed without being
                                     explained. This is the one that keeps
                                     #1113 from being a one-off.

WHY AST AND NOT GREP. A text search for `shell=True` matches the module
docstrings that DISCUSS shell=True - and this file, and the register - so
better documentation would make a grep guard more false-positive, not less. The
`ast` walk sees calls.

ADR 0008 BOUND: these are unit tests whose failure the suite catches, not gates
that let work through, so they need a demonstrated red rather than a committed
control case. Each red was run against the pre-#1113 tree and is recorded on
the pull request.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

from lib.cicd.config import CICDConfig

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
ALLOW_FILE = ROOT / ".bandit-audit-allow"
REGISTER = ROOT / "docs" / "security" / "bandit-finding-dispositions.md"

#: The SIX `shell=True` call sites in `lib/`, each with the number of such
#: calls in that function and the SOURCE of the string it executes.
#:
#: THE COUNT IS PART OF THE KEY, not decoration (counter-model review, #1113).
#: The first cut compared dictionary KEYS, so a SECOND `subprocess.run(...,
#: shell=True)` added inside an already-registered function left the key set
#: unchanged and passed - a tripwire that sees a new function and is blind to a
#: new call, which is most of what "another shell site appeared" looks like in
#: practice.
#:
#: THE SOURCES ARE THE REAL ONES. The first cut said `.claude/cicd.yml` for
#: nearly all of them and it was wrong for four: bootstrap reads
#: `.claude/bootstrap.yaml`, steps and the deploy pair read
#: `.claude/cicd_tasks.yml` or built-in constants, and `.claude/deploy.yaml` -
#: which the first cut named - is read by the `/flow:*` command documents in
#: shell and never by `lib/cicd` at all. A source map that sends a reader to the
#: wrong file is worse than none: it answers the question confidently.
#:
#: This is a TRIPWIRE, not a coverage map. It exists to fail when the set
#: changes, so the annotation is re-read by whoever adds the seventh.
SHELL_TRUE_SITES: dict[tuple[str, str], tuple[int, str]] = {
    ("lib/cicd/bootstrap.py", "check_dependency"): (
        1,
        "BootstrapDependency.check_command - `.claude/bootstrap.yaml` via "
        "BootstrapConfig.load, else built-in constants in bootstrap.py",
    ),
    ("lib/cicd/deploy/docker_compose.py", "_run_shell"): (
        1,
        "DeployConfig.deploy_command / .rollback_command - `.claude/cicd_tasks.yml` "
        "`config:` via DeployConfig.from_dict, else a caller-supplied dict",
    ),
    ("lib/cicd/deploy/guardrails.py", "run"): (
        1,
        "CapabilityCheck.command - ReadinessPolicy.capability_checks[].command, "
        "from `.claude/cicd_tasks.yml` readiness config",
    ),
    ("lib/cicd/smoke.py", "run_single_test"): (
        1,
        "SmokeTest.command - `.claude/cicd.yml` health.smoke_tests[].command",
    ),
    ("lib/cicd/steps.py", "should_skip"): (
        1,
        "StepDef.skip_if - `.claude/cicd_tasks.yml` manifest, else BUILTIN_PLANS "
        "constants in steps.py",
    ),
    ("lib/cicd/steps.py", "execute"): (
        1,
        "StepDef.command - `.claude/cicd_tasks.yml` manifest, else BUILTIN_PLANS "
        "constants in steps.py",
    ),
}

_SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output", "getoutput"}


def _enclosing_function(tree: ast.Module, node: ast.AST) -> str:
    """Name of the innermost function containing `node`, or `<module>`."""
    best: tuple[int, str] = (-1, "<module>")
    for parent in ast.walk(tree):
        if not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if parent.lineno <= node.lineno <= (parent.end_lineno or parent.lineno):
            if parent.lineno > best[0]:
                best = (parent.lineno, parent.name)
    return best[1]


def _subprocess_bindings(tree: ast.Module) -> tuple[set[str], set[str]]:
    """`(module aliases, bare names)` that refer to `subprocess` in this file.

    `bare_names` maps a LOCAL name to a subprocess function we care about, so
    `from subprocess import run as execute` contributes `execute`. The first
    cut stored the local name and then tested it against `_SUBPROCESS_CALLS`,
    which `execute` is not a member of - so an aliased import was silently
    missed (counter-model review, second pass). Resolving the alias to its
    ORIGINAL name at collection time is what makes the membership test mean
    what it reads as.

    Without any of this the extractor matched ANY call whose terminal attribute
    was `run`/`call`/..., so an unrelated `renderer.run(..., shell=True)` was
    reported as an undispositioned subprocess site. A tripwire that cannot tell
    our thing from a neighbour's gets muted the first time it is wrong about
    someone else's code.

    Walks the whole module rather than the top level, so a function-local
    `import subprocess` is seen too.
    """
    module_aliases: set[str] = set()
    bare_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    module_aliases.add(alias.asname or "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name in _SUBPROCESS_CALLS:
                    bare_names.add(alias.asname or alias.name)
    return module_aliases, bare_names


def _shadowed_names(tree: ast.Module, node: ast.AST) -> set[str]:
    """Parameter names of the function lexically containing `node`.

    A parameter shadows a module import inside its function, so
    `def go(subprocess): subprocess.run(x, shell=True)` is a call on whatever
    the CALLER passed, not on the stdlib module - and counting it was a false
    positive (counter-model review, second pass).

    THIS IS PARAMETER SHADOWING ONLY, and deliberately not a scope analyser. A
    local rebinding (`subprocess = something_else`) or a nested-function
    parameter still over-reports. That direction is the safe one for a
    tripwire - it fails loudly and someone dispositions it - whereas the
    aliased-import gap above was an under-report, which is why that one was
    worth resolving properly and this one is bounded and named.
    """
    for parent in ast.walk(tree):
        if not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if parent.lineno <= node.lineno <= (parent.end_lineno or parent.lineno):
            args = parent.args
            names = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
            if args.vararg:
                names.add(args.vararg.arg)
            if args.kwarg:
                names.add(args.kwarg.arg)
            if names:
                return names
    return set()


def _find_shell_true_sites(
    root: Path, rel_to: Path | None = None
) -> dict[tuple[str, str], int]:
    """Count `subprocess.*(..., shell=True)` calls under `root`, by (file, func).

    `rel_to` is the base the reported paths are spelled against, so the real
    call can report `lib/cicd/steps.py` while scanning only `lib/`. It defaults
    to `root`, which is what the control cases below want.

    Returns COUNTS, and the caller compares them: two shell calls in one
    function is a different population from one.
    """
    rel_to = rel_to or root
    found: dict[tuple[str, str], int] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module_aliases, bare_names = _subprocess_bindings(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                owner = func.value
                is_subprocess = (
                    isinstance(owner, ast.Name)
                    and owner.id in module_aliases
                    and func.attr in _SUBPROCESS_CALLS
                    and owner.id not in _shadowed_names(tree, node)
                )
            elif isinstance(func, ast.Name):
                is_subprocess = (
                    func.id in bare_names
                    and func.id not in _shadowed_names(tree, node)
                )
            else:
                is_subprocess = False
            if not is_subprocess:
                continue
            for kw in node.keywords:
                if kw.arg != "shell":
                    continue
                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    key = (
                        path.relative_to(rel_to).as_posix(),
                        _enclosing_function(tree, node),
                    )
                    found[key] = found.get(key, 0) + 1
    return found


class TestShellTrueEnumeration:
    def test_the_extractor_can_see_a_shell_true_call(self, tmp_path: Path) -> None:
        """POSITIVE CONTROL, and it comes first deliberately.

        Every assertion below reads this extractor's output, and an extractor
        that found nothing would make the whole class pass by agreeing that
        `lib/` contains no shell calls. A zero here is only evidence once a
        known-positive returns non-zero.
        """
        (tmp_path / "m.py").write_text(
            "import subprocess\n"
            "def go():\n"
            "    subprocess.run('echo hi', shell=True)\n"
        )
        assert _find_shell_true_sites(tmp_path) == {("m.py", "go"): 1}

    def test_the_extractor_counts_calls_not_functions(self, tmp_path: Path) -> None:
        """Two shell calls in one function is not one shell call.

        The first cut compared key SETS, so this case was invisible: the
        function was already registered, the key set was unchanged, and a
        second `shell=True` rode in silently. That is the ordinary shape of
        "another shell site appeared" - far more common than a whole new
        function - so it was the blind spot that mattered most.
        """
        (tmp_path / "m.py").write_text(
            "import subprocess\n"
            "def go():\n"
            "    subprocess.run('a', shell=True)\n"
            "    subprocess.run('b', shell=True)\n"
        )
        assert _find_shell_true_sites(tmp_path) == {("m.py", "go"): 2}

    def test_the_extractor_does_not_match_prose_about_shell_true(
        self, tmp_path: Path
    ) -> None:
        """NEGATIVE CONTROL: a docstring discussing shell=True is not a call.

        This is the distinction a grep-based guard cannot draw, and the reason
        this module parses instead of searching - `lib/cicd/config.py` now
        carries several paragraphs about `shell=True`, and so does this file.
        """
        (tmp_path / "m.py").write_text(
            '"""We pass shell=True here: subprocess.run(cmd, shell=True)."""\n'
            "import subprocess\n"
            "SHELL_TRUE = 'shell=True'\n"
            "def go():\n"
            "    subprocess.run(['echo', 'hi'], shell=False)\n"
        )
        assert _find_shell_true_sites(tmp_path) == {}

    def test_the_extractor_does_not_match_a_neighbours_run_method(
        self, tmp_path: Path
    ) -> None:
        """NEGATIVE CONTROL: can a finding tell OUR thing from a neighbour's?

        `renderer.run(..., shell=True)` is some other library's API that
        happens to share a method name and a keyword. The first cut matched on
        the terminal attribute alone and reported it as an undispositioned
        subprocess site - a tripwire wrong about somebody else's code, which is
        how tripwires get muted.
        """
        (tmp_path / "m.py").write_text(
            "import renderer\n"
            "def go():\n"
            "    renderer.run('template', shell=True)\n"
        )
        assert _find_shell_true_sites(tmp_path) == {}

    def test_the_extractor_follows_an_aliased_subprocess_import(
        self, tmp_path: Path
    ) -> None:
        """...and the other direction: renaming the import must not hide a site.

        Resolving bindings could have been implemented as "the owner is
        literally named `subprocess`", which would pass every test above and
        let `import subprocess as sp` slip through - a narrower blindness than
        the one it fixed, and harder to notice.
        """
        (tmp_path / "a.py").write_text(
            "import subprocess as sp\n"
            "def go():\n"
            "    sp.Popen('x', shell=True)\n"
        )
        (tmp_path / "b.py").write_text(
            "from subprocess import run\n"
            "def go():\n"
            "    run('y', shell=True)\n"
        )
        assert _find_shell_true_sites(tmp_path) == {
            ("a.py", "go"): 1,
            ("b.py", "go"): 1,
        }

    def test_the_extractor_follows_a_renamed_bare_import(self, tmp_path: Path) -> None:
        """`from subprocess import run as execute` must not hide a site.

        UNDER-report, so the dangerous direction. The first cut stored the
        local name `execute` and then tested it for membership in
        `_SUBPROCESS_CALLS`, which it is not in - so the call vanished
        (counter-model review, second pass).
        """
        (tmp_path / "m.py").write_text(
            "from subprocess import run as execute\n"
            "def go():\n"
            "    execute('x', shell=True)\n"
        )
        assert _find_shell_true_sites(tmp_path) == {("m.py", "go"): 1}

    def test_a_parameter_shadowing_the_module_is_not_our_call(
        self, tmp_path: Path
    ) -> None:
        """OVER-report, the other direction, and also wrong.

        Inside `def go(subprocess)` the name is whatever the caller passed, not
        the stdlib module. Counting it reported a neighbour's API as an
        undispositioned subprocess site.
        """
        (tmp_path / "m.py").write_text(
            "import subprocess\n"
            "def go(subprocess):\n"
            "    subprocess.run('template', shell=True)\n"
        )
        assert _find_shell_true_sites(tmp_path) == {}

    def test_shadowing_resolution_is_parameters_only_and_says_so(
        self, tmp_path: Path
    ) -> None:
        """The BOUND of the previous test, pinned rather than left implied.

        A local rebinding is still counted. That is a deliberate stopping
        point, not an oversight: this is a tripwire over one repository's
        `lib/`, the residual error is an over-report that fails loudly and gets
        dispositioned, and a real scope analyser would be a large amount of
        machinery guarding against a name nobody has used. Recording it here
        means the next reader meets the limit as a decision instead of
        rediscovering it as a bug.
        """
        (tmp_path / "m.py").write_text(
            "import subprocess\n"
            "def go():\n"
            "    subprocess = SomeOtherApi()\n"
            "    subprocess.run('template', shell=True)\n"
        )
        assert _find_shell_true_sites(tmp_path) == {("m.py", "go"): 1}

    def test_the_shell_true_sites_are_exactly_the_dispositioned_ones(self) -> None:
        """A seventh site, or a duplicated call, fails this until dispositioned.

        The B602 disposition is a claim about a POPULATION ("all six execute
        repository-committed config or CPP's own constants"). A population that
        can grow without anybody re-reading the claim is not a disposition, it
        is a sentence that was true once.
        """
        found = _find_shell_true_sites(LIB, ROOT)
        expected = {site: count for site, (count, _source) in SHELL_TRUE_SITES.items()}
        assert found == expected, (
            "the shell=True call sites in lib/ have changed.\n"
            f"  found:    {dict(sorted(found.items()))}\n"
            f"  expected: {dict(sorted(expected.items()))}\n"
            "Add it to SHELL_TRUE_SITES with its COUNT and the SOURCE of the "
            "string it runs, and to docs/security/bandit-finding-dispositions.md. "
            "If that source is not a file in the project checkout or a constant "
            "in CPP's own code, the B602 disposition does not cover it and the "
            "trust model in lib/cicd/config.py must change first."
        )

    def test_every_dispositioned_site_names_its_string_source(self) -> None:
        """An entry with an empty annotation would satisfy the comparison above
        while recording nothing - the failure mode of a registry whose keys are
        checked and whose values are not.

        This cannot check that an annotation is TRUE; four of the six were
        confidently wrong in the first cut and every test still passed. What
        catches that is a reader, which is why the annotations name a file
        someone can go and open.
        """
        for key, (count, source) in SHELL_TRUE_SITES.items():
            assert count >= 1, f"{key} claims {count} calls"
            assert source.strip(), f"{key} carries no source annotation"


class TestCommandTrustBoundary:
    """Where the strings the six sites execute actually come from."""

    def test_a_project_with_no_config_declares_no_smoke_commands(
        self, tmp_path: Path
    ) -> None:
        """Scoped to SMOKE configuration, which is all this module owns.

        The first cut called this "executes no strings" and that was false
        (counter-model review): `get_plan_steps("deploy", root)` returns
        built-in commands including `make deploy` on a project with no config
        at all. The assertions here were true, so the test passed while its
        name made a claim about the whole system that the next reader would
        have taken at face value - the exact overclaim the detector contract
        asks about. The built-ins are covered by their own test below.
        """
        config = CICDConfig.load(str(tmp_path))
        assert config.health.smoke_tests == []
        assert config.health.deploy_verification.enabled is False

    def test_built_in_plan_commands_are_a_known_committed_set(
        self, tmp_path: Path
    ) -> None:
        """The strings a config-less project DOES execute, pinned ENTIRELY.

        These are constants in `lib/cicd/steps.py`, so they are the strongest
        end of the trust model, not an exception to it - but they are not
        nothing, and the disposition is only honest if the whole set is
        enumerated rather than sampled.

        THE FIRST CUT SAMPLED AND CLAIMED A SET (counter-model review, second
        pass). It asserted every command was a non-empty string across
        dynamically discovered plans, then pinned three deploy commands by
        name. An added plan passed; a removed step passed; a changed command in
        `finish` or `check` passed. The name said "known committed set" and the
        body checked "some strings are non-empty" - the detector-contract
        failure of a success claiming more than its input population supports,
        in a test written to enforce exactly that discipline elsewhere.

        Both `command` AND `skip_if` are pinned: `skip_if` is executed through
        `shell=True` by `ShellStep.should_skip`, so leaving it out would pin
        half the population this test exists to bound.
        """
        from lib.cicd.steps import BUILTIN_PLANS, get_plan_steps

        lint = (
            'if grep -q "^lint:" Makefile 2>/dev/null; then make lint; '
            "else uv run --extra dev ruff check .; fi",
            '! grep -q "^lint:" Makefile 2>/dev/null '
            '&& ! grep -q "ruff" pyproject.toml 2>/dev/null',
        )
        test = (
            'if grep -q "^test:" Makefile 2>/dev/null; then make test; '
            "else uv run --extra dev pytest; fi",
            '! grep -q "^test:" Makefile 2>/dev/null '
            '&& ! grep -q "pytest" pyproject.toml 2>/dev/null',
        )
        typecheck = (
            'if grep -q "^typecheck:" Makefile 2>/dev/null; then make typecheck; '
            "else uv run --extra dev mypy .; fi",
            '! grep -q "^typecheck:" Makefile 2>/dev/null '
            '&& ! grep -q "mypy" pyproject.toml 2>/dev/null',
        )
        scan = "! python3 -c 'import lib.security' 2>/dev/null"

        expected = {
            "finish": {
                "lint": lint,
                "test": test,
                "typecheck": typecheck,
                "security_scan": ("python3 -m lib.security gate flow_finish", scan),
            },
            "check": {"lint": lint, "test": test, "typecheck": typecheck},
            "deploy": {
                "bootstrap_check": (
                    "python3 -m lib.cicd.bootstrap check",
                    "! [ -f .claude/bootstrap.yaml ] && ! [ -f pyproject.toml ] "
                    "&& ! [ -f requirements.txt ] && ! [ -f setup.py ]",
                ),
                "stale_commit_check": (
                    "LOCAL=$(git rev-parse HEAD) && git fetch origin main --quiet "
                    "&& REMOTE=$(git rev-parse origin/main) "
                    '&& [ "$LOCAL" = "$REMOTE" ] '
                    '|| { echo "STALE: local=$LOCAL remote=$REMOTE"; exit 1; }',
                    '[ "$(git branch --show-current)" != "main" ] '
                    '|| [ "${CPP_OFFLINE:-0}" = "1" ]',
                ),
                "security_scan": ("python3 -m lib.security gate flow_deploy", scan),
                "deploy": ("make deploy", None),
            },
        }

        actual = {
            plan: {
                step.id: (step.command, step.skip_if)
                for step in get_plan_steps(plan, str(tmp_path))
            }
            for plan in BUILTIN_PLANS
        }
        assert actual == expected, (
            "the built-in command population changed. Every string here is "
            "executed through shell=True on a project that committed no config "
            "at all, so a new or altered one belongs in the B602 disposition "
            "before it belongs here."
        )

    def test_a_manifest_overrides_the_built_ins_from_the_checkout(
        self, tmp_path: Path
    ) -> None:
        """...and the override path is a committed file, not an env var.

        `get_plan_steps` prefers `.claude/cicd_tasks.yml` over the built-ins,
        so that file is a command source the trust model has to name - and the
        first cut's source map did not, attributing step commands to
        `.claude/cicd.yml` instead. This is the test that would have caught
        that attribution being untestable.
        """
        from lib.cicd.steps import get_plan_steps

        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "cicd_tasks.yml").write_text(
            "version: '1'\n"
            "steps:\n"
            "  lint:\n"
            "    command: echo from-the-manifest\n"
            "plans:\n"
            "  check:\n"
            "    steps: [lint]\n"
        )
        commands = [s.command for s in get_plan_steps("check", str(tmp_path))]
        assert commands == ["echo from-the-manifest"]

    def test_a_hostile_environment_cannot_inject_a_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No environment-variable path into a command-bearing field.

        An env var is the trust level the disposition explicitly does NOT
        cover: on a CI runner it is reachable by anything that can set one,
        including - depending on the provider - values derived from a branch or
        tag name. Pydantic settings classes read the environment by default,
        and a future refactor to `BaseSettings` would open exactly this hole
        while every other test kept passing.
        """
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "cicd.yml").write_text(
            "health:\n"
            "  smoke_tests:\n"
            "    - name: committed\n"
            "      command: echo from-the-repo\n"
        )
        for var in (
            "CICD_HEALTH__SMOKE_TESTS",
            "HEALTH__SMOKE_TESTS",
            "SMOKE_TESTS",
            "CICD_SMOKE_TESTS",
        ):
            monkeypatch.setenv(var, '[{"name":"injected","command":"touch /tmp/pwned"}]')

        config = CICDConfig.load(str(tmp_path))
        commands = [t.command for t in config.health.smoke_tests]
        assert commands == ["echo from-the-repo"], (
            f"a command arrived from somewhere other than the checkout: {commands}"
        )

    def test_the_loader_reads_the_project_root_it_was_given(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """...and not the process cwd, which a caller does not control.

        `load()` falls back to `os.getcwd()` only when given no root. Given
        one, a cicd.yml sitting in the cwd must not be read instead - that
        would make the trust boundary depend on where the runner was launched.
        """
        elsewhere = tmp_path / "elsewhere"
        (elsewhere / ".claude").mkdir(parents=True)
        (elsewhere / ".claude" / "cicd.yml").write_text(
            "health:\n"
            "  smoke_tests:\n"
            "    - name: other\n"
            "      command: echo from-the-cwd\n"
        )
        target = tmp_path / "target"
        target.mkdir()
        monkeypatch.chdir(elsewhere)

        assert CICDConfig.load(str(target)).health.smoke_tests == []


@pytest.mark.skipif(
    not ALLOW_FILE.is_file(),
    reason=(
        ".bandit-audit-allow is not present - it arrives with #962. Skipped "
        "rather than passed: an absent ledger is not an empty one."
    ),
)
class TestRegisterCoversTheLedger:
    """Every suppressed finding has a written disposition.

    This is the property that outlives #1113. Without it the register is a
    snapshot of eleven findings someone happened to look at once, and the
    twelfth is suppressed in silence - which is the state #962's allowlist was
    created to end, reproduced one level up.
    """

    @staticmethod
    def _ledger_findings() -> set[tuple[str, str]]:
        entries: set[tuple[str, str]] = set()
        for raw in ALLOW_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "finding":
                entries.add((parts[1], parts[2]))
        return entries

    @staticmethod
    def _register_rows() -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
        """`(accepted, closed)` as (path, rule) pairs read from the TABLE ROWS.

        Rows, not prose. The first cut substring-matched the accepted half for
        the path and the rule anywhere in it, and that fired on this very
        register: the B108 section DISCUSSES the closed `runner.py` finding
        beside the accepted `guardrails.py` one, because the whole point of
        that section is that the two were resolved in opposite directions for
        one reason. A check that cannot tell a row from a sentence about a row
        makes explaining yourself the thing that breaks the build.
        """
        text = REGISTER.read_text(encoding="utf-8")
        accepted_text, marker, closed_text = text.partition("## Closed")
        assert marker, (
            "the register needs a '## Closed' section, so a fixed finding is "
            "moved rather than deleted - deleting it loses the reason it was "
            "closed, and the next person meeting the pattern re-derives it"
        )
        row = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(B\d+)")
        def rows(chunk: str) -> set[tuple[str, str]]:
            return {
                (m.group(1), m.group(2))
                for line in chunk.splitlines()
                if (m := row.match(line))
            }
        return rows(accepted_text), rows(closed_text)

    def test_the_parsers_can_both_see_something(self) -> None:
        """POSITIVE CONTROL for both sides of every comparison below.

        Either parser returning nothing makes the set comparisons vacuously
        true, in the direction that reports success - the shape ADR 0008 calls
        blind, and the one invisible from the passing side. The register's row
        regex is the fragile half: it depends on a markdown table layout that a
        reformat could change without anyone thinking they had touched a test.
        """
        assert self._ledger_findings(), (
            f"{ALLOW_FILE} parsed to zero findings; either the residual is gone "
            f"(then this register should say so) or this parser no longer "
            f"matches the ledger format"
        )
        accepted, closed = self._register_rows()
        assert accepted, (
            f"{REGISTER} parsed to zero accepted rows; the table layout changed "
            f"and the coverage checks below are no longer reading anything"
        )
        assert closed, (
            f"{REGISTER} parsed to zero closed rows; #1113 closed "
            f"lib/cicd/runner.py B108 and that row is the fixture this parser "
            f"is calibrated against"
        )

    def test_every_ledger_finding_has_a_register_entry(self) -> None:
        """Forward: nothing is suppressed without being explained.

        This is the property that outlives #1113. Without it the register is a
        snapshot of eleven findings someone looked at once, and the twelfth is
        suppressed in silence - the state #962's ledger was created to end,
        reproduced one level up.
        """
        accepted, _ = self._register_rows()
        missing = sorted(self._ledger_findings() - accepted)
        assert not missing, (
            f"suppressed with no disposition in {REGISTER.relative_to(ROOT)}: "
            f"{missing}.\n"
            "A line in .bandit-audit-allow says 'we know'; the register is "
            "where it says WHAT we know. Add the row."
        )

    def test_the_register_does_not_outlive_the_ledger(self) -> None:
        """Reverse: an accepted row for a finding nothing suppresses is stale.

        The same rule the ledger applies to itself (`BANDIT-STALE:`), applied
        one level up. A stale row is worse than a missing one: the next reader
        takes it as a current assessment of live code.
        """
        accepted, _ = self._register_rows()
        ledger = self._ledger_findings()
        stale = sorted(accepted - ledger)
        assert not stale, (
            f"these rows accept findings the ledger no longer carries: {stale}. "
            f"If they were fixed, move them to '## Closed' with what changed."
        )

    def test_a_closed_finding_is_not_still_suppressed(self) -> None:
        """A row in both halves at once means the close did not hold.

        Either the fix regressed and the finding is back, or it was moved to
        Closed without being fixed. Both are worse than an honest accept, and
        neither is visible from either check above on its own.
        """
        _, closed = self._register_rows()
        contradictory = sorted(closed & self._ledger_findings())
        assert not contradictory, (
            f"recorded as closed but still in the ledger: {contradictory}"
        )


def test_getuid_scoped_cache_and_shared_lock_are_both_deliberate() -> None:
    """The two B108 sites resolved in OPPOSITE directions, pinned together.

    Read apart, each looks like an inconsistency somebody should tidy up: one
    `/tmp` path was made per-uid and the other was left shared. Read together
    they are one decision - a cache has no cross-process contract, a lock is
    nothing but one - and this test is where that reasoning is anchored so the
    tidy-up attempt fails here instead of in production.
    """
    from lib.cicd.deploy.guardrails import DEPLOY_LOCK_PATH
    from lib.cicd.runner import _default_uv_cache_dir

    assert str(os.getuid()) in _default_uv_cache_dir().name
    assert str(os.getuid()) not in DEPLOY_LOCK_PATH.name
