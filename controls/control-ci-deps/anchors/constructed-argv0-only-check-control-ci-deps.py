#!/usr/bin/env python3
"""CONSTRUCTED BLIND ARTIFACT for controls/control-ci-deps (issue #1036).

This is not a historical revision - the gate is new and never shipped blind, so
there is nothing to vendor and `--verify-provenance` correctly reports
`unverified`, which must never be read as `ok`.

WHAT IT IS: the FIRST FRAMING of the problem, written straight from the
sentence the issue used to ask for it - "a tripwire checking each registered
control's declared `invocation` ... against the binaries the CI image actually
provides". Read literally and implemented directly, you get this file: it looks
at `invocation[0]` and stops.

WHY IT MISSES BOTH BAD CASES, which is what makes it a usable anchor:

  bad-missing-binary  the control's invocation is `["sh", "{gate}", ...]`, and
                      `sh` is in every image. The dependency is inside the GATE
                      - a shell script that hard-requires `git` - which this
                      artifact never opens. That is the real failure's shape:
                      the control that took the whole battery down declared
                      nothing unusual in its invocation either.
  bad-stale-image     this artifact trusts the recorded contents list without
                      checking that the pipeline still runs the image it
                      describes, so a pipeline that moved to `python:3.12-alpine`
                      is scored against a bookworm-slim inventory and reports
                      clean.

And it AGREES with the real gate on `good-all-present`, which is what makes the
demonstration isolated rather than merely different.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BINARY_GATE_REL = "scripts/check-test-binary-guards.py"
WOODPECKER_REL = ".woodpecker.yml"
CONTROLS_REL = "controls"
IMAGE_RE = re.compile(r"^\s{4}image:\s*(\S+)", re.MULTILINE)


def _load(path: Path):
    if not path.is_file():
        return None
    name = f"anchor_{path.stem.replace('-', '_')}"
    try:
        spec = spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return None
        module = module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001
        sys.modules.pop(name, None)
        return None
    return module


def run_check(root: Path) -> int:
    controls_dir = root / CONTROLS_REL
    if not controls_dir.is_dir():
        print(f"control-ci-deps: no {CONTROLS_REL}/ under {root}; nothing compared.")
        return 1
    registered = sorted(p for p in controls_dir.iterdir() if (p / "control.json").is_file())
    if not registered:
        print(f"control-ci-deps: {CONTROLS_REL}/ holds no registered control; nothing compared.")
        return 1

    pipeline = root / WOODPECKER_REL
    if not pipeline.is_file():
        print(f"CI_PIPELINE: {WOODPECKER_REL} does not exist under {root}")
        return 1
    # The image is READ AND DISCARDED - no comparison against the recorded
    # contents list. This is the blindness bad-stale-image exists to catch.
    IMAGE_RE.search(pipeline.read_text(encoding="utf-8"))

    binary_gate = _load(REPO_ROOT / BINARY_GATE_REL)
    if binary_gate is None:
        print(f"CI_PIPELINE: {BINARY_GATE_REL} could not be loaded")
        return 1
    provided = set(binary_gate.CI_IMAGE_BINARIES)

    examined = 0
    findings = 0
    for control_dir in registered:
        try:
            spec = json.loads((control_dir / "control.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        invocation = [str(part) for part in spec.get("invocation", [])]
        if not invocation:
            continue
        command = Path(invocation[0]).name
        if "{gate}" in command or "{case}" in command:
            continue
        examined += 1
        if command not in provided:
            print(
                f"CI_DEP: {control_dir.name} needs `{command}`, which the battery's CI step "
                f"does not provide - this control would not fail alone, it would take the "
                f"whole register down"
            )
            findings += 1

    print(f"CONTROL_CI_DEPS_REGISTERED: {len(registered)}")
    print(f"CONTROL_CI_DEPS_EXAMINED: {examined}")
    print(f"CONTROL_CI_DEPS_PROVIDED: {len(provided)}")
    if findings:
        print(f"control-ci-deps: {findings} finding(s).")
        return 1
    print(f"control-ci-deps: ok - {examined} registered control(s) examined.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("mode", nargs="?", default="check", choices=["check"])
    parser.add_argument("--root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)
    return run_check(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
