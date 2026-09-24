"""Step implementations for the deterministic CI/CD runner.

Each step type knows how to execute a specific kind of operation
(shell command, git operation, deploy) with timeout and retry support.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from .coverage import StageCoverage, merge_stream_coverage, parse_stage_coverage
from .manifest_path import MANIFEST_PATH
from .outcomes import SuiteOutcome, merge_stream_outcomes, parse_suite_outcome
from .state import StepStatus

# Root of the CPP checkout (the parent of ``lib/``), derived from this file's
# own location so ``python3 -m lib.security`` / ``-m lib.cicd.bootstrap`` resolve
# regardless of where CPP is checked out - the hardcoded "${HOME}/Projects/
# claude-power-pack" prefix broke under a sandbox or an alternate checkout
# (/opt, ~/.claude-power-pack), the very fallbacks flow:auto searches (#534).
_CPP_ROOT = str(Path(__file__).resolve().parents[2])

# A step whose id or command names a test runner is the only place a test
# summary line is expected, so the #621 skip-count parse is gated on it - a
# linter that prints "3 files passed" must never be reported as a test suite.
# Word-boundaried on both sides so "latest" / "contested" do not match.
#
# The scan covers the WHOLE command, PATHS INCLUDED: a step whose command names
# ".../my-test-project/.venv/bin/python3" classifies as a test step no matter
# what its id says. That is the accepted cost of recognizing a `make test`
# recipe hiding under an unhelpful step id (#621), and narrowing the pattern to
# dodge paths would weaken the detection it exists for. The consequence for
# TESTS is a hard rule: a fixture must never interpolate an absolute path
# (`sys.executable`, anything under pytest's `tmp_path`) into a step it wants
# classified as a NON-test step, or the classification follows the checkout
# location instead of the fixture's intent - which turned every flow worktree
# whose branch slug contained "test" red (issue #704). Pinned by
# tests/test_cicd_outcomes.py::TestStepGating.
_TEST_STEP_HINT = re.compile(
    r"(?:^|[^a-z])(?:tests?|pytest|jest|vitest|unittest|nose)(?:[^a-z]|$)",
    re.IGNORECASE,
)


class StepExecutor(Protocol):
    """Protocol for step execution implementations."""

    id: str
    timeout_seconds: int
    max_attempts: int
    idempotent: bool

    def execute(self, context: dict[str, Any]) -> StepResult: ...


@dataclass
class StepResult:
    """Result of executing a single step."""

    status: StepStatus
    exit_code: int = 0
    output: str = ""
    error: str = ""
    # Counts parsed from a test runner's summary line, when this step ran one
    # (issue #621). Advisory only - it never changes ``status``, which stays
    # exit-code driven; it exists so a SUCCESS whose suite executed nothing can
    # be reported as such instead of as a bare green.
    tests: Optional[SuiteOutcome] = None
    # What a NON-test stage said about how much it examined (issue #1027).
    # Same contract as ``tests`` above and for the same reason one layer over:
    # ``lint``/``typecheck``/``security_scan`` exit 0 whether they inspected
    # five hundred files or none, so without this a no-op stage and a clean
    # stage are indistinguishable in the step result. Advisory - it never
    # changes ``status``.
    coverage: Optional[StageCoverage] = None

    @property
    def success(self) -> bool:
        return self.status == StepStatus.SUCCESS


#: The exit code a killed-by-timeout step reports. Named rather than repeated
#: as a bare 124, so the producer here and the consumers in runner.py and
#: flow-finish-gate.sh agree by reference instead of by coincidence.
TIMEOUT_EXIT_CODE = 124

@dataclass
class StepDef:
    """Definition of a step from the task manifest or built-in plan.

    This is the configuration - StepExecutor handles execution.
    """

    id: str
    command: str
    description: str = ""
    timeout_seconds: int = 600
    max_attempts: int = 1
    backoff_seconds: float = 2.0
    idempotent: bool = True
    skip_if: Optional[str] = None  # shell expression; step skipped if exits 0
    depends_on: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    # Does skipping this step mean the run verified nothing about some dimension
    # of the change? That question - not "is this one of the three #617 quality
    # gates" - is what the #628 warn reporting needs, so it is declared HERE on
    # the step rather than in a list kept somewhere else (issue #890). See
    # GATE_STEP_IDS, which is derived from these declarations.
    gate: bool = False
    # A RECORDED DECISION that this step's test runner is one CPP does not
    # parse, naming it (e.g. "go test") - issue #977. It is the only thing that
    # may quiet the "no test summary could be parsed" UNKNOWN warning for this
    # step, because it turns an unmeasured fact into a stated, reviewable one.
    # It never makes the result clean: the outcome is still not measured, and
    # the runner still logs that. None means nothing was declared.
    unsupported_runner: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "command": self.command,
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": self.max_attempts,
            "idempotent": self.idempotent,
        }
        if self.env:
            d["env"] = self.env
        return d


class ShellStep:
    """Execute a shell command with timeout and retry support.

    This is the primary step type - most CI/CD operations are shell commands
    (make lint, make test, git push, etc.)
    """

    def __init__(self, step_def: StepDef, covers_test_step: bool = False):
        # An AGGREGATE that subsumes a test step must still be parsed for a
        # test summary (issue #1152, counter-model review post-merge).
        # `is_test_step()` reads the id and command, and `make verify` names
        # neither pytest nor test - so deferring `test` to it removed the #621
        # empty-suite qualification entirely. MEASURED on the merged code: a
        # target printing "0 passed, 66 skipped" inside a green `make verify`
        # produced `tests: {}` and `warnings: []`, and the gate said ok. That
        # is the #621 false green, restored by the fix for a COST issue - the
        # one thing #1152 was not allowed to do.
        self._covers_test_step = covers_test_step
        self.id = step_def.id
        self.command = step_def.command
        self.timeout_seconds = step_def.timeout_seconds
        self.max_attempts = step_def.max_attempts
        self.backoff_seconds = step_def.backoff_seconds
        self.idempotent = step_def.idempotent
        self.skip_if = step_def.skip_if
        self.description = step_def.description
        self.env = step_def.env

    def _resolve_env(self, context: dict[str, Any]) -> Optional[dict[str, str]]:
        """Merge the sanitized runner env with this step's env overrides.

        Both ``skip_if`` and the command run in the same environment so a
        ``skip_if`` probe (e.g. ``import lib.security``) and the command it
        guards see the same PYTHONPATH / CPP_OFFLINE the runner set (#534).
        """
        env = context.get("env")
        test_workers = self.resolve_pytest_workers(context)
        inherited_env = env if env is not None else os.environ
        has_pytest_workers = self.is_test_step() and (
            "PYTEST_WORKERS" in self.env or "PYTEST_WORKERS" in inherited_env
        )
        if self.env or test_workers is not None or has_pytest_workers:
            env = dict(env) if env is not None else dict(os.environ)
            env.update(self.env)
            if self.is_test_step():
                # An empty step override falls through during resolution and
                # must not erase the lower-precedence non-empty value here.
                env.pop("PYTEST_WORKERS", None)
                if test_workers is not None:
                    env["PYTEST_WORKERS"] = test_workers[0]
        return env

    def resolve_pytest_workers(
        self, context: dict[str, Any]
    ) -> Optional[tuple[str, str]]:
        """Return the effective pytest worker cap and its source for test steps.

        Empty values are treated as unset. Values pass through verbatim because
        choosing and validating the worker policy belongs to the host/project.
        """
        if not self.is_test_step():
            return None

        step_value = self.env.get("PYTEST_WORKERS")
        if step_value:
            return step_value, "step-env"

        host_env = context.get("env")
        if host_env is None:
            host_env = os.environ
        host_value = host_env.get("PYTEST_WORKERS")
        if host_value:
            return host_value, "host-env"

        cap_value = host_env.get("CPP_TEST_WORKERS")
        if cap_value:
            return cap_value, "CPP_TEST_WORKERS"
        return None

    def is_test_step(self) -> bool:
        """True when this step's id or command names a test runner (issue #621)."""
        return bool(
            _TEST_STEP_HINT.search(self.id) or _TEST_STEP_HINT.search(self.command)
        )

    def _parse_tests(self, output: str, error: str) -> Optional[SuiteOutcome]:
        """Parse a test summary from BOTH captured streams, if it is a test step.

        Both streams are scanned and their summaries MERGED. pytest prints its
        tail to stdout, but a ``make`` recipe (or a wrapper that redirects) can
        land it on stderr, and a target running two suites can produce one of
        each.

        This read ``parse(output) or parse(error)`` until issue #939. ``or``
        scans the second stream only when the first returns ``None``, and
        ``SuiteOutcome`` is a frozen dataclass with no ``__bool__`` - so even
        the all-zeros "no tests ran" outcome is truthy and short-circuits the
        stderr scan. "Both streams are scanned" was what this docstring said;
        "the first stream that says anything wins" was what the code did. The
        consequence was not cosmetic: a passing stdout summary drove
        ``failed + errors > 0`` to False and failures reported on stderr were
        never retried, then read as ``nothing_ran`` on the re-run.

        The result records which streams it was derived from, so a caller
        reports what its verdict came FROM rather than a bare one (issue #952).
        """
        if not (self.is_test_step() or self._covers_test_step):
            return None
        return merge_stream_outcomes(
            [
                parse_suite_outcome(output, "stdout"),
                parse_suite_outcome(error, "stderr"),
            ]
        )

    def _parse_coverage(self, output: str, error: str) -> Optional[StageCoverage]:
        """Parse a coverage statement from BOTH streams, for a NON-test step.

        Scoped to non-test steps because ``tests`` already answers this
        question for a test step, and answering it twice in two shapes would
        leave a reader unsure which one the gate consults.

        Both streams matter here more than anywhere: ruff prints
        ``All checks passed!`` to stdout and its "no Python files" warning -
        the only evidence the stage no-opped - to stderr, so a stdout-only
        parse would see the cheerful half and miss the whole signal.
        """
        if self.is_test_step():
            return None
        merged = merge_stream_coverage(
            [
                parse_stage_coverage(output, "stdout"),
                parse_stage_coverage(error, "stderr"),
            ]
        )
        if merged is not None:
            return merged
        # An EXPLICIT unknown, not None (issue #1027, cross-model review).
        # Returning None here meant an unrecognized stage carried no coverage
        # key at all - so `lint` printing only "All checks passed!" kept exactly
        # the bare `{id, status}` record this change exists to replace, while
        # the module docstring promised that unmeasurable stages report
        # `unknown`. The promise and the behaviour disagreed, and the behaviour
        # was the older one.
        #
        # `unknown` is still never graded on: it is recorded so a reader can see
        # the stage is unproven, and the gate's verdict logic collects only
        # `zero`.
        return StageCoverage(streams=("stdout", "stderr"))

    def should_skip(self, context: dict[str, Any]) -> bool:
        """Check if this step should be skipped."""
        if not self.skip_if:
            return False
        try:
            result = subprocess.run(
                self.skip_if,
                shell=True,
                capture_output=True,
                timeout=10,
                cwd=context.get("project_root"),
                env=self._resolve_env(context),
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def execute(self, context: dict[str, Any]) -> StepResult:
        """Execute the shell command, streaming output live while capturing it.

        Output is teed line-by-line to ``context['output_stream']`` (when
        present) as the child produces it, so a slow-but-progressing command
        (e.g. a large ``pytest`` suite) shows live progress instead of going
        silent until it exits - a slow run is then distinguishable from a real
        hang. Both stdout and stderr are still captured in the StepResult, and
        partial output is preserved on a timeout so the wall-clock kill shows
        *where* the command was rather than discarding everything (issue #537).
        """
        cwd = context.get("project_root")
        env = self._resolve_env(context)
        stream = context.get("output_stream")

        try:
            proc = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # line-buffered so tee'd progress appears promptly
                cwd=cwd,
                env=env,
                start_new_session=True,  # own process group -> whole tree killable on timeout
            )
        except OSError as e:
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=1,
                error=str(e),
            )

        out_chunks: list[str] = []
        err_chunks: list[str] = []
        tee_lock = threading.Lock()

        def _pump(pipe: Any, sink: list[str]) -> None:
            try:
                for line in pipe:
                    sink.append(line)
                    if stream is not None:
                        with tee_lock:
                            stream.write(line)
                            stream.flush()
            finally:
                pipe.close()

        readers = [
            threading.Thread(target=_pump, args=(proc.stdout, out_chunks), daemon=True),
            threading.Thread(target=_pump, args=(proc.stderr, err_chunks), daemon=True),
        ]
        for reader in readers:
            reader.start()

        timed_out = False
        try:
            proc.wait(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._kill_process_tree(proc)

        # Let the reader threads drain buffered output before assembling the
        # result; capped so a child that leaked a pipe to a survivor can't hang.
        for reader in readers:
            reader.join(timeout=5)

        output = "".join(out_chunks)
        error = "".join(err_chunks)
        tests = self._parse_tests(output, error)
        coverage = self._parse_coverage(output, error)

        if timed_out:
            timeout_msg = f"Step timed out after {self.timeout_seconds}s"
            return StepResult(
                status=StepStatus.FAILED,
                exit_code=TIMEOUT_EXIT_CODE,
                output=output,
                error=f"{error}\n{timeout_msg}".strip() if error else timeout_msg,
                tests=tests,
                coverage=coverage,
            )

        if proc.returncode == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                exit_code=0,
                output=output,
                # Carried on the SUCCESS path too (issue #939). It was dropped
                # here while the failure path kept it, so anything a passing
                # step wrote to stderr was discarded before any caller could
                # look at it - including #939's own UNKNOWN guard, which asks
                # whether the step produced output at all and could therefore
                # see only half the answer. The parse itself was never
                # affected: `_parse_tests` runs on the local streams above.
                error=error,
                tests=tests,
                coverage=coverage,
            )
        return StepResult(
            status=StepStatus.FAILED,
            exit_code=proc.returncode if proc.returncode is not None else 1,
            output=output,
            error=error,
            tests=tests,
            coverage=coverage,
        )

    @staticmethod
    def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
        """Kill a timed-out child and its process group.

        The step runs ``shell=True`` and often spawns children (``make`` ->
        ``pytest``). Killing only the shell leaves those children holding the
        output pipes open, so the reader threads never reach EOF. Signalling the
        whole process group tears the tree down and lets the readers drain.
        """
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    def execute_with_retry(self, context: dict[str, Any]) -> StepResult:
        """Execute with retry policy (exponential backoff)."""
        last_result = StepResult(status=StepStatus.FAILED)
        delay = self.backoff_seconds

        for attempt in range(1, self.max_attempts + 1):
            result = self.execute(context)

            if result.success:
                return result

            last_result = result

            # Don't retry non-idempotent steps
            if not self.idempotent:
                return result

            # Don't sleep after the last attempt
            if attempt < self.max_attempts:
                time.sleep(delay)
                delay = min(delay * 2, 30.0)  # cap backoff at 30s

        return last_result


