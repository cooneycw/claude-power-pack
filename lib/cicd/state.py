"""Run state persistence for the deterministic CI/CD runner.

Persists step execution state to JSON files in .claude/runs/ so that
failed runs can be resumed from the last successful step.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class StepStatus(str, Enum):
    """Status of a single step in a run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepRecord:
    """Persisted record of a step's execution."""

    step_id: str
    status: StepStatus = StepStatus.PENDING
    exit_code: int = 0
    output: str = ""
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    attempt: int = 0
    max_attempts: int = 1

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepRecord:
        data["status"] = StepStatus(data["status"])
        return cls(**data)


@dataclass
class RunState:
    """Persistent state for a runner execution.

    Saved to .claude/runs/<run_id>.json after each step completes.
    Enables resume from the last successful step.
    """

    run_id: str
    plan_name: str
    step_records: list[StepRecord] = field(default_factory=list)
    current_index: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str = "running"  # running, success, failed

    @classmethod
    def create(cls, plan_name: str, step_ids: list[str]) -> RunState:
        """Create a new run state with pending steps."""
        run_id = f"{plan_name}-{uuid.uuid4().hex[:8]}"
        records = [StepRecord(step_id=sid) for sid in step_ids]
        return cls(
            run_id=run_id,
            plan_name=plan_name,
            step_records=records,
            started_at=_now(),
        )

    @property
    def state_dir(self) -> Path:
        return Path(".claude/runs")

    @property
    def state_file(self) -> Path:
        return self.state_dir / f"{self.run_id}.json"

    def save(self, project_root: Optional[Path] = None) -> Path:
        """Persist state to JSON file."""
        root = project_root or Path(".")
        state_dir = root / ".claude" / "runs"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / f"{self.run_id}.json"
        state_file.write_text(json.dumps(self.to_dict(), indent=2))
        return state_file

    def cleanup(self, project_root: Optional[Path] = None) -> None:
        """Remove state file on successful completion."""
        root = project_root or Path(".")
        state_file = root / ".claude" / "runs" / f"{self.run_id}.json"
        if state_file.exists():
            state_file.unlink()

    def mark_step_running(self, index: int) -> None:
        """Mark a step as running."""
        record = self.step_records[index]
        record.status = StepStatus.RUNNING
        record.started_at = _now()
        record.attempt += 1

    def mark_step_success(self, index: int, output: str = "") -> None:
        """Mark a step as successful and advance the index."""
        record = self.step_records[index]
        record.status = StepStatus.SUCCESS
        record.output = _truncate(output, 5000)
        record.finished_at = _now()
        record.exit_code = 0
        self.current_index = index + 1

    def mark_step_failed(self, index: int, exit_code: int = 1, output: str = "", error: str = "") -> None:
        """Mark a step as failed."""
        record = self.step_records[index]
        record.status = StepStatus.FAILED
        record.exit_code = exit_code
        record.output = _truncate(output, 5000)
        record.error = _truncate(error, 5000)
        record.finished_at = _now()
        self.status = "failed"

    def mark_step_skipped(self, index: int) -> None:
        """Mark a step as skipped."""
        record = self.step_records[index]
        record.status = StepStatus.SKIPPED
        record.finished_at = _now()
        self.current_index = index + 1

    def mark_complete(self) -> None:
        """Mark the entire run as successful."""
        self.status = "success"
        self.finished_at = _now()

    def can_retry(self, index: int) -> bool:
        """Check if a step has retries remaining."""
        record = self.step_records[index]
        return record.attempt < record.max_attempts

    def pending_steps(self) -> list[tuple[int, StepRecord]]:
        """Return steps that still need execution."""
        return [
            (i, r)
            for i, r in enumerate(self.step_records)
            if i >= self.current_index and r.status in (StepStatus.PENDING, StepStatus.FAILED)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "plan_name": self.plan_name,
            "step_records": [r.to_dict() for r in self.step_records],
            "current_index": self.current_index,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunState:
        records = [StepRecord.from_dict(r) for r in data.pop("step_records", [])]
        return cls(step_records=records, **data)

    @classmethod
    def load(cls, run_id: str, project_root: Optional[Path] = None) -> RunState:
        """Load state from a JSON file."""
        root = project_root or Path(".")
        state_file = root / ".claude" / "runs" / f"{run_id}.json"
        if not state_file.exists():
            raise FileNotFoundError(f"No run state found: {state_file}")
        data = json.loads(state_file.read_text())
        return cls.from_dict(data)

    @classmethod
    def find_latest(cls, plan_name: str, project_root: Optional[Path] = None) -> Optional[RunState]:
        """Find the most recent run state for a plan (if any failed runs exist)."""
        root = project_root or Path(".")
        state_dir = root / ".claude" / "runs"
        if not state_dir.exists():
            return None
        candidates = sorted(state_dir.glob(f"{plan_name}-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in candidates:
            try:
                state = cls.from_dict(json.loads(path.read_text()))
                if state.status == "failed":
                    return state
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return None

    def summary(self) -> dict[str, Any]:
        """Return a summary suitable for JSON output to the LLM."""
        steps_summary = []
        for r in self.step_records:
            entry: dict[str, Any] = {"id": r.step_id, "status": r.status.value}
            if r.status == StepStatus.FAILED:
                entry["error"] = r.error
                entry["exit_code"] = r.exit_code
                entry["attempt"] = r.attempt
            steps_summary.append(entry)
        return {
            "run_id": self.run_id,
            "plan": self.plan_name,
            "status": self.status,
            "current_step": (
                self.step_records[self.current_index].step_id
                if self.current_index < len(self.step_records)
                else None
            ),
            "steps": steps_summary,
        }


def _now() -> str:
    """ISO timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _truncate(s: str, max_len: int) -> str:
    """Truncate string to max_len, preserving the tail (most useful for errors)."""
    if len(s) <= max_len:
        return s
    return "...[truncated]...\n" + s[-(max_len - 20):]
