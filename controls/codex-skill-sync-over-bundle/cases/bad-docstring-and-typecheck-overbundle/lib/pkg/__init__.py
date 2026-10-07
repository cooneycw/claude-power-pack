"""Quick start:

    from lib.pkg import unrelated_helper

The shape issue #1408 found live in lib/cicd/__init__.py: a USAGE EXAMPLE in
this module's own docstring, matching the line-shape a regex import-scanner
reads the same way it reads real code.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # For type checkers only - never executed. Lists re-exports resolved
    # lazily by __getattr__ below, exactly as lib/cicd/__init__.py does.
    from .unrelated1 import unrelated_helper
    from .unrelated2 import another_helper

__all__ = ["unrelated_helper", "another_helper"]

_NAME_TO_MODULE = {
    "unrelated_helper": "unrelated1",
    "another_helper": "unrelated2",
}


def __getattr__(name: str) -> Any:
    module = _NAME_TO_MODULE.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value
