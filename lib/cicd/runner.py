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
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TextIO

from .coverage import SCOPE_COMPONENT, ZERO
from .outcomes import parse_failed_node_ids
from .state import RunState, StepStatus, compute_tree_signature
from .steps import (
    # GATE_STEP_IDS is deliberately NOT imported here any more (#1155). The
    # runner had one consumer of the global union - the #628 skipped-gate
    # filter - and it now reads each step's own `gate` flag, which is the
    # plan-scoped and correct question. The union survives in steps.py for
    # `step_model_to_step_def`, where inheriting gate-ness BY ID is the point.
    TIMEOUT_EXIT_CODE,
    ShellStep,
    StepDef,
    dropped_gate_ids,
    get_plan_steps,
    plan_gate_ids,
    reset_make_prerequisite_cache,
    subsumed_gate_ids,
)


def _coverage_summary(cover: dict[str, Any]) -> str:
    """Render a PERSISTED coverage dict the way ``StageCoverage.summary`` does.

    A resumed run reads coverage back from the state file as a plain dict, so
    the warning it rebuilds has to say the same sentence the live path says.
    Rehydrating a ``StageCoverage`` would be the tidier shape and is avoided on
    purpose: the state file may have been written by an older CPP whose field
    set differs, and a constructor would raise on the extra keys rather than
    degrade - turning a resume into a crash over a warning string.
    """
    units = cover.get("units")
    unit_name = cover.get("unit_name", "unit")
    component = cover.get("component") or ""
    subject = f"the {component} " if component else ""
    plural = "" if units == 1 else "s"
    if cover.get("state") == ZERO:
        return f"{subject}examined NO {unit_name}{plural}".lstrip()
    return f"{subject}examined {units} {unit_name}{plural}".lstrip()


def _failed_ids_from_both_streams(output: str | None, error: str | None) -> list[str]:
    """Failed/errored node ids from stdout AND stderr, first-seen order, deduped.

    Not `parse(output) or parse(error)`: that reads one stream and discards the
    other the moment the first yields anything. pytest writes its FAILED summary
    to stdout, but a wrapper (make, a tee, a plugin) can route lines to either
    stream, and a retry that reports a new id on stdout and the retried id on
    stderr would be graded as "did not reproduce" with the reproduction sitting
    unread on the other stream (issue #915, cross-model review).
    """
    seen: set[str] = set()
    ids: list[str] = []
    for text in (output, error):
        for node_id in parse_failed_node_ids(text or ""):
            if node_id not in seen:
                seen.add(node_id)
                ids.append(node_id)
    return ids

# Variables the runner launcher injects (or a parent venv leaks) that must NOT
# reach child step processes: PYTHONPATH is added so ``python -m lib.cicd`` can
# import itself but would shadow the target project's imports; VIRTUAL_ENV /
# PYTHONHOME inherited from the CPP venv pin child ``uv run`` to the wrong
# interpreter and hide the project's own dev deps (e.g. pytest-cov), so the
# child must re-resolve the project venv from scratch (issue #534).
RUNNER_STRIP_VARS = frozenset({"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"})

#: What the #769 re-run records when the failed ids pass on their own.
#:
#: NOT "passed" (issue #900). The re-run changes two variables at once - WHEN it
#: ran, and WHAT ran before it - so passing alone is the signature of a flake AND
#: of an order-dependent real failure. The token names what the experiment
#: established: isolation, and nothing about the cause.
#:
#: The narration fix beside it closes what a HUMAN reads in the moment. This
#: closes what a LATER READER greps, which is a different population at a
#: different time - #900's own evidence is a defect that survived WEEKS, by which
#: point nobody is reading terminal output and the record is all there is.
#:
#: `scripts/flow-finish-gate.sh` matches this string with an ANCHORED awk regex,
#: so the two must stay equal. A drift that misses the shell side does not fail
#: loudly - the gate stops emitting RERUN_PASSED and silently reports `ok`, which
#: is #900's exact symptom restored. `tests/test_runner.py` pins both directions.
RERUN_PASSED_IN_ISOLATION = "passed-in-isolation"

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


