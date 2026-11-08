#!/usr/bin/env python3
"""Run the real watch with an Actions permalink and owned offline GH stubs."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    gate, case = map(Path, sys.argv[1:])
    state = (case / "state.txt").read_text().strip()
    assert state in {"SUCCESS", "FAILURE"}
    with tempfile.TemporaryDirectory(prefix="actions-watch-control-") as directory:
        root = Path(directory)
        (root / ".claude").mkdir()
        (root / ".claude/cicd.yml").write_text('{"pipeline":{"providers":["github-actions"]}}\n')
        gh = root / "gh"
        gh.write_text(f"#!{sys.executable}\n" + '''import json, sys
args = sys.argv[1:]
if args[0] == 'api':
    print(json.dumps({'checks':[{'context':'ci'}]} if args[1].endswith('required_status_checks') else []))
elif args[:2] == ['pr','view']:
    fields = args[args.index('--json')+1]
    if fields == 'headRefOid,baseRefName':
        print(json.dumps({'headRefOid':'a'*40,'baseRefName':'main'}))
    elif fields == 'headRefOid': print('a'*40)
    elif fields == 'statusCheckRollup': print('ci|https://github.com/o/r/actions/runs/19|STATE')
    else: raise SystemExit(1)
elif args[:2] == ['run','view']:
    if '--log-failed' in args:
        print('=== short test summary info ===\\n'
              'FAILED tests/test_app.py::test_regression - broken\\n=== 1 failed in 0.1s ===')
    elif '--json' in args and args[args.index('--json')+1] == 'jobs':
        print('unit|failure|2026-11-08T00:00:00Z|81|')
    else: raise SystemExit(1)
else: raise SystemExit(1)
'''.replace('STATE', state))
        gh.chmod(0o755)
        wp = root / "wpcli"
        wp.write_text(f'#!/bin/sh\necho called > "{root / "wp-called"}"\nexit 19\n')
        wp.chmod(0o755)
        env = {**os.environ, "FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wp)}
        env.pop("CPP_FLOW_PR_WATCH_BACKEND", None)
        result = subprocess.run(['bash', str(gate.resolve()), '42', '--repo', 'o/r', '--path', str(root),
                                 '--context', 'ci', '--timeout', '0'],
                                env=env, capture_output=True, text=True, timeout=15)
        verdicts = [line.removeprefix('FLOW_PR_WATCH: ') for line in result.stdout.splitlines()
                    if line.startswith('FLOW_PR_WATCH: ')]
        if len(verdicts) != 1 or result.returncode not in {0, 1, 2}:
            print('ACTIONS_WATCH: unavailable - malformed watcher evidence')
            return 3
        if verdicts[0] == 'red' and result.returncode == 1 and not (root / 'wp-called').exists():
            print('ACTIONS_WATCH: red surfaced')
            return 1
        print('ACTIONS_WATCH: no red (' + verdicts[0] + ')')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
