#!/usr/bin/env python3
"""Stage a CONTENT-PINNED `jq` into `.ci-bin/` for the CI steps that need it (#1017).

WHY THIS EXISTS. `controls/flow-driver-retirement-check` is the first registered
control whose gate needs `jq`, and the CI image
(`ghcr.io/astral-sh/uv:python3.11-bookworm-slim`) has none. Without it the gate
correctly reports `unknown` on EVERY case - which is the honest answer to "I
cannot look" and is also indistinguishable, to the register, from a gate that has
stopped discriminating. So the register reported BLIND and CI went red, exactly
as designed: the harness REFUSES to skip a control it cannot run.

The pytest module was worse. It carried `skipif(shutil.which("jq") is None)`, so
all 26 of its tests SKIPPED in CI and `validate` went green - a suite that was
load-bearing on a dev box and inert in the one environment a reviewer can
re-derive. The register caught what the suite could not, and this script is the
fix for both.

PINNED BY CONTENT, NOT BY TAG. `.woodpecker.yml` pins every image by digest for
a reason it states at the shellcheck step: "running the gate under two different
linters would make the control's verdict depend on which container reached it".
The same applies here and is not hypothetical - `scripts/flow-wave-registry.sh`
carries a "#699 jq-1.6 update trap" comment about an expression that DELETES the
key it was told to update on one version and not the other. A sha256 over the
downloaded bytes gives the same guarantee a digest does.

PYTHON, NOT `curl`. The slim image is guaranteed to have python3 - it is a python
image - and is NOT guaranteed to have curl or wget. A stager that assumes a tool
the image may not carry fails in the same shape as the problem it is fixing.

Idempotent: an already-staged binary whose bytes hash correctly is left alone, so
re-running costs nothing and a step that runs twice does not re-download.
"""

from __future__ import annotations

import hashlib
import stat
import sys
import urllib.request
from pathlib import Path

#: jq 1.7.1, linux-amd64, from the project's own GitHub release.
JQ_URL = "https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64"

#: Measured on 2026-09-16 by downloading the URL above and hashing the bytes.
#: A mismatch is a HARD failure: it means the bytes are not the ones this pin was
#: taken against, and there is no reading of that which makes running them safe.
JQ_SHA256 = "5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5"

DEST_DIR = Path(".ci-bin")
DEST = DEST_DIR / "jq"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if DEST.is_file():
        have = _sha256(DEST.read_bytes())
        if have == JQ_SHA256:
            print(f"ci-stage-jq: ok - {DEST} already staged and matches the pin")
            return 0
        print(f"ci-stage-jq: {DEST} exists but hashes {have}, re-staging", file=sys.stderr)

    try:
        with urllib.request.urlopen(JQ_URL, timeout=120) as response:  # noqa: S310
            payload = response.read()
    except Exception as exc:  # noqa: BLE001 - the cause is reported, not classified
        print(f"ci-stage-jq: FAILED to download {JQ_URL}: {exc}", file=sys.stderr)
        print("ci-stage-jq: this is not a pass - the controls that need jq cannot run.",
              file=sys.stderr)
        return 1

    got = _sha256(payload)
    if got != JQ_SHA256:
        print(f"ci-stage-jq: SHA256 MISMATCH for {JQ_URL}", file=sys.stderr)
        print(f"  expected {JQ_SHA256}", file=sys.stderr)
        print(f"  got      {got}", file=sys.stderr)
        return 1

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(payload)
    DEST.chmod(DEST.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"ci-stage-jq: ok - staged jq 1.7.1 at {DEST} ({len(payload)} bytes, sha256 {got})")
    return 0


if __name__ == "__main__":
    # Deliberately no chdir: every command in `.woodpecker.yml` runs with the
    # workspace as cwd, and a stager that relocates itself would stage into a
    # directory the consuming steps do not put on PATH.
    raise SystemExit(main())
