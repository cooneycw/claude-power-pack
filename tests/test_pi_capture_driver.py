"""Frozen host driver controls; no tmux, pi, provider calls or owner files."""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPORTED = ROOT / 'docs/measurements/pi/issue-1899-b3-driver/exported'
pytestmark = pytest.mark.skipif(
    shutil.which('python3') is None or shutil.which('bash') is None,
    reason='requires Python and bash for frozen classifier/cap replay',
)
VERDICTS = {
    '1-accept.txt': (0, 0), '1b-accept-after-tool.txt': (0, 1),
    '2-empty.txt': (1, 1), '3-stale-footer.txt': (1, 1),
    '4a-tool-running.txt': (1, 1), '4b-tool-phase-no-final.txt': (1, 1),
    '5-real-layout-tool-phase.txt': (0, 1), '6-real-header-only.txt': (0, 1),
    '7-real-layout-final.txt': (0, 0), '9-sanitized-real-layout-tool-phase.txt': (0, 1),
    '10-two-tool-headers-then-final.txt': (0, 0),
}


def stored(name):
    return EXPORTED / (name + '.txt' if name.endswith(('.py', '.sh')) else name)


def classify(version, control):
    return subprocess.run([sys.executable, str(stored(f'classify-v{version}.py')),
                           str(EXPORTED / 'controls' / control)], capture_output=True, text=True)


def candidate_version():
    return 1 if os.environ.get('CPP_PI_CAPTURE_ARCHIVE_V1') == '1' else 2


