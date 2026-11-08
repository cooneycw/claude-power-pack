"""Host probes use bounded local responses; no live credential source is touched."""
import json
import os
import shutil
import subprocess
from dataclasses import replace
from types import SimpleNamespace

import pytest

from lib.cicd import host, providers

CANARY = 'host-ci-private-canary-1609'
requires_git = pytest.mark.skipif(shutil.which('git') is None, reason='requires git')
requires_bash_python = pytest.mark.skipif(
    shutil.which('bash') is None or shutil.which('python3') is None,
    reason='requires bash and python3',
)


def response(code=0, stdout='', stderr=''):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def github(scopes='repo, read:org', *, auth=0, api=0):
    header = '' if scopes is None else f'X-OAuth-Scopes: {scopes}\r\n'
    return {
        ('gh', '--version'): response(stdout='gh version 2.81.0 (private details)'),
        ('gh', 'auth', 'status', '--hostname', 'github.com'): response(auth, stderr=CANARY),
        ('gh', 'api', '--include', '--hostname', 'github.com', 'user'): response(
            api, 'HTTP/2.0 200 OK\r\n' + header + '\r\n' + json.dumps({'login': CANARY})),
    }


def context(mapping=None, *, tools=('gh',), env=None):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert tuple(argv) in (mapping or {}), f'unstubbed command: {argv[0]}'
        result = mapping[tuple(argv)]
        if isinstance(result, Exception):
            raise result
        return result

    return host.ProbeContext(run=run, which=lambda name: name if name in tools else None,
                             env=env or {}, container=False), calls


@pytest.mark.parametrize('scopes,auth,api,status,reason', [
    ('repo', 0, 0, 'ready', 'authenticated'),
    ('read:org, repo, workflow', 0, 0, 'ready', 'authenticated'),
    ('repo', 1, 0, 'missing', 'auth-missing'),
    ('public_repo', 0, 0, 'missing', 'repo-scope-missing'),
    ('repo:status', 0, 0, 'missing', 'repo-scope-missing'),
    ('', 0, 0, 'missing', 'repo-scope-missing'),
    (None, 0, 0, 'unknown', 'scope-not-introspectable'),
    ('repo', 0, 1, 'unknown', 'probe-failed'),
    ('repo', 2, 0, 'unknown', 'probe-failed'),
])
def test_github_real_auth_and_exact_scope(scopes, auth, api, status, reason):
    ctx, calls = context(github(scopes, auth=auth, api=api))
    got = host.check_github(ctx)
    assert (got['status'], got['reason']) == (status, reason)
    assert got['versions'] == {'gh': '2.81.0'}
    assert CANARY not in json.dumps(got)
    assert all(CANARY not in json.dumps(argv) for argv, _ in calls)
    assert not any('repos/' in arg for argv, _ in calls for arg in argv)


@pytest.mark.parametrize('bad', [response(stdout='not headers ' + CANARY),
                                 response(stdout='HTTP/2 200\nX-OAuth-Scopes: repo\n\n[]'),
                                 response(stdout='HTTP/2 200\nX-OAuth-Scopes: repo\n'
                                                 'X-OAuth-Scopes: public_repo\n\n{"login":"x"}'),
                                 subprocess.TimeoutExpired('gh', 15, stderr=CANARY), OSError(CANARY)])
def test_github_unexamined_never_ready(bad):
    mapping = github()
    mapping[('gh', 'api', '--include', '--hostname', 'github.com', 'user')] = bad
    ctx, _ = context(mapping)
    got = host.check_github(ctx)
    assert got['status'] == 'unknown'
    assert CANARY not in json.dumps(got)


def woodpecker(*, secret=None, info=None):
    mapping = {('woodpecker-cli', '--version'): response(stdout='woodpecker-cli version 3.11.0')}
    if secret is not None:
        mapping[('aws', 'secretsmanager', 'get-secret-value', '--secret-id', 'fixture',
                 '--region', 'fixture-region', '--query', 'SecretString', '--output', 'text')] = secret
    if info is not None:
        mapping[('woodpecker-cli', 'info', '--format', '{{ .Login }}')] = info
    return mapping


