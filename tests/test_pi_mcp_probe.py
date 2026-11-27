"""B3 fixture safety and local transport controls. Never invokes pi."""
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'docs/measurements/pi'
pytestmark = pytest.mark.skipif(shutil.which('python3') is None, reason='requires Python fixture subprocesses')


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), HERE / name)
    assert spec is not None and spec.loader is not None
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def probe():
    result = load('issue-1899-b3-probe.py')
    if os.environ.get('CPP_PI_MCP_BLIND_CONTROL') == '1':
        spec = importlib.util.spec_from_file_location('blind', ROOT / 'tests/fixtures/pi-mcp-blind.py')
        assert spec is not None and spec.loader is not None
        blind = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(blind)
        result.verify_events = blind.verify_events
    return result


@pytest.fixture
def root(tmp_path):
    for name in ['agent', 'home', 'config', 'data', 'cache', 'tmp', 'work/repo-alpha', 'work/repo-beta']:
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    load('issue-1899-b2-files.py').prepare(tmp_path)
    (tmp_path / 'work/pi-1899-b2-model-pin.json').write_text(json.dumps({
        'id': 'github-copilot/gpt-5.3-codex', 'listing_sha256': '0' * 64,
        'source': 'pi --offline --list-models 5.3'}))
    return tmp_path


def test_config_transitions_preserve_foreign_and_refuse_edit(probe, root):
    probe.prepare(root)
    foreign_hash = probe.audit(root)['foreign_sha256']
    for case in ['stdio-direct', 'stdio-default', 'foreign']:
        result = probe.set_case(root, case)
        assert result['foreign_sha256'] == foreign_hash and result['foreign_preserved']
    target = root / 'agent/mcp.json'
    target.write_bytes(target.read_bytes() + b' ')
    before = target.read_bytes()
    assert before != probe.encode(probe.BASE)
    with pytest.raises(ValueError, match='changed'):
        probe.set_case(root, 'stdio-direct')
    assert target.read_bytes() == before


def test_preexisting_mcp_never_adopted(probe, root):
    target = root / 'agent/mcp.json'
    target.write_bytes(b'foreign config')
    assert target.read_bytes() == b'foreign config'
    with pytest.raises(ValueError, match='preexisting'):
        probe.prepare(root)
    assert target.read_bytes() == b'foreign config'
    assert not probe.directory(root).exists()


def test_changed_config_mode_refuses_undo(probe, root):
    probe.prepare(root)
    target = root / 'agent/mcp.json'
    target.chmod(0o400)
    assert target.stat().st_mode & 0o777 == 0o400
    before = target.read_bytes()
    with pytest.raises(ValueError, match='mode'):
        probe.set_case(root, 'foreign')
    assert target.read_bytes() == before
    assert target.stat().st_mode & 0o777 == 0o400


def test_prompt_binds_tag_to_configured_case(probe, root):
    probe.prepare(root)
    assert probe.prompt(root, 'T1-alpha')['expected_tool_id'] == 'mcp__cpp_pi1899_stdio__probe_echo'
    probe.set_case(root, 'stdio-direct')
    value = probe.prompt(root, 'T2-beta')
    assert 'T2-beta' in value['prompt'] and 'nonce' not in value['prompt']
    with pytest.raises(ValueError, match='matrix row'):
        probe.prompt(root, 'T4-alpha')


def test_actual_cli_external_cwd_and_missing_evidence_exit(root):
    script = str(HERE / 'issue-1899-b3-probe.py')
    isolated_bin = root / 'empty-bin'
    isolated_bin.mkdir()
    assert shutil.which('pi', path=str(isolated_bin)) is None, 'fixture must lack pi'
    env = {'PATH': str(isolated_bin), 'HOME': str(root / 'home'), 'LANG': 'C.UTF-8'}
    prefix = [sys.executable, script]
    prepared = subprocess.run(prefix + ['prepare', '--root', str(root)], cwd=root / 'work/repo-alpha',
                              env=env, capture_output=True, text=True, check=True)
    assert json.loads(prepared.stdout)['foreign_preserved']
    recorded = subprocess.run(prefix + ['record-reply', '--tag', 'T1-alpha', '--root', str(root)],
                              cwd=root / 'work/repo-beta', env=env, input='TOOL_UNAVAILABLE\n',
                              capture_output=True, text=True, check=True)
    assert json.loads(recorded.stdout)['recorded_reply'] == 'T1-alpha'
    result = subprocess.run(prefix + ['verify', '--tag', 'T1-alpha', '--transport', 'stdio', '--root', str(root)],
                            cwd=root / 'work/repo-beta', env=env, capture_output=True, text=True)
    assert not (root / 'work/pi-1899-b3/events.jsonl').exists()
    assert result.returncode == 4 and 'UNKNOWN' in result.stderr


def test_stdio_compatible_call_and_dead_control(probe, root):
    probe.prepare(root)
    assert probe.control(root, 'stdio')['compatible_call']
    with pytest.raises((ValueError, OSError)):
        probe.control(root, 'stdio', dead=True)
    rows = [json.loads(line) for line in (probe.directory(root) / 'events.jsonl').read_text().splitlines()]
    calls = [row for row in rows if row['event'] == 'tools/call']
    assert len(calls) == 1 and calls[0]['peer'] == 'cpp-pi1899-control'
    assert {row['instance'] for row in rows if row['event'] == 'start'} <= {
        row['instance'] for row in rows if row['event'] == 'stop'}


