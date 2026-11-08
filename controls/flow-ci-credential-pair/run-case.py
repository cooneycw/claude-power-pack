#!/usr/bin/env python3
"""Offline credential-routing controls: owned secret provider and HTTP stubs."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SHA = '2b308175a757e0b17c30caead6aabbe9356b43cc'
TOKEN_A = 'credential-pair-a-canary'
TOKEN_B = 'credential-pair-b-canary'
SERVER_A = 'https://source-a.example.invalid'
SERVER_B = 'https://source-b.example.invalid'


def exercise(gate, scenario):
    with tempfile.TemporaryDirectory(prefix='ci-credential-pair-') as directory:
        root = Path(directory)
        requests = root / 'requests.jsonl'
        aws_called = root / 'aws-called'
        aws = root / 'aws'
        secret = {'WOODPECKER_API_TOKEN': TOKEN_A, 'WOODPECKER_HOST': SERVER_A}
        aws.write_text('#!' + sys.executable + '\nfrom pathlib import Path\n'
                       f'Path({str(aws_called)!r}).touch()\nprint({json.dumps(secret)!r})\n')
        aws.chmod(0o755)
        curl = root / 'curl'
        curl.write_text('#!' + sys.executable + '\nimport json, sys\nfrom pathlib import Path\n'
                        'url=sys.argv[-1]\nheader=sys.stdin.read()\n'
                        f'with Path({str(requests)!r}).open("a") as stream:\n'
                        '    stream.write(json.dumps({"argv":sys.argv[1:],"header":header,"url":url})+"\\n")\n'
                        'if "/lookup/" in url: print(json.dumps({"id":17}))\n'
                        f'else: print(json.dumps([{{"number":1,"commit":{SHA!r},'
                        '"status":"success","event":"push"}]))\n')
        curl.chmod(0o755)
        env = {k: v for k, v in os.environ.items()
               if k not in {'WOODPECKER_API_TOKEN', 'WOODPECKER_SERVER', 'WOODPECKER_HOST'}}
        env.update(FLOW_CI_CURL=str(curl), FLOW_CI_AWS=str(aws), FLOW_CI_GH='/nonexistent/gh',
                   FLOW_CI_WPCLI='/nonexistent/woodpecker-cli', FLOW_CI_SLEEP='/nonexistent/sleep', HOME=str(root))
        supplied = {
            'bad-server-mix': {'WOODPECKER_SERVER': SERVER_B},
            'bad-token-mix': {'WOODPECKER_API_TOKEN': TOKEN_B},
            'good-environment': {'WOODPECKER_SERVER': SERVER_B, 'WOODPECKER_API_TOKEN': TOKEN_B},
            'good-secret': {},
            'good-matching-server': {'WOODPECKER_SERVER': SERVER_A + '/'},
            'good-matching-token': {'WOODPECKER_API_TOKEN': TOKEN_A},
        }[scenario]
        env.update(supplied)
        assert aws.is_file() and curl.is_file() and os.access(aws, os.X_OK) and os.access(curl, os.X_OK)
        assert not requests.exists() and not aws_called.exists()
        if scenario == 'bad-server-mix':
            assert env['WOODPECKER_SERVER'] != secret['WOODPECKER_HOST'] and 'WOODPECKER_API_TOKEN' not in env
        elif scenario == 'bad-token-mix':
            assert env['WOODPECKER_API_TOKEN'] != secret['WOODPECKER_API_TOKEN'] and 'WOODPECKER_SERVER' not in env
        result = subprocess.run(
            ['bash', str(Path(gate).resolve()), SHA, '--repo', 'fixture/project', '--event', 'push'],
                                cwd=root, env=env, capture_output=True, text=True, timeout=10)
        rows = [json.loads(line) for line in requests.read_text().splitlines()] if requests.exists() else []
        for canary in (TOKEN_A, TOKEN_B):
            assert canary not in result.stdout + result.stderr
            assert all(canary not in json.dumps(row['argv']) for row in rows)
        return result, rows, aws_called.exists()


def main():
    gate, case = map(Path, sys.argv[1:])
    scenario = (case / 'scenario.txt').read_text().strip()
    result, rows, called = exercise(gate, scenario)
    assert result.returncode == 0, 'helper must retain fail-open behavior'
    if not rows:
        assert scenario.startswith('bad-') and called
        assert 'FLOW_CI_STATUS: unknown' in result.stdout
        print('CREDENTIAL_PAIR: refused')
        return 1
    expected_server = SERVER_B if scenario == 'good-environment' else SERVER_A
    expected_token = TOKEN_B if scenario == 'good-environment' else TOKEN_A
    if scenario.startswith('good-'):
        assert all(row['url'].startswith(expected_server + '/') for row in rows)
        assert all(expected_token in row['header'] for row in rows)
        assert called is (scenario != 'good-environment')
    assert 'FLOW_CI_STATUS: success' in result.stdout
    print('CREDENTIAL_PAIR: authenticated-request')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
