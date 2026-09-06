"""Tests for scripts/flow-ci-status.sh - SHA-anchored CI verification (#766, #768).

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

No test touches the network: ``curl``, ``aws``, ``woodpecker-cli`` and ``gh`` are
replaced through the FLOW_CI_* test hooks. The third provider lane exercises the
CLI only through ``FLOW_CI_WPCLI``.
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


def _write_fake_wpcli(
    tmp_path: Path,
    ls_rows: list[str],
    ps_rows: list[str],
    argv_log: Path,
) -> Path:
    """A stand-in woodpecker-cli that logs argv and returns canned rows."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    body = [
        "#!/usr/bin/env bash",
        f'{{ printf "ARGV:"; printf " <%s>" "$@"; printf "\\n"; }} >> "{argv_log}"',
        'case "$2" in',
        "ls)",
        "cat <<'ROWS'",
        *ls_rows,
        "ROWS",
        ";;",
        "ps)",
        "cat <<'ROWS'",
        *ps_rows,
        "ROWS",
        ";;",
        "*) exit 1 ;;",
        "esac",
        "",
    ]
    path = tmp_path / "woodpecker-cli"
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
            "FLOW_CI_WPCLI": "/nonexistent/woodpecker-cli",
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
def test_wpcli_selects_pipeline_by_exact_sha_not_list_position(tmp_path):
    """The CLI fallback must not revive the positional #516 regression."""
    missing_curl = Path("/nonexistent/curl")
    assert not missing_curl.exists()
    argv_log = tmp_path / "wpcli-argv.log"
    wpcli = _write_fake_wpcli(
        tmp_path,
        [
            f"1250|failure|{OTHER_SHA}|push",
            f"1249|success|{SHA}|push",
        ],
        [],
        argv_log,
    )
    result = _run(
        tmp_path,
        SHA,
        "--repo",
        "o/r",
        env={"FLOW_CI_CURL": str(missing_curl), "FLOW_CI_WPCLI": str(wpcli)},
    )
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["success"], result.stdout + result.stderr
    assert markers["FLOW_CI_PIPELINE"] == ["1249"]
    assert markers["FLOW_CI_PROVIDER"] == ["woodpecker"]
    assert markers["FLOW_CI_URL"] == ["-"]
    assert result.returncode == 0


@requires_bash
def test_wpcli_event_preference_picks_among_rows_sharing_a_sha(tmp_path):
    missing_curl = Path("/nonexistent/curl")
    assert not missing_curl.exists()
    argv_log = tmp_path / "wpcli-argv.log"
    wpcli = _write_fake_wpcli(
        tmp_path,
        [
            f"90|failure|{SHA}|pull_request",
            f"91|success|{SHA}|push",
        ],
        [],
        argv_log,
    )
    push = _run(
        tmp_path,
        SHA,
        "--repo",
        "o/r",
        env={"FLOW_CI_CURL": str(missing_curl), "FLOW_CI_WPCLI": str(wpcli)},
    )
    assert _markers(push.stdout)["FLOW_CI_PIPELINE"] == ["91"]
    assert _markers(push.stdout)["FLOW_CI_STATUS"] == ["success"]

    pr = _run(
        tmp_path,
        SHA,
        "--repo",
        "o/r",
        "--event",
        "pull_request",
        env={"FLOW_CI_CURL": str(missing_curl), "FLOW_CI_WPCLI": str(wpcli)},
    )
    assert _markers(pr.stdout)["FLOW_CI_PIPELINE"] == ["90"]
    assert _markers(pr.stdout)["FLOW_CI_STATUS"] == ["failure"]
    assert f"2 pipelines share {SHA}" in pr.stderr


