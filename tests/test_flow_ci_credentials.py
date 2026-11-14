"""Real shell resolver against owned secret/HTTP stubs, never a live provider."""
import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / 'scripts/flow-ci-status.sh'
SPEC = importlib.util.spec_from_file_location('flow_ci_credential_cases',
                                             ROOT / 'controls/flow-ci-credential-pair/run-case.py')
assert SPEC and SPEC.loader
cases = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cases)
requires_tools = pytest.mark.skipif(
    shutil.which('bash') is None or shutil.which('jq') is None,
    reason='requires bash and jq',
)


@requires_tools
@pytest.mark.parametrize('scenario', ['bad-server-mix', 'bad-token-mix'])
def test_incompatible_partial_credentials_never_send_an_authenticated_request(scenario):
    result, requests, called = cases.exercise(GATE, scenario)
    assert called, 'fixture must exercise secret fallback'
    assert not requests, 'partial settings must not route credentials from an unrelated source'
    assert result.returncode == 2
    assert 'FLOW_CI_STATUS: unknown' in result.stdout


@requires_tools
@pytest.mark.parametrize('scenario', ['good-environment', 'good-secret', 'good-matching-server', 'good-matching-token'])
def test_complete_and_matching_credential_pairs_still_answer(scenario):
    result, requests, called = cases.exercise(GATE, scenario)
    assert result.returncode == 0 and 'FLOW_CI_STATUS: success' in result.stdout
    expected_server = cases.SERVER_B if scenario == 'good-environment' else cases.SERVER_A
    expected_token = cases.TOKEN_B if scenario == 'good-environment' else cases.TOKEN_A
    assert requests
    assert all(row['url'].startswith(expected_server + '/') for row in requests)
    assert all(expected_token in row['header'] for row in requests)
    assert called is (scenario != 'good-environment')
