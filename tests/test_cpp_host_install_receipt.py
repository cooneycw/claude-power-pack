"""Host-only Tier4 receipt construction, actual write outcomes and old schema1."""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts/cpp-install-receipt.py'
REVISION = 'a' * 40
BASE = ['commands', 'stash-guard', 'scripts', 'permission-profile', 'uv',
        'second-opinion', 'playwright', 'tavily']
CODEX = ['codex-cli', 'codex-doctor', 'codex-auth', 'codex-skills', 'memory-harness']
LEGACY = ROOT / 'tests/fixtures/cpp-host-install-receipt/legacy-tier4.json'


def assert_only_host_observation_is_blind(subject, anchor):
    trees = [ast.parse(text) for text in (subject, anchor)]
    for tree in trees:
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'host_ci_results']
        assert len(functions) == 1
        functions[0].body = [ast.Pass()]
    assert ast.dump(trees[0], include_attributes=False) == ast.dump(trees[1], include_attributes=False), \
        'constructed anchor differs beyond host_ci_results'


@pytest.mark.parametrize('unrelated_change', [False, True])
def test_regenerated_host_anchor_preserves_all_other_behavior(unrelated_change):
    subject = HELPER.read_text()
    anchor = (ROOT / 'controls/cpp-host-install-receipt/anchors/assume-host-written.py').read_text()
    if unrelated_change:
        # Known-bad comparator input: an extra outcome changes the receipt
        # validator independently of the intended host-observation blindness.
        assert '"declined", "FAILED", "unverified"' in anchor
        anchor = anchor.replace('"declined", "FAILED", "unverified"',
                                '"declined", "FAILED", "unverified", "invented-success"', 1)
        with pytest.raises(AssertionError, match='differs beyond host_ci_results'):
            assert_only_host_observation_is_blind(subject, anchor)
    else:
        assert_only_host_observation_is_blind(subject, anchor)


def invoke(project, command, *, data=None, tier=4):
    argv = [sys.executable, str(HELPER), command, '--project-dir', str(project), '--revision', REVISION]
    if command == 'write':
        argv += ['--tier', str(tier), '--profile', 'not-selected',
                 '--offered-steps', json.dumps([row['step'] for row in data])]
    return subprocess.run(argv, input=json.dumps(data) if data is not None else None,
                          text=True, capture_output=True, timeout=10)  # binary-guard: allow explicit revision


def rows(tier=4):
    return [{'step':step, 'outcome':'installed', 'exit_code':0} for step in BASE + (CODEX if tier == 5 else [])]


@pytest.mark.parametrize('tier', [4, 5])
@pytest.mark.parametrize('outcome,code,complete', [('written', 0, True), ('deferred', 3, False),
                                                ('failed', 1, False), ('unknown', 3, False)])
def test_new_host_step_outcome_drives_tier_completion(tmp_path, tier, outcome, code, complete):
    data = rows(tier) + [{'step':'host-ci', 'outcome':outcome, 'exit_code':code}]
    result = invoke(tmp_path, 'write', data=data, tier=tier)
    assert result.returncode == 0, result.stdout
    receipt = json.loads((tmp_path / '.claude/cpp-install.json').read_text())
    assert 'host-ci' in receipt['offered_steps']
    assert not {'framework-makefile', 'cicd-config'} & set(receipt['offered_steps'])
    host = next(row for row in receipt['steps'] if row['step'] == 'host-ci')
    assert (host['outcome'], host['exit_code']) == (outcome, code)
    summary = invoke(tmp_path, 'summary')
    assert (summary.returncode == 0) is complete
    assert ('CPP Installation Complete' in summary.stdout) is complete


def test_tier_selection_does_not_manufacture_a_host_observation(tmp_path):
    assert invoke(tmp_path, 'write', data=rows()).returncode == 0
    receipt = json.loads((tmp_path / '.claude/cpp-install.json').read_text())
    by_id = {row['step']: row for row in receipt['steps']}
    assert 'framework-makefile' not in by_id and 'cicd-config' not in by_id
    assert by_id['host-ci']['outcome'] == 'unverified'
    assert invoke(tmp_path, 'summary').returncode == 1


