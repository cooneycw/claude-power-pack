#!/usr/bin/env python3
"""Exercise actual CLI reconciliation with a withheld or delivered wake hint."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    gate, case = map(Path, sys.argv[1:])
    data = json.loads((case / 'case.json').read_text())
    assert type(data['message']) is bool and type(data['receipt']) is bool
    assert data['outcome'] in ('succeeded','failed','cancelled')
    if case.name == 'bad-dropped-done':
        assert data['receipt'] and not data['message'] and data['outcome'] == 'succeeded'
    elif case.name == 'good-delivered-done':
        assert data['receipt'] and data['message'] and data['outcome'] == 'succeeded'
    elif case.name.startswith('unknown-'):
        assert not data['receipt'] and not data['message']
    else:
        assert data['receipt'] and data['outcome'] in ('failed','cancelled')
        assert data['message'] is case.name.startswith('good-')
    with tempfile.TemporaryDirectory() as temporary:
        base = [sys.executable,str(gate),'VERB','--state-root',temporary,'--wave','control-wave',
                '--role','worker','--assignment-id','task','--generation','1']
        env = {**os.environ,'FLOW_WAVE_RECEIPT_ADAPTER':''}
        def run(verb, *args):
            argv = [verb if item == 'VERB' else item for item in base] + list(args)
            value = subprocess.run(argv,env=env,capture_output=True,text=True,timeout=8)
            return value.returncode, json.loads(value.stdout)
        code, assignment = run('assign','--deadline','2026-01-01T00:01:00Z','--now','2026-01-01T00:00:00Z')
        assert code == 0 and assignment['status'] == 'assigned'
        if data['receipt']:
            code, written = run('complete','--outcome',data['outcome'],'--finished-at','2026-01-01T00:00:30Z')
            assert code == 0 and written['receipt']['outcome'] == data['outcome']
        args = ['--message-arrived'] if data['message'] else []
        code, result = run('check','--now','2026-01-01T00:02:00Z','--liveness','unknown',*args)
        if result['status'] in ('waiting','extended') and code == 4:
            print('WAVE_COMPLETION_CONTROL: ok (no completion reconciled; missing-message detector is blind)')
            return 0
        if result['status'] == 'unknown' and code == 3:
            print('WAVE_COMPLETION_CONTROL: unknown (no usable terminal receipt)')
            return 3
        if (result['status'] != 'complete' or result['outcome'] != data['outcome']
                or code != (0 if data['outcome'] == 'succeeded' else 1)):
            print('WAVE_COMPLETION_CONTROL: unavailable (unexpected CLI response)')
            return 2
        if not data['message']:
            print('WAVE_COMPLETION_CONTROL: finding (reconciled dropped completion with its terminal outcome)')
            return 1
        print('WAVE_COMPLETION_CONTROL: ok (matching delivered completion/receipt with original outcome)')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
