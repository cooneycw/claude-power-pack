"""Own the live collector seam; no real provider or target mutation is invoked."""

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
case = json.loads((Path(sys.argv[1]) / "case.json").read_text())


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("fixture module is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


project = load("cpp_preflight_control_project", Path(sys.argv[2]))
observer = load("cpp_preflight_control_observer", root / "scripts/flow-preflight.py")
checks = [observer.check(name, "ok", "owned fixture") for name in ("gh", "engine")]
if case.get("mode") in ("missing", "unknown"):
    checks[0]["status"] = case["mode"]
report, code = observer.report_for(checks, ("gh", "engine"))
if case.get("mode") == "malformed":
    report = {}
elif case.get("mode") == "contradictory":
    report["full_host_ready"] = True
observed = []


def observe(args):
    if args.checks != ("gh", "engine") or Path(args.engine) != Path(sys.argv[2]).resolve():
        raise RuntimeError("observer must select only the physical entrypoint and gh")
    return report, code


def collect(*args):
    observed.append(True)
    raise project.CollectionError("owned later-collection sentinel")


project._load_preflight = lambda: argparse.Namespace(observe=observe, validate_report=observer.validate_report)
project.collect_repository = collect
with tempfile.TemporaryDirectory() as directory:
    # Actual main catches the controlled CollectionError as normal exit 2.
    status = project.main([directory, "--json"])
if status != 2:
    raise RuntimeError("fixture expected the explicit refusal shape")
print("PROJECT_NEXT_PREFLIGHT_CONTROL: " + ("ready" if observed else "blocked"))
raise SystemExit(0 if observed else 1)
