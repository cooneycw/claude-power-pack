"""Actual B2 handoff guards and opposite inputs; no pi or credential access."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def probe():
    module = load(ROOT / 'docs/measurements/pi/issue-1899-b2-files.py', 'pi_rules_probe')
    if os.environ.get('CPP_PI_RULE_PROBE_BLIND_CONTROL') == '1':
        blind = load(ROOT / 'tests/fixtures/pi-rule-probe-blind.py', 'pi_rules_blind')
        module.verify_rules = blind.verify_rules
    return module


@pytest.fixture
def root(tmp_path):
    (tmp_path / 'agent').mkdir()
    (tmp_path / 'work').mkdir()
    for slug in ['repo-alpha', 'repo-beta']:
        (tmp_path / 'work' / slug).mkdir()
    return tmp_path


def test_real_case_matrix_and_undo(probe, root):
    probe.prepare(root)
    neighbor = root / 'agent/personal.md'
    neighbor.write_bytes(b'foreign sentinel')
    for case, expected in probe.CASES.items():
        probe.apply_case(root, case)
        for name in probe.RULES:
            if name in expected:
                path = root / 'agent' / name
                assert path.read_bytes() == probe.fixture_bytes(expected[name])
                assert path.stat().st_mode & 0o777 == 0o644
            else:
                assert not (root / 'agent' / name).exists()
        assert neighbor.read_bytes() == b'foreign sentinel'
    probe.apply_case(root, 'absent')
    assert not any((root / 'agent' / name).exists() for name in probe.RULES)


@pytest.mark.parametrize('case', ['foreign', 'edited', 'symlink', 'mode', 'missing', 'directory'])
def test_bad_input_preserved_and_refused(probe, root, case):
    probe.prepare(root)
    target = root / 'agent/AGENTS.md'
    if case == 'foreign':
        target.write_bytes(b'foreign')
    else:
        probe.apply_case(root, 'base')
        if case == 'edited':
            target.write_bytes(b'edited')
        elif case == 'mode':
            target.chmod(0o600)
        else:
            target.unlink()
            if case == 'symlink':
                target.symlink_to('personal.md')
            elif case == 'directory':
                target.mkdir()
    state = root / 'work/pi-1899-b2-state.json'
    original = state.read_bytes()
    # Each branch above materially establishes a distinct forbidden condition.
    if case in ['foreign', 'edited']:
        assert target.read_bytes() in [b'foreign', b'edited']
    elif case == 'symlink':
        assert target.is_symlink()
    elif case == 'mode':
        assert target.stat().st_mode & 0o777 == 0o600
    elif case == 'missing':
        assert not target.exists()
    else:
        assert target.is_dir()
    with pytest.raises(ValueError):
        probe.apply_case(root, 'absent')
    assert state.read_bytes() == original
    if case in ['foreign', 'edited']:
        assert target.read_bytes() in [b'foreign', b'edited']
    elif case == 'symlink':
        assert target.is_symlink()
    elif case == 'directory':
        assert target.is_dir()


def test_interrupted_state_is_unknown_not_retryable(probe, root):
    probe.prepare(root)
    state = root / 'work/pi-1899-b2-state.json'
    state.write_text(json.dumps({'phase': 'blocked', 'rules': {}}))
    assert json.loads(state.read_text())['phase'] == 'blocked'
    with pytest.raises(ValueError, match='incomplete'):
        probe.apply_case(root, 'base')
    assert not (root / 'agent/AGENTS.md').exists()


def test_existing_rule_refuses_preparation(probe, root):
    target = root / 'agent/AGENTS.override.md'
    target.write_bytes(b'foreign override')
    assert target.read_bytes() == b'foreign override'
    with pytest.raises(ValueError, match='unexpected'):
        probe.prepare(root)
    assert not (root / 'work/pi-1899-b2-state.json').exists()


def test_t1_resume_is_read_only(probe, root):
    probe.prepare(root)
    probe.apply_case(root, 'absent')
    journal = root / 'work/pi-1899-b2-state.json'
    before = journal.read_bytes()
    assert probe.check_t1(root) == {'phase': 'stable', 'rules': {}}
    assert journal.read_bytes() == before
    assert not journal.with_suffix('.pending').exists()
    assert not any((root / 'agent' / name).exists() for name in probe.RULES)


@pytest.mark.parametrize('bad_state', ['blocked', 'different-rules', 'unexpected-file'])
def test_t1_resume_refuses_other_states(probe, root, bad_state):
    probe.prepare(root)
    journal = root / 'work/pi-1899-b2-state.json'
    if bad_state == 'blocked':
        journal.write_text(json.dumps({'phase': 'blocked', 'rules': {}}))
        assert json.loads(journal.read_text())['phase'] == 'blocked'
    elif bad_state == 'different-rules':
        probe.apply_case(root, 'base')
        assert json.loads(journal.read_text())['rules']
    else:
        (root / 'agent/AGENTS.override.md').write_bytes(b'foreign rule')
        assert (root / 'agent/AGENTS.override.md').exists()
    before = journal.read_bytes()
    with pytest.raises(ValueError):
        probe.check_t1(root)
    assert journal.read_bytes() == before


def test_ancestor_context_refuses_before_mutation(probe, root):
    context = root / 'work/AGENTS.override.md'
    context.write_bytes(b'synthetic ancestor rules')
    assert context.exists()
    with pytest.raises(ValueError, match='ancestor context'):
        probe.prepare(root)
    assert context.read_bytes() == b'synthetic ancestor rules'
    assert not (root / 'work/pi-1899-b2-state.json').exists()


def test_unreadable_ancestor_candidate_is_unknown(probe, root, monkeypatch):
    candidate = root / 'work/CLAUDE.md'
    original = os.lstat
    touched = []

    def unavailable(path, *args, **kwargs):
        if Path(path) == candidate:
            touched.append(candidate)
            raise PermissionError('synthetic unavailable context inspection')
        return original(path, *args, **kwargs)

    # Simulate unavailable metadata explicitly; chmod alone is not effective as root.
    monkeypatch.setattr(os, 'lstat', unavailable)
    with pytest.raises(PermissionError, match='synthetic unavailable'):
        os.lstat(candidate)
    with pytest.raises(PermissionError, match='synthetic unavailable'):
        probe.prepare(root)
    assert touched
    assert not (root / 'work/pi-1899-b2-state.json').exists()


def test_blind_anchor_cannot_satisfy_edited_rule_case(probe, root, monkeypatch):
    probe.prepare(root)
    probe.apply_case(root, 'base')
    target = root / 'agent/AGENTS.md'
    target.write_bytes(b'owner edit')
    assert target.read_bytes() != probe.fixture_bytes('base.md')
    blind = load(ROOT / 'tests/fixtures/pi-rule-probe-blind.py', 'pi_rules_blind')
    monkeypatch.setattr(probe, 'verify_rules', blind.verify_rules)
    # Same known-bad input is accepted/deleted by the deliberately blind guard.
    probe.apply_case(root, 'absent')
    assert not target.exists()
