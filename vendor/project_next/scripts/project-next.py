#!/usr/bin/env python3
"""Portable entry point for the project-next engine."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_ROOT))

main = import_module("lib.project_next.cli").main


if __name__ == "__main__":
    raise SystemExit(main())
