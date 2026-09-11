"""Deterministic CI/CD runner.

Replaces prompt-driven orchestration with a state-machine that executes
steps sequentially, persists state to disk, and supports resume from
the last failed step.

Flow commands (.md prompts) become thin wrappers that invoke this runner
and only re-engage the LLM when code fixes are needed.

Usage:
    python -m lib.cicd run --plan finish
    python -m lib.cicd run --plan deploy
    python -m lib.cicd resume <run_id>
    python -m lib.cicd status <run_id>
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TextIO

from .outcomes import parse_failed_node_ids
from .state import RunState, StepStatus, compute_tree_signature
from .steps import (
    GATE_STEP_IDS,
    TIMEOUT_EXIT_CODE,
    ShellStep,
    StepDef,
    get_plan_steps,
)

# Variables the runner launcher injects (or a parent venv leaks) that must NOT
# reach child step processes: PYTHONPATH is added so ``python -m lib.cicd`` can
# import itself but would shadow the target project's imports; VIRTUAL_ENV /
# PYTHONHOME inherited from the CPP venv pin child ``uv run`` to the wrong
# interpreter and hide the project's own dev deps (e.g. pytest-cov), so the
# child must re-resolve the project venv from scratch (issue #534).
RUNNER_STRIP_VARS = frozenset({"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"})

# A flake is a handful of tests. A hundred failures is a regression, and
# re-running it just doubles the wall clock before reporting the same red
# (issue #769).
MAX_RERUN_IDS = 25


def _project_python_floor(project_root: Optional[Path]) -> Optional[str]:
    """Return the target project's minimum Python version (e.g. "3.12").

    Parsed from the project's ``pyproject.toml`` ``requires-python`` floor so
    child ``uv run`` steps pin the interpreter the project actually needs,
    rather than whatever system Python the sandbox defaults to (issue #534,
    part #2). Returns None when it cannot be determined - the caller then
    leaves UV_PYTHON unset rather than guessing.
    """
    if project_root is None:
        return None
    pyproject = Path(project_root) / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', text)
    if not match:
        return None
    # Take the first "3.N" that appears in the specifier (the floor for the
    # common ">=3.N" / ">=3.N,<3.M" forms).
    ver = re.search(r"(\d+\.\d+)", match.group(1))
    return ver.group(1) if ver else None


def _is_offline() -> bool:
    """Best-effort detection that the runner has no outbound network.

    A restricted sandbox (Codex) blocks DNS/outbound sockets, so network
    steps (git fetch, secret managers) fail loudly. Steps can consult this to
    skip-with-a-message instead of hard-failing (issue #534, part #5). An
    explicit ``CPP_OFFLINE`` env value short-circuits the probe - for tests and
    for sandboxes that also block the probe itself.
    """
    flag = os.environ.get("CPP_OFFLINE", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    try:
        with socket.create_connection(("github.com", 443), timeout=2.0):
            return False
    except OSError:
        return True


def _build_step_env(project_root: Optional[Path] = None) -> dict[str, str]:
    """Build a sanitized copy of os.environ for child step processes.

    Makes the child environment sandbox-aware (issue #534):
    - strips launcher/parent-venv leakage (see RUNNER_STRIP_VARS),
    - defaults UV_CACHE_DIR to a writable path (sandbox ~/.cache is read-only),
    - pins UV_PYTHON to the target project's required floor so child ``uv run``
      steps do not fall back to a stale system interpreter.
    All defaults use ``setdefault`` so an explicit caller env always wins.

    Kept pure (no network) so it stays cheap and hermetic; the offline probe
    that materializes CPP_OFFLINE runs once in the runner's execute loop.
    """
    env = {k: v for k, v in os.environ.items() if k not in RUNNER_STRIP_VARS}
    env.setdefault("UV_CACHE_DIR", "/tmp/uv-cache")
    floor = _project_python_floor(project_root)
    if floor:
        env.setdefault("UV_PYTHON", floor)
    return env


@dataclass
class RunResult:
    """Result of a complete runner execution."""

    success: bool
    run_id: str
    plan_name: str
    steps_completed: int = 0
    steps_total: int = 0
    failed_step: Optional[str] = None
    error: Optional[str] = None
    # Test-runner counts per test step, e.g. {"test": {"passed": 312, ...}}, and
    # the qualifications that go with them (issue #621). A plan whose test step
    # executed nothing still succeeds - but it never reports a bare SUCCESS.
    tests: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # Test steps that failed, were re-run ONCE against only their failed ids, and
    # the outcome of that re-run (issue #769). This is its own channel, NOT
    # `warnings`: `warnings` is the #621 "exited 0 having executed no tests"
    # signal and flow-finish-gate.sh renders it with that exact wording. A
    # re-run that passed is a DIFFERENT qualification and must not borrow #621's
    # sentence.
    reruns: list[dict[str, Any]] = field(default_factory=list)
    # A step killed by its own budget rather than by failing (issue #812).
    # exit 124 is already distinguishable and was being flattened into "the
    # step failed", which sends a reader to debug a suite that never finished.
    # Carried as its own channel so the difference survives to the report.
    timed_out_step: Optional[str] = None
    timed_out_after: Optional[int] = None
    # Step ids whose result was earned in an EARLIER invocation and carried
    # into this one by a resume (issue #838 follow-up). Its own channel and not
    # a `warning`: nothing is wrong, but the reader must be able to tell a
    # result just earned from one merely remembered. Captured on the RESULT
    # rather than read back from state, because the state file is deleted on
    # success - which is exactly why the old `step_details` block could never
    # have shown this on the green path it matters most on.
    carried_from_previous_run: list[str] = field(default_factory=list)
    # True when carried_from_previous_run is non-empty AND the carry was
    # backed by a tree_signature match rather than assumed (issue #804): the
    # tree was hashed at persist time and again at resume time, and the two
    # were equal, so this is a genuine crash-resume and the carried results
    # still describe the tree. False (the default) covers both "nothing was
    # carried" and "something was carried but we could not verify the tree
    # hadn't changed" - flow-finish-gate.sh tells those apart by also
    # checking carried_from_previous_run, and warns only on the second.
    tree_verified: bool = False
    # Full per-step detail, captured BEFORE the success cleanup removes the
    # state file so a green run can report it at all.
    step_details: list[dict[str, Any]] = field(default_factory=list)
    # Step ids that skip_if-skipped this run (issue #628). A skipped GATE step
    # (lint/test/typecheck) means the gate verified nothing about the change, so
    # flow-finish-gate.sh reads this to report `warn` and NAME the skipped gates
    # rather than flatten the run to a bare `ok`.
    skipped_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "success": self.success,
            "run_id": self.run_id,
            "plan": self.plan_name,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
        }
        if self.failed_step:
            d["failed_step"] = self.failed_step
        if self.error:
            d["error"] = self.error
        if self.tests:
            d["tests"] = self.tests
        if self.warnings:
            d["warnings"] = self.warnings
        if self.reruns:
            d["reruns"] = self.reruns
        if self.skipped_steps:
            d["skipped"] = self.skipped_steps
        # The gate parses this JSON, so a field that never reaches it cannot be
        # acted on however carefully it was set (issue #812). Emitted at the top
        # level and keyed by name so the shell reader anchors on the field
        # rather than on error prose, which drifts.
        if self.timed_out_step:
            d["timed_out_step"] = self.timed_out_step
            d["timed_out_after"] = self.timed_out_after
        return d


class DeterministicRunner:
    """Executes CI/CD steps deterministically with persistent state.

    Key properties:
    - Steps execute sequentially in defined order
    - State persisted after each step (crash-safe resume)
    - Failed runs can be resumed from the last successful step
    - Structured JSON output for LLM consumption
    - Retry policy per step with exponential backoff
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        output: Optional[TextIO] = None,
        rerun_failed: bool = False,
    ):
        self.project_root = project_root or Path(".")
        self.output = output or sys.stderr
        self.rerun_failed = rerun_failed

    def run(self, plan_name: str, step_defs: Optional[list[StepDef]] = None) -> RunResult:
        """Execute a named plan from scratch or resume a failed run.

        If a failed run exists for this plan, it is resumed automatically -
        UNLESS the working tree changed since that run failed (issue #804).
        Resume is correct for a crash (the tree the failure left behind is
        still the tree we're about to skip re-testing); it is wrong for a
        repair (the tree changed - usually because the failure was fixed -
        so the results we'd carry describe a tree that no longer exists).
        Which one this is gets decided by comparing tree_signature, not by
        guessing: a match resumes exactly as before this fix, a mismatch
        discards the stale state and starts fresh so every step actually
        runs against the current tree.
        """
        # Check for existing failed run to resume
        existing = RunState.find_latest(plan_name, self.project_root)
        current_sig: Optional[str] = None
        if existing:
            current_sig = compute_tree_signature(self.project_root)
            if (
                existing.tree_signature is not None
                and current_sig is not None
                and existing.tree_signature != current_sig
            ):
                self._log(
                    f"Discarding resumable run {existing.run_id}: the tree "
                    f"changed since step {existing.current_index + 1} failed "
                    "(issue #804) - starting fresh so every step re-runs "
                    "against the current tree."
                )
                existing.discard(self.project_root)
                existing = None
            else:
                # Verified only when BOTH signatures were available and equal.
                # Either side being None means "can't tell" - resume anyway
                # (the pre-#804 behavior, so a non-git target project doesn't
                # regress) but the result must say the carry is unverified so
                # flow-finish-gate.sh's fallback check can still catch it.
                tree_verified = existing.tree_signature is not None and current_sig is not None
                self._log(f"Resuming failed run {existing.run_id} from step {existing.current_index + 1}")
                self._warn_carried_over(existing, tree_verified)
                return self._execute(existing, step_defs, tree_verified=tree_verified)

        # Load step definitions
        if step_defs is None:
            step_defs = get_plan_steps(plan_name, project_root=str(self.project_root))

        # Create new run state
        step_ids = [s.id for s in step_defs]
        state = RunState.create(plan_name, step_ids)
        # Reuse the signature already computed above when a stale run was
        # just discarded, rather than shelling out to git a second time.
        state.tree_signature = current_sig if current_sig is not None else compute_tree_signature(
            self.project_root
        )

        # Set max_attempts from step definitions
        for i, step_def in enumerate(step_defs):
            state.step_records[i].max_attempts = step_def.max_attempts

        self._log(f"Starting plan '{plan_name}' with {len(step_defs)} steps")
        state.save(self.project_root)

        return self._execute(state, step_defs)

    def resume(self, run_id: str) -> RunResult:
        """Resume a specific failed run by ID."""
        state = RunState.load(run_id, self.project_root)
        if state.status != "failed":
            return RunResult(
                success=state.status == "success",
                run_id=run_id,
                plan_name=state.plan_name,
                steps_completed=state.current_index,
                steps_total=len(state.step_records),
                error=f"Run is {state.status}, not resumable" if state.status != "success" else None,
            )

        self._log(f"Resuming run {run_id} from step {state.current_index + 1}")
        self._warn_carried_over(state)
        # Reset state to running for resume
        state.status = "running"

        # Load step definitions for the plan
        step_defs = get_plan_steps(state.plan_name, project_root=str(self.project_root))

        return self._execute(state, step_defs)

    def status(self, run_id: str) -> dict[str, Any]:
        """Get the current status of a run."""
        state = RunState.load(run_id, self.project_root)
        return state.summary()

    def _warn_carried_over(self, state: RunState, tree_verified: bool = False) -> None:
        """Name the steps this invocation will NOT execute (issue #838 follow-up).

        A resumed run starts at ``current_index``, so every earlier step keeps
        the result it earned in a previous invocation - against a tree that may
        since have changed, because the usual reason to resume is that
        something was fixed. Those results are still reported, and until this
        warning they were reported in exactly the form of a step that had just
        run.

        Observed twice on one day: a cached ``test: SUCCESS (103 passed)`` on a
        run where pytest was never invoked, and a cached ``lint: SUCCESS`` for a
        tree whose linted source had been edited between the two runs. Both were
        caught by out-of-band knowledge - grepping for "Resuming" and counting
        pytest invocations, and remembering a hand-run ``make lint`` - neither of
        which is a property of the output.

        ``tree_verified`` (issue #804): true when this resume's tree_signature
        was compared against the current tree and matched, so "the tree may
        since have changed" is no longer a maybe - it's checked. The message
        softens accordingly; callers that can't verify (no git, old state
        file) get the original, more cautious wording.
        """
        carried = [
            record.step_id
            for record in state.step_records[: state.current_index]
            if record.status not in (StepStatus.PENDING, StepStatus.SKIPPED)
        ]
        if not carried:
            return
        if tree_verified:
            self._log(
                f"  NOTE: {len(carried)} step(s) will NOT run in this invocation "
                f"and keep their earlier result: {', '.join(carried)}. "
                "The tree is verified unchanged since then (issue #804) - "
                "those results still describe it."
            )
        else:
            self._log(
                f"  NOTE: {len(carried)} step(s) will NOT run in this invocation "
                f"and keep their earlier result: {', '.join(carried)}. "
                "If the tree changed since that run, those results are stale - "
                "they are marked carried_from_previous_run in step_details."
            )

    def _execute(
        self,
        state: RunState,
        step_defs: Optional[list[StepDef]] = None,
        tree_verified: bool = False,
    ) -> RunResult:
        """Execute steps from the current state index.

        ``tree_verified`` (issue #804): passed through from run() when this
        is a resume whose tree_signature matched - see RunResult.tree_verified.
        False on a fresh run (nothing carried, so it's meaningless) and on a
        resume that couldn't be verified.
        """
        # Where THIS invocation began, so the summary can distinguish a result
        # earned now from one carried over (issue #838 follow-up).
        executed_from = state.current_index
        if step_defs is None:
            step_defs = get_plan_steps(state.plan_name, project_root=str(self.project_root))

        # Materialize CPP_OFFLINE once per run (the probe is the only network
        # touch) so shell ``skip_if`` expressions can skip network steps in a
        # sandbox instead of hard-failing (issue #534, part #5).
        step_env = _build_step_env(self.project_root)
        step_env.setdefault("CPP_OFFLINE", "1" if _is_offline() else "0")

        context = {
            "project_root": str(self.project_root),
            "run_id": state.run_id,
            "plan": state.plan_name,
            "env": step_env,
            # Steps tee live output here; self.output is stderr by default, so
            # stdout stays clean for the machine-readable JSON result (issue #537).
            "output_stream": self.output,
        }

        completed = state.current_index
        self._executed_from = executed_from
        tests: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        reruns: list[dict[str, Any]] = []
        skipped: list[str] = []

        for idx in range(state.current_index, len(state.step_records)):
            step_def = step_defs[idx]
            step = ShellStep(step_def)

            # Check skip condition
            if step.should_skip(context):
                self._log(f"  [{idx + 1}/{len(step_defs)}] {step.id}: SKIPPED ({step.description})")
                state.mark_step_skipped(idx)
                state.save(self.project_root)
                skipped.append(step.id)
                completed = idx + 1
                continue

            # Execute step
            workers = step.resolve_pytest_workers(context)
            workers_suffix = ""
            if step.is_test_step():
                if workers is None:
                    workers_suffix = " [PYTEST_WORKERS=unset]"
                else:
                    value, source = workers
                    workers_suffix = f" [PYTEST_WORKERS={value} via {source}]"
            self._log(
                f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                f"running... ({step.description}){workers_suffix}"
            )
            state.mark_step_running(idx)
            state.save(self.project_root)

            result = step.execute_with_retry(context)

            # A test step's exit code says only that the runner did not error -
            # pytest exits 0 with every test skipped - so carry the counts it
            # reported and qualify the verdict with them (issue #621).
            outcome = result.tests
            outcome_dict = outcome.to_dict() if outcome else None
            if outcome_dict is not None:
                tests[step.id] = outcome_dict
            qualifier = f" ({outcome.summary()})" if outcome else ""

            if result.success:
                if outcome is not None and outcome.nothing_ran:
                    warnings.append(
                        f"{step.id}: exited 0 but executed NO tests ({outcome.summary()}) "
                        "- this gate proved nothing about the change"
                    )
                    self._log(
                        f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                        f"SUCCESS - NO TESTS RAN{qualifier}"
                    )
                elif outcome is not None and outcome.any_invocation_empty:
                    # The same hole as above, hidden by an aggregate (kyle
                    # issue #838). A step running the runner more than once -
                    # `make test` invoking pytest for two disjoint suites -
                    # can have one invocation collect nothing while the total
                    # looks healthy, so `nothing_ran` is False and the warning
                    # above stays silent about a half of the gate that proved
                    # nothing. Summing the counts makes the NUMBER honest and
                    # does not restore the guard; this does.
                    warnings.append(
                        f"{step.id}: {outcome.empty_invocations} of "
                        f"{outcome.invocations} test invocations executed NO tests "
                        f"({outcome.summary()} across all of them) - part of this "
                        "gate proved nothing about the change"
                    )
                    self._log(
                        f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                        f"SUCCESS - {outcome.empty_invocations} OF "
                        f"{outcome.invocations} INVOCATIONS RAN NO TESTS{qualifier}"
                    )
                else:
                    self._log(f"  [{idx + 1}/{len(step_defs)}] {step.id}: SUCCESS{qualifier}")
                state.mark_step_success(idx, result.output, tests=outcome_dict)
                state.save(self.project_root)
                completed = idx + 1
            else:
                # A step killed by its own budget is not a step that failed
                # (issue #812). Saying FAILED sends the reader to debug a
                # suite that never finished, and the #769 targeted re-run
                # below is meaningless for it: there are no failed ids to
                # re-run, only an unfinished run.
                timed_out = result.exit_code == TIMEOUT_EXIT_CODE
                if timed_out:
                    budget = step_def.timeout_seconds
                    self._log(
                        f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                        f"TIMED OUT after {budget}s (exit "
                        f"{TIMEOUT_EXIT_CODE}) - the step did not finish, so "
                        f"this says NOTHING about whether it would have "
                        f"passed. Raise the budget with "
                        f"CPP_GATE_TEST_TIMEOUT=<seconds> if the suite has "
                        f"simply outgrown it."
                    )
                else:
                    self._log(
                        f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                        f"FAILED (exit {result.exit_code}){qualifier}"
                    )
                failed_ids: list[str] = []
                if (
                    self.rerun_failed
                    and not timed_out
                    and step.is_test_step()
                    and outcome is not None
                    and outcome.framework == "pytest"
                    and outcome.failed + outcome.errors > 0
                ):
                    failed_ids = parse_failed_node_ids(
                        result.output
                    ) or parse_failed_node_ids(result.error)
                if failed_ids and len(failed_ids) <= MAX_RERUN_IDS:
                    id_count = len(failed_ids)
                    self._log(
                        f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                        f"RE-RUNNING {id_count} failed id(s) once (issue #769): "
                        f"{', '.join(failed_ids)}"
                    )
                    rerun_env = dict(context.get("env") or os.environ)
                    addopts = rerun_env.get("PYTEST_ADDOPTS", "").strip()
                    rerun_env["PYTEST_ADDOPTS"] = (
                        f"{addopts} --last-failed --last-failed-no-failures none".strip()
                    )
                    rerun_context = {**context, "env": rerun_env}
                    # The step's configured retry policy was spent by the first
                    # attempt; #769 permits exactly one targeted extra execution.
                    rerun_result = step.execute(rerun_context)
                    rerun_outcome = rerun_result.tests
                    if rerun_outcome is not None and rerun_outcome.nothing_ran:
                        rerun_verdict = "inconclusive"
                        self._log(
                            f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                            "RE-RUN INCONCLUSIVE - no tests ran; the original "
                            "failure stands"
                        )
                    elif rerun_result.success and rerun_outcome is not None:
                        rerun_verdict = "passed"
                        self._log(
                            f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                            f"RE-RUN PASSED - first attempt was a flake ({id_count} id(s))"
                        )
                    elif rerun_result.success:
                        rerun_verdict = "inconclusive"
                        self._log(
                            f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                            "RE-RUN INCONCLUSIVE - no test outcome was reported; "
                            "the original failure stands"
                        )
                    else:
                        rerun_verdict = "failed"
                        self._log(
                            f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                            "RE-RUN FAILED - the failure reproduces"
                        )
                    reruns.append(
                        {
                            "step": step.id,
                            "ids": failed_ids,
                            "outcome": rerun_verdict,
                            "first_attempt": outcome_dict,
                            "rerun": rerun_outcome.to_dict() if rerun_outcome else None,
                        }
                    )
                    if rerun_verdict == "passed":
                        # Keep the clean invocation's counts as the primary test
                        # record; the targeted counts live in the rerun channel.
                        state.mark_step_success(
                            idx, rerun_result.output, tests=outcome_dict
                        )
                        state.save(self.project_root)
                        completed = idx + 1
                        continue
                state.mark_step_failed(
                    idx, result.exit_code, result.output, result.error, tests=outcome_dict
                )
                state.save(self.project_root)

                return RunResult(
                    success=False,
                    run_id=state.run_id,
                    plan_name=state.plan_name,
                    steps_completed=completed,
                    steps_total=len(step_defs),
                    failed_step=step.id,
                    timed_out_step=step.id if timed_out else None,
                    timed_out_after=(
                        step_def.timeout_seconds if timed_out else None
                    ),
                    error=result.error or result.output,
                    tests=tests,
                    warnings=warnings,
                    reruns=reruns,
                    skipped_steps=skipped,
                    tree_verified=tree_verified,
                )

        # All steps completed successfully
        state.mark_complete()
        state.save(self.project_root)

        # A plan that reports a bare "completed successfully" is the sentence a
        # reviewer trusts as "safe to merge", so it must never be printed when the
        # run proved less than it appears to. Three ways it can:
        #   - a test step exited 0 having executed no tests (issue #621), and
        #   - a quality gate (lint/test/typecheck) was SKIPPED, so it verified
        #     nothing about the change (issue #628), and
        #   - a first-attempt test failure passed its one targeted re-run, which
        #     is green but explicitly not a clean pass (issue #769).
        skipped_gates = [s for s in skipped if s in GATE_STEP_IDS]
        qualifiers: list[str] = []
        if skipped_gates:
            qualifiers.append(
                f"SKIPPED GATES: {', '.join(skipped_gates)} "
                "(no Makefile target and no configured tool)"
            )
        if warnings:
            qualifiers.append("a test step executed no tests (#621)")
        passed_rerun_ids = [
            node_id
            for rerun in reruns
            if rerun["outcome"] == "passed"
            for node_id in rerun["ids"]
        ]
        if passed_rerun_ids:
            id_count = len(passed_rerun_ids)
            id_word = "id" if id_count == 1 else "ids"
            qualifiers.append(
                f"RE-RAN AND PASSED: {', '.join(passed_rerun_ids)} "
                f"({id_count} {id_word}) - a first attempt failed and the re-run "
                "cleared it; this run is NOT a clean pass"
            )

        if qualifiers:
            self._log(
                f"Plan '{state.plan_name}' completed WITH WARNINGS "
                f"({completed}/{len(step_defs)} steps) - {'; '.join(qualifiers)}"
            )
            for gate in skipped_gates:
                self._log(
                    f"  WARNING: {gate}: quality gate SKIPPED - it did not run and "
                    "proved nothing about the change"
                )
            for warning in warnings:
                self._log(f"  WARNING: {warning}")
        else:
            self._log(f"Plan '{state.plan_name}' completed successfully ({completed}/{len(step_defs)} steps)")

        # Capture the per-step detail BEFORE cleanup deletes the state file.
        # Order matters and is the whole point: reading it afterwards raises
        # FileNotFoundError, which is why `step_details` was previously
        # failure-only and why a resumed GREEN run could not say which of its
        # steps had actually run.
        success_details = state.summary(executed_from=executed_from)["steps"]
        success_carried = [
            entry["id"]
            for entry in success_details
            if entry.get("carried_from_previous_run")
        ]
        if success_carried:
            if tree_verified:
                self._log(
                    f"  NOTE: this run succeeded, and {len(success_carried)} step(s) "
                    f"kept a result from an earlier invocation: "
                    f"{', '.join(success_carried)}. The tree is verified unchanged "
                    "since then (issue #804) - those results still describe it."
                )
            else:
                self._log(
                    f"  NOTE: this run succeeded, but {len(success_carried)} step(s) "
                    f"kept a result from an earlier invocation: "
                    f"{', '.join(success_carried)}. If the tree changed since, those "
                    "results do not describe it."
                )

        # Clean up state file on success
        state.cleanup(self.project_root)

        return RunResult(
            success=True,
            step_details=success_details,
            carried_from_previous_run=success_carried,
            tree_verified=tree_verified,
            run_id=state.run_id,
            plan_name=state.plan_name,
            steps_completed=completed,
            steps_total=len(step_defs),
            tests=tests,
            warnings=warnings,
            reruns=reruns,
            skipped_steps=skipped,
        )

    def _log(self, message: str) -> None:
        """Log a message to stderr (not captured by JSON output)."""
        print(message, file=self.output, flush=True)


def run_plan(
    plan_name: str,
    project_root: Optional[str] = None,
    json_output: bool = True,
    rerun_failed: bool = False,
) -> int:
    """Execute a plan and return exit code.

    This is the main entry point called from the CLI.
    Outputs structured JSON to stdout for LLM consumption.
    """
    root = Path(project_root) if project_root else Path(".")
    # The gate helper resolves whatever CPP checkout is installed, which may
    # predate #769. Its opt-in must therefore be an env var an old runner ignores,
    # not a new CLI flag that old argparse rejects before any gate can run.
    rerun_failed = rerun_failed or os.environ.get("CPP_GATE_RERUN_FAILED") == "1"
    runner = DeterministicRunner(project_root=root, rerun_failed=rerun_failed)

    result = runner.run(plan_name)

    if json_output:
        # Structured output for LLM consumption
        output = result.to_dict()

        # Include step details from state. Emitted on SUCCESS as well as
        # failure (issue #838 follow-up): the carried-over marking added below
        # matters most on a GREEN resumed run, which is exactly the case the
        # old `if not result.success` guard excluded. A resumed success that
        # cannot show which of its steps actually ran this time is the report
        # that misleads - a failure is already being read carefully.
        if result.step_details:
            # Success path: captured before cleanup removed the state file.
            output["step_details"] = result.step_details
        else:
            # Failure path: the state file survives, so read it back and mark
            # carried-over steps the same way.
            try:
                state = RunState.load(result.run_id, root)
                executed_from = getattr(runner, "_executed_from", None)
                output["step_details"] = state.summary(
                    executed_from=executed_from
                )["steps"]
            except FileNotFoundError:
                pass
        carried = [
            entry["id"]
            for entry in output.get("step_details", [])
            if entry.get("carried_from_previous_run")
        ]
        if carried:
            output["carried_from_previous_run"] = carried
            # Only meaningful alongside a non-empty carry (issue #804):
            # whether the carry was backed by a tree_signature match
            # (RunResult.tree_verified) or merely assumed, as it was before
            # this field existed. flow-finish-gate.sh warns on carried-but-
            # unverified and stays quiet on carried-and-verified - the
            # distinction between "the mechanism proved this is safe" and
            # "we don't know, so we're telling you".
            output["tree_verified"] = result.tree_verified

        print(json.dumps(output, indent=2))

    return 0 if result.success else 1


def resume_run(
    run_id: str,
    project_root: Optional[str] = None,
    json_output: bool = True,
    rerun_failed: bool = False,
) -> int:
    """Resume a failed run and return exit code."""
    root = Path(project_root) if project_root else Path(".")
    # Match run_plan's cross-version-safe env opt-in when resuming the same gate.
    rerun_failed = rerun_failed or os.environ.get("CPP_GATE_RERUN_FAILED") == "1"
    runner = DeterministicRunner(project_root=root, rerun_failed=rerun_failed)

    result = runner.resume(run_id)

    if json_output:
        print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.success else 1


def show_status(run_id: str, project_root: Optional[str] = None) -> int:
    """Show status of a run."""
    root = Path(project_root) if project_root else Path(".")
    runner = DeterministicRunner(project_root=root)

    try:
        status = runner.status(run_id)
        print(json.dumps(status, indent=2))
        return 0
    except FileNotFoundError:
        print(json.dumps({"error": f"No run found: {run_id}"}))
        return 1
