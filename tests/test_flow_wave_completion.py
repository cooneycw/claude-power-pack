"""Offline actual-CLI cases for receipt/deadline wave completion (#1658)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'flow-wave-completion.py'
pytestmark = pytest.mark.skipif(shutil.which(sys.executable) is None, reason='requires Python')
IDENTITY = ['--wave','wave-a','--role','worker-a','--assignment-id','task-a','--generation','1']
BEFORE = '2026-11-08T10:00:00Z'
DEADLINE = '2026-11-08T10:01:00Z'
AFTER = '2026-11-08T10:02:00Z'


def call(root, verb, *args, env=None):
    result = subprocess.run([sys.executable, str(SCRIPT), verb, '--state-root', str(root), *IDENTITY, *args],
                            env={**os.environ, 'FLOW_WAVE_RECEIPT_ADAPTER':'', **(env or {})},
                            capture_output=True, text=True, timeout=8)
    assert result.stderr.splitlines()[-1] == f'FLOW_WAVE_COMPLETION_EXIT={result.returncode}'
    assert result.stdout.strip(), result.stderr
    return result.returncode, json.loads(result.stdout)


def assign(root, env=None):
    code, value = call(root, 'assign', '--deadline', DEADLINE, '--now', BEFORE, '--extension-seconds','60',env=env)
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
            'FLOW_WAVE_RECEIPT_TIMEOUT':'5'}


@pytest.mark.parametrize('body', ["raise RuntimeError('PRIVATE_ADAPTER_ERROR')", 'import time; time.sleep(10)'])
def test_adapter_error_or_timeout_is_unknown(tmp_path, body):
    assign(tmp_path)
    env = adapter(tmp_path, body)
    if 'time.sleep' in body:
        env['FLOW_WAVE_RECEIPT_TIMEOUT'] = '0.1'
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
        assert f'flow-wave-completion.py {verb}' in text


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
@pytest.mark.parametrize('section', ['setup','loop'])
def test_published_assign_complete_check_recipe_runs(tmp_path, section):
    import re
    from datetime import datetime, timedelta, timezone

    text = (ROOT / '.claude/commands/flow/wave.md').read_text()
    scope = (text.split('## Completion:',1)[1].split('## Phase 1:',1)[0] if section == 'setup'
             else text.split('## Phase 2:',1)[1].split('## Phase 3:',1)[0])
    recipes = [block for block in re.findall(r'```bash\n(.*?)```', scope, re.S)
               if 'flow-wave-completion.py' in block and 'REWORK_GENERATION' not in block]
    assert len(recipes) == (3 if section == 'setup' else 7)
    task_home = tmp_path / 'home'
    installed = task_home / '.claude/scripts/flow-wave-completion.py'
    installed.parent.mkdir(parents=True)
    installed.write_bytes(SCRIPT.read_bytes())
    env = {**os.environ,'HOME':str(task_home),'FLOW_WAVE_COMPLETION_ROOT':str(tmp_path),
           'WAVE':'wave-a','ROLE':'worker-a','ASSIGNMENT_ID':'task-a','GENERATION':'1',
           'DEADLINE':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
           'OUTCOME':'succeeded','RESULT_REFERENCE':'fixture-result','LIVENESS':'unknown',
           'MERGE_ASSIGNMENT_ID':'task-merge','MERGE_GENERATION':'2',
           'MERGE_DEADLINE':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
           'MERGE_OUTCOME':'succeeded','MERGE_RESULT_REFERENCE':'fixture-github-result',
           'LIVENESS_OBSERVED_AT':'','FLOW_WAVE_RECEIPT_ADAPTER':''}
    env.pop('CPP_DIR', None)
    results = []
    for recipe in recipes:
        result = subprocess.run(['bash','-c',recipe],env=env,capture_output=True,text=True,timeout=8)
        assert result.returncode == 0, result.stdout + result.stderr
        value = json.loads(result.stdout)
        results.append(value)
        if value['status'] == 'assigned':
            env['ASSIGNMENT_ID'] = value['identity']['assignment_id']
            env['GENERATION'] = str(value['identity']['generation'])
    expected = (['assigned','recorded','complete'] if section == 'setup' else
                ['assigned','recorded','complete','complete','assigned','recorded','complete'])
    assert [r['status'] for r in results] == expected


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
    assign(tmp_path, env=env)
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


def load_helper():
    import importlib.util
    spec = importlib.util.spec_from_file_location('wave_completion_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_atomic_replacement_syncs_directory_after_rename(tmp_path, monkeypatch):
    import stat
    helper = load_helper()
    events = []
    real_sync, real_replace = helper.os.fsync, helper.os.replace
    def sync(fd):
        events.append('sync-dir' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'sync-file')
        return real_sync(fd)
    def replace(*args):
        events.append('replace')
        return real_replace(*args)
    monkeypatch.setattr(helper.os,'fsync',sync)
    monkeypatch.setattr(helper.os,'replace',replace)
    helper.atomic_write(tmp_path / 'result.json', {'result':'fixture'})
    assert events == ['sync-file','replace','sync-dir']


@pytest.mark.parametrize('now', [BEFORE, AFTER])
def test_disappeared_store_is_unknown_without_extension(tmp_path, now):
    assign(tmp_path)
    publish(tmp_path)
    store = tmp_path / 'receipts'
    assert store.is_dir()
    store.rename(tmp_path / 'detached-receipts')
    code, value = call(tmp_path,'check','--now',now,'--liveness','alive','--observed-at',now)
    assert code == 3 and value['status'] == 'unknown'
    state = json.loads((tmp_path / 'wave-a/assignments/worker-a.json').read_text())
    assert state['extensions'] == 0
    assert not store.exists()


def test_receipt_finished_during_adapter_get_is_not_future_evidence(tmp_path):
    assign(tmp_path)
    receipt = publish(tmp_path)['receipt']
    env = adapter(tmp_path, 'import json,sys,time\nfrom datetime import datetime,timezone\n'
                  'time.sleep(.05)\n'
                  f'receipt={receipt!r}\n'
                  'receipt["finished_at"]=datetime.now(timezone.utc).isoformat()\n'
                  'print(json.dumps({"key":sys.argv[2],"receipt":receipt}))\n')
    env['FLOW_WAVE_RECEIPT_TIMEOUT'] = '2'
    code, value = call(tmp_path,'check',env=env)
    assert code == 0 and value['status'] == 'complete'


def test_inconsistent_unextended_assignment_is_unknown(tmp_path):
    assign(tmp_path)
    path = tmp_path / 'wave-a/assignments/worker-a.json'
    value = json.loads(path.read_text())
    value['deadline'] = '2027-01-01T00:00:00Z'
    assert value['extensions'] == 0 and value['deadline'] != value['initial_deadline']
    path.write_text(json.dumps(value))
    code, result = call(tmp_path,'check','--now',AFTER)
    assert code == 3 and result['status'] == 'unknown'


def test_assignment_retry_does_not_recreate_disappeared_store(tmp_path):
    assign(tmp_path)
    (tmp_path / 'receipts').rename(tmp_path / 'detached')
    code, value = call(tmp_path,'assign','--deadline',DEADLINE,'--now',BEFORE,'--extension-seconds','60')
    assert code == 3 and value['status'] == 'unknown'
    assert not (tmp_path / 'receipts').exists()


def test_new_state_directories_sync_parent_entries(tmp_path, monkeypatch):
    helper = load_helper()
    synced = []
    actual = helper.sync_directory
    def sync(path):
        synced.append(path)
        actual(path)
    monkeypatch.setattr(helper,'sync_directory',sync)
    helper.durable_mkdir(tmp_path / 'wave/assignments')
    assert synced == [tmp_path, tmp_path / 'wave']


def test_missing_assignment_cannot_reset_one_extension_budget(tmp_path):
    assign(tmp_path)
    code, value = call(tmp_path,'check','--now',AFTER,'--liveness','alive','--observed-at',AFTER)
    assert code == 4 and value['status'] == 'extended'
    path = tmp_path / 'wave-a/assignments/worker-a.json'
    path.unlink()
    assert not path.exists()
    code, value = call(tmp_path,'assign','--deadline','2026-11-08T11:00:00Z','--now',AFTER)
    assert code == 3 and value['status'] == 'unknown'
    assert not path.exists()


def test_failed_directory_sync_is_retried_before_publication_ack(tmp_path, monkeypatch, capsys):
    helper = load_helper()
    common = ['--state-root',str(tmp_path),*IDENTITY]
    assert helper.main(['assign',*common,'--deadline',DEADLINE,'--now',BEFORE]) == 0
    capsys.readouterr()
    actual = helper.sync_directory
    def fail_receipt_directory(path):
        if path == tmp_path / 'receipts':
            raise OSError('fixture directory sync unavailable')
        return actual(path)
    monkeypatch.setattr(helper,'sync_directory',fail_receipt_directory)
    args = ['complete',*common,'--outcome','succeeded','--finished-at',BEFORE]
    assert helper.main(args) == 3
    assert json.loads(capsys.readouterr().out)['status'] == 'unknown'
    receipt = json.loads(next((tmp_path / 'receipts').glob('*.json')).read_text())
    assert helper.main(args) == 3
    assert json.loads(capsys.readouterr().out)['status'] == 'unknown'
    monkeypatch.setattr(helper,'sync_directory',actual)
    assert helper.main(args) == 0
    assert json.loads(capsys.readouterr().out)['receipt'] == receipt


def test_visible_receipt_with_failing_directory_sync_is_unknown_to_reader(tmp_path, monkeypatch, capsys):
    helper = load_helper()
    common = ['--state-root',str(tmp_path),*IDENTITY]
    assert helper.main(['assign',*common,'--deadline',DEADLINE,'--now',BEFORE]) == 0
    actual = helper.sync_directory
    def fail_receipt_directory(path):
        if path == tmp_path / 'receipts':
            raise OSError('fixture directory sync unavailable')
        return actual(path)
    monkeypatch.setattr(helper,'sync_directory',fail_receipt_directory)
    assert helper.main(['complete',*common,'--outcome','succeeded','--finished-at',BEFORE]) == 3
    capsys.readouterr()
    assert helper.main(['check',*common,'--now',AFTER]) == 3
    assert json.loads(capsys.readouterr().out)['status'] == 'unknown'


@pytest.mark.skipif(shutil.which('bash') is None, reason='requires bash installer')
def test_completion_helper_is_installed_at_stable_path(tmp_path):
    home = tmp_path / 'home'
    result = subprocess.run(['bash',str(ROOT / 'scripts/flow-helpers-install.sh')],
                            env={**os.environ,'FLOW_HELPERS_HOME':str(home),
                                 'FLOW_HELPERS_SOURCE':str(ROOT / 'scripts')},
                            capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stderr
    assert (home / '.claude/scripts/flow-wave-completion.py').is_file()


def test_phase_two_calls_completion_protocol_in_actual_loop():
    text = (ROOT / '.claude/commands/flow/wave.md').read_text()
    phase = text.split('## Phase 2:',1)[1].split('## Phase 3:',1)[0]
    for section, verbs in [('2. Assign',('assign',)),('4. Verify the PR',('complete','check')),
                           ('5. Release the next issue',('check',))]:
        body = phase.split('### '+section,1)[1].split('\n### ',1)[0]
        for verb in verbs:
            assert f'flow-wave-completion.py {verb}' in body


def test_higher_generation_recovers_marker_only_assignment(tmp_path):
    assign(tmp_path)
    path = tmp_path / 'wave-a/assignments/worker-a.json'
    path.unlink()
    code, value = call(tmp_path,'assign','--deadline',DEADLINE,'--now',BEFORE,
                       '--generation','2','--assignment-id','task-b')
    assert code == 0 and value['status'] == 'assigned'
    assert value['identity']['generation'] == 2 and value['extensions'] == 0
    code, value = call(tmp_path,'check','--now',AFTER)
    assert code == 3 and value['status'] == 'unknown'


@pytest.mark.parametrize('seconds,expected', [(2,0),(5,0),(6,3)])
def test_finished_at_has_bounded_clock_skew(tmp_path, seconds, expected):
    from datetime import datetime, timedelta
    assign(tmp_path)
    publish(tmp_path)
    path = next((tmp_path / 'receipts').glob('*.json'))
    receipt = json.loads(path.read_text())
    receipt['finished_at'] = (datetime.fromisoformat(AFTER.replace('Z','+00:00'))
                              + timedelta(seconds=seconds)).isoformat()
    path.write_text(json.dumps(receipt))
    code, value = call(tmp_path,'check','--now',AFTER,'--message-arrived')
    assert code == expected
    assert value['status'] == ('complete' if expected == 0 else 'unknown')


def test_readback_inequality_guard(tmp_path, monkeypatch, capsys):
    helper = load_helper()
    receipt = publish_fixture_receipt()
    changed = {**receipt,'finished_at':DEADLINE}
    class Store:
        reads = 0
        def get(self, key):
            self.reads += 1
            return None if self.reads == 1 else changed
        def put(self, key, value):
            return receipt
    monkeypatch.setattr(helper,'store_for',lambda root:Store())
    assert helper.main(['complete','--state-root',str(tmp_path),*IDENTITY,
                        '--outcome','succeeded','--finished-at',BEFORE]) == 3
    assert json.loads(capsys.readouterr().out)['status'] == 'unknown'


def publish_fixture_receipt():
    return {'schema':1,'identity':{'wave':'wave-a','role':'worker-a','assignment_id':'task-a','generation':1},
            'outcome':'succeeded','finished_at':BEFORE,'evidence':''}


def test_adapter_put_rejects_different_terminal_result(monkeypatch):
    helper = load_helper()
    receipt = publish_fixture_receipt()
    store = helper.AdapterStore('["unused"]')
    monkeypatch.setattr(store,'invoke',lambda *args:{**receipt,'outcome':'failed'})
    with pytest.raises(helper.Unknown):
        store.put('fixture-key',receipt)


def test_gone_with_fresh_timestamp_never_extends(tmp_path):
    assign(tmp_path)
    code, value = call(tmp_path,'check','--now',AFTER,'--liveness','gone','--observed-at',AFTER)
    assert code == 3 and value['status'] == 'unknown'
    assert json.loads((tmp_path / 'wave-a/assignments/worker-a.json').read_text())['extensions'] == 0


@pytest.mark.parametrize('body', [
    'print(json.dumps({"key":"wrong-key","receipt":None}))',
    'print(json.dumps({"key":sys.argv[2],"receipt":None}));sys.exit(7)',
    'print(" "*1048577+json.dumps({"key":sys.argv[2],"receipt":None}))',
])
def test_adapter_response_guards_distinguish_unusable_from_absence(tmp_path, body):
    assign(tmp_path)
    env = adapter(tmp_path,'import json,sys\n'+body+'\n')
    env['FLOW_WAVE_RECEIPT_TIMEOUT'] = '2'
    code, value = call(tmp_path,'check','--now',BEFORE,env=env)
    assert code == 3 and value['status'] == 'unknown'


def test_file_store_rejects_conflict_inside_publication_lock(tmp_path):
    helper = load_helper()
    store = helper.FileStore(tmp_path)
    store.initialize()
    receipt = publish_fixture_receipt()
    existing = {**receipt,'outcome':'failed'}
    store.put('fixture',existing)
    with pytest.raises(helper.Refused):
        store.put('fixture',receipt)
    assert store.get('fixture') == existing


@pytest.mark.parametrize('finished', ['20261108T100000Z','2026-11-08 10:00:00Z',
    '2026-11-08T10:00:00-00:00','2026-11-08T10:00:00.1234567Z'])
def test_receipt_timestamp_grammar_is_exact(tmp_path, finished):
    assign(tmp_path)
    code, value = call(tmp_path,'complete','--outcome','succeeded','--finished-at',finished)
    assert code == 3 and value['status'] == 'unknown'


def test_generation_is_json_exact_integer(tmp_path):
    code, value = call(tmp_path,'assign','--deadline',DEADLINE,'--now',BEFORE,
                       '--generation',str(2**53))
    assert code == 3 and value['status'] == 'unknown'


def test_unknown_receipt_fields_are_rejected(tmp_path):
    assign(tmp_path)
    publish(tmp_path)
    path = next((tmp_path / 'receipts').glob('*.json'))
    receipt = json.loads(path.read_text())
    receipt['extra'] = {}
    path.write_text(json.dumps(receipt))
    code, value = call(tmp_path,'check','--now',AFTER)
    assert code == 3 and value['status'] == 'unknown'


@pytest.mark.parametrize('payload', [
    '{"key":"wrong","key":"KEY","receipt":null}',
    '{"key":"KEY","receipt":NaN}',
    '{"key":"KEY","receipt":Infinity}',
    '{"key":"KEY","receipt":-Infinity}',
    '{"key":"KEY","receipt":1e999}',
])
def test_adapter_rejects_non_strict_json(tmp_path, payload):
    helper = load_helper()
    env = adapter(tmp_path, 'import sys\nprint('+repr(payload)+'.replace("KEY",sys.argv[2]))\n')
    os_argv = env['FLOW_WAVE_RECEIPT_ADAPTER']
    store = helper.AdapterStore(os_argv)
    with pytest.raises(helper.Unknown):
        store.get('fixture-key')


def test_adapter_encoding_is_explicit_utf8(tmp_path, monkeypatch):
    helper = load_helper()
    receipt = publish_fixture_receipt()
    receipt['evidence'] = 'caf\u00e9'
    env = adapter(tmp_path,'import json,sys\n'
                  f'value={{"key":sys.argv[2],"receipt":{receipt!r}}}\n'
                  'sys.stdout.buffer.write(json.dumps(value,ensure_ascii=False).encode("utf-8"))\n')
    observed = []
    actual = helper.subprocess.Popen
    def launch(*args, **kwargs):
        observed.append(kwargs)
        return actual(*args, **kwargs)
    monkeypatch.setattr(helper.subprocess,'Popen',launch)
    store = helper.AdapterStore(env['FLOW_WAVE_RECEIPT_ADAPTER'])
    assert store.get('fixture-key')['evidence'] == 'caf\u00e9'
    assert observed and observed[0].get('encoding') == 'utf-8'


@pytest.mark.parametrize('backend', ['filesystem','adapter'])
def test_receipt_cannot_predate_its_assignment(tmp_path, backend):
    assign(tmp_path)  # Initializes the shared store for a different generation.
    args = ['--generation','2','--assignment-id','task-b']
    code, value = call(tmp_path,'complete','--outcome','succeeded',
                       '--finished-at','2000-01-01T00:00:00Z',*args)
    assert code == 0 and value['status'] == 'recorded'
    env = None
    if backend == 'adapter':
        receipt = value['receipt']
        env = adapter(tmp_path,'import json,sys\nprint(json.dumps({"key":sys.argv[2],"receipt":'
                      + repr(receipt) + '}))\n')
    code, value = call(tmp_path,'assign','--deadline',DEADLINE,'--now',BEFORE,*args)
    assert code == 0 and value['status'] == 'assigned'
    code, value = call(tmp_path,'check','--now',AFTER,*args,env=env)
    assert code == 3 and value['status'] == 'unknown'


@pytest.mark.parametrize('seconds,expected', [(2,0),(5,0),(6,3)])
def test_receipt_lower_time_bound_has_skew_allowance(tmp_path, seconds, expected):
    from datetime import datetime, timedelta
    assign(tmp_path)
    finished = (datetime.fromisoformat(BEFORE.replace('Z','+00:00')) - timedelta(seconds=seconds)).isoformat()
    code, value = call(tmp_path,'complete','--outcome','succeeded','--finished-at',finished)
    assert code == 0
    code, value = call(tmp_path,'check','--now',AFTER)
    assert code == expected and value['status'] == ('complete' if expected == 0 else 'unknown')


@pytest.mark.skipif(shutil.which('bash') is None, reason='requires bash recipe')
def test_published_rework_assigns_higher_generation(tmp_path):
    import re
    from datetime import datetime, timedelta, timezone

    text = (ROOT / '.claude/commands/flow/wave.md').read_text()
    recipe = re.search(r'<!-- CPP_WAVE_REWORK_BEGIN -->\s*```bash\n(.*?)```',text,re.S)
    assert recipe is not None, 'verification rework needs its own published assignment'
    assign(tmp_path)
    publish(tmp_path)
    task_home = tmp_path / 'home'
    installed = task_home / '.claude/scripts/flow-wave-completion.py'
    installed.parent.mkdir(parents=True)
    installed.write_bytes(SCRIPT.read_bytes())
    env = {**os.environ,'HOME':str(task_home),'FLOW_WAVE_COMPLETION_ROOT':str(tmp_path),
           'WAVE':'wave-a','ROLE':'worker-a','ASSIGNMENT_ID':'task-a','GENERATION':'1',
           'REWORK_ASSIGNMENT_ID':'task-rework','REWORK_GENERATION':'2',
           'REWORK_DEADLINE':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
           'FLOW_WAVE_RECEIPT_ADAPTER':''}
    env.pop('CPP_DIR',None)
    result = subprocess.run(['bash','-c',recipe[1]],env=env,capture_output=True,text=True,timeout=8)
    assert result.returncode == 0, result.stdout+result.stderr
    assigned = json.loads(result.stdout)
    assert assigned['status'] == 'assigned' and assigned['identity']['generation'] == 2
    assert assigned['identity']['assignment_id'] == 'task-rework'
    assert assigned['extensions'] == 0
    # The old PR-ready receipt cannot complete the rework assignment.
    code, value = call(tmp_path,'check','--generation','2','--assignment-id','task-rework')
    assert code == 4 and value['status'] == 'waiting'


@pytest.mark.skipif(shutil.which('bash') is None, reason='requires bash recipe')
def test_published_merge_observes_github_state(tmp_path):
    import re
    text = (ROOT / '.claude/commands/flow/wave.md').read_text()
    recipe = re.search(r'<!-- CPP_WAVE_MERGE_OBSERVE_BEGIN -->\s*```bash\n(.*?)```',text,re.S)
    assert recipe is not None
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    gh = bindir / 'gh'
    gh.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$GH_CALLS"\n'
                  'printf \'%s\\n\' \'{"state":"MERGED","mergedAt":"2026-11-09T00:00:00Z",'
                  '"mergeCommit":{"oid":"fixture-merge"},"headRefOid":"fixture-head"}\'\n')
    gh.chmod(0o755)
    calls = tmp_path / 'gh-calls'
    env = {**os.environ,'PATH':str(bindir)+os.pathsep+os.environ['PATH'],
           'PR':'42','REPO':'fixture/repo','GH_CALLS':str(calls)}
    assert shutil.which('gh',path=env['PATH']) == str(gh), 'recipe must never contact live GitHub'
    result = subprocess.run(['bash','-c',recipe[1]],env=env,capture_output=True,text=True,timeout=8)
    assert result.returncode == 0
    assert json.loads(result.stdout)['state'] == 'MERGED'
    assert calls.read_text().splitlines() == ['pr','view','42','--repo','fixture/repo','--json',
                                             'state,mergedAt,mergeCommit,headRefOid']


def test_assignment_timestamp_is_stable_on_idempotent_retry(tmp_path):
    code, first = call(tmp_path,'assign','--deadline',DEADLINE,'--now',BEFORE)
    assert code == 0 and first['assigned_at'] == BEFORE
    code, second = call(tmp_path,'assign','--deadline',DEADLINE,'--now','2026-11-08T10:00:30Z')
    assert code == 0 and second['assigned_at'] == first['assigned_at']
