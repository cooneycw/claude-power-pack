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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TextIO

from .state import RunState
from .steps import ShellStep, StepDef, get_plan_steps


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
    ):
        self.project_root = project_root or Path(".")
        self.output = output or sys.stderr

    def run(self, plan_name: str, step_defs: Optional[list[StepDef]] = None) -> RunResult:
        """Execute a named plan from scratch or resume a failed run.

        If a failed run exists for this plan, it will be resumed automatically.
        """
        # Check for existing failed run to resume
        existing = RunState.find_latest(plan_name, self.project_root)
        if existing:
            self._log(f"Resuming failed run {existing.run_id} from step {existing.current_index + 1}")
            return self._execute(existing, step_defs)

        # Load step definitions
        if step_defs is None:
            step_defs = get_plan_steps(plan_name)

        # Create new run state
        step_ids = [s.id for s in step_defs]
        state = RunState.create(plan_name, step_ids)

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
        # Reset state to running for resume
        state.status = "running"

        # Load step definitions for the plan
        step_defs = get_plan_steps(state.plan_name)

        return self._execute(state, step_defs)

    def status(self, run_id: str) -> dict[str, Any]:
        """Get the current status of a run."""
        state = RunState.load(run_id, self.project_root)
        return state.summary()

    def _execute(self, state: RunState, step_defs: Optional[list[StepDef]] = None) -> RunResult:
        """Execute steps from the current state index."""
        if step_defs is None:
            step_defs = get_plan_steps(state.plan_name)

        context = {
            "project_root": str(self.project_root),
            "run_id": state.run_id,
            "plan": state.plan_name,
        }

        completed = state.current_index

        for idx in range(state.current_index, len(state.step_records)):
            step_def = step_defs[idx]
            step = ShellStep(step_def)

            # Check skip condition
            if step.should_skip(context):
                self._log(f"  [{idx + 1}/{len(step_defs)}] {step.id}: SKIPPED ({step.description})")
                state.mark_step_skipped(idx)
                state.save(self.project_root)
                completed = idx + 1
                continue

            # Execute step
            self._log(f"  [{idx + 1}/{len(step_defs)}] {step.id}: running... ({step.description})")
            state.mark_step_running(idx)
            state.save(self.project_root)

            result = step.execute_with_retry(context)

            if result.success:
                self._log(f"  [{idx + 1}/{len(step_defs)}] {step.id}: SUCCESS")
                state.mark_step_success(idx, result.output)
                state.save(self.project_root)
                completed = idx + 1
            else:
                self._log(f"  [{idx + 1}/{len(step_defs)}] {step.id}: FAILED (exit {result.exit_code})")
                state.mark_step_failed(idx, result.exit_code, result.output, result.error)
                state.save(self.project_root)

                return RunResult(
                    success=False,
                    run_id=state.run_id,
                    plan_name=state.plan_name,
                    steps_completed=completed,
                    steps_total=len(step_defs),
                    failed_step=step.id,
                    error=result.error or result.output,
                )

        # All steps completed successfully
        state.mark_complete()
        state.save(self.project_root)

        self._log(f"Plan '{state.plan_name}' completed successfully ({completed}/{len(step_defs)} steps)")

        # Clean up state file on success
        state.cleanup(self.project_root)

        return RunResult(
            success=True,
            run_id=state.run_id,
            plan_name=state.plan_name,
            steps_completed=completed,
            steps_total=len(step_defs),
        )

    def _log(self, message: str) -> None:
        """Log a message to stderr (not captured by JSON output)."""
        print(message, file=self.output, flush=True)


def run_plan(plan_name: str, project_root: Optional[str] = None, json_output: bool = True) -> int:
    """Execute a plan and return exit code.

    This is the main entry point called from the CLI.
    Outputs structured JSON to stdout for LLM consumption.
    """
    root = Path(project_root) if project_root else Path(".")
    runner = DeterministicRunner(project_root=root)

    result = runner.run(plan_name)

    if json_output:
        # Structured output for LLM consumption
        output = result.to_dict()

        # Include step details from state if run failed
        if not result.success:
            try:
                state = RunState.load(result.run_id, root)
                output["step_details"] = state.summary()["steps"]
            except FileNotFoundError:
                pass

        print(json.dumps(output, indent=2))

    return 0 if result.success else 1


def resume_run(run_id: str, project_root: Optional[str] = None, json_output: bool = True) -> int:
    """Resume a failed run and return exit code."""
    root = Path(project_root) if project_root else Path(".")
    runner = DeterministicRunner(project_root=root)

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
