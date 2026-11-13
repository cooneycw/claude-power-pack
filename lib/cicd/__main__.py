"""Enable python -m lib.cicd invocation.

Usage:
    python -m lib.cicd detect [OPTIONS]
    python -m lib.cicd check [OPTIONS]

Examples:
    python -m lib.cicd detect
    python -m lib.cicd detect --json
    python -m lib.cicd check
    python -m lib.cicd check --summary
"""

import os
import sys
from collections.abc import MutableMapping

VALUE = "CPP_RUNNER_TARGET_UV_PROJECT_ENVIRONMENT"
PRESENT = VALUE + "_PRESENT"
PATH_VALUE = "CPP_RUNNER_TARGET_PATH"
PATH_PRESENT = PATH_VALUE + "_PRESENT"


#: NEGATIVE-CONTROL: controls/cicd-target-path
def restore_target_path(environment: MutableMapping[str, str]) -> None:
    """Restore captured caller search policy without accepting new directories."""
    if PATH_VALUE not in environment and PATH_PRESENT not in environment:
        return
    # Defaults keep each validation independent, including under guard mutation.
    value = environment.get(PATH_VALUE, "")
    present = environment.get(PATH_PRESENT, "x")
    if PATH_VALUE not in environment or PATH_PRESENT not in environment:
        raise ValueError("CPP target PATH policy is unverified: incomplete launch handoff")
    if present not in ("", "x"):
        raise ValueError("CPP target PATH policy is unverified: invalid presence marker")
    if present == "" and value != "":
        raise ValueError("CPP target PATH policy is unverified: inconsistent absent value")
    if present == "" and value == "":
        raise ValueError("CPP target PATH policy is unverified: absent search policy cannot be restored")
    if "PATH" not in environment:
        raise ValueError("CPP target PATH policy is unverified: current search policy is unavailable")
    current = environment.get("PATH", "")
    runner_bin = os.path.dirname(sys.executable)
    if current not in (value, runner_bin + os.pathsep + value):
        raise ValueError("CPP target PATH policy is unverified: search policy differs from launch handoff")
    environment.pop(PATH_VALUE, None)
    environment.pop(PATH_PRESENT, None)
    environment["PATH"] = value


#: NEGATIVE-CONTROL: controls/cicd-environment-handoff
def restore_target_environment(environment: MutableMapping[str, str]) -> None:
    """Restore caller policy after uv has selected CPP's own environment."""
    if VALUE not in environment and PRESENT not in environment:
        return
    if VALUE not in environment or PRESENT not in environment:
        raise ValueError("CPP target environment policy is unverified: incomplete launch handoff")
    value, present = environment[VALUE], environment[PRESENT]
    if present not in ("", "x") or (present == "" and value != ""):
        raise ValueError("CPP target environment policy is unverified: invalid launch handoff")
    del environment[VALUE]
    del environment[PRESENT]
    if present == "x":
        environment["UV_PROJECT_ENVIRONMENT"] = value
    else:
        environment.pop("UV_PROJECT_ENVIRONMENT", None)


if __name__ == "__main__":
    try:
        restore_target_path(os.environ)
        restore_target_environment(os.environ)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    os.environ["CPP_RUNNER_PYTHON"] = sys.executable
    # Restore before importing any command implementation, not just before run.
    from .cli import run

    run()