@requires_bash
def test_wpcli_list_uses_machine_readable_go_template(tmp_path):
    missing_curl = Path("/nonexistent/curl")
    assert not missing_curl.exists()
    argv_log = tmp_path / "wpcli-argv.log"
    wpcli = _write_fake_wpcli(
        tmp_path,
        [f"7|success|{SHA}|push"],
        [],
        argv_log,
    )
    result = _run(
        tmp_path,
        SHA,
        "--repo",
        "o/r",
        env={"FLOW_CI_CURL": str(missing_curl), "FLOW_CI_WPCLI": str(wpcli)},
    )
    assert result.returncode == 0
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    list_calls = [line for line in calls if line.startswith("ARGV: <pipeline> <ls>")]
    assert list_calls
    assert all("<--output-no-headers>" in line for line in list_calls)
    assert all("go-template=" in line for line in list_calls)
    assert all(line.strip() != "ARGV: <pipeline> <ls>" for line in list_calls)


@requires_bash
def test_wpcli_failure_names_only_failed_steps_from_pipeline_ps(tmp_path):
    missing_curl = Path("/nonexistent/curl")
    assert not missing_curl.exists()
    argv_log = tmp_path / "wpcli-argv.log"
    wpcli = _write_fake_wpcli(
        tmp_path,
        [f"1275|failure|{SHA}|push"],
        [
            "clone|success",
            "test-unit|failure",
            "deploy|error",
            "cleanup|killed",
        ],
        argv_log,
    )
    result = _run(
        tmp_path,
        SHA,
        "--repo",
        "o/r",
        env={"FLOW_CI_CURL": str(missing_curl), "FLOW_CI_WPCLI": str(wpcli)},
    )
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["failure"]
    assert markers["FLOW_CI_FAILED_STEP"] == ["test-unit", "deploy", "cleanup"]
    assert "clone" not in markers["FLOW_CI_FAILED_STEP"]


@requires_bash
def test_wpcli_reports_not_found_when_no_row_carries_the_sha(tmp_path):
    missing_curl = Path("/nonexistent/curl")
    assert not missing_curl.exists()
    argv_log = tmp_path / "wpcli-argv.log"
    wpcli = _write_fake_wpcli(
        tmp_path,
        [f"1|success|{OTHER_SHA}|push"],
        [],
        argv_log,
    )
    result = _run(
        tmp_path,
        SHA,
        "--repo",
        "o/r",
        env={"FLOW_CI_CURL": str(missing_curl), "FLOW_CI_WPCLI": str(wpcli)},
    )
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["not-found"]
    assert markers["FLOW_CI_PIPELINE"] == ["-"]
    assert markers["FLOW_CI_PROVIDER"] == ["woodpecker"]


@requires_bash
def test_wpcli_is_not_consulted_when_api_lane_answers(tmp_path):
    curl_log = tmp_path / "curl-argv.log"
    wpcli_log = tmp_path / "wpcli-argv.log"
    curl = _write_fake_curl(
        tmp_path / "api",
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(4, SHA, "success")]},
        curl_log,
    )
    wpcli = _write_fake_wpcli(
        tmp_path / "cli",
        [f"5|failure|{SHA}|push"],
        [],
        wpcli_log,
    )
    result = _run(
        tmp_path,
        SHA,
        "--repo",
        "o/r",
        env={"FLOW_CI_CURL": str(curl), "FLOW_CI_WPCLI": str(wpcli)},
    )
    assert _markers(result.stdout)["FLOW_CI_PIPELINE"] == ["4"]
    assert not wpcli_log.exists()


@requires_bash
def test_missing_wpcli_falls_through_and_stays_fail_open(tmp_path):
    missing_curl = Path("/nonexistent/curl")
    missing_wpcli = Path("/nonexistent/woodpecker-cli")
    missing_gh = Path("/nonexistent/gh")
    assert not missing_curl.exists()
    assert not missing_wpcli.exists()
    assert not missing_gh.exists()
    result = _run(
        tmp_path,
        SHA,
        "--repo",
        "o/r",
        env={
            "FLOW_CI_CURL": str(missing_curl),
            "FLOW_CI_WPCLI": str(missing_wpcli),
        },
    )
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["unknown"]
    assert markers["FLOW_CI_PROVIDER"] == ["none"]
    assert result.returncode == 0


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
    assert not Path("/nonexistent/curl").exists()
    assert not Path("/nonexistent/woodpecker-cli").exists()
    assert not Path("/nonexistent/gh").exists()
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


