#!/usr/bin/env python3
"""Bounded API responses, never a real provider, CLI, token, or secret store."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.cicd.host import ProbeContext


def main():
    gate, case = map(Path, sys.argv[1:])
    scenario = (case / 'scenario.txt').read_text().strip()
    spec = importlib.util.spec_from_file_location('lib.cicd._host_control', gate)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if scenario in {'bad-container', 'bad-record-missing', 'bad-record-invalid', 'bad-timestamp', 'good-record-ready'}:
        with tempfile.TemporaryDirectory(prefix='host-record-control-') as directory:
            root = Path(directory)
            main = root / 'project'
            main.mkdir()
            module.main_checkout = lambda repo: main
            module.in_container = lambda: scenario == 'bad-container'
            target = root / '.claude/cpp-host.json'
            if scenario != 'bad-record-missing':
                target.parent.mkdir()
                record = {'schema': 1, 'checked_at': ('0001-01-01T00:00:00+01:00' if scenario == 'bad-timestamp'
                                         else '2026-11-08T10:00:00Z'),
                          'providers': {name: {'status': 'ready', 'reason': 'authenticated', 'versions': {}}
                                        for name in ('github-actions', 'woodpecker')}}
                target.write_text('invalid-private-canary' if scenario == 'bad-record-invalid' else json.dumps(record))
            if scenario == 'bad-record-missing':
                assert not target.exists()
            elif scenario == 'bad-record-invalid':
                assert target.read_text() == 'invalid-private-canary'
            else:
                assert target.exists()
            result = module.read_host_record(main)
            assert 'private-canary' not in json.dumps(result)
            ready = all(row['status'] == 'ready' for row in result['providers'].values())
            print('HOST_CI: ready' if ready else 'HOST_CI: not-ready unknown')
            return 0 if ready else 1
    if scenario in {'bad-credential-mix', 'good-credential-pair'}:
        calls = []
        def woodpecker_run(argv, **kwargs):
            calls.append(argv)
            if argv[:2] == ['woodpecker-cli', '--version']:
                return SimpleNamespace(returncode=0, stdout='woodpecker-cli 3.11.0')
            if argv[0] == 'aws':
                return SimpleNamespace(returncode=0, stdout=json.dumps({
                    'WOODPECKER_API_TOKEN': 'private-canary', 'WOODPECKER_HOST': 'https://source.invalid'}))
            assert argv[:2] == ['woodpecker-cli', 'info']
            return SimpleNamespace(returncode=0, stdout='fixture-user')
        server = 'https://other.invalid' if scenario == 'bad-credential-mix' else 'https://source.invalid'
        assert server == 'https://source.invalid' or scenario == 'bad-credential-mix'
        ctx = ProbeContext(run=woodpecker_run, which=lambda tool: tool, container=False,
                           env={'WOODPECKER_SERVER': server})
        result = module.check_woodpecker(ctx)
        if result['status'] == 'ready':
            print('HOST_CI: ready')
            return 0
        assert not any(argv[1:2] == ['info'] for argv in calls)
        print('HOST_CI: not-ready ' + result['status'])
        return 1
    auth = 1 if scenario == 'bad-auth' else 0
    scopes = 'public_repo, repo:status' if scenario == 'bad-scope' else 'repo'
    header = '' if scenario == 'bad-unintrospectable' else 'X-OAuth-Scopes: ' + scopes + '\n'
    api = 1 if scenario == 'bad-probe-error' else 0
    assert auth or api or scopes != 'repo' or not header or scenario == 'good-ready'

    def run(argv, **kwargs):
        if argv == ['gh', '--version']:
            return SimpleNamespace(returncode=0, stdout='gh version 2.81.0')
        if argv == ['gh', 'auth', 'status', '--hostname', 'github.com']:
            return SimpleNamespace(returncode=auth, stdout='', stderr='private-canary')
        assert argv == ['gh', 'api', '--include', '--hostname', 'github.com', 'user']
        return SimpleNamespace(returncode=api,
                               stdout='HTTP/2 200\n' + header + '\n' + json.dumps({'login': 'private-canary'}))

    ctx = ProbeContext(run=run, which=lambda tool: 'gh' if tool == 'gh' else None, env={}, container=False)
    result = module.check_github(ctx)
    assert 'private-canary' not in json.dumps(result)
    if result['status'] == 'ready':
        print('HOST_CI: ready')
        return 0
    print('HOST_CI: not-ready ' + result['status'])
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