@pytest.mark.parametrize('secret,status,reason', [
    (response(1, stderr=CANARY), 'unknown', 'credential-resolution-failed'),
    (response(stdout='not JSON ' + CANARY), 'unknown', 'credential-resolution-failed'),
    (response(stdout='{}'), 'missing', 'credentials-missing'),
    (response(stdout=json.dumps({'WOODPECKER_API_TOKEN': CANARY, 'WOODPECKER_HOST': 'https://fixture.invalid'})),
     'ready', 'authenticated'),
])
def test_woodpecker_resolver_is_stubbed_and_does_not_leak(secret, status, reason):
    ctx, calls = context(woodpecker(secret=secret, info=response(stdout=CANARY)),
                         tools=('woodpecker-cli', 'aws'),
                         env={'CPP_WOODPECKER_SECRET': 'fixture', 'AWS_REGION': 'fixture-region'})
    got = host.check_woodpecker(ctx)
    assert (got['status'], got['reason']) == (status, reason)
    assert CANARY not in json.dumps(got)
    assert all(CANARY not in json.dumps(argv) for argv, _ in calls)
    if status == 'ready':
        assert calls[-1][1]['env']['WOODPECKER_TOKEN'] == CANARY


def test_woodpecker_environment_positive_and_error():
    for info, status in [
                             (response(stdout='fixture-user'), 'ready'),
                             (response(1, stderr=CANARY), 'unknown')]:
        ctx, calls = context(woodpecker(info=info), tools=('woodpecker-cli',),
                             env={'WOODPECKER_API_TOKEN': CANARY, 'WOODPECKER_SERVER': 'https://fixture.invalid'})
        assert host.check_woodpecker(ctx)['status'] == status
        assert all('aws' not in argv for argv, _ in calls)


def test_missing_tools_and_credentials():
    ctx, _ = context(tools=())
    assert host.check_github(ctx) == host.verdict('missing', 'tool-absent')
    assert host.check_woodpecker(ctx) == host.verdict('missing', 'tool-absent')
    ctx, _ = context(woodpecker(), tools=('woodpecker-cli',))
    assert host.check_woodpecker(ctx)['reason'] == 'credentials-missing'


def test_registry_drives_mixed_probes_and_a_third_provider(monkeypatch):
    third = replace(providers.PROVIDERS['github-actions'], name='third', host_check='third-auth')
    monkeypatch.setitem(providers.PROVIDERS, 'third', third)
    monkeypatch.setitem(providers.HOST_CHECKS, 'third-auth',
                        providers.HostCheckSpec(__name__ + ':third_probe', ('third-cli',)))
    ctx, _ = context(github())
    got = host.probe_host(ctx)
    assert {name: row['status'] for name, row in got['providers'].items()} == {
        'github-actions': 'ready', 'woodpecker': 'missing', 'third': 'ready'}
    assert got['providers']['third']['versions'] == {'third-cli': '1.2.3'}
    assert CANARY not in json.dumps(got)
    monkeypatch.setitem(providers.HOST_CHECKS, 'third-auth', providers.HostCheckSpec('absent_module:absent', ()))
    assert host.probe_host(ctx)['providers']['third']['status'] == 'unknown'


def third_probe(ctx):
    return {**host.verdict('ready', 'authenticated', {'third-cli': '1.2.3', 'secret': CANARY}), 'token': CANARY}


def test_container_never_probes(monkeypatch):
    ctx, calls = context(github())
    ctx.container = True
    got = host.probe_host(ctx)
    assert {row['reason'] for row in got['providers'].values()} == {'container-view'}
    assert not calls


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / 'projects/project'
    repo.mkdir(parents=True)
    git(repo, 'init', '-b', 'main')
    git(repo, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '--allow-empty', '-m', 'fixture')
    return repo


def put_record(root, record):
    path = root / '.claude/cpp-host.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))
    return path


@requires_git
def test_main_worktree_and_decoy_share_one_record(repository, tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'in_container', lambda: False)
    ctx, _ = context(github())
    real = host.probe_host(ctx)
    put_record(repository.parent, real)
    relocated = tmp_path / 'elsewhere/linked'
    git(repository, 'worktree', 'add', '-b', 'linked', str(relocated))
    decoy = put_record(relocated.parent, {'schema': 1, 'providers': {}})
    assert decoy.is_file() and decoy != repository.parent / '.claude/cpp-host.json'
    assert host.main_checkout(relocated) == repository
    assert host.read_host_record(repository) == host.read_host_record(relocated) == real
    monkeypatch.setattr(host, 'in_container', lambda: True)
    assert {v['status'] for v in host.read_host_record(relocated)['providers'].values()} == {'unknown'}


@requires_git
@pytest.mark.parametrize('raw', [None, 'not-json', '{}', '{"schema":1,"providers":{},"checked_at":"secret"}',
                               '{"schema":1,"providers":{},"checked_at":"2026-11-08T10:00:00Z"}'])
def test_absent_malformed_and_unrecorded_unknown(repository, monkeypatch, raw):
    monkeypatch.setattr(host, 'in_container', lambda: False)
    if raw is not None:
        target = put_record(repository.parent, {})
        target.write_text(raw)
    got = host.read_host_record(repository)
    assert {v['status'] for v in got['providers'].values()} == {'unknown'}


