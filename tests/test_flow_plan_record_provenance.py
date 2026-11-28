"""Optional closing-text provenance validation through the real finish CLI (#1877)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from tests import test_flow_plan_record_wrappers as wrappers

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/flow-provenance'
SCRIPT = Path(os.environ.get('CPP_FLOW_PLAN_TEST_SCRIPT', ROOT / 'scripts/flow-plan-record.py'))
pytestmark = [pytest.mark.skipif(shutil.which('git') is None, reason='requires git'),
              pytest.mark.skipif(shutil.which('python3') is None, reason='requires python3')]
repo = wrappers.repo
fake_gh = wrappers.fake_gh


@pytest.fixture(autouse=True)
def selected_helper(monkeypatch):
    monkeypatch.setattr(wrappers, 'HELPER', SCRIPT)


@pytest.fixture
def ready(repo, fake_gh, tmp_path):
    wrappers.approved(repo, fake_gh, tmp_path)
    (repo / 'src').mkdir()
    (repo / 'src/a.py').write_text('x = 1\n')
    wrappers.git(repo, 'add', '-A')
    wrappers.git(repo, 'commit', '-qm', 'the change')
    return repo, fake_gh, wrappers.git(repo, 'rev-parse', 'HEAD').strip()


def finish(ready, *extra):
    repo, bindir, head = ready
    return wrappers.helper(repo, bindir, 'finish', '42', '--head', head, '--base', 'HEAD~1', *extra)


@pytest.mark.parametrize('name,code,state', [('valid', 0, 'valid'), ('invalid', 1, 'invalid'),
                                           ('missing', 1, 'invalid'), ('conflicting', 1, 'invalid'),
                                           ('invalid-origin', 1, 'invalid'), ('invalid-missed', 1, 'invalid')])
def test_committed_provenance_pair_through_finish(ready, name, code, state):
    text = (FIXTURES / f'{name}.md').read_text()
    if name == 'invalid':
        assert 'introduced by #123' in text and 'the unit tests missed it' in text
    if name == 'invalid-origin':
        assert 'Origin: introduced by #123' in text and 'Missed because: no test covered it' in text
    if name == 'invalid-missed':
        assert 'Origin: #123' in text and 'Missed because: the unit tests missed it' in text
    if name == 'missing':
        assert 'Missed because:' not in text
    if name == 'conflicting':
        assert text.count('Origin:') == 2
    done = finish(ready, '--provenance-file', str(FIXTURES / f'{name}.md'))
    assert done.returncode == code, done.stdout + done.stderr
    assert f'FLOW_PROVENANCE: {state}' in done.stdout
    assert f'FLOW_PLAN_FINISH: drift=0 compliance=0 head-check=0 provenance={code}' in done.stdout


def copied_helper(tmp_path, monkeypatch):
    package = tmp_path / 'package'
    script = package / 'scripts/flow-plan-record.py'
    script.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, script)
    contract = package / 'docs/agents/closing-report-contract.md'
    contract.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / 'docs/agents/closing-report-contract.md', contract)
    monkeypatch.setattr(wrappers, 'HELPER', script)
    return contract


@pytest.mark.parametrize('fault', ['missing', 'malformed', 'invalid-bytes', 'reversed-markers'])
def test_contract_unavailable_is_unknown_and_all_finish_checks_run(ready, tmp_path, monkeypatch, fault):
    contract = copied_helper(tmp_path, monkeypatch)
    if fault == 'missing':
        contract.unlink()
        assert not contract.exists()
    elif fault == 'malformed':
        contract.write_text('# No answer lists here\n')
        assert '<!-- defect-origin-answers -->' not in contract.read_text()
    elif fault == 'invalid-bytes':
        contract.write_bytes(b'\xff')
        assert contract.read_bytes() == b'\xff'
    else:
        text = contract.read_text()
        text = text.replace('<!-- defect-origin-answers -->', '<!-- /defect-origin-answers -->', 1)
        closing = text.rfind('<!-- /defect-origin-answers -->')
        text = text[:closing] + text[closing:].replace('<!-- /defect-origin-answers -->',
                                                    '<!-- defect-origin-answers -->', 1)
        contract.write_text(text)
        assert text.index('<!-- /defect-origin-answers -->') < text.index('<!-- defect-origin-answers -->')
    done = finish(ready, '--provenance-file', str(FIXTURES / 'valid.md'))
    assert done.returncode == 4, done.stdout + done.stderr
    assert 'FLOW_PROVENANCE: unknown' in done.stdout
    assert 'FLOW_PLAN_FINISH: drift=0 compliance=0 head-check=0 provenance=4' in done.stdout


def test_without_flag_is_byte_identical_even_if_contract_disappears(ready, tmp_path, monkeypatch):
    contract = copied_helper(tmp_path, monkeypatch)
    before = finish(ready)
    contract.unlink()
    assert not contract.exists()
    after = finish(ready)
    assert before.returncode == after.returncode == 0
    assert before.stdout == after.stdout and before.stderr == after.stderr
    assert 'FLOW_PROVENANCE:' not in after.stdout and 'provenance=' not in after.stdout


def test_unreadable_provenance_file_is_unknown(ready, tmp_path):
    missing = tmp_path / 'missing.md'
    assert not missing.exists()
    done = finish(ready, '--provenance-file', str(missing))
    assert done.returncode == 4, done.stdout + done.stderr
    assert 'FLOW_PROVENANCE: unknown' in done.stdout


@pytest.mark.parametrize('origin', ['#1', 'never worked', 'not traced - inspected the history'])
def test_valid_origin_forms_and_duplicate_identical_lines(ready, tmp_path, origin):
    text = tmp_path / 'closing.md'
    text.write_text(f'Origin: {origin}\nOrigin: {origin}\nMissed because: not a defect in earlier work\n')
    done = finish(ready, '--provenance-file', str(text))
    assert done.returncode == 0, done.stdout + done.stderr
    assert 'FLOW_PROVENANCE: valid' in done.stdout


def test_invalid_provenance_does_not_hide_an_existing_head_failure(ready):
    repo, bindir, _head = ready
    wrappers.git(repo, 'rm', 'docs/flow-runs/issue-42.md')
    wrappers.git(repo, 'commit', '-qm', 'remove the plan record')
    assert not (repo / 'docs/flow-runs/issue-42.md').exists()
    done = wrappers.helper(repo, bindir, 'finish', '42', '--head', 'HEAD', '--base', 'HEAD~2',
                           '--provenance-file', str(FIXTURES / 'invalid.md'))
    assert done.returncode == 1
    assert 'head-check=1 provenance=1' in done.stdout
    assert 'FLOW_PROVENANCE: invalid' in done.stdout


@pytest.mark.parametrize('name,expected', [('valid', 'recorded'), ('invalid', 'INVALID')])
def test_real_finish_input_is_read_by_the_real_review_yield_reader(ready, name, expected):
    import importlib.util
    spec = importlib.util.spec_from_file_location('provenance_report_reader', ROOT / 'scripts/review-yield-report.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    file = FIXTURES / f'{name}.md'
    done = finish(ready, '--provenance-file', str(file))
    assert done.returncode == (0 if name == 'valid' else 1)
    lists = reader.answer_lists((ROOT / 'docs/agents/closing-report-contract.md').read_text())
    state, values = reader.provenance({'body': file.read_text(), 'comments': []}, lists)
    assert state.startswith(expected)
    assert all(value is not None for value in values) == (name == 'valid')


def test_contract_is_the_only_vocabulary_source(ready, tmp_path, monkeypatch):
    contract = copied_helper(tmp_path, monkeypatch)
    contract.write_text(contract.read_text().replace('`no test covered it`', '`fixture-only answer`'))
    text = tmp_path / 'closing.md'
    text.write_text('Origin: #123\nMissed because: fixture-only answer\n')
    assert finish(ready, '--provenance-file', str(text)).returncode == 0
    text.write_text('Origin: #123\nMissed because: no test covered it\n')
    done = finish(ready, '--provenance-file', str(text))
    assert done.returncode == 1 and 'FLOW_PROVENANCE: invalid' in done.stdout


def test_generated_flow_auto_package_runs_optional_finish(ready, tmp_path, monkeypatch):
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location('provenance_codex_bundle', ROOT / 'scripts/codex-skill-sync.py')
    sync = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = sync
    spec.loader.exec_module(sync)
    files = sync.generate_skill(ROOT / '.claude/commands/flow/auto.md', 'flow', sync.generated_names(['flow']))
    package = tmp_path / 'flow-auto'
    for name, content in files.items():
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    contract = package / 'docs/agents/closing-report-contract.md'
    original = (ROOT / 'docs/agents/closing-report-contract.md').read_text()
    bundled = contract.read_text()
    for marker in ('defect-origin-answers', 'defect-missed-answers'):
        opening, closing = f'<!-- {marker} -->', f'<!-- /{marker} -->'
        assert original.count(opening) == bundled.count(opening) == 1
        assert original.split(opening)[1].split(closing)[0] == bundled.split(opening)[1].split(closing)[0]
    monkeypatch.setattr(wrappers, 'HELPER', package / 'scripts/flow-plan-record.py')
    valid = finish(ready, '--provenance-file', str(FIXTURES / 'valid.md'))
    invalid = finish(ready, '--provenance-file', str(FIXTURES / 'invalid.md'))
    assert valid.returncode == 0 and 'FLOW_PROVENANCE: valid' in valid.stdout
    assert invalid.returncode == 1 and 'FLOW_PROVENANCE: invalid' in invalid.stdout
