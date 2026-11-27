"""Frozen fixture replay; private tmux only, no pi/provider calls or owner files."""
import base64
import csv
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


def archive_path(folder, name):
    if name.endswith('.sh.txt'):
        name = name[:-4] + '.b64'
    elif name.endswith('.sh'):
        name += '.b64'
    elif name.endswith('.py'):
        name += '.txt'
    return folder / name


def fixture_bytes(path):
    raw = path.read_bytes()
    if path.suffix != '.b64':
        return raw
    if not raw.endswith(b'\n'):
        raise ValueError('frozen base64 must have one terminating newline')
    decoded = base64.b64decode(raw[:-1], validate=True)
    if base64.b64encode(decoded) + b'\n' != raw:
        raise ValueError('noncanonical frozen base64')
    return decoded


def fixture_text(path):
    return fixture_bytes(path).decode('utf-8')


def stored(name):
    return archive_path(EXPORTED, name)


def test_serialized_shell_population_and_both_digests():
    root = EXPORTED.parent
    recorded = {}
    for name in ['exported', 'xcheck', 'v3', 'v4', 'exact-target', 'exact-pane-target', 'final']:
        folder = root / name
        manifest = folder / ('SOURCE-SHA256SUMS.txt' if name == 'final' else 'SHA256SUMS')
        for line in manifest.read_text().splitlines():
            digest, member = line.split('  ', 1)
            path = archive_path(folder, member)
            if path.suffix == '.b64':
                recorded[path.relative_to(root).as_posix()] = digest
    # These derived collaborators were not members of the supplied tarballs;
    # their complete hashes were recorded in the pre-packaging driver README.
    recorded.update({
        'v3/session-v3.sh.b64': '80495a5ab7b812d0e93425fe695e938b52bbb26b1ad987056da1d67cf2d0813a',
        'v4/run-v4.sh.b64': '8d054e350928b6afa582ab0370d483516e83ccece16d54dcf68d54e6b3993a2b',
        'v4/session-v4.sh.b64': 'b44ada9545bf4c3a559ee12a7a2167b4de8c304efcee81e8a053d54e09970afb',
    })
    with (root / 'SHELL-STORAGE.tsv').open() as source:
        rows = list(csv.DictReader(source, delimiter='\t'))
    assert rows
    assert {p.relative_to(root).as_posix() for p in root.rglob('*.sh.b64')} == {
        row['stored_path'] for row in rows}
    assert set(recorded) == {row['stored_path'] for row in rows}
    for row in rows:
        path = root / row['stored_path']
        assert row['stored_path'] == row['previous_path'][:-4] + '.b64'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['stored_sha256']
        decoded = fixture_bytes(path)
        assert decoded.startswith(b'#!')
        assert row['decoded_sha256'] == recorded[row['stored_path']]
        assert hashlib.sha256(decoded).hexdigest() == row['decoded_sha256']


@pytest.mark.parametrize('name,expected', [
    ('invalid', b'not base64!\n'), ('no-newline', b'YQ=='), ('noncanonical', b'YR==\n'),
])
def test_serialized_shell_reader_refuses_corrupt_input(name, expected):
    path = ROOT / 'tests/fixtures' / f'pi-driver-{name}.b64'
    assert path.read_bytes() == expected, 'negative input precondition changed'
    with pytest.raises(ValueError):
        fixture_bytes(path)


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
        assert hashlib.sha256(fixture_bytes(path)).hexdigest() == digest, name
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
    wrapper = (V4 / 'session-v4.sh.b64' if version == 4
               else V3 / 'session-v3.sh.b64' if version == 3 else stored('session.sh'))
    script.write_bytes(fixture_bytes(wrapper))
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
    record.write_bytes(fixture_bytes(stored('record.sh')))
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
    script.write_bytes(fixture_bytes(XCHECK / 'xcheck-v1.sh.b64'))
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
        path = archive_path(XCHECK, name)
        assert hashlib.sha256(fixture_bytes(path)).hexdigest() == digest
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
        path = archive_path(V3, name)
        assert hashlib.sha256(fixture_bytes(path)).hexdigest() == digest
    base = fixture_bytes(stored('session.sh'))
    assert fixture_bytes(V3 / 'session-v3.sh.b64') == base.replace(b'"$T5/run.sh"', b'"$T5/run-v3.sh"')
    assert 'capture-pane -p -e -J' in fixture_text(V3 / 'run-v3.sh.b64')


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
        original = archive_path(V3, name) if name == 'run-v3.sh' else stored(name)
        assert fixture_bytes(archive_path(EXACT, name)) == fixture_bytes(original).replace(b'-t pib3', b'-t =pib3')


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
        script.write_bytes(fixture_bytes(stored('close.sh') if original else EXACT / 'close.sh.b64'))
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
    scripts = '\n'.join(fixture_text(archive_path(folder, name))
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
    text = fixture_text(PANE_EXACT / 'close.sh.b64')
    assert 'send-keys -t =pib3:' in text
    assert 'kill-session -t =pib3 ' in text


V4 = EXPORTED.parent / 'v4'


def test_v4_export_and_wrapper_bindings():
    for line in (V4 / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = archive_path(V4, name)
        assert hashlib.sha256(fixture_bytes(path)).hexdigest() == digest
    assert fixture_bytes(V4 / 'run-v4.sh.b64') == fixture_bytes(PANE_EXACT / 'run-v3.sh.b64').replace(
        b'v3/classify-v3.py', b'v4/classify-v4.py')
    assert fixture_bytes(V4 / 'session-v4.sh.b64') == fixture_bytes(V3 / 'session-v3.sh.b64').replace(
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
