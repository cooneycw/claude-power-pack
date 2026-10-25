"""Run state persistence for the deterministic CI/CD runner.

Persists step execution state to JSON files (see `runner_state_dir()`: inside
the target repository's git directory since issue #1409, `.claude/runs/`
when git is unavailable) so that failed runs can be resumed from the last
successful step. Exact-buffer producer metadata is documented in
``docs/cicd-resume-state-protocol.md``; it is not a cache-admission certificate.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
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
    # A gate that RAN, inside an aggregate that covers it (issue #1152). NOT
    # `skipped`: a skipped gate proved nothing and #628 warns on it, while a
    # subsumed one was executed as a prerequisite of a target that succeeded.
    # Collapsing them would make the cost fix report a false warn on every run.
    SUBSUMED = "subsumed"
    # A gate deferred to an aggregate that then FAILED, so it never ran at all
    # (issue #1152). Distinct from both: `subsumed` would claim it passed inside
    # the aggregate, and that is false the moment the aggregate stops early -
    # make halts at the first failing prerequisite, so everything after it in
    # the list was never reached.
    NOT_RUN = "not-run"


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
    # Coverage evidence for a NON-test step (issue #1027), e.g.
    # {"state": "zero", "units": 0, "tool": "ruff", ...}. ``tests`` above gives
    # the test step an "it ran and was not empty" assertion; this is the same
    # assertion for lint/typecheck/security_scan, which had only {id, status}
    # and so reported one identical green for a stage that examined everything
    # and one that examined nothing. Optional and defaulted for the same reason
    # ``tests`` is: a state file written before this field existed still loads.
    coverage: Optional[dict[str, Any]] = None
    # The aggregate step id that ran this gate, when status is SUBSUMED, and
    # why it did not run, when status is NOT_RUN (issue #1152). Carried so a
    # report NAMES the derivation instead of leaving a reader to infer it.
    # Optional and defaulted for the same reason the two above are: a state
    # file written before these fields existed still loads.
    subsumed_by: Optional[str] = None
    not_run_reason: Optional[str] = None

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


def _git_dir(root: Path) -> Optional[Path]:
    """The repository's real ``.git`` directory for ``root``, or ``None``.

    Never raises, never guesses (issue #1409): no git binary, ``root`` not a
    repository, or any subprocess failure all answer ``None`` the same way
    ``compute_tree_signature`` does below.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.strip()
    return Path(text) if text else None


def runner_state_dir(root: Path) -> Path:
    """Where ``RunState`` writes its bookkeeping (issue #1409).

    Prefers ``<git-dir>/cpp-runs`` - never inside the working tree, so it can
    never be picked up by ``git add -A`` and committed into a repository that
    does not ``.gitignore`` it. That happened for real in
    cooneycw/skillc#8 (Nit Store #864 comment 5847507826): a failed gate left
    an untracked ``.claude/runs/finish-cfaef128.json``, the next prescribed
    ``git add -A`` committed it, and a later successful run's cleanup then
    committed its DELETION too - gate bookkeeping and a deletion nobody did,
    both in the repository's history. The same ``git rev-parse
    --path-format=absolute --git-dir`` call already backs
    ``lib/cicd/evidence.py``'s and ``scripts/flow-plan-record.py``'s own
    out-of-tree state, for the identical reason.

    Falls back to the pre-#1409 ``<root>/.claude/runs`` when git is
    unavailable (no binary, not a repository, or any subprocess failure) -
    the same fail-open rule ``compute_tree_signature`` states below: an
    unanswerable "where" must never become a behavior change for an
    environment this runner never promised git to.

    Deliberately per-WORKTREE (``--git-dir``, not ``--git-common-dir``): a
    linked worktree's own ``.git/worktrees/<name>/`` does not survive
    ``git worktree remove``, matching this file's existing lifecycle exactly
    - the pre-#1409 location did not survive worktree removal either, since
    it lived inside the worktree's own working tree. `lib/cicd/evidence.py`'s
    execution-evidence record chooses the COMMON dir instead because IT is
    meant to outlive the worktree that produced it; this is resume
    bookkeeping for one run and is correctly gone with it.
    """
    git_dir = _git_dir(root)
    if git_dir is not None:
        return git_dir / "cpp-runs"
    return root / ".claude" / "runs"


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


# The one spelling of a step timestamp. `_now()` writes it and
# `_duration_seconds()` reads it; a change to either without the other would
# silently stop every duration being derivable (issue #1152).
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def _duration_seconds(started: Optional[str], finished: Optional[str]) -> Optional[float]:
    """Wall seconds between two ISO timestamps, or None if either is missing.

    None rather than 0.0 for an unstarted or unfinished step: a zero reads as
    "ran instantly", and a cost report that cannot tell that from "never ran"
    is the failure this field was added to remove.

    GRANULARITY IS ONE SECOND, because `_now()` writes whole seconds. A step
    faster than that reports 0.0, which is true to the nearest second and is
    NOT the same as None. Stated rather than implied: the figures this field
    exists for are minutes apart (390.77s against 233.44s), so second
    resolution is adequate - but a reader comparing two sub-second steps is
    comparing noise, and nothing in the number says so.
    """
    if not started or not finished:
        return None
    # Parsed with the EXACT format `_now()` writes, not fromisoformat: the
    # timestamps are this module's own output, so the format is known, and
    # matching it means a future change to `_now()` fails here loudly instead
    # of silently returning None for every step.
    try:
        began = datetime.strptime(started, _TIMESTAMP_FORMAT)
        ended = datetime.strptime(finished, _TIMESTAMP_FORMAT)
    except (ValueError, TypeError):
        return None
    return round((ended - began).total_seconds(), 2)


RESUME_STATE_MAX_BYTES = 64 * 1024 * 1024
_RESUME_PLAN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_RESUME_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_STATE_ERRORS = (OSError, UnicodeError, ValueError, KeyError, TypeError)


def _no_identity(status: str, reason: str) -> dict[str, Any]:
    return {"status": status, "file": None, "sha256": None, "bytes": None, "reason": reason}


class ResumeStateEvidence:
    """One invocation's exact I/O facts, never persisted state or writer authentication.

    The private exception reference identifies an ORIGINAL state-operation error
    at the JSON CLI boundary. It is never serialized or used for same-class
    exception matching. Actual stream validation belongs to the consumer.
    """

    def __init__(self, plan: Optional[str] = None):
        self.plan = plan
        self.consumed = _no_identity("unreadable", "not-observed")
        self.generated = _no_identity("none", "no-save")
        self.final_state: dict[str, Any] = {"status": "unreadable", "reason": "not-observed"}
        self.target: Optional[Path] = None
        self.logical_id: Any = None
        self.error: Optional[Exception] = None
        self.error_operation: Optional[str] = None
        self._cleanup_failed = False
        self._logical_unreadable = False

    def no_selected_input(self) -> None:
        self.consumed = _no_identity("none", "no-selected-state")
        self.target = None
        self.logical_id = None
        self._logical_unreadable = False
        self.final_state = {"status": "unreadable", "reason": "not-observed"}

    def clear_error(self) -> None:
        self.error = None
        self.error_operation = None

    @staticmethod
    def logical_leaf(logical_id: Any, path: Path) -> bool:
        # Validate the ORIGINAL id, not its basename. A normal filesystem path
        # may be absolute, but a run id may not redirect outside its state dir.
        return (isinstance(logical_id, str)
                and _RESUME_FILE.fullmatch(logical_id + ".json") is not None
                and logical_id + ".json" == path.name)

    def identity(self, status: str, path: Path, raw: bytes,
                 logical_id: Any = None) -> dict[str, Any]:
        if not self.logical_leaf(logical_id, path):
            return _no_identity("unreadable", "unsafe-logical-id")
        if len(raw) > RESUME_STATE_MAX_BYTES:
            return _no_identity("unreadable", "size-limit")
        return {"status": status, "file": path.name,
                "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw), "reason": None}

    def selected(self, state: RunState, path: Path, raw: bytes, logical_id: Any) -> None:
        self.plan = state.plan_name
        self.target = path
        self.logical_id = state.run_id
        self.consumed = self.identity("loaded", path, raw, logical_id)
        if (not self.logical_leaf(logical_id, path)
                or not self.logical_leaf(state.run_id, path)):
            self._logical_unreadable = True
            self.consumed = _no_identity("unreadable", "unsafe-logical-id")
        state._resume_evidence = self
        self.observe_remaining()

    def failed(self, error: Exception, operation: str, reason: str, slot: str) -> None:
        self.error = error
        self.error_operation = operation
        if slot == "consumed":
            self.consumed = _no_identity("unreadable", reason)
        elif slot == "generated":
            self.generated = _no_identity("unreadable", reason)
        else:
            self._cleanup_failed = True
            self.final_state = {"status": "unreadable", "reason": reason}

    def observe_remaining(self) -> None:
        if self._cleanup_failed or self.target is None:
            return
        try:
            info = self.target.lstat()
        except FileNotFoundError:
            self.final_state = {"status": "absent", "reason": None}
        except (OSError, ValueError):
            self.final_state = {"status": "unreadable", "reason": "presence-unreadable"}
        else:
            self.final_state = ({"status": "present", "reason": None} if stat.S_ISREG(info.st_mode)
                                else {"status": "unreadable", "reason": "presence-unreadable"})

    def snapshot(self) -> dict[str, Any]:
        self.observe_remaining()
        plan = self.plan if isinstance(self.plan, str) and _RESUME_PLAN.fullmatch(self.plan) else None
        consumed, generated, final = dict(self.consumed), dict(self.generated), dict(self.final_state)
        if (self._logical_unreadable or (self.target is not None
                and not self.logical_leaf(self.logical_id, self.target))):
            final = {"status": "unreadable", "reason": "unsafe-logical-id"}
        if self.plan is not None and plan is None:
            consumed = _no_identity("unreadable", "unsafe-logical-id")
            generated = _no_identity("unreadable", "unsafe-logical-id")
            final = {"status": "unreadable", "reason": "unsafe-logical-id"}
        return {"version": 1, "family": "cpp-run-state", "plan": plan,
                "consumed": consumed, "generated": generated, "final_state": final}


@dataclass
class RunState:
    """Persistent state for a runner execution.

    Saved to ``<run_id>.json`` under ``runner_state_dir()`` after each step
    completes. Enables resume from the last successful step.
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
    _resume_evidence: Optional[ResumeStateEvidence] = field(default=None, init=False, repr=False, compare=False)

    @classmethod
    def create(cls, plan_name: str, step_ids: list[str], *,
               evidence: Optional[ResumeStateEvidence] = None) -> RunState:
        """Create a new run state with pending steps."""
        run_id = f"{plan_name}-{uuid.uuid4().hex[:8]}"
        records = [StepRecord(step_id=sid) for sid in step_ids]
        state = cls(run_id=run_id, plan_name=plan_name, step_records=records, started_at=_now())
        state._resume_evidence = evidence or ResumeStateEvidence(plan_name)
        if evidence is None:
            state._resume_evidence.no_selected_input()
        return state

    def _resume_tracker(self) -> ResumeStateEvidence:
        if self._resume_evidence is None:
            self._resume_evidence = ResumeStateEvidence(self.plan_name)
        return self._resume_evidence

    def resume_state_evidence(self) -> dict[str, Any]:
        return self._resume_tracker().snapshot()

    @property
    def state_dir(self) -> Path:
        return runner_state_dir(Path("."))

    @property
    def state_file(self) -> Path:
        return self.state_dir / f"{self.run_id}.json"

    def save(self, project_root: Optional[Path] = None) -> Path:
        """Persist the exact serialized byte buffer; a partial write is an error."""
        evidence = self._resume_tracker()
        evidence.plan = self.plan_name
        evidence.logical_id = self.run_id
        evidence.clear_error()
        evidence._cleanup_failed = False
        evidence.target = None
        evidence.final_state = {"status": "unreadable", "reason": "not-observed"}
        evidence.generated = _no_identity("unreadable", "write-failed")
        reason = "write-failed"
        try:
            root = project_root or Path(".")
            state_dir = runner_state_dir(root)
            state_file = state_dir / f"{self.run_id}.json"
            evidence.target = state_file
            if not evidence.logical_leaf(self.run_id, state_file):
                evidence._logical_unreadable = True
            state_dir.mkdir(parents=True, exist_ok=True)
            reason = "serialization-failed"
            raw = json.dumps(self.to_dict(), indent=2).encode("utf-8")
            reason = "write-failed"
            written = state_file.write_bytes(raw)
            if written != len(raw):
                reason = "short-write"
                raise OSError("incomplete resume state write")
        except _STATE_ERRORS as error:
            evidence.failed(error, "save", reason, "generated")
            raise
        evidence.generated = evidence.identity("written", state_file, raw, self.run_id)
        evidence.observe_remaining()
        return state_file

    def cleanup(self, project_root: Optional[Path] = None) -> None:
        """Remove successful state without claiming a surviving cache."""
        evidence = self._resume_tracker()
        evidence.logical_id = self.run_id
        evidence.clear_error()
        try:
            root = project_root or Path(".")
            state_file = runner_state_dir(root) / f"{self.run_id}.json"
            evidence.target = state_file
            if state_file.exists():
                state_file.unlink()
        except _STATE_ERRORS as error:
            evidence.failed(error, "cleanup", "cleanup-failed", "final")
            raise
        evidence._cleanup_failed = False
        evidence.observe_remaining()

    def discard(self, project_root: Optional[Path] = None) -> None:
        """Remove state file because it was invalidated, not because it succeeded.

        Same file operation as cleanup() - both just delete the state file -
        but a different name at the call site (issue #804): the runner calls
        this when a resumable failed run's tree_signature no longer matches
        the current tree, so a reader of runner.py sees WHY the file is gone
        without following cleanup()'s docstring into the wrong story.
        """
        self.cleanup(project_root)

    def mark_step_pending(self, index: int) -> None:
        """Reopen a settled record so the step can be REPLAYED (issue #1166).

        Used on resume for a gate the failed run recorded NOT_RUN which the
        RESUMED tree's derivation no longer subsumes: nothing is going to run
        it, so it must run itself, and its old verdict must not survive into
        the new run's result.

        `not_run_reason` is cleared with the status, deliberately. It names the
        aggregate that failed last time, and a reason left attached to a record
        that is about to be re-executed would outlive the fact it described -
        the stale half of exactly the defect this issue is about.
        """
        record = self.step_records[index]
        record.status = StepStatus.PENDING
        record.not_run_reason = None
        record.started_at = None

    def mark_step_running(self, index: int) -> None:
        """Mark a step as running."""
        record = self.step_records[index]
        record.status = StepStatus.RUNNING
        record.started_at = _now()
        record.attempt += 1

    def mark_step_success(
        self,
        index: int,
        output: str = "",
        tests: Optional[dict[str, Any]] = None,
        coverage: Optional[dict[str, Any]] = None,
    ) -> None:
        """Mark a step as successful and advance the index."""
        record = self.step_records[index]
        record.status = StepStatus.SUCCESS
        record.output = _truncate(output, 5000)
        record.finished_at = _now()
        record.exit_code = 0
        record.tests = tests
        record.coverage = coverage
        # THE FRONTIER NEVER RETREATS (issue #1166, counter-model review).
        # A REPLAYED step sits BELOW `current_index` - that is what replay
        # means - so `index + 1` would move the resume point backwards and the
        # next invocation would re-run every settled step between the two.
        # Measured: replaying `lint` at index 0 set the frontier to 1, putting
        # `security_scan` (already green at index 2) back in the firing line.
        self.current_index = max(self.current_index, index + 1)

    def mark_step_failed(
        self,
        index: int,
        exit_code: int = 1,
        output: str = "",
        error: str = "",
        tests: Optional[dict[str, Any]] = None,
        coverage: Optional[dict[str, Any]] = None,
    ) -> None:
        """Mark a step as failed."""
        record = self.step_records[index]
        record.status = StepStatus.FAILED
        record.exit_code = exit_code
        record.output = _truncate(output, 5000)
        record.error = _truncate(error, 5000)
        record.finished_at = _now()
        record.tests = tests
        record.coverage = coverage
        self.status = "failed"

    def mark_step_skipped(self, index: int) -> None:
        """Mark a step as skipped."""
        record = self.step_records[index]
        record.status = StepStatus.SKIPPED
        record.finished_at = _now()
        # THE FRONTIER NEVER RETREATS (issue #1166, counter-model review).
        # A REPLAYED step sits BELOW `current_index` - that is what replay
        # means - so `index + 1` would move the resume point backwards and the
        # next invocation would re-run every settled step between the two.
        # Measured: replaying `lint` at index 0 set the frontier to 1, putting
        # `security_scan` (already green at index 2) back in the firing line.
        self.current_index = max(self.current_index, index + 1)

    def mark_step_subsumed(self, index: int, aggregate_id: str) -> None:
        """This gate RAN, as a prerequisite of ``aggregate_id`` (issue #1152).

        Only ever called after that aggregate SUCCEEDED. On a failure the
        aggregate stopped at its first failing prerequisite and everything
        after it was never reached, so the honest record is NOT_RUN.
        """
        record = self.step_records[index]
        record.status = StepStatus.SUBSUMED
        record.subsumed_by = aggregate_id
        record.finished_at = _now()
        # A SETTLED RECORD KEEPS NO FAILURE STORY (issue #1166, counter-model
        # review). A re-deferred gate arrives here carrying the reason the
        # PREVIOUS run recorded, and leaving it attached publishes a record
        # that says both `status: subsumed` and `not_run_reason: verify
        # failed` - two accounts of one gate, one of them describing a run that
        # has since been superseded. Measured in `step_details` before this.
        record.not_run_reason = None

    def mark_step_not_run(self, index: int, reason: str) -> None:
        """Deferred to an aggregate that failed, so it never ran (issue #1152)."""
        record = self.step_records[index]
        record.status = StepStatus.NOT_RUN
        record.not_run_reason = reason
        record.finished_at = _now()

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
    def load(cls, run_id: str, project_root: Optional[Path] = None, *,
             evidence: Optional[ResumeStateEvidence] = None) -> RunState:
        """Parse the exact buffer whose identity is retained; preserve original errors."""
        observed = evidence or ResumeStateEvidence()
        observed.logical_id = run_id
        observed.clear_error()
        reason = "input-unreadable"
        try:
            root = project_root or Path(".")
            state_file = runner_state_dir(root) / f"{run_id}.json"
            observed.target = state_file
            if not observed.logical_leaf(run_id, state_file):
                observed._logical_unreadable = True
            if not state_file.exists():
                raise FileNotFoundError(f"No run state found: {state_file}")
            raw = state_file.read_bytes()
            reason = "parse-failed"
            state = cls.from_dict(json.loads(raw.decode("utf-8")))
        except _STATE_ERRORS as error:
            observed.failed(error, "load", reason, "consumed")
            raise
        observed.selected(state, state_file, raw, run_id)
        return state

    @classmethod
    def find_latest(cls, plan_name: str, project_root: Optional[Path] = None, *,
                    evidence: Optional[ResumeStateEvidence] = None) -> Optional[RunState]:
        """Select the same failed candidate as before, retaining its actual buffer."""
        observed = evidence or ResumeStateEvidence(plan_name)
        observed.plan = plan_name
        observed.clear_error()
        observed.no_selected_input()
        try:
            root = project_root or Path(".")
            state_dir = runner_state_dir(root)
            if not state_dir.exists():
                return None
            candidates = sorted(state_dir.glob(f"{plan_name}-*.json"),
                                key=lambda path: path.stat().st_mtime, reverse=True)
        except _STATE_ERRORS as error:
            observed.failed(error, "select", "selection-unreadable", "consumed")
            raise
        unreadable = False
        for path in candidates:
            try:
                raw = path.read_bytes()
                state = cls.from_dict(json.loads(raw.decode("utf-8")))
            except (json.JSONDecodeError, KeyError, TypeError):
                # Preserve the existing skip decision, but not a false clean scan.
                unreadable = True
                continue
            except _STATE_ERRORS as error:
                observed.target = path
                observed.failed(error, "select", "input-unreadable", "consumed")
                raise
            if state.status == "failed":
                observed.selected(state, path, raw, path.stem)
                return state
        if unreadable:
            observed.consumed = _no_identity("unreadable", "selection-unreadable")
        return None

    def summary(
        self,
        executed_from: Optional[int] = None,
        settled_in_this_run: Optional[set[int]] = None,
    ) -> dict[str, Any]:
        """Return a summary suitable for JSON output to the LLM.

        ``executed_from`` is the step index the CURRENT invocation started at
        (issue #838 follow-up). Records before it were produced by an earlier
        invocation and are carried over: their command did not run this time,
        and the tree may have changed since it did. Without the distinction a
        carried-over ``success`` renders identically to one just earned, which
        is how a stale ``lint: SUCCESS`` was reported for a tree whose lint
        input had been edited between the two runs.

        ``settled_in_this_run`` names indices BELOW ``executed_from`` that this
        invocation nevertheless settled (issue #1166): a gate the failed run
        left NOT_RUN, which the resume re-deferred to an aggregate that ran
        here, or replayed outright. Index order stops being a sufficient test
        for "carried" the moment a resume can reach backwards, and calling such
        a step carried is wrong in both directions - it did run in this
        invocation, and there was no earlier result to carry. Measured before
        this: a fail-fix-resume whose three gates were freshly settled
        ``subsumed`` by a passing aggregate still reported
        ``warn (carried, unverified: ...)``, so a genuinely green retry read as
        action-required - the #1166 rejection in a second costume.
        """
        settled = settled_in_this_run or set()
        steps_summary = []
        for index, r in enumerate(self.step_records):
            entry: dict[str, Any] = {"id": r.step_id, "status": r.status.value}
            # WALL TIME PER STEP (issue #1152). The runner published no timing
            # at all, which made it the wrong instrument for a cost question:
            # every before/after figure in that issue had to be measured
            # OUTSIDE the gate, and a later reader could not check the claim
            # against the artifact that made it. Derived from timestamps the
            # record already carried rather than by adding state. ADDITIVE -
            # readers anchor on `id` and `status`, and the shell's awk matches
            # the id line only.
            duration = _duration_seconds(r.started_at, r.finished_at)
            if duration is not None:
                entry["duration_seconds"] = duration
            if r.subsumed_by:
                entry["subsumed_by"] = r.subsumed_by
            if r.not_run_reason:
                entry["not_run_reason"] = r.not_run_reason
            if (
                executed_from is not None
                and index < executed_from
                and index not in settled
            ):
                # Only meaningful for a record that HAS a result; a pending
                # step before the resume point has nothing to be stale about.
                if r.status not in (StepStatus.PENDING, StepStatus.SKIPPED):
                    entry["executed_in_this_run"] = False
                    entry["carried_from_previous_run"] = True
            if r.tests:
                # A green test step whose suite executed nothing is the #621
                # false green - carry the counts so the summary can say so.
                entry["tests"] = r.tests
            if r.coverage:
                # The same for a non-test gate (issue #1027). Carried even when
                # the state is "unknown": the reported defect is that three of
                # four stages emitted {id, status} and left a reader unable to
                # tell a stage that examined everything from one that examined
                # nothing. An explicit "unknown" is the answer to that - it says
                # the stage is unproven rather than letting "success" imply it
                # is not.
                entry["coverage"] = r.coverage
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
    return time.strftime(_TIMESTAMP_FORMAT, time.localtime())


def _truncate(s: str, max_len: int) -> str:
    """Truncate string to max_len, preserving the tail (most useful for errors)."""
    if len(s) <= max_len:
        return s
    return "...[truncated]...\n" + s[-(max_len - 20):]
