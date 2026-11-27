"""Actual offline-table parser and probe environment; pi is never executed."""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests/fixtures/pi-model-list'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def model():
    result = load(ROOT / 'docs/measurements/pi/issue-1899-b2-model.py', 'pi_model_pin')
    if os.environ.get('CPP_PI_MODEL_PIN_BLIND_CONTROL') == '1':
        blind = load(ROOT / 'tests/fixtures/pi-model-pin-blind.py', 'pi_model_blind')
        result.unique_pin = blind.unique_pin
    return result


@pytest.fixture
def root(tmp_path):
    for name in ['home', 'agent', 'work/repo-alpha', 'config', 'data', 'cache', 'tmp']:
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_one_exact_provider_model(model):
    assert model.unique_pin((DATA / 'one.txt').read_text())['id'] == 'github-copilot/gpt-5.3-codex'


def test_ambiguous_listing_refused(model):
    output = (DATA / 'two.txt').read_text()
    assert len(model.candidates(output)) == 2
    with pytest.raises(ValueError, match='exactly one'):
        model.unique_pin(output)


@pytest.mark.parametrize('fixture', ['none.txt', 'malformed.txt'])
def test_absent_and_unknown_listing_refused(model, fixture):
    output = (DATA / fixture).read_text()
    if fixture == 'none.txt':
        assert model.candidates(output) == []
    else:
        assert output.splitlines()[0].split() != model.HEADER
    with pytest.raises(ValueError):
        model.unique_pin(output)


def test_resolve_uses_only_probe_env_and_offline_cli(model, root, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert '--offline' in argv and '--list-models' in argv
        assert '--print' not in argv and '--mode' not in argv
        assert argv[-1] == '5.3'
        assert kwargs['stdin'] == subprocess.DEVNULL
        assert kwargs['env']['HOME'] == str(root / 'home')
        assert kwargs['env']['PI_CODING_AGENT_DIR'] == str(root / 'agent')
        assert kwargs['cwd'] == root / 'work/repo-alpha'
        assert 'UNRELATED_FIXTURE_ENV' not in kwargs['env']
        return subprocess.CompletedProcess(argv, 0, (DATA / 'one.txt').read_text(), '')

    monkeypatch.setenv('UNRELATED_FIXTURE_ENV', 'synthetic')
    monkeypatch.setattr(model.subprocess, 'run', fake_run)
    model.resolve(root)
    assert len(calls) == 1
    assert model.read_pin(root) == 'github-copilot/gpt-5.3-codex'
    with pytest.raises(FileExistsError):
        model.resolve(root)
    assert len(calls) == 1


@pytest.mark.parametrize('failure', ['stderr', 'exit', 'ambiguous'])
def test_unusable_resolution_never_creates_readable_pin(model, root, monkeypatch, failure):
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, 1 if failure == 'exit' else 0,
            (DATA / ('two.txt' if failure == 'ambiguous' else 'one.txt')).read_text(),
            'synthetic diagnostic' if failure == 'stderr' else '')

    monkeypatch.setattr(model.subprocess, 'run', fake_run)
    with pytest.raises(ValueError):
        model.resolve(root)
    assert (root / 'work' / model.PIN_NAME).read_bytes() == b''
    with pytest.raises(json.JSONDecodeError):
        model.read_pin(root)


def test_pin_symlink_refused(model, root):
    target = root / 'personal.txt'
    target.write_bytes(b'foreign sentinel')
    (root / 'work' / model.PIN_NAME).symlink_to(target)
    assert (root / 'work' / model.PIN_NAME).is_symlink()
    with pytest.raises(OSError):
        model.read_pin(root)
    assert target.read_bytes() == b'foreign sentinel'