def test_exported_members_match_delivered_digests():
    assert hashlib.sha256((EXPORTED / 'SHA256SUMS').read_bytes()).hexdigest() == (
        '1a7585845015da109cfd806746865d36b0193821a26188e6edad0c8a54ece924')
    names = set()
    for line in (EXPORTED / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = stored(name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
        names.add(path.relative_to(EXPORTED).as_posix())
    actual = {p.relative_to(EXPORTED).as_posix() for p in EXPORTED.rglob('*') if p.is_file()}
    assert actual == names | {'SHA256SUMS'}


@pytest.mark.parametrize('control', sorted(VERDICTS))
@pytest.mark.parametrize('version', [1, 2])
def test_actual_archived_classifier_matrix(version, control):
    result = classify(version, control)
    expected = VERDICTS[control][version - 1]
    assert result.returncode == expected, result.stderr
    assert json.loads(result.stdout)['accept'] is (expected == 0)


def test_real_tool_phase_must_not_be_final():
    control = '9-sanitized-real-layout-tool-phase.txt'
    text = (EXPORTED / 'controls' / control).read_text()
    assert 'cpp-pi1899-stdio/probe-echo' in text
    assert text.count('NONCE_PLACEHOLDER_32_HEX_0000000') == 1
    result = classify(candidate_version(), control)
    assert result.returncode == 1, 'tool result without final was accepted'


def session_replay(tmp_path, control, version):
    # Exact session.sh bytes, with only its external run/close/record collaborators
    # replaced by fixture stubs. The real wrapper cap itself is not copied/rederived.
    folder = tmp_path / 'driver'
    folder.mkdir()
    script = folder / 'session.sh'
    wrapper = (V4 / 'session-v4.sh.txt' if version == 4
               else V3 / 'session-v3.sh.txt' if version == 3 else stored('session.sh'))
    script.write_bytes(wrapper.read_bytes())
    script.chmod(0o700)
    classifier = ((V4 if version == 4 else V3) / f'classify-v{version}.py.txt'
                  if version >= 3 else stored(f'classify-v{version}.py'))
    capture = EXPORTED / 'controls' / control
    run = (f'#!/bin/sh\n{shlex.quote(sys.executable)} {shlex.quote(str(classifier))} '
           f'{shlex.quote(str(capture))} > "$(dirname "$0")/accept-$2.json"\n')
    for name, body in [(f'run-v{version}.sh' if version >= 3 else 'run.sh', run),
                       ('close.sh', '#!/bin/sh\nprintf "close\\n" >> "$CAPTURE_TEST_TRACE"\n'),
                       ('record.sh', '#!/bin/sh\nprintf "record\\n" >> "$CAPTURE_TEST_TRACE"\n')]:
        path = folder / name
        path.write_text(body)
        path.chmod(0o700)
    tools = tmp_path / 'tools'
    tools.mkdir()
    (tools / 'python3').symlink_to(sys.executable)
    # dirname is the only other external command used by the wrapper/stubs.
    dirname = tools / 'dirname'
    dirname.write_text('#!/usr/bin/env python3\nimport os,sys\nprint(os.path.dirname(sys.argv[1]))\n')
    dirname.chmod(0o700)
    trace = tmp_path / 'trace'
    assert shutil.which('tmux', path=str(tools)) is None, 'fixture must lack live tmux'
    env = {'PATH': str(tools), 'HOME': str(tmp_path), 'CAPTURE_TEST_TRACE': str(trace)}
    result = subprocess.run([shutil.which('bash'), str(script), 'alpha', 'T2-alpha', 'stdio'],
                            env=env, cwd=tmp_path, capture_output=True, text=True)
    return result, trace


def test_session_cap_refuses_two_tools_before_close_record(tmp_path):
    control = '10-two-tool-headers-then-final.txt'
    text = (EXPORTED / 'controls' / control).read_text()
    assert text.count('cpp-pi1899-stdio/probe-echo tag=') == 2
    result, trace = session_replay(tmp_path, control, candidate_version())
    assert result.returncode == 6, result.stdout + result.stderr
    assert 'extra tool attempt' in result.stdout and 'pi LEFT OPEN' in result.stdout
    assert not trace.exists(), 'close or record ran after the extra-attempt STOP'


def test_session_cap_allows_one_completed_tool(tmp_path):
    result, trace = session_replay(tmp_path, '7-real-layout-final.txt', 2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert trace.read_text().splitlines() == ['close', 'record']


def test_actual_record_script_keeps_log_without_accepted_reply(tmp_path):
    setup, _trace = session_replay(tmp_path, '7-real-layout-final.txt', 2)
    assert setup.returncode == 0
    folder = tmp_path / 'driver'
    (folder / 'accept-T2-alpha.json').unlink()
    assert not (folder / 'accept-T2-alpha.json').exists()
    record = folder / 'record.sh'
    record.write_bytes(stored('record.sh').read_bytes())
    log = folder / 'pipe-T2-alpha.log'
    log.write_bytes(b'controlled fixture capture retained')
    assert shutil.which('tmux', path=str(tmp_path / 'tools')) is None, 'fixture must lack live tmux'
    result = subprocess.run([shutil.which('bash'), str(record), 'T2-alpha', 'stdio'],
                            env={'PATH': str(tmp_path / 'tools'), 'HOME': str(tmp_path)},
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1 and 'pane log KEPT' in result.stdout
    assert log.read_bytes() == b'controlled fixture capture retained'


XCHECK = EXPORTED.parent / 'xcheck'
XCASES = {'a-screen1-backend0': 1, 'b-screen0-backend1': 1,
          'c-0eq0': 0, 'd-1eq1': 0, 'e-missing-accept': 4,
          'e2-missing-accept-backend0': 4, 'f-malformed-events': 4,
          'g-other-batch': 1}


def xcheck_replay(case, tmp_path, version=2):
    folder = XCHECK / 'cases' / case
    if version == 2:
        return subprocess.run([sys.executable, str(XCHECK / 'xcheck-v2.py.txt'),
                               str(folder / 'events.jsonl'), str(XCHECK / 'cases/batch.json'),
                               str(folder / 'accept-T2-alpha.json'), 'T2-alpha'],
                              capture_output=True, text=True)
    # Exact v1 script, isolated HOME and only fixture-controlled inputs.
    script = tmp_path / 'xcheck.sh'
    script.write_bytes((XCHECK / 'xcheck-v1.sh.txt').read_bytes())
    accept = folder / 'accept-T2-alpha.json'
    if accept.exists():
        shutil.copyfile(accept, tmp_path / accept.name)
    backend = tmp_path / '.cpp-pi-1899-probe/work/pi-1899-b3'
    backend.mkdir(parents=True)
    shutil.copyfile(folder / 'events.jsonl', backend / 'events.jsonl')
    return subprocess.run([shutil.which('bash'), str(script), 'T2-alpha'],
                          env={**os.environ, 'HOME': str(tmp_path)},
                          capture_output=True, text=True)


def test_xcheck_export_hashes():
    for line in (XCHECK / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = XCHECK / (name + '.txt' if name.endswith(('.py', '.sh')) else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert hashlib.sha256((XCHECK / 'xcheck-v2.py.txt').read_bytes()).hexdigest() == (
        'ad77186ad2ec9e8954b81dabcaeabaa92357a2f677b510c950e748f4af2593d7')


@pytest.mark.parametrize('case', sorted(XCASES))
def test_xcheck_bound_verdicts(case, tmp_path):
    version = 1 if os.environ.get('CPP_PI_XCHECK_ARCHIVE_V1') == '1' else 2
    result = xcheck_replay(case, tmp_path, version)
    assert result.returncode == XCASES[case], result.stdout + result.stderr
    if version == 2:
        assert json.loads(result.stdout)['verdict'] == {0: 'AGREE', 1: 'DISAGREE', 4: 'REFUSE'}[XCASES[case]]


V3 = EXPORTED.parent / 'v3'


def test_v3_delivered_hashes_and_selected_wrapper():
    for line in (V3 / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = V3 / (name + '.txt' if name.endswith(('.py', '.sh')) else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    base = stored('session.sh').read_bytes()
    assert (V3 / 'session-v3.sh.txt').read_bytes() == base.replace(b'"$T5/run.sh"', b'"$T5/run-v3.sh"')
    assert 'capture-pane -p -e -J' in (V3 / 'run-v3.sh.txt').read_text()


@pytest.mark.parametrize('control', sorted(p.name for p in (V3 / 'cases').glob('*.txt')))
def test_v3_final_only_controls(control):
    version = 2 if os.environ.get('CPP_PI_CAPTURE_ARCHIVE_V2') == '1' else 3
    result = subprocess.run([sys.executable, str(V3 / f'classify-v{version}.py.txt'),
                             str(V3 / 'cases' / control)], capture_output=True, text=True)
    expected = 0 if control.startswith(('S1-', 'S8-')) else 1 if control.startswith('S') else VERDICTS[control][1]
    assert result.returncode == expected, result.stdout + result.stderr
    data = json.loads(result.stdout)
    if control.startswith('S1-'):
        assert data['reply'] == 'TOOL_UNAVAILABLE'
    if control.startswith('S8-'):
        assert data['reply'].startswith('{') and '\x1b' not in data['reply']
        assert data['reply'].count('\n') == 0


def test_v3_actual_session_cap_and_positive(tmp_path):
    two = tmp_path / 'two'
    two.mkdir()
    result, trace = session_replay(two, '10-two-tool-headers-then-final.txt', 3)
    assert result.returncode == 6 and not trace.exists()
    one = tmp_path / 'one'
    one.mkdir()
    result, trace = session_replay(one, '7-real-layout-final.txt', 3)
    assert result.returncode == 0 and trace.read_text().splitlines() == ['close', 'record']


EXACT = EXPORTED.parent / 'exact-target'


@pytest.fixture
def tmux_case(tmp_path):
    # Caller files deliberately exceed an AF_UNIX socket path's length budget.
    # Only the private socket needs a short path, independent of TMPDIR/xdist.
    caller = tmp_path / ('long-caller-' * 10)
    caller.mkdir()
    with tempfile.TemporaryDirectory(prefix='pi1899-tmux-', dir='/tmp') as folder:
        yield caller, str(Path(folder) / 's')


def test_exact_target_variants_change_only_target_selection():
    for name in ['start.sh', 'run.sh', 'run-v3.sh', 'close.sh']:
        original = V3 / (name + '.txt') if name == 'run-v3.sh' else stored(name)
        assert (EXACT / (name + '.txt')).read_bytes() == original.read_bytes().replace(b'-t pib3', b'-t =pib3')


@pytest.mark.skipif(shutil.which('tmux') is None, reason='requires tmux on an isolated socket')
@pytest.mark.parametrize('pi_exists', [False, True])
def test_actual_close_preserves_prefix_neighbor(tmux_case, pi_exists):
    # A separate server, disposable sessions, no provider or real fixture.
    tmp_path, socket = tmux_case
    tmux = shutil.which('tmux')

    def call(*args):
        return subprocess.run([tmux, '-S', socket, *args], capture_output=True, text=True)

    assert call('new-session', '-d', '-s', 'pib3http', 'sleep 60').returncode == 0
    try:
        if pi_exists:
            assert call('new-session', '-d', '-s', 'pib3', 'sleep 60').returncode == 0
        tools = tmp_path / 'tools'
        tools.mkdir()
        shim = tools / 'tmux'
        shim.write_text(f'#!/bin/sh\nexec {shlex.quote(tmux)} -S {shlex.quote(socket)} "$@"\n')
        shim.chmod(0o700)
        # Prevent the close script's wait; these are controlled exit receipts.
        (tmp_path / 'exit-T6-beta').write_text('0\n')
        script = tmp_path / 'close.sh'
        original = os.environ.get('CPP_PI_TMUX_PREFIX_OLD') == '1'
        script.write_bytes((stored('close.sh') if original else EXACT / 'close.sh.txt').read_bytes())
        subprocess.run([shutil.which('bash'), str(script), 'T6-beta'],
                       env={**os.environ, 'HOME': str(tmp_path), 'PATH': str(tools) + os.pathsep + os.environ['PATH']},
                       capture_output=True, text=True, timeout=5)
        assert call('has-session', '-t', '=pib3http').returncode == 0, 'close killed prefix-neighbor session'
        if pi_exists:
            assert call('has-session', '-t', '=pib3').returncode != 0
    finally:
        call('kill-server')


PANE_EXACT = EXPORTED.parent / 'exact-pane-target'


@pytest.mark.skipif(shutil.which('tmux') is None, reason='requires tmux on an isolated socket')
@pytest.mark.parametrize('operation', ['send-keys', 'capture-pane', 'pipe-pane'])
def test_actual_pane_target_from_corrected_scripts(tmux_case, operation):
    old = os.environ.get('CPP_PI_PANE_TARGET_OLD') == '1'
    folder = EXACT if old else PANE_EXACT
    scripts = '\n'.join((folder / (name + '.txt')).read_text()
                        for name in ['start.sh', 'run.sh', 'run-v3.sh', 'close.sh'])
    targets = set(re.findall(r'tmux ' + operation + r'[^;\n]*?-t (\S+)', scripts))
    assert len(targets) == 1
    target = targets.pop()
    _caller, socket = tmux_case

    def call(*args):
        return subprocess.run([shutil.which('tmux'), '-S', socket, *args], capture_output=True, text=True)

    assert call('new-session', '-d', '-s', 'pib3http', 'sleep 60').returncode == 0
    try:
        # No pi session: never resolve to the prefix neighbor.
        args = ['-p'] if operation == 'capture-pane' else []
        assert call(operation, '-t', target, *args).returncode != 0
        assert call('has-session', '-t', '=pib3http').returncode == 0
        assert call('new-session', '-d', '-s', 'pib3', 'sleep 60').returncode == 0
        # With pi present every selected pane operation must actually work.
        result = call(operation, '-t', target, *args)
        assert result.returncode == 0, result.stderr
    finally:
        call('kill-server')


def test_corrected_close_keeps_session_target_and_pane_target_distinct():
    text = (PANE_EXACT / 'close.sh.txt').read_text()
    assert 'send-keys -t =pib3:' in text
    assert 'kill-session -t =pib3 ' in text


V4 = EXPORTED.parent / 'v4'


def test_v4_export_and_wrapper_bindings():
    for line in (V4 / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = V4 / (name + '.txt' if name.endswith('.py') else name)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert (V4 / 'run-v4.sh.txt').read_bytes() == (PANE_EXACT / 'run-v3.sh.txt').read_bytes().replace(
        b'v3/classify-v3.py', b'v4/classify-v4.py')
    assert (V4 / 'session-v4.sh.txt').read_bytes() == (V3 / 'session-v3.sh.txt').read_bytes().replace(
        b'run-v3.sh', b'run-v4.sh')


@pytest.mark.parametrize('control', sorted(p.name for p in (V4 / 'cases').glob('*.txt')))
def test_v4_colour_and_retained_controls(control):
    version = 3 if os.environ.get('CPP_PI_CAPTURE_ARCHIVE_V3') == '1' else 4
    result = subprocess.run([sys.executable, str(V4 / f'classify-v{version}.py.txt'),
                             str(V4 / 'cases' / control)], capture_output=True, text=True)
    if control.startswith('C'):
        expected = 1 if control.startswith('C10-') else 0
    else:
        expected = 0 if control.startswith(('S1-', 'S8-')) else 1 if control.startswith('S') else VERDICTS[control][1]
    assert result.returncode == expected, result.stdout + result.stderr
    if control.startswith('C') and expected == 0:
        assert json.loads(result.stdout)['reply'] == 'TOOL_UNAVAILABLE'


def test_v4_session_cap_and_completed_positive(tmp_path):
    for name, control, expected in [('two', '10-two-tool-headers-then-final.txt', 6),
                                     ('one', '7-real-layout-final.txt', 0)]:
        folder = tmp_path / name
        folder.mkdir()
        result, trace = session_replay(folder, control, 4)
        assert result.returncode == expected, result.stdout + result.stderr
        assert trace.exists() is (expected == 0)
