"""Tests for scripts/flow-ci-status.sh - SHA-anchored CI verification (issue #766).

Contract:
- The pipeline is selected by matching ``.commit`` against the SHA, NEVER by
  list position. This is the regression under test: on flow:auto #516 a
  positional grep over a shared pipeline list reported an unrelated concurrent
  session's failure as the run's own.
- When several pipelines share a SHA (a merge commit usually has both a ``push``
  and a ``pull_request`` run), the ``--event`` preference decides which one the
  verdict describes.
- A failure names the failed STEPS - pipeline colour alone cannot separate a red
  test suite from a red deploy step.
- The Woodpecker token is taken from the environment, else fetched from AWS
  Secrets Manager, and never reaches stdout/stderr or a command line.
- Everything is fail-open: no credentials, no provider, no checkout ⇒ ``unknown``
  and exit 0. Only ``--exit-code`` turns a ``failure`` verdict into exit 1.

No test touches the network: ``curl``, ``aws`` and ``gh`` are replaced through the
FLOW_CI_* test hooks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-ci-status.sh"

SHA = "2b308175a757e0b17c30caead6aabbe9356b43cc"
OTHER_SHA = "ffffffffffffffffffffffffffffffffffffffff"

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="requires bash and jq on PATH (absent in the CI validate container)",
)


def _write_fake_curl(tmp_path: Path, routes: dict[str, object], argv_log: Path) -> Path:
    """A stand-in curl that dispatches on URL substring and logs its argv."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    body = [
        "#!/usr/bin/env bash",
        f'echo "ARGV: $*" >> "{argv_log}"',
        "cat >/dev/null 2>&1 || true",
        'url="${@: -1}"',
    ]
    for substr, payload in routes.items():
        body += [
            f'case "$url" in *"{substr}"*)',
            "cat <<'JSON'",
            json.dumps(payload),
            "JSON",
            "exit 0;; esac",
        ]
    body += ["echo '{}'", ""]
    path = tmp_path / "curl"
    path.write_text("\n".join(body), encoding="utf-8")
    path.chmod(0o755)
    return path


def _pipeline(number: int, commit: str, status: str, event: str = "push") -> dict:
    return {"number": number, "commit": commit, "status": status, "event": event}


def _run(tmp_path: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    # Never let a real credential or a real binary leak into a test.
    for key in ("WOODPECKER_API_TOKEN", "WOODPECKER_SERVER", "WOODPECKER_HOST"):
        full_env.pop(key, None)
    full_env.update(
        {
            "FLOW_CI_AWS": "/nonexistent/aws",
            "FLOW_CI_GH": "/nonexistent/gh",
            "FLOW_CI_SLEEP": "/bin/true",
            "WOODPECKER_SERVER": "https://wp.example.invalid",
            "WOODPECKER_API_TOKEN": "test-token-canary",
        }
    )
    full_env.update(env or {})
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(tmp_path),
    )


def _markers(out: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for line in out.splitlines():
        if line.startswith("FLOW_CI_"):
            key, _, value = line.partition(": ")
            found.setdefault(key, []).append(value)
    return found


@requires_bash
def test_selects_pipeline_by_sha_not_by_list_position(tmp_path):
    """The #516 regression: a red pipeline from another session must not be read as ours."""
    argv_log = tmp_path / "argv.log"
    curl = _write_fake_curl(
        tmp_path,
        {
            "/api/repos/lookup/": {"id": 17},
            "pipelines?per_page": [
                # Newest first, exactly as the API returns it: two unrelated
                # FAILING pipelines sit above ours.
                _pipeline(1277, OTHER_SHA, "failure", "pull_request"),
                _pipeline(1276, OTHER_SHA, "failure", "pull_request"),
                _pipeline(1275, SHA, "success", "push"),
            ],
        },
        argv_log,
    )
    result = _run(tmp_path, SHA, "--repo", "o/r", env={"FLOW_CI_CURL": str(curl)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["success"], result.stdout + result.stderr
    assert markers["FLOW_CI_PIPELINE"] == ["1275"]
    assert markers["FLOW_CI_PROVIDER"] == ["woodpecker"]
    assert result.returncode == 0


@requires_bash
def test_event_preference_picks_among_pipelines_sharing_a_sha(tmp_path):
    argv_log = tmp_path / "argv.log"
    routes = {
        "/api/repos/lookup/": {"id": 17},
        "pipelines?per_page": [
            _pipeline(90, SHA, "failure", "pull_request"),
            _pipeline(91, SHA, "success", "push"),
        ],
    }
    curl = _write_fake_curl(tmp_path, routes, argv_log)
    push = _run(tmp_path, SHA, "--repo", "o/r", env={"FLOW_CI_CURL": str(curl)})
    assert _markers(push.stdout)["FLOW_CI_PIPELINE"] == ["91"]
    assert _markers(push.stdout)["FLOW_CI_STATUS"] == ["success"]

    pr = _run(tmp_path, SHA, "--repo", "o/r", "--event", "pull_request",
              env={"FLOW_CI_CURL": str(curl)})
    assert _markers(pr.stdout)["FLOW_CI_PIPELINE"] == ["90"]
    assert _markers(pr.stdout)["FLOW_CI_STATUS"] == ["failure"]


@requires_bash
def test_failure_names_the_failed_steps(tmp_path):
    """Colour cannot separate a red test suite from a red deploy step."""
    argv_log = tmp_path / "argv.log"
    curl = _write_fake_curl(
        tmp_path,
        {
            "/api/repos/lookup/": {"id": 17},
            "pipelines?per_page": [_pipeline(1275, SHA, "failure")],
            "pipelines/1275": {
                "workflows": [
                    {
                        "children": [
                            {"name": "lint", "state": "success"},
                            {"name": "test-unit", "state": "failure"},
                            {"name": "deploy", "state": "skipped"},
                        ]
                    }
                ]
            },
        },
        argv_log,
    )
    result = _run(tmp_path, SHA, "--repo", "o/r", env={"FLOW_CI_CURL": str(curl)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["failure"]
    assert markers["FLOW_CI_FAILED_STEP"] == ["test-unit"]


@requires_bash
def test_exit_code_flag_gates_only_on_failure(tmp_path):
    argv_log = tmp_path / "argv.log"
    green = _write_fake_curl(
        tmp_path / "green",
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(1, SHA, "success")]},
        argv_log,
    )
    result = _run(tmp_path, SHA, "--repo", "o/r", "--exit-code", env={"FLOW_CI_CURL": str(green)})
    assert result.returncode == 0

    red = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(1, SHA, "failure")],
         "pipelines/1": {"workflows": []}},
        argv_log,
    )
    result = _run(tmp_path, SHA, "--repo", "o/r", "--exit-code", env={"FLOW_CI_CURL": str(red)})
    assert result.returncode == 1
    # Without the flag the same red verdict is advisory.
    result = _run(tmp_path, SHA, "--repo", "o/r", env={"FLOW_CI_CURL": str(red)})
    assert result.returncode == 0


