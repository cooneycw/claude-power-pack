"""#1758 optional broader fallback exit policy; separable pending owner ruling."""

import pytest

from tests.test_flow_ci_boundary import boundary_env_fixture, wp_env  # noqa: F401
from tests.test_flow_ci_status import SHA, _markers, _run, requires_bash


@requires_bash
@pytest.mark.parametrize("wait", [False, True])
def test_invalid_ref_stops_before_fallback_requests(tmp_path, boundary_env, wait):
    env, calls = wp_env(tmp_path, boundary_env, routes={
        "/api/repos/lookup/": {"id": 1, "timeout": 60}, "pipelines?per_page": [],
    })
    invalid = "fixture-ref-does-not-exist"
    assert invalid != SHA and not (tmp_path / ".git").exists()
    args = [invalid, "--path", str(tmp_path), "--repo", "o/r", "--event", "push"]
    if wait:
        args.extend(["--wait", "1"])
    result = _run(tmp_path, *args, env=env)
    assert result.returncode == 2, result.stdout + result.stderr
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["unknown"]
    assert not calls.exists(), "unreadable ref must stop before provider lookup"


@requires_bash
@pytest.mark.parametrize("exit_code", [False, True])
def test_fallback_valid_ref_not_found_is_two(tmp_path, boundary_env, exit_code):
    env, _ = wp_env(tmp_path, boundary_env, routes={
        "/api/repos/lookup/": {"id": 1, "timeout": 60}, "pipelines?per_page": [],
    })
    args = [SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "push"]
    if exit_code:
        args.append("--exit-code")
    result = _run(tmp_path, *args, env=env)
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["not-found"]
    assert result.returncode == 2, result.stdout + result.stderr
