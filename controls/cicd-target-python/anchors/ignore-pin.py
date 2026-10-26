from __future__ import annotations

RUNNER_STRIP_VARS = frozenset({"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"})

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

class TargetPythonPolicyError(ValueError):
    """The target declared a pin whose contents cannot be observed safely."""

MAX_TARGET_PYTHON_PIN_BYTES = 4096

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
    # A target's own interpreter file is more specific than its compatibility
    # floor. Leave a readable pin for uv; refuse unreadable policy explicitly.
    # manufacturing UV_PYTHON here would override or conceal that evidence.
    target_pin = False
    if project_root is not None and "UV_PYTHON" not in env:
        target_pin = _observe_target_python_pin(Path(project_root) / ".python-version")
    floor = None if target_pin else _project_python_floor(project_root)
    if floor:
        env.setdefault("UV_PYTHON", floor)
    return env

def _observe_target_python_pin(pin: Path) -> bool:
    """Constructed blindness: observe presence, never validate the opened pin."""
    return pin.is_symlink() or pin.exists()