def test_http_control_shutdown_dead_and_scoped_undo(probe, root):
    try:
        with socket.socket() as capability:
            capability.bind(('127.0.0.1', 0))
    except PermissionError:
        pytest.skip('requires fixture-only loopback sockets')
    probe.prepare(root)
    folder = probe.directory(root)
    isolated_bin = root / 'empty-bin'
    isolated_bin.mkdir()
    assert shutil.which('pi', path=str(isolated_bin)) is None, 'fixture must lack pi'
    process = subprocess.Popen([sys.executable, str(probe.SERVER), 'http', '--directory', str(folder)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env={'PATH': str(isolated_bin), 'HOME': str(root / 'home'), 'LANG': 'C.UTF-8'})
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError(process.stderr.read().decode())
            try:
                ep = probe.endpoint(folder)
                break
            except (probe.Unknown, ValueError):
                time.sleep(0.02)
        else:
            pytest.fail('fixture HTTP readiness timed out')
        assert ep['pid'] == process.pid
        assert probe.control(root, 'http')['compatible_call']
        assert probe.control(root, 'http')['compatible_call']
        probe.set_case(root, 'http-direct')
        probe.set_case(root, 'http-default')
        probe.set_case(root, 'foreign')
        assert probe.stop_http(root)['http_stopped']
        assert process.wait(timeout=5) == 0
        with pytest.raises(OSError):
            probe.control(root, 'http')
        probe.set_case(root, 'http-dead')
        probe.set_case(root, 'foreign')
        assert probe.undo(root)['probe_mcp_absent']
        assert not (root / 'agent/mcp.json').exists()
        rows = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()]
        nonces = [row['nonce'] for row in rows if row['event'] == 'tools/call']
        assert len(nonces) == 2 and len(set(nonces)) == 2
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def evidence(tag='T2-alpha', peer='pi'):
    common = {'batch': 'fixture', 'instance': 'instance', 'pid': 123, 'transport': 'stdio'}
    rows = [{**common, 'event': 'start', 'time_ns': 1},
            {**common, 'event': 'initialize', 'time_ns': 2, 'peer': peer},
            {**common, 'event': 'tools/call', 'time_ns': 3, 'peer': peer, 'name': 'probe-echo',
             'tag': tag, 'nonce': 'a' * 32, 'request_id': 3},
            {**common, 'event': 'response', 'time_ns': 4, 'peer': peer, 'request_id': 3,
             'tag': tag, 'nonce': 'a' * 32, 'response': {'id': 3, 'result': {'content': [{'text': json.dumps({
                 'tag': tag, 'nonce': 'a' * 32, 'transport': 'stdio'})}]}}}]
    return b'\n'.join(json.dumps(row).encode() for row in rows)


def test_actual_call_and_reply_nonce_required(probe):
    reply = 'T2-alpha ' + 'a' * 32
    assert probe.verify_events(evidence(), 'fixture', 'T2-alpha', 'stdio', reply)['verified_pi_call']
    with pytest.raises(ValueError, match='nonce'):
        probe.verify_events(evidence(), 'fixture', 'T2-alpha', 'stdio', 'TOOL_UNAVAILABLE')


def test_dead_server_exit_zero_cannot_reuse_old_call(probe):
    # A synthetic earlier positive is present, but the new dead-server row never called.
    data = evidence(tag='T2-alpha')
    assert b'T6-alpha' not in data
    pi_exit = 0
    assert pi_exit == 0
    with pytest.raises(ValueError, match='no unique'):
        probe.verify_events(data, 'fixture', 'T6-alpha', 'stdio', 'TOOL_UNAVAILABLE')


def test_compatible_client_cannot_be_counted_as_pi(probe):
    data = evidence(peer='cpp-pi1899-control')
    assert b'cpp-pi1899-control' in data
    with pytest.raises(ValueError, match='no unique'):
        probe.verify_events(data, 'fixture', 'T2-alpha', 'stdio', 'T2-alpha ' + 'a' * 32)


def test_missing_send_record_is_unknown(probe):
    rows = [line for line in evidence().splitlines() if json.loads(line)['event'] != 'response']
    assert all(json.loads(line)['event'] != 'response' for line in rows)
    with pytest.raises(probe.Unknown, match='response-send'):
        probe.verify_events(b'\n'.join(rows), 'fixture', 'T2-alpha', 'stdio', 'T2-alpha ' + 'a' * 32)


@pytest.mark.parametrize('field', ['pid', 'instance', 'request_id'])
def test_missing_call_binding_is_unknown(probe, field):
    rows = [json.loads(line) for line in evidence().splitlines()]
    call = next(row for row in rows if row['event'] == 'tools/call')
    for row in rows:
        row.pop(field, None)
    if field == 'request_id':
        next(row for row in rows if row['event'] == 'response')['response'].pop('id')
    assert all(field not in row for row in rows) and field not in call
    with pytest.raises(probe.Unknown):
        probe.verify_events(b'\n'.join(json.dumps(row).encode() for row in rows),
                            'fixture', 'T2-alpha', 'stdio', 'T2-alpha ' + 'a' * 32)


@pytest.mark.parametrize('data', [b'', b'not JSON', b'{"event":"tools/call"}'])
def test_unknown_server_evidence_never_green(probe, data):
    assert not data or b'"batch"' not in data
    with pytest.raises(probe.Unknown):
        probe.verify_events(data, 'fixture', 'T2-alpha', 'stdio', 'T2-alpha ' + 'a' * 32)
