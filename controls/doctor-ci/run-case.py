#!/usr/bin/env python3
"""Drive stdlib verdict functions with normalized facts, not service mocks.

This control pins each diagnostic decision, not YAML/API collection. The full
collector/real published recipe is separately exercised by pytest with actual
canonical readers and bounded GitHub command responses. No dependency packages,
network, credentials, subprocesses or writable host surfaces are needed here.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    gate, case = map(Path, sys.argv[1:])
    data = json.loads((case / 'facts.json').read_text())
    spec = importlib.util.spec_from_file_location('lib.cicd._doctor_control', gate)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    selected = data.get('providers', ['github-actions'])
    target = data['target']
    if target == 'pipeline-files':
        if case.name == 'bad-provider-files':
            assert selected == ['github-actions'] and data['inventory']['github-actions'] == []
            assert data['inventory']['woodpecker'] == ['.woodpecker.yml']
        elif case.name.startswith('unknown-'):
            assert not selected or data.get('inventory') is None
        value = module.pipeline_row(selected, data.get('inventory'))
    elif target == 'required-checks':
        if case.name.startswith('bad-'):
            assert data['declared']['status'] == 'drift' or data['live']['status'] == 'drift'
        elif case.name.startswith('unknown-'):
            assert data['live']['status'] == 'unknown'
        value = module.required_row(data['declared'], data['live'])
    elif target == 'host-capability':
        if case.name.startswith('bad-'):
            assert data['host']['providers']['github-actions']['status'] == 'missing'
        elif case.name.startswith('unknown-'):
            assert data['host']['providers']['github-actions']['status'] == 'unknown'
        value = module.host_row(selected, data['host'])
    else:
        assert target == 'fallback'
        value = module.lane_row(selected, data['plan'], data['explicit'])
    print('DOCTOR_ROW: ' + value['status'] + ' (' + value['reason'] + ')')
    return {'ok':0, 'drift':1, 'unknown':3}[value['status']]


if __name__ == '__main__':
    raise SystemExit(main())
