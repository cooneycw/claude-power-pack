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
        restore_target_environment(os.environ)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    # Restore before importing any command implementation, not just before run.
    from .cli import run

    run()