def _default_uv_cache_dir() -> Path:
    """Where child `uv run` steps cache packages when the caller names nowhere.

    UID-SCOPED, and that is the whole change from the old `/tmp/uv-cache`
    literal (issue #1113, bandit B108). A fixed name in a world-writable
    directory is pre-creatable by any other local user on the host, and a
    package cache is executable content - whoever owns the directory decides
    what `uv` unpacks out of it on the next run.

    Unlike the deploy lock in `lib/cicd/deploy/guardrails.py`, which is
    deliberately shared and is hardened at the open instead, a cache has no
    cross-process contract to preserve, so scoping it costs nothing.

    STABLE across calls on purpose: `tempfile.mkdtemp()` would clear the same
    finding and silently turn every run into a cold download, with nothing else
    going red. `tests/test_runner.py` pins both properties.

    Still under the temp dir rather than `~/.cache`: the reason the default
    exists at all is that a sandboxed `~/.cache` is read-only (#534).

    THE UID SUFFIX ALONE IS NOT THE FIX, and saying so was the first version's
    mistake (counter-model review, #1113). `/tmp/uv-cache-1000` is every bit as
    predictable as `/tmp/uv-cache`; a uid in the name says who SHOULD own it,
    not who does. Any other local user can still create that exact directory
    first and own what `uv` unpacks out of it. So the name is only half of it
    and `_ensure_private_dir` below is the other half: create it 0700 and
    refuse to hand `uv` a directory that is a symlink, or that somebody else
    owns.
    """
    return Path(tempfile.gettempdir()) / f"uv-cache-{os.getuid()}"


def _ensure_private_dir(path: Path) -> Path:
    """Create `path` owned by us and mode 0700, or refuse to use it.

    The predictable-path hazard bandit's B108 names is not that the name is
    guessable - it is that a guessable name in a world-writable directory can
    already be OCCUPIED when we get there. Checking the directory we actually
    got is the part that answers it.

    Returns `path` on success. Raises `RuntimeError` on a hijacked directory
    rather than silently falling back: a cache supplied by somebody else is
    executable content, and quietly using a different path would leave the
    operator with a mystery slow run instead of a stated refusal.

    `lstat`, not `stat`, so a symlink is caught rather than followed to a
    directory that passes every other check. The residual race - the directory
    being swapped between this check and `uv` opening it - is not closable from
    here without holding a descriptor `uv` never receives; it is far narrower
    than the standing pre-creation it replaces, and it is named rather than
    implied.
    """
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        raise RuntimeError(
            f"uv cache path {path} is a symlink; refusing to use it"
        )
    if not stat.S_ISDIR(st.st_mode):
        raise RuntimeError(
            f"uv cache path {path} is not a directory; refusing to use it"
        )
    if st.st_uid != os.getuid():
        raise RuntimeError(
            f"uv cache path {path} is owned by uid {st.st_uid}, not {os.getuid()}; "
            f"refusing to use a package cache another user controls"
        )
    # OWNERSHIP IS NOT EXCLUSIVITY (counter-model review, second pass). `mkdir`
    # applies `mode` only when it CREATES the directory, so a pre-existing
    # `0777` cache - left by an older run under a permissive umask - passes the
    # owner check and is still writable by everybody on the host, which is the
    # whole hazard. Refuse rather than `chmod`: tightening the mode would keep
    # whatever contents were already placed there, and a cache is trusted for
    # its contents, not its permissions.
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise RuntimeError(
            f"uv cache path {path} is mode {stat.S_IMODE(st.st_mode):04o} and so is "
            f"writable by other users; refusing to use it. Remove it and let this "
            f"run recreate it 0700."
        )
    return path


def _build_step_env(project_root: Optional[Path] = None) -> dict[str, str]:
    """Build a sanitized copy of os.environ for child step processes.

    Makes the child environment sandbox-aware (issue #534):
    - strips launcher/parent-venv leakage (see RUNNER_STRIP_VARS),
    - defaults UV_CACHE_DIR to a writable, uid-scoped path (sandbox ~/.cache is
      read-only; see `_default_uv_cache_dir`),
    - pins UV_PYTHON to the target project's required floor so child ``uv run``
      steps do not fall back to a stale system interpreter.
    All defaults use ``setdefault`` so an explicit caller env always wins.

    Kept pure (no network) so it stays cheap and hermetic; the offline probe
    that materializes CPP_OFFLINE runs once in the runner's execute loop.
    """
    env = {k: v for k, v in os.environ.items() if k not in RUNNER_STRIP_VARS}
    # NOT `env.setdefault(..., _ensure_private_dir(...))` (counter-model review,
    # second pass): Python evaluates the default argument eagerly, so that form
    # created and validated the DEFAULT cache even when the caller had already
    # chosen one - and a hijacked default then aborted a run that was never
    # going to use it. That contradicts this function's own contract two
    # paragraphs up: "an explicit caller env always wins".
    if "UV_CACHE_DIR" not in env:
        env["UV_CACHE_DIR"] = str(_ensure_private_dir(_default_uv_cache_dir()))
    floor = _project_python_floor(project_root)
    if floor:
        env.setdefault("UV_PYTHON", floor)
    return env


_MAKE_FAILING_TARGET = re.compile(
    r"^make(?P<nested>\[\d+\])?: \*\*\* \[[^\]]*?:\s*(?P<target>[A-Za-z0-9_.-]+)\]",
    re.MULTILINE,
)


