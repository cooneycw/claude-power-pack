#!/bin/sh
# #1917 PR-A, one host trip: default shell probe and actual root witnesses.
# Usage: sh host-run.sh CHECKPOINT_SHA ABSOLUTE_OUTPUT_DIRECTORY
set -eu
python3 - "$@" <<'PYHOST'
import re
import hashlib
import json
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
    if result.returncode == 0:
        raw = (output / "image.json").read_bytes()
        record = json.loads(raw)
        observed_mask = int((output / "validate-default-shell.log").read_text().splitlines()[0], 8)
        identity = record["lanes"][0]["identity"]
        if (record["state"] != "GOOD" or record["commit"] != checkpoint or record["image"] != image
                or observed_mask != record["pytest_time_umask"]["umask"]
                or identity["uid"] != 0 or identity["euid"] != 0
                or not all(lane["identity"] == identity for lane in record["lanes"])):
            raise SystemExit("default shell/profile/root receipt mismatch; no profile published")
        candidate = {"state": "GOOD", "image": image, "umask": observed_mask, "identity": identity,
                     "root_checkpoint": checkpoint, "receipt_sha256": hashlib.sha256(raw).hexdigest(),
                     "evidence": "docs/measurements/ci-shape-check/validate-default-shell.txt"}
        (output / "validate-profile-observed.json").write_text(json.dumps(candidate, indent=2) + "\n")
        command_file = root / "docs/measurements/ci-shape-check/host-run.sh"
        (output / "host-command-sha256.txt").write_text(hashlib.sha256(command_file.read_bytes()).hexdigest() + "\n")
    raise SystemExit(result.returncode)
PYHOST