def test_historical_schema1_project_generation_record_still_reads(tmp_path):
    receipt = tmp_path / '.claude/cpp-install.json'
    receipt.parent.mkdir()
    receipt.write_bytes(LEGACY.read_bytes())
    before = receipt.read_bytes()
    assert {'framework-makefile', 'cicd-config'} <= set(json.loads(before)['offered_steps'])
    assert invoke(tmp_path, 'summary').returncode == 0
    assert invoke(tmp_path, 'status').returncode == 0
    assert receipt.read_bytes() == before


@pytest.mark.skipif(shutil.which('bash') is None or shutil.which('env') is None
                    or shutil.which('python3') is None, reason='requires bash, env, python3')
@pytest.mark.parametrize('provider_state', ['ready', 'missing', 'unknown'])
def test_actual_host_step_records_write_receipt_independent_of_provider_verdict(tmp_path, provider_state):
    tier = (ROOT / '.claude/commands/cpp/init.md').read_text().split('### CI/CD Execution', 1)[1]
    blocks = [b for b in re.findall(r'```bash\n(.*?)```', tier.split('### Codex Execution', 1)[0], re.S)
              if 'CPP_HOST_RUNTIME=' in b]
    assert len(blocks) == 1
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    uv = bindir / 'uv'
    uv.write_text('#!/bin/bash\nprintf "%s\\n" "$FIXTURE_REPORT"\nexit 0\n')
    uv.chmod(0o755)
    env = {**os.environ, 'PATH':str(bindir) + os.pathsep + os.environ['PATH'],
           'CPP_DIR':str(ROOT), 'CPP_CAPABILITIES_JSON':'["cicd"]',
           'CPP_PROJECTS_ROOT':str(tmp_path / 'projects'), 'HOME':str(tmp_path),
           'STEP_RESULTS_JSON':json.dumps(rows()),
           'FIXTURE_REPORT':f'github-actions: {provider_state} (fixture)\nHOST_CI_RECORD: written'}
    assert shutil.which('uv', path=env['PATH']) == str(uv)
    script = blocks[0] + '\nprintf "OBSERVED_ROWS: %s\\n" "$STEP_RESULTS_JSON"\n'
    result = subprocess.run(['bash', '-c', script], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    observed = json.loads(next(line.removeprefix('OBSERVED_ROWS: ') for line in result.stdout.splitlines()
                               if line.startswith('OBSERVED_ROWS: ')))
    assert [row for row in observed if row['step'] == 'host-ci'] == [
        {'step':'host-ci', 'outcome':'written', 'exit_code':0}]
    assert observed[:-1] == rows(), 'must preserve every non-host general outcome'


@pytest.mark.parametrize('report,code,outcome', [
    ('HOST_CI_RECORD: written', 0, 'written'),
    ('HOST_CI_RECORD: deferred', 3, 'deferred'),
    ('HOST_CI_RECORD: failed', 1, 'failed'),
    ('HOST_CI_RECORD: unknown', 3, 'unknown'),
    ('HOST_CI_RECORD: unavailable', 3, 'unknown'),
    ('HOST_CI_RECORD: written', 3, 'unknown'),
    ('', 0, 'unknown'),
    ('HOST_CI_RECORD: written\nHOST_CI_RECORD: malformed!', 0, 'unknown'),
    ('HOST_CI_RECORD: written', 127, 'failed'),
])
def test_mapper_replaces_old_green_from_actual_receipt_and_drops_raw_payload(tmp_path, report, code, outcome):
    previous = rows() + [{'step':'host-ci', 'outcome':'written', 'exit_code':0}]
    result = subprocess.run(  # binary-guard: allow explicit --revision bypasses git
        [sys.executable, str(HELPER), 'host-ci-outcome', '--revision', REVISION,
         '--exit-code', str(code), '--steps-json', json.dumps(previous)],
        input='PRIVATE_PAYLOAD_CANARY\n' + report, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed[:-1] == rows()
    assert observed[-1] == {'step':'host-ci', 'outcome':outcome, 'exit_code':code}
    assert 'PRIVATE_PAYLOAD_CANARY' not in result.stdout + result.stderr


@pytest.mark.parametrize('outcome,code', [('written', 3), ('deferred', 0), ('failed', 0),
                                        ('unknown', 1), ('installed', 0), ('already', 0)])
def test_typed_host_success_or_inconsistent_exit_cannot_replace_previous_receipt(tmp_path, outcome, code):
    target = tmp_path / '.claude/cpp-install.json'
    target.parent.mkdir()
    target.write_bytes(LEGACY.read_bytes())
    before = target.read_bytes()
    assert outcome in {'installed', 'already'} or (outcome, code) not in {
        ('written', 0), ('deferred', 3), ('failed', 1), ('unknown', 3), ('unknown', 0)}
    result = invoke(tmp_path, 'write', data=rows() + [{'step':'host-ci', 'outcome':outcome, 'exit_code':code}])
    assert result.returncode == 1
    assert target.read_bytes() == before


def test_incomplete_legacy_population_is_not_a_compatibility_bypass(tmp_path):
    record = json.loads(LEGACY.read_text())
    record['offered_steps'].remove('cicd-config')
    record['steps'] = [row for row in record['steps'] if row['step'] != 'cicd-config']
    assert 'host-ci' not in record['offered_steps'] and 'cicd-config' not in record['offered_steps']
    target = tmp_path / '.claude/cpp-install.json'
    target.parent.mkdir()
    target.write_text(json.dumps(record))
    assert invoke(tmp_path, 'summary').returncode == 1
    assert 'unreadable or invalid receipt' in invoke(tmp_path, 'status').stdout


@pytest.mark.skipif(shutil.which('bash') is None or shutil.which('env') is None
                    or shutil.which('python3') is None, reason='requires bash, env, python3')
def test_observation_failure_invalidates_old_green_metadata_before_receipt_save(tmp_path):
    source = (ROOT / '.claude/commands/cpp/init.md').read_text()
    block = next(b for b in re.findall(r'```bash\n(.*?)```', source, re.S) if '\nCPP_HOST_RUNTIME=' in b)
    cpp = tmp_path / 'cpp'
    (cpp / 'scripts').mkdir(parents=True)
    (cpp / 'scripts/cpp-install-receipt.py').write_text(
        'import runpy, sys\n'
        'if sys.argv[1] == "host-ci-outcome": raise SystemExit(1)\n'
        f'runpy.run_path({str(HELPER)!r}, run_name="__main__")\n'
    )
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    uv = bindir / 'uv'
    uv.write_text('#!/bin/bash\nprintf "HOST_CI_RECORD: written\\n"\nexit 0\n')
    uv.chmod(0o755)
    old_rows = rows() + [{'step':'host-ci', 'outcome':'written', 'exit_code':0}]
    env = {**os.environ, 'PATH':str(bindir) + os.pathsep + os.environ['PATH'],
           'CPP_DIR':str(cpp), 'CPP_CAPABILITIES_JSON':'["cicd"]',
           'CPP_PROJECTS_ROOT':str(tmp_path / 'projects'), 'HOME':str(tmp_path),
           'STEP_RESULTS_JSON':json.dumps(old_rows)}
    assert shutil.which('uv', path=env['PATH']) == str(uv)
    assert old_rows[-1]['outcome'] == 'written'
    script = 'trap \'printf "FINAL_ROWS: <%s>\\n" "$STEP_RESULTS_JSON"\' EXIT\n' + block
    result = subprocess.run(['bash', '-c', script], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert 'FINAL_ROWS: <>' in result.stdout
    assert 'Host CI observation unverified' in result.stderr
    assert 'Host CI record persisted;' not in result.stdout


@pytest.mark.skipif(any(shutil.which(name) is None for name in ('bash', 'env', 'python3', 'git')),
                    reason='registered control requires bash/env/python3/git')
def test_registered_host_control_preserves_fresh_shell_mcp_receipt_integration():
    # Bounded by the suite's own per-test limit. A private 30 second limit here
    # reddened pipelines 3689 and 3754 under load (issue #1718).
    result = subprocess.run([
        sys.executable, str(ROOT / 'scripts/check-negative-controls.py'), '--root', str(ROOT),
        '--strict', '--control', 'controls/cpp-host-install-receipt',
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'NEGATIVE_CONTROL_VERDICT: PASS' in result.stdout
    for name in ('good-written', 'good-missing-provider-written', 'good-unknown-provider-written'):
        assert f'case {name}: expected=GOOD observed=GOOD' in result.stdout
    for name in ('bad-deferred', 'bad-failed-retry', 'bad-unknown', 'bad-no-receipt-zero',
                 'bad-contradictory-receipt', 'bad-duplicate-receipt'):
        assert f'on case {name}: missed the known-bad input (blind, as required)' in result.stdout
