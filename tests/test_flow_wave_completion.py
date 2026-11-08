"""Offline actual-CLI cases for receipt/deadline wave completion (#1658)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/flow-wave-completion.py'
pytestmark = pytest.mark.skipif(shutil.which(sys.executable) is None, reason='requires Python')
IDENTITY = ['--wave','wave-a','--role','worker-a','--assignment-id','task-a','--generation','1']
BEFORE = '2026-11-08T10:00:00Z'
DEADLINE = '2026-11-08T10:01:00Z'
AFTER = '2026-11-08T10:02:00Z'


def call(root, verb, *args, env=None):
    result = subprocess.run([sys.executable, str(SCRIPT), verb, '--state-root', str(root), *IDENTITY, *args],
                            env={**os.environ, 'FLOW_WAVE_RECEIPT_ADAPTER':'', **(env or {})},
                            capture_output=True, text=True, timeout=8)
    assert result.stdout.strip(), result.stderr
    return result.returncode, json.loads(result.stdout)


def assign(root):
    code, value = call(root, 'assign', '--deadline', DEADLINE, '--now', BEFORE, '--extension-seconds','60')
    assert code == 0 and value['status'] == 'assigned'


def publish(root, outcome='succeeded', env=None):
    code, value = call(root, 'complete', '--outcome', outcome, '--finished-at', BEFORE, env=env)
    assert code == 0 and value['status'] == 'recorded'
    return value


@pytest.mark.parametrize('message', [False, True])
@pytest.mark.parametrize('outcome,code', [('succeeded',0), ('failed',1), ('cancelled',1)])
def test_receipt_controls_completion_even_if_done_message_dropped(tmp_path, message, outcome, code):
    assign(tmp_path)
    publish(tmp_path, outcome)
    args = ['--message-arrived'] if message else []
    actual, value = call(tmp_path, 'check', '--now', AFTER, *args)
    assert actual == code and value['status'] == 'complete'
    assert value['outcome'] == outcome


@pytest.mark.parametrize('liveness', ['gone','unknown'])
def test_no_message_no_receipt_is_unknown_at_deadline(tmp_path, liveness):
    assign(tmp_path)
    code, value = call(tmp_path, 'check', '--now', AFTER, '--liveness', liveness)
    assert code == 3 and value['status'] == 'unknown'


def test_alive_extends_once_persistently_then_escalates(tmp_path):
    assign(tmp_path)
    code, value = call(tmp_path, 'check', '--now', AFTER, '--liveness','alive','--observed-at',AFTER)
    assert code == 4 and value['status'] == 'extended'
    assert value['deadline'] == '2026-11-08T10:03:00Z'
    assign(tmp_path)  # An assignment retry must not reset extension history.
    code, value = call(tmp_path, 'check', '--now','2026-11-08T10:02:30Z')
    assert code == 4 and value['status'] == 'waiting'
    code, value = call(tmp_path, 'check', '--now','2026-11-08T10:03:00Z',
                       '--liveness','alive','--observed-at','2026-11-08T10:03:00Z')
    assert code == 3 and value['status'] == 'escalated'


@pytest.mark.parametrize('observed', [None, BEFORE])
def test_unproven_or_stale_alive_does_not_extend(tmp_path, observed):
    assign(tmp_path)
    args = ['--observed-at',observed] if observed else []
    code, value = call(tmp_path, 'check', '--now', AFTER, '--liveness','alive',*args)
    assert code == 3 and value['status'] == 'unknown'


def test_message_without_receipt_is_never_success(tmp_path):
    assign(tmp_path)
    code, value = call(tmp_path, 'check', '--now', AFTER, '--message-arrived')
    assert code == 3 and value['status'] == 'unknown'


def test_before_deadline_waits_and_early_receipt_shortcuts_wait(tmp_path):
    assign(tmp_path)
    code, value = call(tmp_path, 'check', '--now', BEFORE)
    assert code == 4 and value['status'] == 'waiting'
    publish(tmp_path)
    code, value = call(tmp_path, 'check', '--now', BEFORE, '--message-arrived')
    assert code == 0 and value['status'] == 'complete'


def test_terminal_publish_idempotent_and_conflicting_outcome_refused(tmp_path):
    assign(tmp_path)
    first = publish(tmp_path)
    code, second = call(tmp_path, 'complete','--outcome','succeeded','--finished-at', AFTER)
    assert code == 0 and second['receipt'] == first['receipt']
    code, value = call(tmp_path, 'complete','--outcome','failed','--finished-at', AFTER)
    assert code == 1 and value['status'] == 'refused'
    code, value = call(tmp_path, 'check','--now', AFTER)
    assert code == 0 and value['outcome'] == 'succeeded'


def adapter(tmp_path, body):
    path = tmp_path / 'adapter.py'
    path.write_text(body)
    return {'FLOW_WAVE_RECEIPT_ADAPTER':json.dumps([sys.executable,str(path)]),
            'FLOW_WAVE_RECEIPT_TIMEOUT':'0.1'}


@pytest.mark.parametrize('body', ["raise RuntimeError('PRIVATE_ADAPTER_ERROR')", 'import time; time.sleep(10)'])
def test_adapter_error_or_timeout_is_unknown(tmp_path, body):
    assign(tmp_path)
    env = adapter(tmp_path, body)
    code, value = call(tmp_path,'check','--now',AFTER,'--liveness','alive','--observed-at',AFTER,env=env)
    assert code == 3 and value['status'] == 'unknown'
    assert 'PRIVATE_ADAPTER_ERROR' not in json.dumps(value)


@pytest.mark.parametrize('field,value', [('assignment_id','different'),('generation',2)])
def test_wrong_adapter_receipt_identity_is_unknown(tmp_path, field, value):
    assign(tmp_path)
    receipt = publish(tmp_path)['receipt']
    receipt['identity'][field] = value
    env = adapter(tmp_path, 'import json,sys\nprint(json.dumps({"key":sys.argv[2],"receipt":' + repr(receipt) + '}))\n')
    code, value = call(tmp_path,'check','--now',AFTER,env=env)
    assert code == 3 and value['status'] == 'unknown'


def test_unavailable_filesystem_store_is_unknown(tmp_path):
    missing = tmp_path / 'missing'
    assert not missing.exists()
    code, value = call(missing,'check','--now',AFTER)
    assert code == 3 and value['status'] == 'unknown'
    assert not missing.exists()


def test_published_wave_requires_receipts_and_deadline_check():
    text = (ROOT / '.claude/commands/flow/wave.md').read_text()
    assert 'the message is the shortcut, the receipt plus the deadline is the guarantee' in text
    for verb in ('assign','complete','check'):
        assert f'flow-wave-completion.py" {verb}' in text


def test_adapter_ack_without_readable_receipt_is_unknown(tmp_path):
    assign(tmp_path)
    env = adapter(tmp_path, 'import json,sys\n'
                  'value=json.load(sys.stdin) if sys.argv[1]=="put" else {"key":sys.argv[2],"receipt":None}\n'
                  'print(json.dumps(value))\n')
    code, value = call(tmp_path,'complete','--outcome','succeeded',env=env)
    assert code == 3 and value['status'] == 'unknown'


def test_json_null_receipt_is_not_established_absence(tmp_path):
    assign(tmp_path)
    publish(tmp_path)
    path = next((tmp_path / 'receipts').glob('*.json'))
    path.write_text('null')
    code, value = call(tmp_path,'check','--now',AFTER,'--liveness','alive','--observed-at',AFTER)
    assert code == 3 and value['status'] == 'unknown'


@pytest.mark.skipif(shutil.which('bash') is None or shutil.which('python3') is None, reason='requires bash/Python')
def test_published_assign_complete_check_recipe_runs(tmp_path):
    import re
    from datetime import datetime, timedelta, timezone

    text = (ROOT / '.claude/commands/flow/wave.md').read_text()
    recipes = [block for block in re.findall(r'```bash\n(.*?)```', text, re.S)
               if 'flow-wave-completion.py"' in block]
    assert len(recipes) == 3
    env = {**os.environ,'CPP_DIR':str(ROOT),'FLOW_WAVE_COMPLETION_ROOT':str(tmp_path),
           'WAVE':'wave-a','ROLE':'worker-a','ASSIGNMENT_ID':'task-a','GENERATION':'1',
           'DEADLINE':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
           'OUTCOME':'succeeded','RESULT_REFERENCE':'fixture-result','LIVENESS':'unknown',
           'LIVENESS_OBSERVED_AT':'','FLOW_WAVE_RECEIPT_ADAPTER':''}
    results = []
    for recipe in recipes:
        result = subprocess.run(['bash','-c',recipe],env=env,capture_output=True,text=True,timeout=8)
        assert result.returncode == 0, result.stdout + result.stderr
        results.append(json.loads(result.stdout))
    assert [r['status'] for r in results] == ['assigned','recorded','complete']


def test_new_generation_supersedes_old_assignment(tmp_path):
    assign(tmp_path)
    publish(tmp_path)
    argv = ['--generation','2','--assignment-id','task-b']
    code, value = call(tmp_path,'assign','--deadline',DEADLINE,'--now',BEFORE,*argv)
    assert code == 0 and value['status'] == 'assigned'
    code, value = call(tmp_path,'check','--now',AFTER)
    assert code == 3 and value['status'] == 'unknown'
    code, value = call(tmp_path,'assign','--deadline',DEADLINE,'--now',BEFORE)
    assert code == 1 and value['status'] == 'refused'


@pytest.mark.parametrize('content', ['null','{broken', '[]'])
def test_malformed_assignment_never_overwritten(tmp_path, content):
    assign(tmp_path)
    path = tmp_path / 'wave-a/assignments/worker-a.json'
    path.write_text(content)
    code, value = call(tmp_path,'assign','--deadline',DEADLINE,'--now',BEFORE)
    assert code == 3 and value['status'] == 'unknown'
    assert path.read_text() == content


def test_external_adapter_round_trip_shared_across_processes(tmp_path):
    shared = tmp_path / 'remote-store.json'
    env = adapter(tmp_path, 'import json,sys\nfrom pathlib import Path\n'
                  f'p=Path({str(shared)!r})\n'
                  'if sys.argv[1]=="put": p.write_text(sys.stdin.read())\n'
                  'print(p.read_text() if p.exists() else json.dumps({"key":sys.argv[2],"receipt":None}))\n')
    assign(tmp_path)
    publish(tmp_path, env=env)
    code, value = call(tmp_path,'check','--now',AFTER,env=env)
    assert code == 0 and value['outcome'] == 'succeeded'
    assert not (tmp_path / 'receipts').exists()


def test_committed_empty_adapter_response_is_unknown(tmp_path):
    assign(tmp_path)
    fixture = ROOT / 'tests/fixtures/flow-wave-completion/empty-adapter.py'
    assert fixture.is_file() and 'print(' not in fixture.read_text()
    env = {'FLOW_WAVE_RECEIPT_ADAPTER':json.dumps([sys.executable,str(fixture)])}
    for verb, args in [('check',['--now',AFTER]), ('complete',['--outcome','succeeded'])]:
        code, value = call(tmp_path,verb,*args,env=env)
        assert code == 3 and value['status'] == 'unknown'
