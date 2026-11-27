#!/bin/sh
# #1917 PR-A, one host trip: default shell probe and actual root witnesses.
# Usage: sh host-run.sh CHECKPOINT_SHA ABSOLUTE_OUTPUT_DIRECTORY
set -eu
python3 - "$@" <<'PYHOST'
import re
import subprocess
import sys
import tempfile
from pathlib import Path

checkpoint, output_arg = sys.argv[1:]
if not re.fullmatch(r"[0-9a-f]{40}", checkpoint):
    raise SystemExit("exact pushed checkpoint SHA required")
output = Path(output_arg)
if not output.is_absolute():
    raise SystemExit("output directory must be absolute")
output.mkdir(parents=True, exist_ok=True)
# Cleanup can reach only this owned temporary directory, never an input path.
with tempfile.TemporaryDirectory(prefix="cpp-ci-shape-host-") as owned:
    root = Path(owned) / "source"
    subprocess.run(["git", "clone", "--quiet", "https://github.com/cooneycw/claude-power-pack.git", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "fetch", "--quiet", "origin", checkpoint], check=True)
    subprocess.run(["git", "-C", str(root), "checkout", "--quiet", "--detach", checkpoint], check=True)
    actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if actual != checkpoint:
        raise SystemExit("checkpoint mismatch")
    sys.path.insert(0, str(root))
    from lib.ci_shape_check import image_pin
    image = image_pin(root)
    (output / "validate-image.txt").write_text(image + "\n")
    with (output / "validate-default-shell.log").open("w") as log:
        subprocess.run(["docker", "run", "--rm", "--user", "0:0", "--entrypoint", "/bin/sh",
                        image, "-c", "umask; id"], stdout=log, stderr=subprocess.STDOUT, check=True)
    with (output / "image-launch.log").open("w") as log:
        result = subprocess.run([sys.executable, str(root / "scripts/ci-shape-check.py"), "run",
                                 "--tier", "image", "--receipt", str(output / "image.json")],
                                stdout=log, stderr=subprocess.STDOUT)
    raise SystemExit(result.returncode)
PYHOST