def _failing_prerequisite(output: str) -> Optional[str]:
    """The target make named when it stopped, or None (issue #1152).

    `make: *** [Makefile:121: lint] Error 1` names the prerequisite that
    failed, which is the useful half of an aggregate failure - "verify failed"
    sends a reader to read all 29 of its prerequisites. Returns None when make
    said nothing matchable, and the caller then reports the aggregate alone
    rather than guessing a target: a WRONG prerequisite name is worse than no
    name, because it sends the reader somewhere specific and innocent.
    """
    if not output:
        return None
    matches = list(_MAKE_FAILING_TARGET.finditer(output))
    if not matches:
        return None
    # THE TERMINAL DIAGNOSTIC, NOT THE FIRST (counter-model review, post-merge).
    # `search` took the first match anywhere in the combined streams, and a
    # recipe that tolerates a nested failure - `$(MAKE) something || true`, or a
    # fixture deliberately exercising one - prints `make[1]: *** [...] Error 1`
    # BEFORE the real failure. The helper then named a neighbour's target, which
    # is precisely the "wrong name is worse than none" this function's own
    # docstring warns about, sending a reader somewhere specific and innocent.
    #
    # Prefer the OUTERMOST make - the one with no `[n]` depth marker, which is
    # the invocation the runner itself started - and among those the LAST, which
    # is the one it stopped on. Fall back to the last nested diagnostic only
    # when the outer make printed none.
    outer = [m for m in matches if not m.group("nested")]
    return (outer or matches)[-1].group("target")


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
    # Coverage evidence per NON-test gate, e.g. {"lint": {"state": "zero", ...}}
    # (issue #1027). The counterpart of `tests` above for the three gates that
    # had no such channel: without it `lint`, `typecheck` and `security_scan`
    # reported {id, status} and one identical green whether they examined the
    # whole tree or nothing in it.
    coverage: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Which ids in THIS run's plan are quality gates (issue #1147). Carried on
    # the result rather than recomputed in `to_dict` because the answer needs
    # the RESOLVED step list, which only the executing code has: see
    # `steps.plan_gate_ids` for why the global GATE_STEP_IDS is the wrong set
    # to publish here.
    gates: list[str] = field(default_factory=list)
    # Gates the BUILT-IN plan of this name declares that the resolved plan does
    # not contain (issue #1155). `None` means NOT APPLICABLE - no built-in plan
    # of this name, so there is nothing to reconcile against - which is a
    # different fact from "reconciled, none missing" and must not render as it.
    dropped_gates: Optional[list[str]] = None
    # Gate id -> the aggregate that ran it (issue #1152). Published so the
    # report NAMES the derivation: a reader seeing three gates absent from the
    # executed list must be able to see WHY without re-deriving it.
    subsumed_gates: dict[str, str] = field(default_factory=dict)
    # When an AGGREGATE gate failed and make named the prerequisite it stopped
    # at (issue #1152). `verify` has 29 prerequisites here, so "verify failed"
    # asks a reader to search all of them; this is the one make pointed at.
    # None when make said nothing matchable - a wrong name is worse than none,
    # because it sends the reader somewhere specific and innocent.
    failed_prerequisite: Optional[str] = None
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
    # means the gate verified nothing about the change, so flow-finish-gate.sh
    # reads this to report `warn` and NAME the skipped gates rather than flatten
    # the run to a bare `ok`. Which steps those are is DECLARED on the step and
    # derived into GATE_STEP_IDS - it was the literal {lint, test, typecheck}
    # until #890, which is how `security_scan` sat outside it for three
    # releases.
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
        if self.coverage:
            # Top level and keyed by step id, for the same reason `timed_out_step`
            # is (issue #812's note below): the gate reads this JSON, so a field
            # that never reaches it cannot be acted on however carefully it was
            # set. It also reaches `step_details`, but that is the per-step
            # record - this is the roll-up the gate greps.
            d["coverage"] = self.coverage
        if self.warnings:
            d["warnings"] = self.warnings
        if self.reruns:
            d["reruns"] = self.reruns
        if self.skipped_steps:
            d["skipped"] = self.skipped_steps
        # WHICH IDS ARE GATES, emitted so the shell does not have to restate them
        # (issue #1147). `GATE_STEP_IDS` is derived from each step's `gate=`
        # declaration - #890 made it so after a hand-written literal drifted -
        # but it never reached this JSON, so `scripts/flow-finish-gate.sh` kept
        # a SECOND copy as a regex alternation it could not import. That copy is
        # now deleted and the shell filters on this field.
        #
        # Same reason as `coverage` and `timed_out_step` above, and the third
        # instance of it: the gate reads this JSON, so a field that never
        # reaches it cannot be acted on however carefully it was set (#812).
        #
        # Emitted UNCONDITIONALLY, unlike its neighbours, and that asymmetry is
        # the point: the shell fails closed when the field is absent, so an
        # empty set has to be distinguishable from a runner too old to send one.
        # A conditional emit would make "no gates ran" and "this runner does not
        # say" the same bytes.
        d["gates"] = sorted(self.gates)
        # Emitted UNCONDITIONALLY, with `null` preserved, for the same reason
        # `gates` is: the shell has to tell three states apart - reconciled and
        # clean (`[]`), reconciled and missing (`[...]`), and not applicable
        # (`null`) - and a field absent for one of them collapses it into "this
        # runner is too old to say" (#1155).
        # Always emitted, `{}` included: "nothing was subsumed" and "this runner
        # does not deduplicate" must not be the same bytes, for the same reason
        # `gates` is unconditional (#1147).
        d["subsumed_gates"] = dict(sorted(self.subsumed_gates.items()))
        if self.failed_prerequisite:
            d["failed_prerequisite"] = self.failed_prerequisite
        d["dropped_gates"] = (
            None if self.dropped_gates is None else sorted(self.dropped_gates)
        )
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

    def _resolve_deferred(
        self,
        state: RunState,
        deferred: dict[int, str],
        finished_step_id: str,
        *,
        aggregate_ok: bool,
        failing_prerequisite: Optional[str] = None,
    ) -> None:
        """Settle gates deferred to ``finished_step_id`` now that it has run."""
        mine = [i for i, agg in deferred.items() if agg == finished_step_id]
        if not mine:
            return
        for index in mine:
            if aggregate_ok:
                state.mark_step_subsumed(index, finished_step_id)
            else:
                at = (
                    f" at prerequisite {failing_prerequisite}"
                    if failing_prerequisite
                    else ""
                )
                state.mark_step_not_run(
                    index, f"{finished_step_id} failed{at}"
                )
            del deferred[index]
        names = ", ".join(state.step_records[i].step_id for i in mine)
        if aggregate_ok:
            self._log(
                f"  SUBSUMED: {names} ran as prerequisite(s) of "
                f"`{finished_step_id}`, which passed"
            )
        else:
            self._log(
                f"  NOT RUN: {names} were deferred to `{finished_step_id}`, "
                f"which FAILED - make stops at its first failing prerequisite, "
                f"so these were never reached"
            )

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
                gates=plan_gate_ids(
                    state.plan_name,
                    get_plan_steps(state.plan_name, project_root=str(self.project_root)),
                ),
                dropped_gates=dropped_gate_ids(
                    state.plan_name,
                    get_plan_steps(state.plan_name, project_root=str(self.project_root)),
                ),
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
        coverage: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        reruns: list[dict[str, Any]] = []
        skipped: list[str] = []
        # Gates an aggregate in this plan already runs (issue #1152), with
        # WHICH ones answered by asking make rather than reading the makefile
        # (issue #1165): a textual reader cannot evaluate `ifeq`, so it names
        # prerequisites make will never run, and a broken gate then passes as
        # `subsumed`.
        # A FRESH ANSWER PER RUN. `make_prerequisites` memoises to keep
        # `make -p -n` to one execution per aggregate, and that memo spans the
        # PROCESS: a resumed run, or a second run in one interpreter, would
        # otherwise suppress gates according to a makefile read earlier and
        # possibly since changed (counter-model review).
        reset_make_prerequisite_cache()
        subsumable, subsumption_refusals = subsumed_gate_ids(
            state.plan_name, step_defs, str(self.project_root)
        )
        # WHY a gate was NOT subsumed, said rather than left to inference. A
        # reader seeing three gates deduplicated and a fourth not must see the
        # reason without re-deriving it - and the reasons ARE the two refusals
        # that keep this safe: make could not be asked, or the step does not run
        # the prerequisite's command.
        for refusal in subsumption_refusals:
            self._log(f"  NOT SUBSUMED: {refusal}")
        # index -> aggregate id, for gates deferred to an aggregate that has
        # not run yet. Resolved when that aggregate finishes, and ONLY then:
        # whether these ran is a fact about the aggregate's outcome, not about
        # the derivation.
        deferred: dict[int, str] = {}

        for idx in range(state.current_index, len(state.step_records)):
            step_def = step_defs[idx]
            # An aggregate that something was deferred TO inherits the need to
            # parse a test summary from whatever it subsumes (issue #1152).
            _covers_test = any(
                agg == step_def.id
                and ShellStep(step_defs[i]).is_test_step()
                for i, agg in deferred.items()
            )
            step = ShellStep(step_def, covers_test_step=_covers_test)

            # DEFERRED TO AN AGGREGATE (issue #1152). Not executed here and
            # deliberately not marked yet: the honest status depends on whether
            # the aggregate succeeds, and it has not run. Left PENDING until
            # then, so an interrupted run records the truth - deferred and
            # unresolved - rather than a pass nobody earned.
            if step.id in subsumable:
                aggregate = subsumable[step.id]
                self._log(
                    f"  [{idx + 1}/{len(step_defs)}] {step.id}: DEFERRED to "
                    f"`{aggregate}`, which lists it as a direct prerequisite"
                )
                deferred[idx] = aggregate
                completed = idx + 1
                continue

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

            # A non-test gate's exit code says the tool did not error, not that
            # it looked at anything (issue #1027). `ruff check .` on a tree with
            # no Python files warns on stderr, prints "All checks passed!" on
            # stdout and exits 0 - so without this the step result of a stage
            # that examined NOTHING is identical to one that examined the whole
            # tree, which is the reported defect.
            cover = result.coverage
            cover_dict = cover.to_dict() if cover else None
            if cover_dict is not None:
                coverage[step.id] = cover_dict
            if cover is not None and cover.stated:
                qualifier = f" ({cover.summary()})"

            if result.success:
                if cover is not None and cover.examined_nothing:
                    # Deliberately BEFORE the test branches rather than after:
                    # they are mutually exclusive (coverage is parsed only for
                    # non-test steps), so the order is about which reads first,
                    # and a stage that examined nothing is the more fundamental
                    # fact - there is no point qualifying findings from a scan
                    # that had nothing to find them in.
                    # The CLAIM is bounded by what the measurement covered
                    # (issue #1027, cross-model review). A stage-wide number
                    # licenses "this gate proved nothing"; a component number
                    # does not - `security_scan` runs gitignore, permissions
                    # and debug-flag checks that have their own subjects and
                    # were never counted here, so saying the gate proved
                    # nothing would be a conclusion about checks this number
                    # never looked at.
                    if cover.scope == SCOPE_COMPONENT:
                        scope_clause = (
                            f"that part of the '{step.id}' gate proved nothing "
                            "about the change; its other checks are not measured "
                            "by this number"
                        )
                    else:
                        scope_clause = (
                            "this gate proved nothing about the change"
                        )
                    warnings.append(
                        f"{step.id}: exited 0 but {cover.summary()} "
                        f"({cover.tool}) - {scope_clause} (issue #1027)"
                    )
                    self._log(
                        f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                        f"SUCCESS - EXAMINED NOTHING{qualifier}"
                    )
                elif cover is not None and cover.any_invocation_empty:
                    # The same hole hidden by an aggregate, the shape kyle #838
                    # found for test steps: a stage whose command runs the tool
                    # over two paths can have one run examine nothing while the
                    # total looks healthy, so `examined_nothing` is False and
                    # the warning above stays silent about the half that proved
                    # nothing.
                    warnings.append(
                        f"{step.id}: {cover.empty_invocations} of "
                        f"{cover.invocations} invocations examined NOTHING "
                        f"({cover.summary()} across all of them) - part of this "
                        "gate proved nothing about the change"
                    )
                    self._log(
                        f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                        f"SUCCESS - {cover.empty_invocations} OF "
                        f"{cover.invocations} INVOCATIONS EXAMINED NOTHING"
                        f"{qualifier}"
                    )
                elif outcome is not None and outcome.nothing_ran:
                    warnings.append(
                        f"{step.id}: exited 0 but executed NO tests ({outcome.summary()}) "
                        "- this gate proved nothing about the change (issue #621)"
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
                elif (
                    outcome is None
                    and step.is_test_step()
                    and (result.output.strip() or result.error.strip())
                ):
                    # A parse that examined nothing reads UNKNOWN, not clean
                    # (issue #952, first implementation ticket #939). Silence
                    # here used to be indistinguishable from a healthy result:
                    # the step logged a bare SUCCESS, `tests` gained no entry,
                    # and a reader could not tell "the suite reported 312
                    # passed" from "nothing in either stream was recognizable
                    # as a summary". Those are different facts and only one of
                    # them is evidence.
                    #
                    # Both streams were examined and neither yielded a
                    # summary, so the denominator is stated rather than left
                    # to inference.
                    #
                    # SCOPED to a step that actually PRODUCED output, and the
                    # bound is deliberate. A test step that printed nothing at
                    # all (`command: true`) is not a suite whose result is
                    # unknown - there is no result to be unknown about - and
                    # #628/#890 pinned that shape as a bare success. Warning
                    # there would fire on the normal case, which is how a
                    # warning stops being read.
                    #
                    # The bound does NOT cover a runner CPP cannot parse (Go,
                    # Rust, a shell harness): that produces output, so it warns
                    # on every run. That is a policy question wider than #939
                    # and is flagged as a residual rather than settled here.
                    warnings.append(
                        f"{step.id}: exited 0 but NO test summary could be parsed "
                        "from stdout or stderr - this gate's result is UNKNOWN, "
                        "not clean"
                    )
                    self._log(
                        f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                        "SUCCESS - NO TEST OUTCOME PARSED (UNKNOWN, not clean)"
                    )
                else:
                    self._log(f"  [{idx + 1}/{len(step_defs)}] {step.id}: SUCCESS{qualifier}")
                state.mark_step_success(
                    idx, result.output, tests=outcome_dict, coverage=cover_dict
                )
                # The aggregate finished GREEN, so everything it lists as a
                # prerequisite did run and did pass (issue #1152). Only now is
                # `subsumed` an honest record.
                self._resolve_deferred(state, deferred, step.id, aggregate_ok=True)
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
                    failed_ids = _failed_ids_from_both_streams(
                        result.output, result.error
                    )
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
                    # Attribution of the re-run's failures to the retried ids.
                    # Populated only on the invocation-failed path below; empty
                    # on the others, and recorded either way (issue #915).
                    reproduced: list[str] = []
                    appeared: list[str] = []
                    unobserved: list[str] = []
                    if rerun_outcome is not None and rerun_outcome.nothing_ran:
                        rerun_verdict = "inconclusive"
                        self._log(
                            f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                            "RE-RUN INCONCLUSIVE - no tests ran; the original "
                            "failure stands"
                        )
                    elif (
                        rerun_outcome is not None
                        and rerun_outcome.any_invocation_empty
                    ):
                        # The merge across streams (issue #939) made this
                        # reachable and it must not be allowed to clear a real
                        # failure. A re-run whose pytest invocation collected
                        # nothing while an UNRELATED suite passed now totals a
                        # healthy count - `nothing_ran` is False - so without
                        # this branch the runner would record
                        # `passed-in-isolation` against ids that were never
                        # executed. Before the merge the empty pytest summary
                        # won outright and the run read inconclusive, which was
                        # the correct verdict for the wrong reason.
                        #
                        # #900's rule, one layer down: the experiment cannot
                        # support the conclusion, so the conclusion is not
                        # drawn.
                        rerun_verdict = "inconclusive"
                        self._log(
                            f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                            f"RE-RUN INCONCLUSIVE - {rerun_outcome.empty_invocations} "
                            f"of {rerun_outcome.invocations} re-run invocations "
                            "executed NO tests, so the retried ids were not "
                            "necessarily among those that ran; the original "
                            "failure stands"
                        )
                    elif rerun_result.success and rerun_outcome is not None:
                        rerun_verdict = RERUN_PASSED_IN_ISOLATION
                        # Say what the re-run ESTABLISHED, which is narrower than
                        # what it used to claim (issue #900).
                        #
                        # The re-run changes TWO variables at once: when it ran,
                        # and what ran before it. A flake is explained by the
                        # first; an order-dependent real failure is explained by
                        # the second. Passing alone is the signature of BOTH, so
                        # the experiment cannot separate them and its result
                        # cannot support the word "flake".
                        #
                        # This line used to say "first attempt was a flake", and
                        # that is the sentence that did the damage rather than the
                        # SUCCESS status. flow-finish-gate.sh has reported
                        # `warn (rerun passed: ...)` since #769 landed, offering
                        # both causes - but this line printed FIRST, named one
                        # cause confidently, and so read as the explanation for
                        # the warning underneath it. The warn was not missing; it
                        # was DEFUSED. An order-dependent failure in kyle survived
                        # weeks of this, cleared every time it fired.
                        #
                        # `flow-pr-watch.sh` already states the principle this
                        # restores: it "does not decide what is a flake. That
                        # stays a human/critic judgment."
                        self._log(
                            f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                            f"RE-RUN PASSED IN ISOLATION - {id_count} id(s) pass "
                            "when run alone. That is NOT evidence of a flake: an "
                            "order-dependent real failure passes alone too, and "
                            "this re-run cannot tell the two apart (issue #900). "
                            "NOT a clean pass - do not summarize as 'tests passed'"
                        )
                    elif rerun_result.success:
                        rerun_verdict = "inconclusive"
                        self._log(
                            f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                            "RE-RUN INCONCLUSIVE - no test outcome was reported; "
                            "the original failure stands"
                        )
                    else:
                        # Grade on the NAMED IDS, not the invocation (issue #915).
                        #
                        # This branch fires on `rerun_result.success` being false,
                        # which is the re-run INVOCATION's exit code. The re-run
                        # re-executes the whole test target, so any unrelated
                        # failure anywhere in it made the gate announce "the
                        # failure reproduces" and name the retried id - an id that
                        # had PASSED. Worse than a plain false negative: it points
                        # a person at an innocent test while hiding the failure
                        # that is genuinely there.
                        #
                        # Observed (kyle #1176): the retried id passed on re-run,
                        # a DIFFERENT test failed in the OTHER phase because a
                        # commit landed in another repository between the two
                        # invocations, and the verdict named the innocent id.
                        #
                        # The third state is the one the two-way answer threw
                        # away, and it is the most informative of the three: a
                        # test that passes and then fails inside one gate run,
                        # with no edit to the tree, points OUTSIDE the tree.
                        rerun_failed_ids = _failed_ids_from_both_streams(
                            rerun_result.output, rerun_result.error
                        )
                        retried = set(failed_ids)
                        rerun_set = set(rerun_failed_ids)
                        reproduced = [i for i in failed_ids if i in rerun_set]
                        unobserved = [i for i in failed_ids if i not in rerun_set]
                        appeared = [i for i in rerun_failed_ids if i not in retried]
                        # Three facts, reported independently (cross-model review
                        # on #915 found the first cut collapsed them):
                        #  - a retried id in the re-run's failed set REPRODUCED;
                        #  - an id that failed on re-run but was not retried
                        #    APPEARED, and is named whether or not anything
                        #    reproduced - the mixed case used to drop it;
                        #  - a retried id ABSENT from the failed set is
                        #    UNOBSERVED, not passed: a collection error in another
                        #    module, or fail-fast, leaves it unexecuted, and its
                        #    absence proves nothing about it.
                        # A changed failing set is a changed failing set. Its
                        # cause - a move in the tree, in another repo, or an
                        # order/race inside this one - is not something the
                        # detector measured, so it is not something it says.
                        appeared_note = (
                            f"; and {len(appeared)} failure(s) not retried "
                            f"appeared: {', '.join(appeared)} - a SEPARATE "
                            "finding, cause undetermined"
                            if appeared else ""
                        )
                        if reproduced:
                            rerun_verdict = "failed"
                            self._log(
                                f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                                f"RE-RUN FAILED - the failure reproduces: "
                                f"{', '.join(reproduced)}{appeared_note}"
                            )
                        elif appeared:
                            rerun_verdict = "new-failures"
                            self._log(
                                f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                                f"RE-RUN: the retried id(s) were not among the "
                                f"re-run's reported failures ({', '.join(unobserved)}) "
                                "- their reproduction status is UNKNOWN, not "
                                f"established as passing{appeared_note}. The "
                                "original failure stands (issue #915)"
                            )
                        else:
                            # The invocation failed and no ids could be attributed
                            # to it. Distinct from both above, and NOT a claim that
                            # anything reproduced.
                            rerun_verdict = "failed-unattributed"
                            self._log(
                                f"  [{idx + 1}/{len(step_defs)}] {step.id}: "
                                "RE-RUN FAILED - but no failing id could be read "
                                "from its output, so whether the original failure "
                                "reproduced is UNKNOWN; the original failure stands"
                            )
                    reruns.append(
                        {
                            "step": step.id,
                            "ids": failed_ids,
                            "outcome": rerun_verdict,
                            "reproduced": reproduced,
                            "appeared": appeared,
                            "unobserved": unobserved,
                            "first_attempt": outcome_dict,
                            "rerun": rerun_outcome.to_dict() if rerun_outcome else None,
                        }
                    )
                    if rerun_verdict == RERUN_PASSED_IN_ISOLATION:
                        # Keep the clean invocation's counts as the primary test
                        # record; the targeted counts live in the rerun channel.
                        state.mark_step_success(
                            idx,
                            rerun_result.output,
                            tests=outcome_dict,
                            coverage=cover_dict,
                        )
                        state.save(self.project_root)
                        completed = idx + 1
                        continue
                state.mark_step_failed(
                    idx,
                    result.exit_code,
                    result.output,
                    result.error,
                    tests=outcome_dict,
                    coverage=cover_dict,
                )
                # The aggregate stopped early, so make never reached the
                # prerequisites after the failing one and NONE of the deferred
                # gates can be claimed as run (issue #1152). `subsumed` here
                # would be the exact false green this whole family of guards
                # exists to refuse, produced by the COST fix.
                self._resolve_deferred(
                    state,
                    deferred,
                    step.id,
                    aggregate_ok=False,
                    failing_prerequisite=_failing_prerequisite(
                        f"{result.output}\n{result.error or ''}"
                    ),
                )
                state.save(self.project_root)

                return RunResult(
                    success=False,
                    run_id=state.run_id,
                    plan_name=state.plan_name,
                    steps_completed=completed,
                    steps_total=len(step_defs),
                    gates=plan_gate_ids(state.plan_name, step_defs),
                    dropped_gates=dropped_gate_ids(state.plan_name, step_defs),
                    subsumed_gates={
                        r.step_id: r.subsumed_by
                        for r in state.step_records
                        if r.subsumed_by
                    },
                    # CARRIED ON THE FAILURE PATH TOO (issue #1152). It was
                    # only on the success result, so a run that failed inside
                    # an aggregate published no per-step records at all - and
                    # the `not-run (verify failed at prerequisite lint)` rows
                    # are exactly what a reader needs THERE. A reader told only
                    # "verify failed" has 29 prerequisites to search.
                    step_details=state.summary(executed_from=executed_from)["steps"],
                    failed_step=step.id,
                    # ONLY WHEN IT NAMES SOMETHING ELSE. make prints the same
                    # `*** [Makefile:N: lint]` line whether lint failed as an
                    # aggregate's prerequisite or as the step itself, and
                    # reporting `fail (at prerequisite lint)` for a failed
                    # `lint` STEP tells a reader to look for an aggregate that
                    # is not there. The field exists to save a search through
                    # 29 prerequisites; where there is no search, it is noise.
                    failed_prerequisite=(
                        lambda named: named if named and named != step.id else None
                    )(_failing_prerequisite(f"{result.output}\n{result.error or ''}")),
                    timed_out_step=step.id if timed_out else None,
                    timed_out_after=(
                        step_def.timeout_seconds if timed_out else None
                    ),
                    error=result.error or result.output,
                    tests=tests,
                    coverage=coverage,
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
        #   - a quality gate was SKIPPED, so it verified nothing about the
        #     change (issue #628; which steps are gates is declared on the step
        #     and derived into GATE_STEP_IDS, issue #890), and
        #   - a first-attempt test failure passed its one targeted re-run, which
        #     is green but explicitly not a clean pass (issue #769).
        # The step's OWN flag, not the global union (issue #1155). GATE_STEP_IDS
        # answers "is this id a gate anywhere"; the question here is whether
        # skipping it in THIS plan proved nothing, which is plan-scoped. Since
        # #1155 a manifest-resolved StepDef inherits the flag by id, so the
        # per-step answer exists and is the narrower, correct one.
        _gate_ids = {d.id for d in step_defs if d.gate}
        skipped_gates = [s for s in skipped if s in _gate_ids]
        qualifiers: list[str] = []
        if skipped_gates:
            qualifiers.append(
                f"SKIPPED GATES: {', '.join(skipped_gates)} "
                "(no Makefile target and no configured tool)"
            )
        if warnings:
            # Do NOT name a cause here (issue #939). `warnings` carries three
            # distinct findings and only the first is "executed no tests":
            # #621's "exited 0 having executed nothing", #838's "SOME
            # invocation executed nothing while the total looked healthy", and
            # #939's "no summary could be parsed from either stream, so this
            # is UNKNOWN". Asserting the #621 sentence for all of them makes
            # this line false for the other two - an instrument claiming more
            # than its input supports, which is the defect #939 fixes one
            # layer down.
            #
            # #838 already falsified it before #939 widened the collection;
            # nothing pinned the string, so nothing said so.
            word = "qualification" if len(warnings) == 1 else "qualifications"
            qualifiers.append(f"{len(warnings)} test step {word} (see warnings)")
        passed_rerun_ids = [
            node_id
            for rerun in reruns
            if rerun["outcome"] == RERUN_PASSED_IN_ISOLATION
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
        # Re-derive the coverage roll-up and its warnings from the PERSISTED
        # records, not only from the steps this invocation executed (issue
        # #1027, cross-model review). `coverage` and `warnings` start empty on
        # every invocation, so after a resume a zero-coverage step earned
        # earlier survived in `step_details` and vanished from both - and the
        # gate reads the roll-up. A run whose lint examined nothing, failed
        # later on a transient, and then resumed cleanly on a verified-unchanged
        # tree therefore reported `ok`/0: the #1027 false green, restored by
        # resume, for the exact stage #1027 is about.
        for entry in success_details:
            carried_cover = entry.get("coverage")
            if not carried_cover or entry["id"] in coverage:
                continue
            coverage[entry["id"]] = carried_cover
            summary = _coverage_summary(carried_cover)
            tool = carried_cover.get("tool", "unknown")
            if carried_cover.get("scope") == SCOPE_COMPONENT:
                scope_clause = (
                    f"that part of the '{entry['id']}' gate proved nothing about "
                    "the change; its other checks are not measured by this number"
                )
            else:
                scope_clause = "this gate proved nothing about the change"
            if carried_cover.get("state") == ZERO:
                warnings.append(
                    f"{entry['id']}: exited 0 but {summary} ({tool}) - "
                    f"{scope_clause} "
                    "(issue #1027, result carried from an earlier invocation)"
                )
            elif carried_cover.get("empty_invocations", 0) > 0:
                # The partially-empty carry (cross-model review, second pass).
                # Rebuilding only the `zero` case dropped this one: a stage with
                # one empty invocation and one populated invocation is `covered`,
                # so its warning vanished across a resume while the equivalent
                # live run kept it - the same roll-up hole, one state over.
                warnings.append(
                    f"{entry['id']}: {carried_cover['empty_invocations']} of "
                    f"{carried_cover.get('invocations', 0)} invocations examined "
                    f"NOTHING ({summary} across all of them) - part of this gate "
                    "proved nothing about the change "
                    "(issue #1027, result carried from an earlier invocation)"
                )
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

        resolved_subsumed = {
            r.step_id: r.subsumed_by for r in state.step_records if r.subsumed_by
        }

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
            gates=plan_gate_ids(state.plan_name, step_defs),
            dropped_gates=dropped_gate_ids(state.plan_name, step_defs),
            subsumed_gates=resolved_subsumed,
            tests=tests,
            coverage=coverage,
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
