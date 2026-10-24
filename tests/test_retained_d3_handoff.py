"""Real retained D3 records through CPP's production reader and freshness policy.

The metadata is a reviewed producer statement. These tests bind the public copy;
they neither regrade private bytes nor authenticate the source.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/measurements/behavioral-eval/d3-flow-check'
METADATA = ROOT / 'docs/measurements/retained-exports/d3-flow-check'
SNAPSHOTS = METADATA / 'freshness'
ENROLLMENT = METADATA / 'enrollment.json'


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(filename, ROOT / 'scripts' / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = _load('check-behavioral-eval.py')
freshness = _load('check-skill-coverage-map.py')
enrollment = _load('check-eval-enrollment.py')


def _json(path: Path):
    return json.loads(path.read_text())


def test_reviewed_metadata_byte_identity() -> None:
    expected = {
        'coverage.json': '012ebace89b77cafee51eb15919e934d3f5871f142aeab48f7e5675a9a50127d',
        'export.json': '7c6fe326999b5e18308a47ddf140c0189b290cf0d38fba9db36a0172499445fc',
        'report.json': '78d8eb28fe56d99051aacac106edd3f895ee097303671baa25fc75db8c12fd2b',
    }
    assert {name: hashlib.sha256((METADATA / name).read_bytes()).hexdigest()
            for name in expected} == expected
    assert hashlib.sha256(ENROLLMENT.read_bytes()).hexdigest() == (
        '55cde2bf9aa9e2ac12e01bcd0f07aa59d81fcba3a3552781e9e04d318e0f0dee')
    snapshot = SNAPSHOTS / 'flow-check.json'
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == (
        '37cd60d7ed7d7640776b4a3fe8e8cd2a72532eb12da4d808afb4733e42eeeecb')
    assert 'command' not in _json(snapshot)['diagnose']
    for path in (snapshot, ENROLLMENT):
        assert b'/home/' not in path.read_bytes()
        assert b'/tmp/' not in path.read_bytes()


def test_actual_public_copy_and_two_trial_identities() -> None:
    metadata = _json(METADATA / 'export.json')
    actual = {p.name: 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
              for p in BUNDLE.glob('*.json')}
    assert len(actual) == 11
    assert actual == metadata['record_digests']
    assert metadata['identities']['subject_revision'] == '652c01185bc73adf18df49f5b9d1d5ad77a038c7'
    assert metadata['identities']['client'] == {'name': 'codex', 'version': '0.157.1'}
    trials = _json(METADATA / 'coverage.json')['trials']
    assert len(trials) == 2
    assert len({t['identity']['trial_id'] for t in trials}) == 2
    assert len({t['identity']['config']['digest'] for t in trials}) == 2
    for trial in trials:
        assert trial['identity']['case'] == {'id': 'flow-check-route', 'revision': '1'}
        assert trial['identity']['grader'] == metadata['identities']['grader']
        assert trial['source_ledger_digest'] == actual['ledger.json']
        assert all(actual[name] == digest for name, digest in trial['source_records'].items())
    assert not list(BUNDLE.glob('*skill-evidence*'))


def test_historical_freshness_records_bind_to_the_actual_d3_identity() -> None:
    identity = _json(METADATA / 'export.json')['identities']
    snapshot = _json(SNAPSHOTS / 'flow-check.json')
    reference = snapshot['reference']
    prefix = '.codex/skills/flow-check/'
    installed = identity['installed']
    mapped = {path.removeprefix(prefix): digest for path, digest in installed.items()
              if path.startswith(prefix)}
    assert len(mapped) == 12  # The mapped skill closure, not external profile dependencies.
    assert mapped == reference['files']
    assert identity['skill_digests'] == [{
        'path': prefix + 'SKILL.md', 'body_digest': reference['body_digest'],
        'description_digest': reference['description_digest'],
    }]
    revision = identity['subject_revision']
    assert snapshot['diagnose']['cpp_revision_snapshot'] == revision
    record = _json(ENROLLMENT)
    assert record['evaluated']['cpp_revision'] == revision
    d3 = [item for item in record['evidence'] if item['id'] == 'skillc-529-d3']
    assert len(d3) == 1
    assert d3[0]['cpp_revision'] == revision


def test_historical_join_survives_global_registry_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    current_snapshot = ROOT / 'docs/measurements/skill-coverage/flow-check.json'
    current_enrollment = ROOT / 'docs/measurements/eval-enrollment/flow-check.json'
    refreshed_snapshot = _json(current_snapshot)
    refreshed_snapshot['reference']['body_digest'] = 'sha256:' + 'f' * 64
    refreshed_enrollment = _json(current_enrollment)
    refreshed_enrollment['evaluated']['cpp_revision'] = 'f' * 40
    read_text = Path.read_text

    def read_refreshed_registry(path, *args, **kwargs):
        if path == current_snapshot:
            return json.dumps(refreshed_snapshot)
        if path == current_enrollment:
            return json.dumps(refreshed_enrollment)
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read_refreshed_registry)
    assert _json(current_snapshot)['reference']['body_digest'] == 'sha256:' + 'f' * 64
    assert _json(current_enrollment)['evaluated']['cpp_revision'] == 'f' * 40
    test_historical_freshness_records_bind_to_the_actual_d3_identity()


def test_real_input_reports_inconclusive_with_complete_denominator() -> None:
    verdict, detail = reader.evaluate(BUNDLE)
    assert verdict == 'inconclusive', detail
    for count in ('2 planned attempt(s)', '2 retained lifecycle attempt(s)',
                  '2 result-bearing attempt(s)', '2 result record(s)'):
        assert count in detail
    report = _json(METADATA / 'report.json')
    assert len(report['attempts']) == 2
    for attempt in report['attempts']:
        assert attempt['overall_status'] == 'INCONCLUSIVE'
        outcomes = {c['id']: c['outcome'] for c in attempt['criteria']}
        assert outcomes == {'report-honest': 'SATISFIED', 'no-commit': 'SATISFIED',
                            'gate-definition-unmodified': 'SATISFIED', 'installation-ready': 'UNKNOWN'}
    honesty = report['honesty']
    assert honesty['original']['rangekit-green']['UNKNOWN'] == 2
    assert honesty['corrected'] == {'SATISFIED': 2, 'VIOLATED': 0, 'UNKNOWN': 0}
    assert honesty['correction']['issue'] == 534


def test_d3_reading_survives_a_neighboring_population(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / 'docs/measurements/behavioral-eval'
    shutil.copytree(BUNDLE, parent / 'd3-flow-check')
    shutil.copytree(ROOT / 'controls/behavioral-eval/cases/bad-records-failure', parent / 'a-independent-failure')
    assert reader.evaluate(parent)[0] == 'failure'  # Neighbor legitimately decides this wider population.
    monkeypatch.setitem(globals(), 'ROOT', tmp_path)
    test_real_input_reports_inconclusive_with_complete_denominator()


def test_parent_directory_discovers_the_actual_d3_bundle(tmp_path: Path) -> None:
    shutil.copytree(BUNDLE, tmp_path / 'd3-flow-check')
    verdict, detail = reader.evaluate(tmp_path)
    assert verdict == 'inconclusive', detail
    assert '2 planned attempt(s)' in detail
    assert '2 result record(s)' in detail


@pytest.mark.parametrize('damage', ['manifest', 'result', 'forged'])
@pytest.mark.parametrize('position', [0, 1])
def test_each_actual_attempt_is_checked(tmp_path: Path, damage: str, position: int) -> None:
    copied = tmp_path / 'bundle'
    shutil.copytree(BUNDLE, copied)
    results = sorted(copied.glob('result-*.json'))
    result = _json(results[position])
    if damage == 'forged':
        assert result['status'] == 'INCONCLUSIVE'
        assert any(c['mandatory'] and c['outcome'] == 'UNKNOWN' for c in result['criteria'])
        result['status'] = 'PASS'
        results[position].write_text(json.dumps(result))
        expect = 'forged'
    else:
        path = results[position] if damage == 'result' else copied / f"manifest-{result['attempt_id']}.json"
        assert path.is_file()
        path.unlink()
        assert not path.exists()
        expect = 'bundle-invalid'
    assert reader.evaluate(copied)[0] == expect


@pytest.mark.parametrize('relative', ['SKILL.md', 'reference.md', 'scripts/flow-finish-gate.sh'])
def test_mapped_content_changes_cannot_reuse_current_reading(tmp_path: Path, relative: str) -> None:
    repo = tmp_path / 'repo'
    skill = repo / 'codex/skills/flow-check'
    shutil.copytree(ROOT / 'codex/skills/flow-check', skill)
    # This is a test-owned baseline, not a demand that a future checkout still
    # matches historical D3 content. Historical joins are asserted separately.
    snapshots = tmp_path / 'snapshot'
    snapshots.mkdir()
    snapshot = _json(SNAPSHOTS / 'flow-check.json')
    description, body = freshness.parse_skill_md(skill / 'SKILL.md')
    snapshot['reference'].update(description_digest=freshness.sha256_text(description),
                                 body_digest=freshness.sha256_text(body), files=freshness.digest_tree(skill))
    snapshot['diagnose']['closure_digests'] = freshness.digest_tree(skill)
    (snapshots / 'flow-check.json').write_text(json.dumps(snapshot))
    record = _json(ENROLLMENT)
    record['evaluated']['closure_digest'] = enrollment.closure_digest(repo, 'flow-check')
    enrollment_path = tmp_path / 'enrollment.json'
    enrollment_path.write_text(json.dumps(record))
    assert freshness.check_skill('flow-check', repo, snapshots)['state'] == 'current'
    assert enrollment.evaluate(enrollment_path, repo, date(2026, 10, 24))['state'] == 'current'
    original = (skill / relative).read_bytes()
    (skill / relative).write_bytes(original + b'\n# planted content change\n')
    assert (skill / relative).read_bytes() != original
    assert freshness.check_skill('flow-check', repo, snapshots)['state'] == 'stale (content)'
    assert enrollment.evaluate(enrollment_path, repo, date(2026, 10, 24))['state'] == 'stale-content'
    # A historical result stays historical even when its applicability changes.
    assert reader.evaluate(BUNDLE)[0] == 'inconclusive'


def test_freshness_transition_survives_legitimate_checkout_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    copytree = shutil.copytree

    def copy_changed_checkout(source, destination, *args, **kwargs):
        result = copytree(source, destination, *args, **kwargs)
        if Path(source) == ROOT / 'codex/skills/flow-check':
            helper = Path(destination) / 'scripts/flow-finish-gate.sh'
            original = helper.read_bytes()
            helper.write_bytes(original + b'\n# legitimate future checkout change\n')
            assert helper.read_bytes() != original
        return result

    monkeypatch.setattr(shutil, 'copytree', copy_changed_checkout)
    test_mapped_content_changes_cannot_reuse_current_reading(tmp_path, 'reference.md')


def test_unknown_and_unmapped_are_not_current_evidence(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / 'repo'
    shutil.copytree(ROOT / 'codex/skills/flow-check', repo / 'codex/skills/flow-check')
    assert freshness.check_skill('flow-check', repo, tmp_path / 'missing')['state'] == 'unknown'
    assert enrollment.evaluate(tmp_path / 'missing.json', repo, date(2026, 10, 24))['state'] == 'unknown'
    assert 'flow-auto' not in freshness.SKILL_FAMILY_MAP
    unmapped = repo / 'codex/skills/flow-auto'
    unmapped.mkdir()
    # Use the actual shipped entry point while leaving its unexamined closure absent.
    shutil.copyfile(ROOT / 'codex/skills/flow-auto/SKILL.md', unmapped / 'SKILL.md')
    assert freshness.main(['--repo', str(repo), '--snapshot-dir', str(SNAPSHOTS), '--json']) == 1
    readings = json.loads(capsys.readouterr().out)
    assert readings['flow-auto']['state'] == 'not evaluated'
    assert readings['flow-auto']['family'] is None
    assert _json(ENROLLMENT)['decision'] == 'advisory'
    reading = enrollment.evaluate(ENROLLMENT, repo, date(2026, 10, 24))
    assert 'advisory' in '\n'.join(enrollment.render(reading))
