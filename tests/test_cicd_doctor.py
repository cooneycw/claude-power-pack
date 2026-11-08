"""Provider consistency diagnostics use canonical records and bounded offline facts."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lib.cicd import providers
from lib.cicd.checks import read_pipeline_files

ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / '.claude/commands/flow/doctor.md'


def _published_pipeline_check():
    section = DOCTOR.read_text().split('### Step 7b:', 1)[1].split('### Step 7c:', 1)[0]
    if '<!-- CPP_DOCTOR_CI_BEGIN -->' in section:
        return re.search(r'<!-- CPP_DOCTOR_CI_BEGIN -->\s*```bash\n(.*?)```', section, re.S)[1]
    block = next(b for b in re.findall(r'```bash\n(.*?)```', section, re.S) if '# 5. CI pipeline files' in b)
    return block.split('# 5. CI pipeline files\n', 1)[1].split('\n\n', 1)[0]


@pytest.mark.skipif(shutil.which('bash') is None or shutil.which('git') is None, reason='requires bash and git')
@pytest.mark.skipif(shutil.which(str(ROOT / '.venv/bin/python')) is None,
                    reason='requires existing CPP Python environment')
@pytest.mark.parametrize('recorded,expected', [(True, 'drift'), (False, 'unknown')])
def test_published_doctor_never_clears_inconsistent_or_unrecorded_provider(tmp_path, recorded, expected):
    # CONSTRUCTED mismatch: explicit Actions record plus actual CPP Woodpecker
    # file. Historical CPP's absent record is unknown, never implicit Actions.
    if recorded:
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude/cicd.yml').write_text('pipeline:\n  providers: [github-actions]\n')
    (tmp_path / '.woodpecker.yml').write_bytes((ROOT / '.woodpecker.yml').read_bytes())
    assert not (tmp_path / '.github/workflows/ci.yml').exists()
    assert recorded is (tmp_path / '.claude/cicd.yml').exists()
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    gh = bindir / 'gh'
    gh.write_text('#!/bin/bash\nexit 1\n')
    gh.chmod(0o755)
    test_path = str(bindir) + os.pathsep + os.environ['PATH']
    assert shutil.which('gh', path=test_path) == str(gh), 'never contact a live service in the recipe test'
    result = subprocess.run(['bash', '-c', _published_pipeline_check()], cwd=tmp_path,
                            env={**os.environ, 'CPP_DIR':str(ROOT), 'PATH':test_path},
                            capture_output=True, text=True, timeout=20)
    assert f'CI_PIPELINE_FILES: {expected}' in result.stdout, result.stdout + result.stderr
    assert 'PASS CI pipeline' not in result.stdout


def test_shared_inventory_includes_a_new_registry_providers_canonical_path(tmp_path, monkeypatch):
    name = 'third-ci'
    spec = providers.ProviderSpec(name, 'fixture_generator', '.third/pipeline.yml',
                                  'fixture:checks', 'fixture-lane', 'fixture-host')
    monkeypatch.setitem(providers.PROVIDERS, name, spec)
    target = tmp_path / spec.pipeline_file
    target.parent.mkdir()
    target.write_text('fixture: pipeline\n')
    assert target.is_file() and target.relative_to(tmp_path).as_posix() == '.third/pipeline.yml'
    assert spec.pipeline_file in read_pipeline_files(tmp_path)


def test_existing_alternate_workflow_paths_remain_in_shared_inventory(tmp_path):
    path = tmp_path / '.github/workflows/alternate.yaml'
    path.parent.mkdir(parents=True)
    path.write_text('name: fixture\n')
    assert read_pipeline_files(tmp_path) == {'.github/workflows/alternate.yaml':'name: fixture\n'}


def test_unreadable_pipeline_directory_is_not_a_known_empty_inventory(tmp_path, monkeypatch):
    folder = tmp_path / '.github/workflows'
    folder.mkdir(parents=True)
    (folder / 'ci.yml').write_text('fixture: pipeline\n')
    assert folder.is_dir() and (folder / 'ci.yml').is_file()
    original_scandir, original_listdir = os.scandir, os.listdir
    seen = []

    def guarded_scandir(path):
        if Path(path) == folder:
            seen.append('scandir')
            raise PermissionError('fixture unreadable')
        return original_scandir(path)

    def guarded_listdir(path):
        if Path(path) == folder:
            seen.append('listdir')
            raise PermissionError('fixture unreadable')
        return original_listdir(path)

    monkeypatch.setattr(os, 'scandir', guarded_scandir)
    monkeypatch.setattr(os, 'listdir', guarded_listdir)
    with pytest.raises(PermissionError):
        read_pipeline_files(tmp_path)
    assert seen, 'must exercise an actual refused directory read'

# Literal expected contexts are independent of the deriver under test.
GHA = '''name: fixture
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - run: make test
'''
WP = '''when:
  event: [push, pull_request]
  branch: main
steps:
  - name: verify
    image: python:3.11
    commands: [make test]
'''


def _project(root, names=('github-actions',)):
    import json
    root.mkdir(parents=True, exist_ok=True)
    (root / '.claude').mkdir(exist_ok=True)
    (root / '.claude/cicd.yml').write_text('pipeline:\n  providers: [' + ', '.join(names) + ']\n')
    contexts = []
    for name in names:
        if name == 'github-actions':
            path, content = root / '.github/workflows/ci.yml', GHA
            contexts.append('verify')
        else:
            path, content = root / '.woodpecker.yml', WP
            contexts.append('ci/woodpecker/pr/woodpecker')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    posture = {'branch':'main', 'protection':{'required_status_checks':{'contexts':contexts}}}
    (root / '.claude/branch-protection.json').write_text(json.dumps(posture))
    return posture


def _host(status='ready'):
    return {'schema':1, 'checked_at':'2026-11-08T00:00:00+00:00',
            'providers':{name:{'status':status, 'reason':'fixture', 'versions':{}} for name in providers.PROVIDERS}}


def _context(root, *, classic=None, rules=None, classic_code=200, rules_code=200, host=None,
             rule_pages=None, late_failure=False):
    import json
    from types import SimpleNamespace

    from lib.cicd.doctor import DoctorContext
    calls = []
    classic = {'required_status_checks':{'contexts':['verify']}} if classic is None else classic
    rules = [] if rules is None else rules

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs['cwd'] == root
        assert not any(key.startswith('GIT_') for key in kwargs['env'])
        if argv[0] == 'git':
            if argv[-2:] == ['rev-parse', '--show-toplevel']:
                return SimpleNamespace(returncode=0, stdout=str(root) + '\n')
            assert argv == ['git', '-C', str(root), 'remote', 'get-url', 'origin']
            return SimpleNamespace(returncode=0, stdout='git@github.com:fixture/selected.git\n')
        assert argv[0:2] == ['gh', 'api']
        assert argv[argv.index('--hostname') + 1] == 'github.com'
        assert argv[-1].startswith('repos/fixture/selected/')
        if '/rules/' in argv[-1] and '--paginate' in argv:
            assert '--slurp' in argv and 'per_page=100' in argv[-1]
            pages = rule_pages if rule_pages is not None else [rules]
            return SimpleNamespace(returncode=0 if rules_code == 200 and not late_failure else 1,
                                   stdout=json.dumps(pages[:1] if late_failure else pages),
                                   stderr='PRIVATE_API_PAYLOAD_CANARY')
        code, body = (rules_code, rule_pages[0] if rule_pages is not None else rules) \
            if '/rules/' in argv[-1] else (classic_code, classic)
        return SimpleNamespace(returncode=0 if code == 200 else 1,
                               stdout=f'HTTP/2.0 {code} fixture\r\n\r\n' + json.dumps(body),
                               stderr='PRIVATE_API_PAYLOAD_CANARY')
    ctx = DoctorContext(run=run, which=lambda name:name, host_reader=lambda path:_host() if host is None else host)
    return ctx, calls


def _by_id(value):
    return {item['id']:item for item in value['rows']}


@pytest.mark.parametrize('names,contexts', [
    (('github-actions',), ['verify']),
    (('woodpecker',), ['ci/woodpecker/pr/woodpecker']),
    (('github-actions', 'woodpecker'), ['verify', 'ci/woodpecker/pr/woodpecker']),
])
def test_known_relationships_and_explicit_unavailable_lane_plan(tmp_path, names, contexts):
    from lib.cicd.doctor import collect
    _project(tmp_path, names)
    ctx, _ = _context(tmp_path, classic={'required_status_checks':{'contexts':contexts}})
    before = {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    value = collect(tmp_path, ctx)
    assert [row['status'] for row in value['rows']] == ['ok', 'ok', 'ok', 'unknown']
    assert value['rows'][-1]['reason'] == 'lane plan unavailable (#1610)'
    assert value['status'] == 'unknown' and value['exit_code'] == 3
    assert {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('classic,rules,classic_code,rules_code,expected', [
    ({'required_status_checks':{'checks':[{'context':'verify','app_id':None}]}}, [], 200, 200, 'ok'),
    ({'required_status_checks':{'contexts':[]}},
     [{'type':'required_status_checks','parameters':{'required_status_checks':[{'context':'verify'}]}}],
     200, 200, 'ok'),
    ({'message':'Branch not protected'}, [], 404, 200, 'drift'),
    ({'message':'Not Found'}, [], 404, 200, 'unknown'),
    ({'message':'PRIVATE_API_PAYLOAD_CANARY'}, [], 403, 200, 'unknown'),
    ({'required_status_checks':{'contexts':['verify']}}, [], 200, 403, 'unknown'),
    ({}, [], 200, 200, 'unknown'),
    ({'required_status_checks':{}}, [], 200, 200, 'unknown'),
    ({'required_status_checks':{'contexts':['verify']}}, {'bad':'shape'}, 200, 200, 'unknown'),
    ({'required_status_checks':{'checks':[{'context':'verify','app_id':123}]}}, [], 200, 200, 'unknown'),
    ({'required_status_checks':{'contexts':['other']}}, [], 200, 200, 'drift'),
])
def test_protection_collection_keeps_unknown_distinct_from_absent_checks(
        tmp_path, classic, rules, classic_code, rules_code, expected):
    import json

    from lib.cicd.doctor import collect, render
    _project(tmp_path)
    ctx, calls = _context(tmp_path, classic=classic, rules=rules, classic_code=classic_code, rules_code=rules_code)
    value = collect(tmp_path, ctx)
    assert _by_id(value)['required-checks']['status'] == expected
    assert 'PRIVATE_API_PAYLOAD_CANARY' not in json.dumps(value) + render(value)
    assert all('PRIVATE_API_PAYLOAD_CANARY' not in str(argv) for argv in calls)


@pytest.mark.parametrize('change', ['push-only', 'unreadable-declared', 'wrong-declared'])
def test_shared_derivation_and_declared_posture_are_required(tmp_path, change):
    from lib.cicd.doctor import collect
    _project(tmp_path)
    if change == 'push-only':
        path = tmp_path / '.github/workflows/ci.yml'
        path.write_text(GHA.replace('  pull_request:\n    branches: [main]\n', ''))
        assert 'pull_request:' not in path.read_text()
    elif change == 'unreadable-declared':
        path = tmp_path / '.claude/branch-protection.json'
        path.unlink()
        path.mkdir()
        assert path.is_dir()
    else:
        path = tmp_path / '.claude/branch-protection.json'
        path.write_text('{"branch":"main","protection":{"required_status_checks":{"contexts":["push-only"]}}}')
        assert 'push-only' in path.read_text()
    ctx, _ = _context(tmp_path)
    value = collect(tmp_path, ctx)
    assert _by_id(value)['required-checks']['status'] == ('drift' if change == 'wrong-declared' else 'unknown')


@pytest.mark.parametrize('state,expected', [('ready','ok'), ('missing','drift'), ('unknown','unknown')])
def test_host_line_is_an_explicit_historical_snapshot(tmp_path, state, expected):
    from lib.cicd.doctor import collect, render
    _project(tmp_path)
    ctx, _ = _context(tmp_path, host=_host(state))
    value = collect(tmp_path, ctx)
    host = _by_id(value)['host-capability']
    assert host['status'] == expected
    assert host['evidence']['checked_at'] == '2026-11-08T00:00:00+00:00'
    assert host['evidence']['current_connectivity'] == 'not examined'
    assert 'historical' in render(value) and '/cpp:init Tier 4' in render(value)


def test_missing_record_never_probes_or_defaults_and_omits_invalid_values(tmp_path):
    import json

    from lib.cicd.doctor import collect
    _project(tmp_path)
    (tmp_path / '.claude/cicd.yml').write_text('pipeline:\n  providers: [PRIVATE_API_PAYLOAD_CANARY]\n')
    ctx, calls = _context(tmp_path)
    value = collect(tmp_path, ctx)
    assert not calls
    assert {row['status'] for row in value['rows']} == {'unknown'}
    assert 'PRIVATE_API_PAYLOAD_CANARY' not in json.dumps(value)


def test_aggregate_requires_a_complete_known_row_population():
    from lib.cicd.doctor import IDS, report, row
    good = [row(name, 'ok', 'fixture') for name in IDS]
    assert report(good, ['github-actions'])['exit_code'] == 0
    assert report(good[:-1], ['github-actions'])['exit_code'] == 3
    assert report([*good[:-1], row('foreign', 'ok', 'fixture')], [])['exit_code'] == 3
    mixed = [row(IDS[0], 'drift', 'fixture'), *good[1:-1], row(IDS[-1], 'unknown', 'fixture')]
    assert report(mixed, [])['exit_code'] == 1


def test_historical_cpp_record_is_unknown_and_constructed_mismatch_is_drift(tmp_path):
    from lib.cicd.doctor import collect
    historical = ROOT / 'controls/doctor-ci/cases/unknown-historical-record/project/.claude/cicd.yml'
    root = tmp_path / 'historical'
    (root / '.claude').mkdir(parents=True)
    (root / '.claude/cicd.yml').write_bytes(historical.read_bytes())
    assert 'pipeline:' not in historical.read_text()
    ctx, calls = _context(root)
    assert {item['status'] for item in collect(root, ctx)['rows']} == {'unknown'}
    assert not calls
    # This explicitly chosen Actions record is constructed. Only the pipeline
    # file is copied from actual CPP; no historical implicit default is invented.
    constructed = ROOT / 'controls/doctor-ci/cases/bad-provider-files/project/.claude/cicd.yml'
    (root / '.claude/cicd.yml').write_bytes(constructed.read_bytes())
    (root / '.woodpecker.yml').write_bytes((ROOT / '.woodpecker.yml').read_bytes())
    assert 'github-actions' in (root / '.claude/cicd.yml').read_text()
    assert _by_id(collect(root, ctx))['pipeline-files']['status'] == 'drift'


@pytest.mark.skipif(shutil.which('git') is None, reason='requires git')
def test_canonical_host_reader_is_used_from_relocated_worktree_and_container(tmp_path, monkeypatch):
    import json

    from lib.cicd import host
    from lib.cicd.doctor import collect
    main = tmp_path / 'projects/main'
    _project(main)

    def git(*args):
        return subprocess.run(['git', '-C', str(main), *args], check=True, text=True, capture_output=True).stdout
    git('init', '-b', 'main')
    git('add', '.')
    git('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
    linked = tmp_path / 'relocated/worktree'
    git('remote', 'add', 'origin', 'git@github.com:fixture/selected.git')
    git('worktree', 'add', '-b', 'linked', str(linked))
    target = main.parent / '.claude/cpp-host.json'
    target.parent.mkdir()
    record = _host()
    for value in record['providers'].values():
        value['reason'] = 'authenticated'
    target.write_text(json.dumps(record))
    decoy = linked.parent / '.claude/cpp-host.json'
    decoy.parent.mkdir()
    decoy.write_text('not a record')
    assert decoy.is_file() and decoy != target
    monkeypatch.setattr(host, 'in_container', lambda:False)
    monkeypatch.setattr(host, 'probe_host', lambda *args:pytest.fail('doctor must never probe host credentials'))
    ctx, _ = _context(linked)
    ctx.host_reader = host.read_host_record
    fake = ctx.run
    ctx.run = lambda argv, **kwargs: subprocess.run(argv, **kwargs) if argv[0] == 'git' else fake(argv, **kwargs)
    before = target.read_bytes()
    assert _by_id(collect(linked, ctx))['host-capability']['status'] == 'ok'
    assert target.read_bytes() == before
    monkeypatch.setattr(host, 'in_container', lambda:True)
    assert _by_id(collect(linked, ctx))['host-capability']['status'] == 'unknown'
    assert target.read_bytes() == before


@pytest.mark.parametrize('failure', [OSError('PRIVATE_API_PAYLOAD_CANARY'),
                                    subprocess.TimeoutExpired('gh', 15)])
def test_protection_probe_errors_do_not_escape_or_become_green(tmp_path, failure):
    from lib.cicd.doctor import collect, render
    _project(tmp_path)
    ctx, _ = _context(tmp_path)
    original = ctx.run

    def broken(argv, **kwargs):
        if argv[0] == 'gh':
            raise failure
        return original(argv, **kwargs)
    ctx.run = broken
    value = collect(tmp_path, ctx)
    assert _by_id(value)['required-checks']['status'] == 'unknown'
    assert 'PRIVATE_API_PAYLOAD_CANARY' not in render(value)


def test_cli_json_and_text_have_identical_unknown_verdict(tmp_path, monkeypatch, capsys):
    import json

    from lib.cicd import cli, doctor
    _project(tmp_path)
    ctx, _ = _context(tmp_path)
    actual = doctor.collect
    monkeypatch.setattr(doctor, 'collect', lambda path:actual(path, ctx))
    assert cli.main(['doctor-ci', '--path', str(tmp_path), '--json']) == 3
    data = json.loads(capsys.readouterr().out)
    assert data['rows'][-1]['reason'] == 'lane plan unavailable (#1610)'
    assert cli.main(['doctor-ci', '--path', str(tmp_path)]) == 3
    text = capsys.readouterr().out
    assert 'CI_FALLBACK: unknown' in text
    assert 'CI_PIPELINE_FILES: ok' in text


def test_unreachable_pipeline_directory_link_is_not_known_absent(tmp_path):
    folder = tmp_path / '.github/workflows'
    folder.parent.mkdir()
    folder.symlink_to(tmp_path / 'missing-workflows', target_is_directory=True)
    assert folder.is_symlink() and not folder.exists()
    with pytest.raises(OSError):
        read_pipeline_files(tmp_path)


def third_checks(files):
    from lib.cicd.checks import RequiredChecks
    return (RequiredChecks('known', ('third-verify',), examined_files=1) if '.third/pipeline.yml' in files else
            RequiredChecks('unknown', reason='fixture file missing'))


def test_full_collector_has_no_binary_provider_assumption(tmp_path, monkeypatch):
    import json

    from lib.cicd.doctor import collect
    spec = providers.ProviderSpec('third-ci', 'fixture', '.third/pipeline.yml',
                                  __name__ + ':third_checks', 'third-lane', 'third-host')
    monkeypatch.setitem(providers.PROVIDERS, 'third-ci', spec)
    _project(tmp_path, ())
    (tmp_path / '.claude/cicd.yml').write_text('pipeline:\n  providers: [third-ci]\n')
    target = tmp_path / spec.pipeline_file
    target.parent.mkdir()
    target.write_text('fixture: pipeline\n')
    (tmp_path / '.claude/branch-protection.json').write_text(json.dumps({
        'branch':'main', 'protection':{'required_status_checks':{'contexts':['third-verify']}}}))
    ctx, _ = _context(tmp_path, classic={'required_status_checks':{'contexts':['third-verify']}})
    assert [row['status'] for row in collect(tmp_path, ctx)['rows']] == ['ok','ok','ok','unknown']


def test_bad_provider_hook_cannot_erase_independent_file_and_host_evidence(tmp_path, monkeypatch):
    from lib.cicd import checks
    from lib.cicd.doctor import collect, render
    _project(tmp_path)
    ctx, _ = _context(tmp_path)

    def unavailable(*args):
        raise RuntimeError('PRIVATE_API_PAYLOAD_CANARY')
    monkeypatch.setattr(checks, 'derive_required_checks', unavailable)
    value = collect(tmp_path, ctx)
    assert _by_id(value)['pipeline-files']['status'] == 'ok'
    assert _by_id(value)['required-checks']['status'] == 'unknown'
    assert _by_id(value)['host-capability']['status'] == 'ok'
    assert 'PRIVATE_API_PAYLOAD_CANARY' not in render(value)


def test_unresolvable_target_is_unknown_without_a_traceback(tmp_path):
    from lib.cicd.doctor import collect
    target = tmp_path / 'loop'
    target.symlink_to(target)
    assert target.is_symlink()
    value = collect(target)
    assert value['exit_code'] == 3
    assert {row['status'] for row in value['rows']} == {'unknown'}


def test_cli_without_dependency_packages_reports_unknown_instead_of_a_traceback(tmp_path):
    import json
    import sys
    result = subprocess.run(  # binary-guard: allow -S deliberately removes dependencies before collection can run
        [sys.executable, '-S', '-B', '-m', 'lib.cicd', 'doctor-ci', '--json', '--path', str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 3
    value = json.loads(result.stdout)
    assert {item['status'] for item in value['rows']} == {'unknown'}
    assert all('dependencies unavailable' in item['reason'] for item in value['rows'])
    assert result.stderr == ''


@pytest.mark.parametrize('late_failure,expected', [(False, 'drift'), (True, 'unknown')])
def test_later_rules_page_is_examined_and_failed_pagination_is_unknown(tmp_path, late_failure, expected):
    from lib.cicd.doctor import collect
    _project(tmp_path)
    pages = [[], [{'type':'required_status_checks',
                   'parameters':{'required_status_checks':[{'context':'later-page-check'}]}}]]
    assert not pages[0] and pages[1][0]['parameters']['required_status_checks'][0]['context'] == 'later-page-check'
    ctx, _ = _context(tmp_path, rule_pages=pages, late_failure=late_failure)
    item = _by_id(collect(tmp_path, ctx))['required-checks']
    assert item['status'] == expected
    if not late_failure:
        assert item['evidence']['sources']['live']['extra'] == ['later-page-check']


@pytest.mark.skipif(shutil.which('git') is None, reason='requires git')
def test_nested_project_does_not_borrow_parent_git_identity(tmp_path):
    from lib.cicd.doctor import collect
    parent = tmp_path / 'parent'
    project = parent / 'nested'
    _project(project)
    subprocess.run(['git', '-C', str(parent), 'init'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(parent), 'remote', 'add', 'origin',
                    'git@github.com:fixture/selected.git'], check=True, capture_output=True)
    assert not (project / '.git').exists() and (parent / '.git').is_dir()
    ctx, calls = _context(project)
    fake = ctx.run

    def actual_git(argv, **kwargs):
        return subprocess.run(argv, **kwargs) if argv[0] == 'git' else fake(argv, **kwargs)
    ctx.run = actual_git
    value = collect(project, ctx)
    assert _by_id(value)['required-checks']['status'] == 'unknown'
    assert not any(argv[0] == 'gh' for argv in calls), 'must not query protection for an ancestor repository'


def test_empty_successful_git_identity_is_not_the_current_directory(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from lib.cicd.doctor import collect
    _project(tmp_path)
    ctx, calls = _context(tmp_path)
    original = ctx.run
    seen = []

    def empty_identity(argv, **kwargs):
        if argv[0] == 'git' and argv[-2:] == ['rev-parse', '--show-toplevel']:
            seen.append(True)
            return SimpleNamespace(returncode=0, stdout='')
        return original(argv, **kwargs)
    ctx.run = empty_identity
    monkeypatch.chdir(tmp_path)
    assert Path.cwd() == tmp_path
    value = collect(tmp_path, ctx)
    assert seen, 'must inspect a successful but empty identity response'
    assert _by_id(value)['required-checks']['status'] == 'unknown'
    assert not any(argv[0] == 'gh' for argv in calls)
