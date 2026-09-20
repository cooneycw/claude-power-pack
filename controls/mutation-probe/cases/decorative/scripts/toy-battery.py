#!/usr/bin/env python3
"""A miniature control battery over toy-gate, for the mutation-probe control.

It does what `scripts/check-negative-controls.py` does and nothing more: run each
registered case through the gate and refuse when an observed verdict differs from
its registered one.

WHY THE FIXTURE CARRIES ITS OWN BATTERY rather than invoking the register. The
probe's contract is "run the declared battery, and require the mutation to turn
it red"; the register is one battery among several it must drive (the #953
prototype declares `forced-claim-check.py --selftest`, and a research sweep
declares its own `--self-test`). A fixture that could only be driven through the
register would test the probe's DEFAULT wiring and leave the contract itself
unexercised - and vendoring a copy of the register into a fixture would buy that
coverage at the price of a copy that drifts.

What that leaves uncovered here is stated in the control's `limits`: the default
`--control`-narrowed register invocation is exercised by the real probe run over
`controls/shellcheck-gate`, not by this pair.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "controls" / "toy-gate" / "control.json"


def main() -> int:
    spec = json.loads(MANIFEST.read_text())
    gate = ROOT / spec["gate"]
    good_exit = int(spec["good_exit"])
    failed = 0
    for case in spec["cases"]:
        case_path = MANIFEST.parent / case["input"]
        argv = [part.replace("{gate}", str(gate)).replace("{case}", str(case_path))
                for part in spec["invocation"]]
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        observed = "GOOD" if proc.returncode == good_exit else "BAD"
        if observed != case["expect"]:
            failed += 1
            print(f"TOY-BATTERY-FAIL: {case['name']} expected={case['expect']} "
                  f"observed={observed} (exit {proc.returncode})", file=sys.stderr)
        else:
            print(f"toy-battery: {case['name']} {observed} as registered")
    if failed:
        print(f"toy-battery: {failed} case(s) did not discriminate.", file=sys.stderr)
        return 1
    print(f"toy-battery: ok - {len(spec['cases'])} case(s) discriminate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
