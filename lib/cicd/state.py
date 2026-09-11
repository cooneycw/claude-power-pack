"""Run state persistence for the deterministic CI/CD runner.

Persists step execution state to JSON files in .claude/runs/ so that
failed runs can be resumed from the last successful step.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
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
    # Test-runner counts for a test step (issue #621), e.g.
    # {"passed": 312, "skipped": 66, ...}. Optional and defaulted so state files
    # written before this field existed still load.
    tests: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepRecord:
        data["status"] = StepStatus(data["status"])
        # Ignore keys a newer/older writer added so a stale state file on disk
        # resumes instead of dying on an unexpected keyword.
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def compute_tree_signature(project_root: Path) -> Optional[str]:
    """Content signature of the working tree, or None when it can't be trusted.

    Used to tell a genuine crash-resume (the tree a failed run left behind is
    still the tree we're about to resume against) apart from a repair-resume
    (the tree changed - usually because the failure was fixed - so any step
    result earned against the OLD tree no longer describes the one we're
    about to skip re-running it against). Issue #804.

    Deliberately a CONTENT hash (via a scratch git index + ``git write-tree``,
    scoped to tracked + untracked-but-not-gitignored files), not a cheaper
    ``git status`` (paths + M/A/D codes, no content). A status-only signature
    was considered and rejected: it cannot distinguish a file that was
    modified once from one modified TWICE between the two runner invocations
    - both show the identical status line ``M path``, so the signature would
    match and the stale result would be carried anyway. That is not a rare
    edge case, it is this fleet's most common repair loop: a gate fails on an
    uncommitted change, the SAME file is edited again to fix it, nothing is
    committed until the gate goes green. A status-only signature would have
    shipped as a fix for #804 and fixed nothing in exactly the case #804 was
    filed for.

    The scratch index is created via ``GIT_INDEX_FILE`` so this never touches
    the caller's real index or working tree - safe to call from inside a live
    ``run()`` without side effects on the checkout it's inspecting.

    ``.claude/runs/`` - this runner's OWN state directory - is excluded
    unconditionally, not left to the target project's ``.gitignore``. It
    lives inside ``project_root`` and a failed run writes its state file
    there before this function is ever asked to verify a resume, so without
    the exclusion the file `find_latest()` is about to read back would
    itself be new input to the hash: signature-at-persist-time computed
    before the file existed, signature-at-resume-time computed after -
    mismatched on every single resume regardless of whether the TREE changed
    at all, silently deleting the crash-safety this feature exists for. CPP's
    own ``.gitignore`` happens to cover this path, which is exactly why this
    bug did not show up testing against a CPP checkout and only surfaced
    against a bare scratch repo with no ``.gitignore`` - a target project
    cannot be trusted to have made the same choice, so the exclusion does not
    depend on it.

    Returns None - "cannot verify" - rather than raising, on any of: no
    ``git`` binary, ``project_root`` is not a git repository, or any
    subprocess/OS failure (timeout, permissions). Callers MUST treat None as
    unverifiable and fall back to the pre-#804 unconditional-resume behavior;
    this function never turns "I don't know" into "nothing changed".
    """
    if shutil.which("git") is None:
        return None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
            subprocess.run(
                ["git", "-C", str(project_root), "add", "-A"],
                env=env,
                check=True,
                capture_output=True,
                timeout=30,
            )
            # Drop the runner's own bookkeeping from the scratch index before
            # hashing it - see the docstring above. --ignore-unmatch so a run
            # with no .claude/runs/ yet (nothing has failed here before) is
            # not an error.
            subprocess.run(
                [
                    "git", "-C", str(project_root),
                    "rm", "-r", "--cached", "--ignore-unmatch", "-q",
                    "--", ".claude/runs",
                ],
                env=env,
                check=True,
                capture_output=True,
                timeout=30,
            )
            result = subprocess.run(
                ["git", "-C", str(project_root), "write-tree"],
                env=env,
                check=True,
                capture_output=True,
                timeout=30,
                text=True,
            )
    except (subprocess.SubprocessError, OSError):
        return None
    signature = result.stdout.strip()
    return signature or None


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
    # Content signature of the working tree at the moment this run first
    # became resumable (issue #804), from compute_tree_signature(). Compared
    # against a freshly computed signature before a resume is honored: equal
    # means a genuine crash left the tree untouched, so carried-over step
    # results are still valid; different means the tree changed - the usual
    # reason to resume is that something was fixed - so those results
    # describe a tree that no longer exists. None on a state file written
    # before this field existed, or when the signature could not be computed
    # (no git, not a repo); either way the caller must treat it as
    # unverifiable and fall back to the pre-#804 unconditional resume.
    tree_signature: Optional[str] = None

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

    def discard(self, project_root: Optional[Path] = None) -> None:
        """Remove state file because it was invalidated, not because it succeeded.

        Same file operation as cleanup() - both just delete the state file -
        but a different name at the call site (issue #804): the runner calls
        this when a resumable failed run's tree_signature no longer matches
        the current tree, so a reader of runner.py sees WHY the file is gone
        without following cleanup()'s docstring into the wrong story.
        """
        self.cleanup(project_root)

    def mark_step_running(self, index: int) -> None:
        """Mark a step as running."""
        record = self.step_records[index]
        record.status = StepStatus.RUNNING
        record.started_at = _now()
        record.attempt += 1

    def mark_step_success(
        self, index: int, output: str = "", tests: Optional[dict[str, Any]] = None
    ) -> None:
        """Mark a step as successful and advance the index."""
        record = self.step_records[index]
        record.status = StepStatus.SUCCESS
        record.output = _truncate(output, 5000)
        record.finished_at = _now()
        record.exit_code = 0
        record.tests = tests
        self.current_index = index + 1

    def mark_step_failed(
        self,
        index: int,
        exit_code: int = 1,
        output: str = "",
        error: str = "",
        tests: Optional[dict[str, Any]] = None,
    ) -> None:
        """Mark a step as failed."""
        record = self.step_records[index]
        record.status = StepStatus.FAILED
        record.exit_code = exit_code
        record.output = _truncate(output, 5000)
        record.error = _truncate(error, 5000)
        record.finished_at = _now()
        record.tests = tests
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
            "tree_signature": self.tree_signature,
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

    def summary(self, executed_from: Optional[int] = None) -> dict[str, Any]:
        """Return a summary suitable for JSON output to the LLM.

        ``executed_from`` is the step index the CURRENT invocation started at
        (issue #838 follow-up). Records before it were produced by an earlier
        invocation and are carried over: their command did not run this time,
        and the tree may have changed since it did. Without the distinction a
        carried-over ``success`` renders identically to one just earned, which
        is how a stale ``lint: SUCCESS`` was reported for a tree whose lint
        input had been edited between the two runs.
        """
        steps_summary = []
        for index, r in enumerate(self.step_records):
            entry: dict[str, Any] = {"id": r.step_id, "status": r.status.value}
            if executed_from is not None and index < executed_from:
                # Only meaningful for a record that HAS a result; a pending
                # step before the resume point has nothing to be stale about.
                if r.status not in (StepStatus.PENDING, StepStatus.SKIPPED):
                    entry["executed_in_this_run"] = False
                    entry["carried_from_previous_run"] = True
            if r.tests:
                # A green test step whose suite executed nothing is the #621
                # false green - carry the counts so the summary can say so.
                entry["tests"] = r.tests
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