@requires_git
@requires_bash_python
def test_atomic_persistence_defer_failure_and_repo_no_change(repository, monkeypatch):
    monkeypatch.setattr(host, 'in_container', lambda: False)
    ctx, _ = context(github())
    record = host.probe_host(ctx)
    record['token'] = CANARY
    real = host.ProbeContext(container=False, env=dict(os.environ))
    before = {str(p.relative_to(repository)): p.read_bytes() for p in repository.rglob('*') if p.is_file()}
    assert host.write_host_record(record, repository.parent, repository, real) == 'written'
    target = repository.parent / '.claude/cpp-host.json'
    old = target.read_bytes()
    assert CANARY.encode() not in old
    assert host.read_host_record(repository)['providers'] == record['providers']
    real.env['CPP_DEFER_SURFACES'] = str(target)
    assert host.write_host_record(record, repository.parent, repository, real) == 'deferred'
    assert target.read_bytes() == old
    del real.env['CPP_DEFER_SURFACES']
    assert host.write_host_record(record, repository, repository, real) == 'failed'
    assert {str(p.relative_to(repository)): p.read_bytes() for p in repository.rglob('*') if p.is_file()} == before
    # A symlink target is a known bad atomic destination, not a permission guess
    # (root could bypass chmod). Its referent must remain byte-for-byte intact.
    target.unlink()
    source = repository.parent / 'previous'
    source.write_bytes(old)
    target.symlink_to(source)
    assert target.is_symlink()
    assert host.write_host_record(record, repository.parent, repository, real) == 'failed'
    assert source.read_bytes() == old


@requires_git
@requires_bash_python
def test_cli_suppresses_probe_payloads_on_both_streams(repository, monkeypatch, capsys):
    from lib.cicd.cli import main
    ctx, calls = context(github())
    record = host.probe_host(ctx)
    monkeypatch.setattr(host, 'probe_host', lambda: record)
    assert main(['host-ci', '--path', str(repository), '--json']) == 0
    captured = capsys.readouterr()
    assert CANARY not in captured.out + captured.err
    assert json.loads(captured.out)['providers']['github-actions']['status'] == 'ready'


@requires_git
def test_separate_git_dir_still_uses_main_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'in_container', lambda: False)
    repo = tmp_path / 'projects/separate'
    repo.mkdir(parents=True)
    git(repo, 'init', '--separate-git-dir', str(tmp_path / 'metadata'))
    assert (repo / '.git').is_file()
    assert host.main_checkout(repo) == repo


def test_unreachable_main_is_unknown_and_never_walks_up(tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'in_container', lambda: False)
    monkeypatch.setattr(host, 'main_checkout', lambda repo: None)
    put_record(tmp_path, {'schema': 1, 'providers': {'github-actions': {'status': 'ready'}}})
    got = host.read_host_record(tmp_path / 'not-a-repo')
    assert {row['reason'] for row in got['providers'].values()} == {'host-root-unavailable'}


@pytest.mark.parametrize('payload', [None, [], {'status': [], 'reason': 'authenticated'},
                                     {'status': 'ready', 'reason': 'auth-missing'},
                                     {'status': 'ready', 'reason': 'authenticated',
                                      'versions': {'gh': CANARY, 'token': CANARY}}])
def test_reader_payload_sanitizer_never_leaks(payload):
    got = host._sanitize(payload, ('gh',))
    assert CANARY not in json.dumps(got)
    if not isinstance(payload, dict) or payload.get('versions') is None:
        assert got['status'] == 'unknown'


@requires_git
@requires_bash_python
def test_nested_linked_worktree_root_is_never_a_host_destination(repository, tmp_path):
    relocated = tmp_path / 'elsewhere/linked'
    git(repository, 'worktree', 'add', '-b', 'nested-linked', str(relocated))
    nested = relocated / 'src'
    nested.mkdir()
    target = relocated / '.claude/cpp-host.json'
    assert not target.exists()
    record = host._unknown('record-unavailable')
    ctx = host.ProbeContext(container=False)
    assert host.write_host_record(record, relocated, nested, ctx) == 'failed'
    assert not target.parent.exists()


