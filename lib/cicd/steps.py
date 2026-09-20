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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from .coverage import StageCoverage, merge_stream_coverage, parse_stage_coverage
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

    def __init__(self, step_def: StepDef):
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
        if not self.is_test_step():
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
        command=(
            f'if grep -q "^{step_id}:" Makefile 2>/dev/null; then make {step_id}; '
            f"else uv run --extra dev {uv_tool}; fi"
        ),
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


def subsumed_gate_ids(
    plan_name: str, step_defs: list[StepDef], project_root: str
) -> dict[str, str]:
    """Gate id -> the aggregate gate in THIS plan whose recipe already runs it.

    `make verify` in this repository lists `lint test typecheck` among its
    prerequisites, so a finish plan running all four executes those three TWICE
    - measured at 390.77s against 233.44s for the same coverage (issue #1152).

    DIRECT PREREQUISITES ONLY. A target two levels down is not claimed, even
    though make would still run it: the derivation would then rest on a
    transitive walk with cycle handling, and being wrong in that direction
    means a gate is marked as covered when it was not. The safe failure is
    running a gate TWICE, which costs time; the unsafe one is skipping a gate
    that nothing ran, which costs the thing the gate exists for. So this stays
    shallow on purpose and the cost of that choice is duplicate work, never a
    missing check.

    ONE PARSER. `scripts/verify-coverage-check.py`'s `Makefile` is the
    repository's canonical Makefile reader and is what `check-ci-coverage.py`
    already loads - this adds no second reader of the same file.
    `lib/cicd/makefile.py::parse_makefile` is deliberately NOT used: it does not
    join backslash continuations and returns 9 of this repository's 29 verify
    prerequisites, the last being a literal backslash (issue #1162). It would
    have been right BY LUCK here, since lint, test and typecheck all sit on the
    first physical line.

    Returns an empty mapping when there is no Makefile, no aggregate gate in the
    plan, or no parser - every one of which means "nothing is known to be
    covered", so every gate runs on its own, which is the pre-#1152 behaviour.
    """
    from importlib.util import module_from_spec, spec_from_file_location

    aggregates = [d.id for d in step_defs if d.gate and d.id in _AGGREGATE_GATE_IDS]
    if not aggregates:
        return {}
    parser_path = Path(_CPP_ROOT) / "scripts" / "verify-coverage-check.py"
    makefile_path = Path(project_root) / "Makefile"
    if not parser_path.is_file() or not makefile_path.is_file():
        return {}
    try:
        spec = spec_from_file_location("cpp_makefile_reader", parser_path)
        if spec is None or spec.loader is None:
            return {}
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        parsed = module.Makefile(makefile_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - an unusable parser means "nothing known"
        return {}

    in_plan = {d.id for d in step_defs if d.gate}
    covered: dict[str, str] = {}
    for aggregate in aggregates:
        for prereq in parsed.prereqs.get(aggregate, ()):
            if prereq in in_plan and prereq != aggregate and prereq not in covered:
                covered[prereq] = aggregate
    return covered


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

    # Try loading from manifest first
    try:
        from .manifest import get_manifest_plan_steps, load_manifest

        manifest = load_manifest(root)
        if manifest is not None and plan_name in manifest.plans:
            return get_manifest_plan_steps(manifest, plan_name)
    except (ImportError, ValueError):
        # Pydantic not installed or manifest invalid - fall back to built-in
        pass

    # Fall back to built-in plans
    if plan_name not in BUILTIN_PLANS:
        available = ", ".join(sorted(BUILTIN_PLANS.keys()))
        raise ValueError(f"Unknown plan: {plan_name}. Available: {available}")
    return BUILTIN_PLANS[plan_name]