# GATE_STEP_IDS is DERIVED from the plans, below BUILTIN_PLANS - see the comment
# there. It used to be a hand-written literal here and drifted (issue #890).


#: Default budget for the whole `test` STEP - not for one pytest invocation.
#: A step runs a command, and that command may run pytest several times: kyle's
#: `make test` deliberately runs two (non-Playwright, then Playwright) to avoid
#: an event-loop leak between pytest-asyncio and pytest-playwright. A budget
#: sized by watching one invocation is therefore wrong by construction, which is
#: how 600s came to be under the real cost (issue #812): the first invocation
#: alone took 457s and the second needed ~160s more, so the step was killed at
#: 91% of the second and reported FAILED on a suite that would have passed.
#:
#: This number WILL be wrong again. A suite grows every merge and no constant
#: tracks that, which is why the substantive half of #812's fix is that a
#: timeout is now REPORTED as a timeout rather than flattened into a test
#: failure - a reader can tell "ran out of budget" from "the tree is broken",
#: and the message says how to raise it.
DEFAULT_TEST_STEP_TIMEOUT = 1800


def _test_step_timeout() -> int:
    """Budget for the test step, overridable without a code change (#812).

    Read at plan-construction time so an operator whose suite has outgrown the
    default can raise it for one run - the alternative is editing this file,
    which nobody does mid-incident and which does not survive an update.
    """
    raw = os.environ.get("CPP_GATE_TEST_TIMEOUT", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return DEFAULT_TEST_STEP_TIMEOUT


def gate_conditional_command(step_id: str, fallback: str) -> str:
    """THE one spelling of the generated gate command, for every producer.

    Two places emitted this string independently - `BUILTIN_PLANS` here and
    `generate_manifest` in manifest.py - and a third place, the subsumption
    allowlist, tried to RECOGNISE it with a regex over shell text. That regex
    is where two counter-model findings landed: `\\s` spans newlines, so
    `make\\nlint` satisfied the direct form, and the conditional form matched a
    PREFIX, so `... else true\\nfi\\nexit 1\\n#; fi` was recognised while
    exiting 1. Both suppressed a step whose failure the aggregate cannot
    reproduce.

    So there is one producer and recognition is EQUALITY against it
    (`command_runs_make_target`). A generated command is recognised by identity
    with its own source; anything else is not recognised, and the gate runs
    twice. This function is why that is a fact about the code rather than about
    a pattern's cleverness.

    It lives HERE, not in manifest.py, on purpose: manifest.py imports pydantic
    and `lib.cicd.steps` must stay importable without it (#1163), so the
    dependency runs generator -> steps and never the other way.
    """
    return (
        f'if grep -q "^{step_id}:" Makefile 2>/dev/null; then make {step_id}; '
        f"else {fallback}; fi"
    )


def _generated_fallback(command: str, target: str) -> Optional[str]:
    """The fallback slot of ``command``, if it is the generated shape at all.

    Taken by removing the builder's OWN literal prefix and suffix - not by
    matching a pattern - so the only freedom left is the fallback text, and
    `command_runs_make_target` then rebuilds and compares bytes. Trailing shell
    cannot survive: the suffix must end the string.
    """
    sentinel = "\x00FALLBACK\x00"
    template = gate_conditional_command(target, sentinel)
    prefix, _, suffix = template.partition(sentinel)
    if not command.startswith(prefix) or not command.endswith(suffix):
        return None
    return command[len(prefix): len(command) - len(suffix)]


def _gate_step(
    step_id: str, uv_tool: str, pyproject_token: str, timeout_seconds: int
) -> "StepDef":
    """Build a quality-gate step that prefers ``make <id>`` but falls back to the
    pyproject-configured tool via ``uv run --extra dev`` when no Makefile target
    exists (issue #628).

    Before this, a Makefile-less repo skipped every gate on the ``make`` guard
    alone even though ``pyproject.toml`` fully configured ruff/mypy/pytest, and
    the runner still reported a bare SUCCESS (hit on flow:auto #2 in
    oneninety-budget). The step now SKIPS only when NEITHER a Makefile target NOR
    the tool is configured - and a genuinely-skipped gate is surfaced as a
    warning by the runner (never a silent ok). CPP itself is unaffected: it has a
    Makefile with all three targets, so the ``make`` branch always wins.
    """
    return StepDef(
        id=step_id,
        gate=True,
        command=gate_conditional_command(step_id, f"uv run --extra dev {uv_tool}"),
        description=f"Run {step_id} (make {step_id}, else uv run {uv_tool.split()[0]})",
        timeout_seconds=timeout_seconds,
        max_attempts=1,
        skip_if=(
            f'! grep -q "^{step_id}:" Makefile 2>/dev/null '
            f'&& ! grep -q "{pyproject_token}" pyproject.toml 2>/dev/null'
        ),
    )


# Built-in plan definitions for flow commands
# These define the steps that each flow command executes
#
# The `finish` plan's contract is that a green gate means a green CI, so its
# gate steps must cover everything the shipped CI templates run. All four
# templates (templates/workflows/ci-python.yml, ci-node.yml,
# woodpecker-python.yml, woodpecker-node.yml) run exactly lint + test +
# typecheck, and PipelineConfig.branches["pr"] defaults to the same three - so a
# plan without `typecheck` went green on trees CI then rejected (issue #617,
# observed twice in agentic-poker). Any step added to those templates belongs
# here too; tests/test_runner.py::TestPlansCoverCITemplates pins the invariant.
# Each gate prefers its Makefile target but falls back to `uv run --extra dev`
# when pyproject configures the tool and no target exists (issue #628).
# Test gates get their PYTEST_WORKERS cap through ShellStep, with step env then
# host PYTEST_WORKERS then host CPP_TEST_WORKERS precedence (issue #640).

BUILTIN_PLANS: dict[str, list[StepDef]] = {
    "finish": [
        _gate_step("lint", "ruff check .", "ruff", 300),
        _gate_step("test", "pytest", "pytest", _test_step_timeout()),
        _gate_step("typecheck", "mypy .", "mypy", 300),
        StepDef(
            id="security_scan",
            gate=True,
            command="python3 -m lib.security gate flow_finish",
            description="Run security quick scan",
            timeout_seconds=120,
            max_attempts=1,
            skip_if="! python3 -c 'import lib.security' 2>/dev/null",
            env={"PYTHONPATH": _CPP_ROOT},
        ),
        # `make verify`, THE GATE THIS HELPER WAS ALREADY SPEAKING FOR (#1147).
        #
        # `/flow:auto` clears a PR on this plan's verdict, and CLAUDE.md's own
        # directive is "after any fix, verify through the full pipeline with
        # `make verify`" - but the plan ran three of verify's prerequisites and
        # nothing else, so the gate consumed verify's authority without running
        # it. Measured on af348f8: 25 verify gates, 3 run, 22 never. #1145 is
        # the instance - `claude-md-behavior-check` exited 2 on that tree while
        # this gate reported `ok` and cleared PR #1144.
        #
        # A TEST OF AN INSTRUMENT IS NOT A RUN OF IT. That checker's own tests
        # passed in the same suite, because the checker works; its verdict on
        # the real tree was never asked for.
        #
        # No `uv run` fallback, unlike the three above: `verify` is a Makefile
        # aggregate with no tool equivalent, so a repo without the target has
        # nothing to degrade to. It SKIPS there, and the skip is reported by
        # name - "this repo has no verify target" and "verify passed" must not
        # render the same.
        #
        # KNOWN COST, measured and not hidden: verify's own prerequisites
        # include lint, test and typecheck (Makefile:385), and these are
        # separate `make` invocations, so those three run twice per gate. The
        # subsumption - running verify INSTEAD of the three where it exists - is
        # a change to the existing ids and is tracked separately.
        StepDef(
            id="verify",
            gate=True,
            command="make verify",
            description="Run the repository's full verification pipeline (make verify)",
            timeout_seconds=1800,
            max_attempts=1,
            skip_if='! grep -q "^verify:" Makefile 2>/dev/null',
        ),
    ],
    "check": [
        _gate_step("lint", "ruff check .", "ruff", 300),
        _gate_step("test", "pytest", "pytest", _test_step_timeout()),
        _gate_step("typecheck", "mypy .", "mypy", 300),
    ],
    "deploy": [
        # Keep these Python markers aligned with built_in_advisories() in
        # bootstrap.py so applicable advisories are not skipped by the plan.
        StepDef(
            id="bootstrap_check",
            command="python3 -m lib.cicd.bootstrap check",
            description="Check bootstrap dependencies and built-in advisories",
            timeout_seconds=30,
            max_attempts=1,
            skip_if=(
                "! [ -f .claude/bootstrap.yaml ] && "
                "! [ -f pyproject.toml ] && "
                "! [ -f requirements.txt ] && "
                "! [ -f setup.py ]"
            ),
            env={"PYTHONPATH": _CPP_ROOT},
        ),
        StepDef(
            id="stale_commit_check",
            command=(
                'LOCAL=$(git rev-parse HEAD) && '
                'git fetch origin main --quiet && '
                'REMOTE=$(git rev-parse origin/main) && '
                '[ "$LOCAL" = "$REMOTE" ] || '
                '{ echo "STALE: local=$LOCAL remote=$REMOTE"; exit 1; }'
            ),
            description="Verify HEAD matches origin/main (stale commit guard)",
            timeout_seconds=30,
            max_attempts=1,
            # Skip off main, or when offline: the git fetch cannot reach the
            # remote in a sandbox, so skip-with-a-message beats a hard fail (#534).
            skip_if='[ "$(git branch --show-current)" != "main" ] || [ "${CPP_OFFLINE:-0}" = "1" ]',
        ),
        StepDef(
            # RENAMED from `security_scan` (issue #1155). BUILTIN_PLANS is keyed
            # per plan, so it could reuse one id for two different commands -
            # `flow_finish` in finish, `flow_deploy` here. A manifest cannot:
            # its `steps:` namespace is FLAT, one id to one command. So
            # `.claude/cicd_tasks.yml` had to call this one something else, and
            # the divergence was FORCED by the schema rather than chosen.
            #
            # Since gate-ness now inherits by id and reconciliation keys on id,
            # the two namespaces have to agree - and the manifest is the side
            # that cannot move. Renaming the other way was considered and
            # REFUSED: `security_scan` already exists in the manifest as the
            # FINISH scan, so pointing deploy at it would silently swap
            # `flow_deploy` (blocks CRITICAL and HIGH) for `flow_finish`
            # (blocks CRITICAL only) and stop HIGH findings blocking a deploy.
            # tests/test_runner.py pins the command, which is the input that
            # would have caught that.
            id="deploy_security_scan",
            gate=True,
            command="python3 -m lib.security gate flow_deploy",
            description="Run security scan before deploy",
            timeout_seconds=120,
            max_attempts=1,
            skip_if="! python3 -c 'import lib.security' 2>/dev/null",
            env={"PYTHONPATH": _CPP_ROOT},
        ),
        StepDef(
            id="deploy",
            command="make deploy",
            description="Run deployment",
            timeout_seconds=1800,
            max_attempts=1,
            idempotent=False,
        ),
    ],
}


# A quality gate is a step whose SKIP means the run verified nothing about some
# dimension of the change. A plan that reports success while one was SKIPPED is
# the #628 false green, so the runner names skipped gates and
# flow-finish-gate.sh reports `warn` rather than flattening the run to `ok`.
#
# DERIVED from the step declarations above, never hand-written (issue #890).
# The literal it replaces said {"lint", "test", "typecheck"} and omitted
# `security_scan` for three releases. That omission was not a typo - it was a
# CATEGORICAL reading of the word "gate" (the three #617 quality gates) rather
# than an answer to the question the set is actually consulted for. The two
# readings agree for lint/test/typecheck and disagree for security_scan, whose
# skip_if is `! python3 -c 'import lib.security'`: it skips exactly when the
# scanner is not installed, which is precisely when a warn is warranted. A
# containerised session has no CPP checkout, so it could run its gate, skip the
# security scan and report a bare `ok`.
#
# Deriving it is what makes a repeat impossible rather than merely corrected:
# there is no second place to update, so a gate cannot be declared and left out
# of the set. What deriving CANNOT catch is a new step that never declares
# `gate=` at all and silently takes the default - so that is pinned separately,
# by an exhaustive classification test over the verification plans
# (tests/test_runner.py::TestGateDeclarationIsExhaustive), which fails on a step
# in neither bucket AND on an exemption for a step that no longer exists.
# Gate ids whose recipe is an AGGREGATE over other gates (issue #1152). Named
# rather than derived because "is this target an aggregate" is not a property of
# the Makefile - every target with prerequisites has some - it is a statement
# about which of OUR gates is meant to stand in for the others. `verify` is the
# one CLAUDE.md names as the full pipeline.
_AGGREGATE_GATE_IDS: frozenset[str] = frozenset({"verify"})

GATE_STEP_IDS: frozenset[str] = frozenset(
    step.id for steps in BUILTIN_PLANS.values() for step in steps if step.gate
)


def plan_gate_ids(plan_name: str, step_defs: list[StepDef]) -> list[str]:
    """Which ids in THIS plan's RESOLVED steps are quality gates.

    `GATE_STEP_IDS` is the union across every plan, and that is the right set
    for "is this id a gate anywhere". It is the WRONG set to publish to a
    consumer that requires every member to be accounted for: a successful
    `--plan check` runs lint/test/typecheck and has no security_scan or verify
    in it, and `--plan deploy` shares none of the five. Handing the global set
    to such a reader turns both into failures (#1147, counter-model review).

    Since #1155 this is simply the resolved steps' own `gate` flags. It used to
    read `s.gate or s.id in declared`, consulting the built-in declaration a
    SECOND time, because a manifest-resolved StepDef always had `gate=False` -
    `step_model_to_step_def` never passed the field. That conversion now
    inherits gate-ness by id, so the flag on the step is the answer and this is
    the only consumer of it.

    Whether the resolved plan is MISSING a gate the built-in plan declares is a
    different question, answered by `dropped_gate_ids` below.
    """
    return sorted({s.id for s in step_defs if s.gate})


#: One `make -p -n` per (root, target) per process. The read is cheap - 0.00s
#: and 56KB on this repository - but it PARSES the target makefile, and a
#: makefile's `$(shell ...)` runs at parse time (measured: one execution under
#: `-p -n`). Doing it once per gate run rather than once per question keeps
#: that at the minimum the answer requires.
_MAKE_PREREQ_CACHE: dict[tuple[Any, ...], Optional[str]] = {}

#: A makefile that reads `MAKEFLAGS` can resolve differently under the query
#: than under the run, because `-p -n` ARE make flags (counter-model review,
#: round 2). Measured: `verify: lint` guarded by
#: `ifneq (,$(findstring n,$(MAKEFLAGS)))` is reported by the query and is NOT
#: run by `make verify`, which is this issue's false green with the conditional
#: keyed on the query itself. Naming the goal fixed `MAKECMDGOALS`; nothing can
#: fix `MAKEFLAGS` while the query needs flags. So a makefile that mentions it
#: is refused outright rather than answered wrongly.
_MAKEFLAGS_SENSITIVE = re.compile(r"\bMAKEFLAGS\b")

#: Make's OWN variables, removed from the query's environment.
#:
#: A parent make exports these to everything it runs, so a derivation invoked
#: from inside a make recipe - `make verify` running the test suite is exactly
#: that - inherits the outer make's flags. Measured: with `MAKEFLAGS=w` and
#: `MAKELEVEL=1` in the environment, the query's make announces `Entering
#: directory`, the recursion guard fires, and subsumption silently turns OFF
#: for a makefile that is perfectly inside the grammar. It fails SAFE (every
#: gate runs), but it is still wrong, and it would have removed the whole
#: saving in the nested case without saying so.
#:
#: The query is a question about a MAKEFILE, not about whichever make happens
#: to be running us, so it is asked in a controlled environment. This is the
#: same lesson as the MAKEFLAGS grammar refusal one layer down: flags that
#: reach the query change its answer.
_MAKE_OWN_ENV = frozenset(
    {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKE_TERMOUT", "MAKE_TERMERR", "MAKECMDGOALS"}
)


def _query_env(env: Optional[dict[str, str]]) -> dict[str, str]:
    """``env`` with the outer make's own variables removed."""
    base = dict(os.environ if env is None else env)
    for name in _MAKE_OWN_ENV:
        base.pop(name, None)
    return base


def reset_make_prerequisite_cache() -> None:
    """Drop every memoised `make -p -n` answer; call once per RUN.

    The cache spans a PROCESS, and the makefile it answers about is a file on
    disk that a resumed run, a long-lived server, or the step before this one
    can have changed (counter-model review). A stale entry does not fail - it
    suppresses gates according to a makefile that is no longer there, which is
    this issue's own defect with a different reader. The runner clears it at
    the top of every run; within a run the makefile is fixed and the memo is
    what keeps `make -p -n` to one execution per aggregate.
    """
    _MAKE_PREREQ_CACHE.clear()


def _make_database(
    project_root: str, target: str, env: Optional[dict[str, str]] = None
) -> Optional[str]:
    """The `make -p -n <target>` dump, or None when make cannot be asked.

    CACHED AS THE DUMP rather than as the parsed answer, so the two questions
    asked of it - what are `target`'s prerequisites, and is a given name a rule
    in its own right - cost ONE make invocation between them and are answered
    from the same database. Two invocations could disagree with each other.

    ASKS MAKE RATHER THAN READING THE MAKEFILE, and that is the whole of issue
    #1165. A textual reader cannot evaluate `ifeq`, `ifdef`, `include` or
    variable expansion, so it reports prerequisites make will never run.
    Measured on a fixture whose `verify: lint` sits inside `ifeq (1,0)`:

        textual reader -> ['lint', 'test', 'typecheck']
        make -p -n     -> verify: test typecheck
        make -n verify -> runs test, typecheck; lint never runs

    Subsumption built on the first marks `lint` covered, and a BROKEN LINT then
    passes as a `subsumed` gate - a false green produced by a cost fix.

    A better textual parser is the same defect one conditional at a time, and a
    textual reader consulted ALONGSIDE make is that defect with a quorum: every
    case where the two differ is a case where the text is wrong, and wrong in
    the unsafe direction. So the text is not consulted here at all.

    `-p` rather than `-n`: `-n` prints RECIPES, and mapping recipe lines back to
    target names is a second inference. `-p` prints the rule database with
    conditionals already resolved, so the rule is read rather than
    reconstructed. EXPLICIT rules only - an implicit or pattern-derived match is
    not a statement that these prerequisites run for this target.

    THE COST, STATED: `make -p -n` parses the target makefile, and `$(shell ...)`
    executes AT PARSE TIME - confirmed, one execution under these flags. That
    cost has a bound worth knowing: the gate is about to run `make verify` in
    this same tree, which parses the same makefile and runs the same `$(shell)`.
    This front-runs one parse; it introduces no side effect the run was not
    already going to have.

    None means MAKE DID NOT ANSWER - absent, a makefile that will not parse, or
    no explicit rule for the target - and every caller treats that as "nothing
    is subsumed". The failure mode is duplicated work, never a skipped check.
    """
    # THE ENVIRONMENT IS PART OF THE QUESTION, so it is part of the key
    # (counter-model review, round 2). A step may carry `env` overrides, and a
    # makefile conditional can read them - so "what does `verify` run" has a
    # different answer per environment, and a memo keyed on the path alone
    # would serve one environment's answer to another.
    key = (str(project_root), target, tuple(sorted((env or {}).items())))
    if key in _MAKE_PREREQ_CACHE:
        return _MAKE_PREREQ_CACHE[key]

    result: Optional[str] = None
    makefile = Path(project_root) / "Makefile"
    # THE GRAMMAR IS CHECKED FIRST, so a makefile outside it is never QUERIED -
    # `$(MAKE)` recursion and MAKEFLAGS conditionals do not execute (#1165, B).
    if makefile.is_file() and makefile_grammar_refusal(project_root) is None:
        try:
            # THE TARGET IS NAMED (counter-model review). Without it make
            # evaluates its DEFAULT goal with an empty `MAKECMDGOALS`, so a
            # rule guarded by `ifneq ($(MAKECMDGOALS),verify)` resolves the
            # other way: measured, the query returned ['test', 'lint'] for a
            # tree where `make verify` runs only test. Asking about the wrong
            # goal is the same defect as reading the wrong text.
            proc = subprocess.run(
                ["make", "-p", "-n", target],
                env=_query_env(env),
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            proc = None
        # A FAILED QUERY IS NOT AN ANSWER (counter-model review). GNU make
        # emits a PARTIAL database even when it exits non-zero: measured, a
        # makefile whose `$(error ...)` aborts the parse still printed a
        # `verify: lint` line, and parsing it returned ['lint'] from a make
        # that had refused to run. "Cannot answer means subsume nothing" has to
        # include "answered badly".
        if proc is not None and proc.returncode == 0 and proc.stdout:
            result = proc.stdout
    _MAKE_PREREQ_CACHE[key] = result
    return result


def make_prerequisites(
    project_root: str, target: str, env: Optional[dict[str, str]] = None
) -> Optional[list[str]]:
    """``target``'s prerequisites as make resolves them, or None if unanswerable."""
    database = _make_database(project_root, target, env)
    return None if database is None else _explicit_rule(database, target)


def make_declares_target(
    project_root: str, target: str, name: str, env: Optional[dict[str, str]] = None
) -> bool:
    r"""Is ``name`` an explicit RULE in the database ``target`` was queried from?

    A PREREQUISITE NAME IS NOT PROOF A TARGET OF THAT NAME EXISTS, and one
    shape makes the two genuinely indistinguishable in the dump: a filename
    containing an escaped space. `make -p` prints `verify: lint\ aux test` as

        verify: lint aux test

    with the backslash GONE, so one file named `lint aux` and two files named
    `lint` and `aux` are BYTE-IDENTICAL there. No parser can separate them -
    this is a limit of the output, not a bug in the reader - and the wrong
    reading credits a step called `lint` to an aggregate that never runs one.

    The targets are not ambiguous, though: the same dump prints the rule as
    `lint aux:`, and no `lint:` line exists. So a prerequisite is credited only
    when the database also declares it as a rule in its own right, which is in
    any case the only kind of prerequisite `make <name>` can mean
    (counter-model review, round 2).
    """
    database = _make_database(project_root, target, env)
    if database is None:
        return False
    prefix = f"{name}:"
    in_files = False
    for line in database.splitlines():
        if line.startswith("# Files"):
            in_files = True
            continue
        if in_files and line.startswith("# files hash-table stats"):
            break
        if in_files and line.startswith(prefix):
            return True
    return False


#: THE POSITIVE GRAMMAR (issue #1165, orchestrator ratification of option B).
#:
#: Two counter-model passes produced FIFTEEN findings against this derivation,
#: every one of them a way for a quality gate to be recorded as covered while
#: never running, and every one a construct the reader had not anticipated:
#: inactive conditionals, MAKECMDGOALS, MAKEFLAGS, recursive `$(MAKE)`,
#: target-specific variables, escaped hashes, escaped spaces, `$(error)`. A
#: sixteenth was always going to exist, because a list of FORBIDDEN constructs
#: can only ever name the ones somebody already thought of.
#:
#: So the set is what is ALLOWED, and it is CLOSED. A makefile is queried only
#: when every one of its logical lines is one of four shapes; anything else -
#: including a shape nobody has imagined yet - refuses by construction, names
#: the line and the construct, and every gate runs. The cost of refusing is a
#: duplicate run. The cost of accepting wrongly is the check not happening.
#:
#: DO NOT "relax the grammar a little". The grammar IS the instrument; widening
#: it re-opens the class above one construct at a time, which is the history
#: this replaced.
_PLAIN_NAME = re.compile(r"\A[A-Za-z0-9_.-]+\Z")

#: `NAME = value`, `:=`, `?=`, `+=`. The name uses the same plain class as a
#: target, so make's own dotted specials (`.DEFAULT_GOAL`) are ordinary
#: assignments - CPP's Makefile carries one, and a narrower class would have
#: put this repository outside its own grammar.
_ASSIGNMENT = re.compile(
    r"\A[A-Za-z0-9_.-]+[ \t]*(?::=|\?=|\+=|=)(?P<value>.*)\Z", re.S
)

#: Values that make the makefile's meaning depend on something other than its
#: own text: a subprocess, a re-parse, a recursive make, or make's own flags.
_GRAMMAR_FORBIDDEN_VALUES = (
    "$(shell", "${shell", "$(eval", "${eval",
    "$(MAKE)", "${MAKE}", "MAKEFLAGS",
)

_NAMED_CONSTRUCTS = (
    ("an include", ("include ", "-include ", "sinclude ")),
    ("a conditional", ("ifeq", "ifneq", "ifdef", "ifndef", "else", "endif")),
    ("a define block", ("define ", "endef")),
    ("an export directive", ("export ", "unexport ")),
    ("a vpath directive", ("vpath ",)),
)


def _construct_name(line: str) -> str:
    """Name what refused, so the duplicate run explains itself."""
    stripped = line.strip()
    for name, prefixes in _NAMED_CONSTRUCTS:
        if any(stripped == pre.strip() or stripped.startswith(pre) for pre in prefixes):
            return name
    if "%" in stripped:
        return "a pattern rule"
    if "::" in stripped:
        return "a double-colon rule"
    if "$$" in stripped:
        return "a secondary expansion"
    if "\\" in stripped:
        return "a backslash escape in a rule line"
    if "#" in stripped:
        return "a hash in a rule line"
    return "a line the grammar does not recognise"


def _logical_lines(text: str) -> Iterator[tuple[int, str]]:
    """Physical lines joined on a trailing backslash, with the START line number.

    A TRAILING backslash is a continuation - the ordinary way to write a long
    prerequisite list, and CPP's own `verify` uses it across eight physical
    lines. It is not the hazard. A backslash ESCAPING a character inside a name
    (`lint\\ aux`, `lint\\#aux`) is, and that one SURVIVES the join and is
    refused below. Joining first is what keeps the grammar a statement about
    makefiles rather than a statement about where the line breaks fall.
    """
    buf, start = "", 1
    for number, raw in enumerate(text.splitlines(), 1):
        if not buf:
            start = number
        if raw.endswith("\\"):
            buf += raw[:-1] + " "
            continue
        yield start, buf + raw
        buf = ""
    if buf:
        yield start, buf


def makefile_grammar_refusal(project_root: str) -> Optional[str]:
    """None when the makefile is inside the grammar, else line and construct.

    RUN BEFORE THE `make -p -n` QUERY, and that ordering is load-bearing: a
    file outside the grammar is never queried, so `$(MAKE)` recursion and
    MAKEFLAGS-sensitive conditionals never execute at all. Both this and the
    query must agree or nothing is subsumed.

    THE NET IS MUCH WIDER THAN THE TWO HAZARDS ABOVE (issue #1192). EVERY
    include form is refused, and that includes ones neither hazard describes.
    Measured, git 2.43.0 era, against fixtures in this repository:

        plain rules only               -> None          <- the negative control
        -include $(VAR)                -> 'line N: an include'
        -include .env  (a plain path)  -> 'line N: an include'
        include config.mk              -> 'line N: an include'

    An `-include` of an optional env file is ordinary project configuration,
    not recursive make and not a flag-sensitive conditional. Such a repository
    pays every gate twice, and #1152's dedup - whose measured saving was 390s
    down to 233s - never reaches it.

    THIS REPOSITORY CANNOT OBSERVE THAT. CPP's own Makefile returns None: it is
    inside the grammar, it benefits from the dedup, and so the population that
    would notice the bound is exactly the population that does not run this
    code. A different repository had to surface it. That is why the refusal is
    now REPORTED by the runner and the finish gate (`subsumption_refusals`,
    `SUBSUMPTION REFUSED`) rather than left to whoever thinks to call this
    function: a bound nobody can see from inside the tree it is maintained in
    is discoverable only by accident.

    THE REFUSAL IS CORRECT AND STAYS WIDE. Refusing costs a duplicate run;
    accepting wrongly costs the thing the gate exists for. Admitting an
    `include` of a VARIABLE would query a tree whose included CONTENT was never
    inspected - `_reads_makeflags` reads the top-level makefile only and says
    so - and admitting only a statically resolvable include is safe precisely
    because it excludes the variable form, so it would not reach the consumer
    that motivated the issue. Either the admission is unsafe or it is useless.

    OSCILLATION TRIGGER, pre-committed rather than decided later under
    pressure: what would move this bound is NOT a consumer asking for it. It is
    someone making an included file's contents statically VERIFIABLE. If that
    lands, the admission widens because the verification widened - never the
    reverse.
    """
    makefile = Path(project_root) / "Makefile"
    try:
        text = makefile.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"the makefile could not be read ({exc.__class__.__name__})"

    for number, line in _logical_lines(text):
        if not line.strip() or line.lstrip().startswith("#"):
            continue  # blank, or a comment
        if line.startswith("\t"):
            continue  # a recipe line; its contents are make's business, not ours
        assignment = _ASSIGNMENT.match(line)
        if assignment is not None:
            value = assignment.group("value")
            for token in _GRAMMAR_FORBIDDEN_VALUES:
                if token in value:
                    return (
                        f"line {number}: an assignment whose value contains {token}"
                    )
            continue
        head, separator, tail = line.partition(":")
        if separator and "=" not in head and not tail.startswith(":"):
            if not any(ch in line for ch in ("\\", "#", "%")):
                targets, prerequisites = head.split(), tail.split()
                if targets and all(
                    _PLAIN_NAME.match(name) for name in targets + prerequisites
                ):
                    continue  # a rule, all plain names
        return f"line {number}: {_construct_name(line)}"
    return None


def _reads_makeflags(makefile: Path) -> bool:
    """Does this makefile resolve differently depending on make's own flags?

    The query runs `make -p -n`; the gate runs `make verify`. Those differ in
    `MAKEFLAGS`, and a makefile is allowed to branch on it - so for such a tree
    the query answers a question about itself. Measured (counter-model review,
    round 2): `verify: lint` guarded by `ifneq (,$(findstring n,$(MAKEFLAGS)))`
    is REPORTED by the query and is NOT run by `make verify`, so a broken lint
    would be suppressed in favour of an aggregate that never runs it.

    THE BOUND, STATED: this reads the top-level `Makefile` only. A reference
    inside an `include`d file is not seen, so this narrows the hazard rather
    than closing it. It is worth having anyway - the shape is rare, the check
    is two lines, and the failure it removes is a silent false green - but a
    reader must not take a pass here as proof the tree is flag-insensitive.
    Unreadable counts AS sensitive: refusing costs a duplicate run.
    """
    try:
        return bool(_MAKEFLAGS_SENSITIVE.search(makefile.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return True


def _explicit_rule(database: str, target: str) -> Optional[list[str]]:
    """``target``'s prerequisites from a `make -p` dump, explicit rules only.

    `-p` also prints pattern rules and entries make merely considered, so a
    bare search for the name would answer a different question. An entry
    preceded by `# Not a target:` is exactly that, and is skipped.
    """
    # ONE DATABASE, OR NONE. `-n` does NOT suppress a recipe line containing
    # `$(MAKE)` - documented GNU behaviour - so a tree using recursive make runs
    # its children during the query, and a child's `-p` dump is printed BEFORE
    # the parent's. Measured: a parent whose rule is `verify: test` returned
    # `['lint']`, read out of a child makefile in a subdirectory. The parser
    # cannot tell whose database it is reading, so where there is more than one
    # it reads none (counter-model review, round 2).
    if database.count("\n# Files") > 1 or "Entering directory" in database:
        return None

    prefix = f"{target}:"
    previous = ""
    in_files = False
    for line in database.splitlines():
        # SCOPED TO THE FILES SECTION. `-p` prints variables, directories and
        # implicit rules as well, and a `verify: lint` occurring inside a
        # multi-line variable value is not a rule - measured, it was read as
        # one. The dump labels the section; anchoring on the label is what
        # makes this a rule reader rather than a text search.
        if line.startswith("# Files"):
            in_files = True
            continue
        if in_files and line.startswith("# files hash-table stats"):
            break
        if not in_files:
            continue
        if line.startswith(prefix) and not line.startswith(f"{target}::"):
            if previous.strip().startswith("# Not a target"):
                previous = line
                continue
            rhs = line[len(prefix):]
            # AMBIGUOUS MEANS REFUSED, NOT GUESSED. Splitting on whitespace and
            # cutting at `#` is correct only for a rule whose prerequisites are
            # plain names, and three shapes break it - each measured returning a
            # WRONG NAME rather than an error (counter-model review, round 2):
            #
            #   `verify: CHECK/LIST = lint`  -> ['CHECK/LIST', '=', 'lint']
            #        a target-specific variable. The previous guard keyed on the
            #        variable NAME, so any name outside its character class
            #        walked straight past it; `=` anywhere is the general tell.
            #   `verify: lint\#aux`          -> ['lint']
            #        an escaped `#` is part of the filename, and cutting there
            #        invents a target `lint` that does not exist.
            #   `verify: lint\ aux test`     -> ['lint', 'aux', 'test']
            #        an escaped space is ONE file; splitting makes it two.
            #
            # Every wrong name is a gate id that may match a real step and
            # suppress it. There is no reading of these where guessing beats
            # running the gate twice, so any marker refuses the whole rule.
            # CPP's own `verify` carries none, which the 29-prerequisite
            # consumer-side pin re-confirms on every run.
            # AN ASSIGNMENT IS SKIPPED; AN AMBIGUOUS RULE REFUSES. The two
            # are different facts and deserve different answers. `=` anywhere
            # in the right-hand side means this line assigns a target-specific
            # variable, so it is not a prerequisite list at all - skip it and
            # keep looking for the real rule, which is what make itself does.
            # `#` or `\` mean the prerequisite LIST cannot be tokenised
            # reliably, and there is no further line to fall back to, so the
            # whole target refuses.
            if "=" in rhs:
                previous = line
                continue
            if "#" in rhs or "\\" in rhs:
                return None
            seen: set[str] = set()
            out: list[str] = []
            for name in rhs.split():
                if name not in seen:
                    seen.add(name)
                    out.append(name)
            return out
        previous = line
    return None


#: Step commands that are a recognised way of running `make <target>`.
#:
#: An ALLOWLIST, defaulting to "not subsumed", because the question - does this
#: step run the same check the aggregate's prerequisite runs? - is not decidable
#: in general from a shell string. Two shapes exist in this repository and both
#: are genuinely equivalent where the question arises:
#:
#:   `make lint`
#:   `if grep -q "^lint:" Makefile 2>/dev/null; then make lint; else <alt>; fi`
#:
#: The second runs `make lint` exactly when a `lint:` target exists - and
#: subsumption only arises when make NAMED lint a prerequisite, which requires
#: that target. Anything else is reported by name WITH its command, so the
#: duplicate run explains itself and the allowlist grows from evidence rather
#: than from guessing.
#: HORIZONTAL whitespace only, and the WHOLE command must match. `\s` spans
#: newlines, so `make\nlint` - two shell commands - satisfied the direct form;
#: and the conditional form matched a PREFIX, so `... && false; then make lint;
#: else exit 1; fi` and a trailing `; exit 1` were both accepted. Suppressing
#: such a step removes a failure the aggregate cannot reproduce (counter-model
#: review).
_MAKE_INVOCATION = re.compile(r"\Amake[ \t]+(?P<target>[A-Za-z0-9_.-]+)[ \t]*\Z")
_GENERATED_CONDITIONAL = re.compile(
    r'\Aif[ \t]+grep[ \t]+-q[ \t]+"\^(?P<guard>[A-Za-z0-9_.-]+):"[ \t]+Makefile'
    r"[ \t]*(?:2>/dev/null)?[ \t]*;[ \t]*"
    r"then[ \t]+make[ \t]+(?P<target>[A-Za-z0-9_.-]+);[ \t]*"
    r"else[ \t]+[^;]+;[ \t]*fi[ \t]*\Z"
)
#: `verify: CHECKS = lint` and friends - an assignment, not a rule.
_TARGET_VARIABLE = re.compile(r"\A[ \t]*[A-Za-z0-9_.-]+[ \t]*[:+?]?=")


def command_runs_make_target(
    command: str, target: str, project_root: Optional[str] = None
) -> bool:
    """Does ``command`` run `make <target>` on the path it will take HERE?

    "On the path it will take here" is the whole contract, and the generated
    conditional is where it bites. `generate_manifest` emits

        if grep -q "^lint:" Makefile; then make lint; else <fallback>; fi

    and recognising the shape only establishes what the command CAN do. Which
    branch it takes is decided by that grep, against this project's makefile -
    so this runs the same grep rather than assuming the `then` side. A tree
    whose target comes from a variable (`$(CHECKS):`) has no literal `lint:`
    line, takes the ELSE branch, and runs a fallback `make verify` never runs.
    Suppressing it there would drop the check entirely (counter-model review).

    `project_root=None` means the guard CANNOT be evaluated, so the conditional
    form is refused. The cost of refusing is one duplicate run; the cost of
    accepting is a gate that never executes.
    """
    text = command.strip()
    # ONE LINE, OR NOT RECOGNISED. Both recognised shapes are single-line, and
    # a newline is how trailing shell got past the old pattern.
    if "\n" in text or "\r" in text:
        return False
    # Horizontal whitespace only - `str.split()` would fold a newline away and
    # undo the line above.
    normalised = " ".join(text.split(" "))
    normalised = " ".join(normalised.split("\t"))
    while "  " in normalised:
        normalised = normalised.replace("  ", " ")
    normalised = normalised.strip()

    # EQUALITY, NOT PATTERN (#1165, option B). The direct form is one string.
    if normalised == f"make {target}":
        return True

    # The generated form is recognised by IDENTITY WITH ITS PRODUCER: strip the
    # builder's own literal prefix and suffix, rebuild with what is left, and
    # require the bytes to match. No regex touches the shell text.
    fallback = _generated_fallback(normalised, target)
    if fallback is None:
        return False
    if normalised != gate_conditional_command(target, fallback):
        return False
    # The fallback runs only when the grep MISSES, and `_makefile_declares`
    # below proves it hits - so its contents never execute on the path that
    # matters. Refused anyway if it could chain: a slot that can carry `;` is a
    # slot that can carry anything, and this is the one place a caller's text
    # reaches an accepted command.
    if any(ch in fallback for ch in (";", "&", "|", "`", "\n")):
        return False
    return _makefile_declares(project_root, target)


def _makefile_declares(project_root: Optional[str], target: str) -> bool:
    """The `grep -q "^<target>:" Makefile` the generated command itself runs."""
    if project_root is None:
        return False
    makefile = Path(project_root) / "Makefile"
    try:
        text = makefile.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    prefix = f"{target}:"
    return any(line.startswith(prefix) for line in text.splitlines())


def subsumed_gate_ids(
    plan_name: str, step_defs: list[StepDef], project_root: str
) -> tuple[dict[str, str], list[str]]:
    """Gate id -> the aggregate that already runs it, and the refusals.

    `make verify` here lists `lint test typecheck` among its prerequisites, so
    the finish plan executed those three TWICE - measured at 390.77s against
    233.44s for the same coverage (issue #1152).

    WHICH prerequisites is answered by MAKE, not by reading the makefile
    (issue #1165): see `make_prerequisites`. WHETHER the step runs the same
    check is answered by `command_runs_make_target`, an allowlist that refuses
    what it does not recognise. Both refusals cost a duplicate run; accepting
    either wrongly costs the thing the gate exists for.

    Returns the mapping and a list of human-readable refusals, so a reader sees
    why a gate was NOT subsumed instead of inferring it from silence.
    """
    aggregates = [d.id for d in step_defs if d.gate and d.id in _AGGREGATE_GATE_IDS]
    if not aggregates:
        return {}, []

    by_id = {d.id: d for d in step_defs}
    in_plan = {d.id for d in step_defs if d.gate}
    covered: dict[str, str] = {}
    refusals: list[str] = []

    # THE GRAMMAR DECIDES FIRST, AND SAYS WHICH LINE (#1165, option B). A
    # makefile outside the positive grammar is never queried - so `$(MAKE)`
    # recursion and MAKEFLAGS conditionals do not execute - and the reader is
    # told the line number and the construct rather than left with a generic
    # "make could not be asked". The author who pays for a duplicate run can
    # see exactly what put their makefile outside the set.
    # AN ABSENT MAKEFILE IS A DIFFERENT FACT from one outside the grammar, and
    # the two must not share a sentence: "there is no makefile to ask about"
    # and "this makefile uses a construct I cannot be sure about" send a reader
    # to different places. Absence falls through to the existing refusal below.
    grammar = (
        makefile_grammar_refusal(project_root)
        if (Path(project_root) / "Makefile").is_file()
        else None
    )
    if grammar is not None:
        refusals.append(
            f"the makefile is outside the grammar subsumption requires "
            f"({grammar}), so nothing is subsumed and every gate runs"
        )
        return {}, refusals

    for aggregate in aggregates:
        # THE AGGREGATE'S OWN COMMAND IS CHECKED FIRST (counter-model review).
        # Every suppression below rests on `make verify` running the
        # prerequisite - which rests on this step running `make verify`. It was
        # never verified: a step declared `id: verify` whose command was `true`
        # (or `make verify-fast`, or a wrapper) still credited the whole plan,
        # so the gates were suppressed in favour of an aggregate that ran none
        # of them. The step ids are labels; only the command runs.
        aggregate_step = by_id.get(aggregate)
        if aggregate_step is None or not command_runs_make_target(
            aggregate_step.command, aggregate, project_root
        ):  # noqa: SIM114 - the two refusals report different reasons
            refusals.append(
                f"`{aggregate}` is declared as the aggregate but this plan runs it as "
                f"{aggregate_step.command!r} - not a recognised way of running "
                f"`make {aggregate}`, so it cannot be credited with running anything "
                f"and every gate runs on its own"
                if aggregate_step is not None
                else f"`{aggregate}` is declared as the aggregate but is not a step here"
            )
            continue
        # ASKED IN THE ENVIRONMENT THE AGGREGATE WILL RUN IN (counter-model
        # review, round 2). A step may carry `env` overrides and a makefile
        # conditional may read them, so the query and the run can disagree
        # about what `verify` does while both are correct about their own
        # environment. Measured: a `verify` step with `env={"SKIP_LINT": "1"}`
        # whose makefile drops lint under that variable was reported as
        # covering lint, with no refusal, while standalone lint failed.
        aggregate_env = dict(os.environ)
        aggregate_env.update(aggregate_step.env)
        prereqs = make_prerequisites(project_root, aggregate, aggregate_env)
        if prereqs is None:
            refusals.append(
                f"make could not be asked what `{aggregate}` runs (absent, unparseable, "
                f"or no explicit rule), so nothing is subsumed and every gate runs"
            )
            continue
        for prereq in prereqs:
            if prereq not in in_plan or prereq == aggregate or prereq in covered:
                continue
            # ...AND ONLY A NAME THE DATABASE DECLARES AS A RULE. An escaped
            # space makes `lint aux` and `lint` + `aux` byte-identical in the
            # prerequisite list, so the name alone cannot be trusted; the rule
            # lines can (counter-model review, round 2).
            if not make_declares_target(project_root, aggregate, prereq, aggregate_env):
                refusals.append(
                    f"`{prereq}` appears in `{aggregate}`'s prerequisite list but the "
                    f"database declares no `{prereq}:` rule - the name may be part of "
                    f"a filename containing a space, which make prints without its "
                    f"escape, so it is NOT subsumed"
                )
                continue
            step = by_id.get(prereq)
            # A PREREQUISITE STEP WITH A DIFFERENT ENVIRONMENT RUNS A
            # DIFFERENT CHECK, whatever its command says. `make lint` under
            # `env={"STRICT": "1"}` is not the `make lint` the aggregate runs,
            # so an identical command string is not equivalence (counter-model
            # review, round 2).
            if step is not None and step.env != aggregate_step.env:
                refusals.append(
                    f"`{prereq}` is a prerequisite of `{aggregate}`, but the two steps "
                    f"declare different environments ({step.env!r} against "
                    f"{aggregate_step.env!r}) - the same command in a different "
                    f"environment is not the same check, so it is NOT subsumed"
                )
                continue
            if step is None or not command_runs_make_target(
                step.command, prereq, project_root
            ):
                refusals.append(
                    f"`{prereq}` is a prerequisite of `{aggregate}`, but this plan runs it "
                    f"as {step.command!r} - not a recognised way of running "
                    f"`make {prereq}`, so it is NOT subsumed and runs on its own"
                    if step is not None
                    else f"`{prereq}` is a prerequisite of `{aggregate}` but is not a step here"
                )
                continue
            covered[prereq] = aggregate
    return covered, refusals


def dropped_gate_ids(
    plan_name: str, step_defs: list[StepDef]
) -> Optional[list[str]]:
    """Gates the built-in plan of this NAME declares that the resolved plan lacks.

    This is the #1155 reconciliation: `.claude/cicd_tasks.yml` wins over
    `BUILTIN_PLANS`, so a manifest can drop a declared gate and - before this -
    nothing compared the two. #1147 shipped a green over four of five gates
    that way, and codex-power-pack is carrying the same defect for `typecheck`
    and `verify` today (cooneycw/codex-power-pack#290).

    KEYED BY PLAN NAME, and the missing-plan case is DISTINCT from the
    zero-dropped one. A manifest may define a plan the built-ins know nothing
    about; there is then no declaration to reconcile against, which is not the
    same fact as "reconciled, nothing missing". Returning `[]` for both would
    let a plan nobody can check report exactly what a clean plan reports -
    unscanned rendering as clean, which is the failure this whole family of
    guards exists to refuse. `None` means NOT APPLICABLE and the reader says so
    by name.

    A gate that is PRESENT and skips is not dropped: it appears in the resolved
    steps, and its skip is reported by #628's `warn (skipped gates: ...)` with
    the reason attached. Dropping is silent, skipping is loud, and keeping those
    distinguishable is the point - a repository that lacks a target should LIST
    the step and let `skip_if` skip it.
    """
    if plan_name not in BUILTIN_PLANS:
        return None
    declared = {s.id for s in BUILTIN_PLANS[plan_name] if s.gate}
    return sorted(declared - {s.id for s in step_defs})


# Gates the Makefile-fallback lane in scripts/flow-finish-gate.sh cannot run, with
# the reason it cannot. This exists because GATE_STEP_IDS is read by two
# consumers that want different things (issue #890): runner.py asks "did skipping
# this prove nothing?", while the #617 fallback-parity test asks "must the
# degraded lane run this?". Those agreed until `security_scan` became a gate, and
# conflating them is what made a one-line fix red a test about something else.
#
# An entry here is a claim that the fallback CANNOT cover the gate, not a licence
# to leave it out: tests/test_runner.py asserts every finish-plan gate is either
# invoked by the fallback or named here, so a new gate has to land in one bucket
# on purpose.
FALLBACK_UNRUNNABLE_GATES: dict[str, str] = {
    "security_scan": (
        "the scanner is `python3 -m lib.security`, which lives in the CPP "
        "checkout. The fallback lane exists precisely when uv or that checkout "
        "is unavailable - the same condition that skips the step - so there is "
        "no degraded form of it to run. A skipped scan is surfaced as a #628 "
        "warn instead, which is the honest report rather than a substitute."
    ),
}


class DeployStep:
    """Execute a deployment with readiness gate and automatic rollback.

    Wraps a DeploymentStrategy to provide:
    1. Deploy via the configured strategy
    2. Poll readiness URL until success threshold or timeout
    3. Automatic rollback if readiness check fails

    Usage:
        config = DeployConfig(strategy="docker_compose", ...)
        step = DeployStep(config)
        result = step.execute(context)
    """

    def __init__(self, config: Optional[Any] = None):
        from .deploy.strategy import DeployConfig, get_strategy

        if config is None:
            config = DeployConfig()
        elif isinstance(config, dict):
            config = DeployConfig.from_dict(config)

        self.config: DeployConfig = config
        self.id = "deploy"
        self.timeout_seconds = config.timeout_seconds
        self.max_attempts = 1
        self.idempotent = False

        self.strategy = get_strategy(config.strategy)

    def execute(self, context: dict[str, Any]) -> StepResult:
        """Execute deploy, check readiness, rollback on failure."""
        from .deploy.strategy import poll_readiness

        # Step 1: Deploy
        deploy_result = self.strategy.deploy(context, self.config)
        if not deploy_result.success:
            return deploy_result

        # Step 2: Readiness gate (if configured)
        if self.config.readiness:
            readiness = poll_readiness(self.config.readiness)
            if not readiness.ready:
                # Step 3: Auto-rollback on readiness failure
                rollback_result = self.strategy.rollback(context, self.config)
                rollback_info = (
                    "rollback succeeded" if rollback_result.success
                    else f"rollback also failed: {rollback_result.error}"
                )
                return StepResult(
                    status=StepStatus.FAILED,
                    exit_code=1,
                    output=deploy_result.output,
                    error=(
                        f"Readiness check failed: {readiness.summary}. "
                        f"Rollback: {rollback_info}"
                    ),
                )

        return deploy_result


def get_plan_steps(plan_name: str, project_root: Optional[str] = None) -> list[StepDef]:
    """Get step definitions for a plan.

    Loads from `.claude/cicd_tasks.yml` manifest if present,
    otherwise falls back to built-in plan definitions.
    """
    from pathlib import Path

    root = Path(project_root) if project_root else Path(".")

    # A MANIFEST THAT EXISTS AND CANNOT BE READ IS A HARD FAILURE (issue #1163,
    # counter-model review post-merge). This used to catch ImportError and fall
    # through to BUILTIN_PLANS, which was harmless only because the CLI could
    # not START without pydantic - the process died before reaching here.
    #
    # #1163 deliberately removed that: `python3 -m lib.cicd run` now starts on
    # the stdlib alone, so the fall-through became reachable, and it SILENTLY
    # SUBSTITUTES A DIFFERENT PLAN. Measured on this repository with pydantic
    # blocked: `deploy` returned the built-in steps, losing `drift_check` and
    # gaining `stale_commit_check`, with no warning and a successful run. A
    # loud failure had been turned into a quiet change of which checks execute,
    # by a change whose whole purpose was to make a lane reachable.
    #
    # So the two cases are separated. No manifest FILE means there is nothing
    # to lose and the built-in plans are the right answer. A manifest that is
    # present but whose reader will not load means the caller asked for a
    # configured plan and cannot be given one, and saying so is the only honest
    # option. An INVALID manifest keeps its old fall-back: that is a different
    # question from a missing dependency, and narrowing it belongs with whoever
    # decides what an unparseable manifest should mean.
    manifest_path = root / MANIFEST_PATH
    try:
        from .manifest import get_manifest_plan_steps, load_manifest
    except ImportError as exc:
        if manifest_path.is_file():
            raise RuntimeError(
                f"{manifest_path} exists but its reader could not be imported "
                f"({exc}). Refusing to fall back to the built-in plans: they are "
                f"a DIFFERENT set of steps, and substituting them silently would "
                f"change which checks run (issue #1163). Install the manifest "
                f"dependencies, or remove the manifest to use the built-ins "
                f"deliberately."
            ) from exc
    else:
        try:
            manifest = load_manifest(root)
            if manifest is not None and plan_name in manifest.plans:
                return get_manifest_plan_steps(manifest, plan_name)
        except ValueError:
            # An invalid manifest falls back as it always has.
            pass

    # Fall back to built-in plans
    if plan_name not in BUILTIN_PLANS:
        available = ", ".join(sorted(BUILTIN_PLANS.keys()))
        raise ValueError(f"Unknown plan: {plan_name}. Available: {available}")
    return BUILTIN_PLANS[plan_name]