@requires_git
@requires_bash_python
def test_timeout_commit_outcome_is_unknown_and_writer_cannot_outlive_caller(repository, tmp_path):
    import time

    root = repository.parent
    target = put_record(root, {'previous': 'record'})
    old = target.read_bytes()
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    paused = tmp_path / 'paused'
    release = tmp_path / 'release'
    resumed = tmp_path / 'resumed'
    stub = bindir / 'python3'
    stub.write_text(
        '#!' + shutil.which('python3') + '\n'
        'import os, pathlib, sys, time\n'
        f'pathlib.Path({str(paused)!r}).touch()\n'
        'end=time.monotonic()+8\n'
        f'while not pathlib.Path({str(release)!r}).exists():\n'
        '    if time.monotonic()>end: sys.exit(2)\n'
        '    time.sleep(0.01)\n'
        f'pathlib.Path({str(resumed)!r}).touch()\n'
        'os.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n'
    )
    stub.chmod(0o755)
    env = {**os.environ, 'PATH': str(bindir) + os.pathsep + os.environ['PATH']}
    assert shutil.which('python3', path=env['PATH']) == str(stub)

    def timeout_run(argv, **kwargs):
        return subprocess.run(argv, **{**kwargs, 'timeout': 2})

    ctx = host.ProbeContext(run=timeout_run, env=env, container=False)
    state = host.write_host_record(host._unknown('record-unavailable'), root, repository, ctx)
    assert paused.exists(), 'must time out during an actual pending writer'
    release.touch()
    end = time.monotonic() + 0.4
    while time.monotonic() < end:
        time.sleep(0.01)
    assert state == 'unknown', 'a timeout cannot certify that the previous record survived'
    assert not resumed.exists(), 'writer must be the timed process, with no surviving child'
    assert target.read_bytes() == old


@requires_git
@requires_bash_python
def test_selected_projects_folder_applies_to_its_projects_not_installer(repository, tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'in_container', lambda: False)
    custom = tmp_path / 'custom-projects'
    project = custom / 'consumer'
    project.mkdir(parents=True)
    git(project, 'init')
    decoy = host._unknown('record-unavailable')
    decoy['checked_at'] = '2026-11-08T10:00:00Z'
    put_record(repository.parent, decoy)
    ctx, _ = context(github())
    record = host.probe_host(ctx)
    assert host.write_host_record(record, custom, repository, host.ProbeContext(container=False)) == 'written'
    assert host.read_host_record(project)['providers'] == record['providers']
    assert {v['status'] for v in host.read_host_record(repository)['providers'].values()} == {'unknown'}


@pytest.mark.parametrize('partial', [
    {'WOODPECKER_SERVER': 'https://other.invalid'},
    {'WOODPECKER_API_TOKEN': 'other-private-canary'},
])
def test_partial_environment_never_mixes_unrelated_aws_credentials(partial):
    secret = response(stdout=json.dumps({'WOODPECKER_API_TOKEN': CANARY,
                                        'WOODPECKER_HOST': 'https://fixture.invalid'}))
    ctx, calls = context(woodpecker(secret=secret, info=response(stdout='fixture-user')),
                         tools=('woodpecker-cli', 'aws'),
                         env={**partial, 'CPP_WOODPECKER_SECRET': 'fixture', 'AWS_REGION': 'fixture-region'})
    got = host.check_woodpecker(ctx)
    assert got['status'] == 'unknown'
    assert not any(argv[1:2] == ['info'] for argv, _ in calls), 'no token may be sent to a different source endpoint'
    assert CANARY not in json.dumps(got)


@requires_git
@pytest.mark.parametrize('timestamp,expected', [
    ('0001-01-01T00:00:00+01:00', None),
    ('9999-12-31T23:59:59-01:00', None),
    ('2026-11-08T10:00:00+01:00', '2026-11-08T09:00:00+00:00'),
])
def test_timestamp_overflow_is_unknown_and_normal_offset_normalizes(repository, monkeypatch, timestamp, expected):
    monkeypatch.setattr(host, 'in_container', lambda: False)
    record = host._unknown('record-unavailable')
    record['checked_at'] = timestamp
    put_record(repository.parent, record)
    result = host.read_host_record(repository)
    assert result['checked_at'] == expected
    if expected is None:
        assert {v['reason'] for v in result['providers'].values()} == {'record-invalid'}


@pytest.mark.parametrize('partial', [
    {'WOODPECKER_SERVER': 'https://fixture.invalid/'},
    {'WOODPECKER_API_TOKEN': CANARY},
])
def test_matching_partial_environment_can_use_the_same_aws_pair(partial):
    secret = response(stdout=json.dumps({'WOODPECKER_API_TOKEN': CANARY,
                                        'WOODPECKER_HOST': 'https://fixture.invalid'}))
    ctx, _ = context(woodpecker(secret=secret, info=response(stdout='fixture-user')),
                     tools=('woodpecker-cli', 'aws'),
                     env={**partial, 'CPP_WOODPECKER_SECRET': 'fixture', 'AWS_REGION': 'fixture-region'})
    assert host.check_woodpecker(ctx)['status'] == 'ready'