@requires_bash
def test_not_found_when_no_pipeline_carries_the_sha(tmp_path):
    argv_log = tmp_path / "argv.log"
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(1, OTHER_SHA, "success")]},
        argv_log,
    )
    result = _run(tmp_path, SHA, "--repo", "o/r", env={"FLOW_CI_CURL": str(curl)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["not-found"]
    assert markers["FLOW_CI_PIPELINE"] == ["-"]
    assert result.returncode == 0


@requires_bash
def test_token_never_reaches_output_or_a_command_line(tmp_path):
    argv_log = tmp_path / "argv.log"
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(1, SHA, "success")]},
        argv_log,
    )
    canary = "SENTINEL-LEAK-CANARY"
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": str(curl), "WOODPECKER_API_TOKEN": canary})
    assert canary not in result.stdout
    assert canary not in result.stderr
    # `-H @-` feeds the header on stdin, so `ps` never sees the credential.
    assert canary not in argv_log.read_text(encoding="utf-8")


@requires_bash
def test_fetches_token_from_aws_when_not_exported(tmp_path):
    argv_log = tmp_path / "argv.log"
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(7, SHA, "success")]},
        argv_log,
    )
    aws = tmp_path / "aws"
    secret = json.dumps({"WOODPECKER_API_TOKEN": "from-aws", "WOODPECKER_HOST": "https://wp.example.invalid"})
    aws.write_text(f"#!/usr/bin/env bash\ncat <<'JSON'\n{secret}\nJSON\n", encoding="utf-8")
    aws.chmod(0o755)
    env = {"FLOW_CI_CURL": str(curl), "FLOW_CI_AWS": str(aws)}
    result = subprocess.run(
        ["bash", str(SCRIPT), SHA, "--repo", "o/r"],
        capture_output=True, text=True, cwd=str(tmp_path),
        env={**{k: v for k, v in os.environ.items()
                if k not in ("WOODPECKER_API_TOKEN", "WOODPECKER_SERVER", "WOODPECKER_HOST")},
             **env, "FLOW_CI_GH": "/nonexistent/gh", "FLOW_CI_SLEEP": "/bin/true"},
    )
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["success"], result.stdout + result.stderr
    assert markers["FLOW_CI_PIPELINE"] == ["7"]
    assert "from-aws" not in result.stdout and "from-aws" not in result.stderr


@requires_bash
def test_fails_open_without_credentials_or_provider(tmp_path):
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": "/nonexistent/curl", "WOODPECKER_API_TOKEN": "",
                       "WOODPECKER_SERVER": ""})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["unknown"]
    assert markers["FLOW_CI_PROVIDER"] == ["none"]
    assert result.returncode == 0


@requires_bash
def test_fails_open_on_a_missing_checkout(tmp_path):
    result = _run(tmp_path, "--path", str(tmp_path / "nope"))
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["unknown"]
    assert result.returncode == 0


@requires_bash
def test_unknown_argument_is_a_usage_error(tmp_path):
    result = _run(tmp_path, "--bogus")
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_registered_in_the_helper_family_and_allowlist():
    """A helper only runs prompt-free if it is installed and allowlisted."""
    installer = (ROOT / "scripts" / "flow-helpers-install.sh").read_text(encoding="utf-8")
    assert "flow-ci-status.sh" in installer

    permissions = (ROOT / "templates" / "claude-settings-permissions.json").read_text(encoding="utf-8")
    assert "Bash(~/.claude/scripts/flow-ci-status.sh:*)" in permissions


def test_flow_auto_step_8_calls_the_helper():
    auto = (ROOT / ".claude" / "commands" / "flow" / "auto.md").read_text(encoding="utf-8")
    assert "flow-ci-status.sh" in auto
    assert "FLOW_CI_STATUS" in auto