# --------------------------------------------------------------------------- #
# jq preflight (issue #789)
# --------------------------------------------------------------------------- #
def _jq_free_path(tmp_path: Path, *extra: str) -> Path:
    """A PATH with everything the script needs EXCEPT jq (precondition asserted)."""
    fake_path = tmp_path / "bin"
    fake_path.mkdir(exist_ok=True)
    for tool in ("bash", "sed", "date", "cat", "printf", "tr", "grep", "sort", "head", *extra):
        real = shutil.which(tool)
        if real and not (fake_path / tool).exists():
            (fake_path / tool).symlink_to(real)
    assert shutil.which("jq", path=str(fake_path)) is None, (
        "precondition: this fixture must construct a PATH without jq (#697)"
    )
    assert shutil.which("bash", path=str(fake_path)) is not None, (
        "precondition: the absence must be jq ALONE - a PATH missing bash proves nothing (#697)"
    )
    return fake_path


@requires_bash
def test_missing_jq_names_itself_instead_of_reporting_a_bare_unknown(tmp_path):
    """Without jq the verdict was `unknown` - identical to "no credentials" (#789).

    Step 8 proceeds on `unknown`, so a missing formatter used to be indistinguishable
    from a CI result. It must now say which it is.
    """
    fake_path = _jq_free_path(tmp_path)
    result = subprocess.run(
        ["bash", str(SCRIPT), SHA, "--repo", "o/r", "--path", str(tmp_path)],
        capture_output=True,
        text=True,
        env={
            "PATH": str(fake_path),
            "FLOW_CI_CURL": "/nonexistent/curl",
            "FLOW_CI_AWS": "/nonexistent/aws",
            "FLOW_CI_WPCLI": "/nonexistent/woodpecker-cli",
            "FLOW_CI_GH": "/nonexistent/gh",
            "FLOW_CI_SLEEP": "/bin/true",
            "WOODPECKER_SERVER": "https://wp.example.invalid",
            "WOODPECKER_API_TOKEN": "test-token-canary",
        },
    )
    assert result.returncode == 0, "fail-open: a missing tool must never block the flow"
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["unknown"], result.stdout
    assert "jq not found" in result.stderr
    assert "MISSING TOOL" in result.stderr, "the reason must be legible, not inferred"
    assert "test-token-canary" not in result.stdout + result.stderr


@requires_bash
def test_the_wpcli_lane_still_answers_without_jq(tmp_path):
    """The jq check is per-lane, not an early exit: woodpecker-cli needs no jq (#768).

    Hoisting the preflight to the top of the script would have disabled the one
    provider lane that still works on a jq-less host.
    """
    fake_path = _jq_free_path(tmp_path)
    argv_log = tmp_path / "wpcli-argv.log"
    wpcli = _write_fake_wpcli(tmp_path, [f"1249|success|{SHA}|push"], [], argv_log)
    result = subprocess.run(
        ["bash", str(SCRIPT), SHA, "--repo", "o/r", "--path", str(tmp_path)],
        capture_output=True,
        text=True,
        env={
            "PATH": str(fake_path),
            "FLOW_CI_CURL": "/nonexistent/curl",
            "FLOW_CI_AWS": "/nonexistent/aws",
            "FLOW_CI_WPCLI": str(wpcli),
            "FLOW_CI_GH": "/nonexistent/gh",
            "FLOW_CI_SLEEP": "/bin/true",
        },
    )
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_STATUS"] == ["success"], result.stdout + result.stderr
    assert markers["FLOW_CI_PIPELINE"] == ["1249"]
    assert markers["FLOW_CI_PROVIDER"] == ["woodpecker"]
