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
import re
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
    # The absence this test rests on, asserted in the function that builds the
    # environment rather than only inside _jq_free_path (#933). The helper's own
    # assert is real, but nothing couples it to THIS call: a future test could
    # take the path without the helper, or the helper without the path, and the
    # fail-open assertions below would still pass on a fixture that never
    # removed jq at all - which is the #695 failure exactly.
    assert shutil.which("jq", path=str(fake_path)) is None, "fixture must lack jq"
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
    assert shutil.which("jq", path=str(fake_path)) is None, "fixture must lack jq"
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


# --------------------------------------------------------------------------- #
# A value-taking flag as the FINAL argument (issue #992)
# --------------------------------------------------------------------------- #
# `shift 2` fails when only one positional remains and shifts NOTHING. `${2:-}`
# made the missing value benign, so nothing errored - and `$#` never decreased,
# so `while [ $# -gt 0 ]` spun forever on the same argument. The script did not
# crash, print, or exit; it burned a core until something killed it.
#
# THE `timeout=` BELOW IS THE ASSERTION. On the unfixed script this test does not
# fail, it never returns - so an assertion about the exit STATUS would be
# unfalsifiable there, and "exit is 2" would hang the suite rather than red it.
# A hanging suite is not a red run, it is no run at all.


@pytest.mark.parametrize("flag", ["--secret-name", "--region"])
@pytest.mark.skipif(shutil.which("bash") is None, reason="shells out to bash")
def test_a_dangling_value_flag_is_a_usage_error_not_a_hang(flag: str) -> None:
    """Both flags HUNG before #992, three lines below three that were guarded.

    `--path`, `--repo` and `--event` all carried `[[ -n "$X" ]] || die_usage`;
    these two did not. The fix is this file's own idiom applied twice, not a new
    mechanism - two spellings of one rule inside a single `case` statement is
    the defect #933 was about, one level down.
    """
    result = subprocess.run(
        ["bash", str(SCRIPT), flag], capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2, f"{flag} with no value -> {result.returncode}"
    assert "needs a value" in result.stderr, result.stderr


#: Flags DERIVED from the script's own `case` arms, not a list written here.
#:
#: The first version of this hardcoded five flag names and its docstring claimed
#: a flag added later without a guard would fail here. It would not: a name not
#: in the list is not exercised, so the test claimed coverage of a population it
#: could never see - the #933 defect, in the test written for #992. Review
#: caught it with an in-memory counterexample: adding an unguarded `--new-value`
#: left all five cases green while the new flag hung.
#:
#: Deriving the members means the universe is the parser itself.
def _value_taking_flags() -> list[str]:
    """Every `--flag)` arm of flow-ci-status.sh that consumes a value."""
    flags = []
    for line in SCRIPT.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        m = re.match(r"^(--[a-z][a-z-]*)\)", stripped)
        if m and "shift 2" in stripped:
            flags.append(m.group(1))
    return sorted(set(flags))


#: `--wait` takes an OPTIONAL value - `--wait` alone means the default - so it is
#: the one arm for which a bare flag is a correct call, not a usage error. Named
#: with its reason rather than silently filtered, so the exclusion is auditable.
_OPTIONAL_VALUE_FLAGS = {"--wait"}


def test_the_flag_derivation_can_actually_see_the_parser() -> None:
    """An empty derived list would make the test below pass over nothing.

    The population is derived, so its extractor needs its own control: a regex
    that silently matches no arms yields an empty parametrisation, zero cases
    run, and the suite reports green for a parser it never examined.
    """
    flags = _value_taking_flags()
    assert len(flags) >= 5, f"derivation found too few arms to be working: {flags}"
    for known in ("--path", "--repo", "--event", "--secret-name", "--region"):
        assert known in flags, f"{known} is a value-taking arm and must be derived: {flags}"


@pytest.mark.parametrize("flag", [f for f in _value_taking_flags() if f not in _OPTIONAL_VALUE_FLAGS])
@pytest.mark.skipif(shutil.which("bash") is None, reason="shells out to bash")
def test_every_value_flag_refuses_a_missing_value_the_same_way(flag: str) -> None:
    """The guard is a property of the PARSER, not of the two flags that were noticed.

    Because the list is derived from the script's own `case` arms, a flag added
    later without a guard is exercised the moment it exists - which is what the
    previous hardcoded version only claimed.
    """
    result = subprocess.run(
        ["bash", str(SCRIPT), flag], capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2, f"{flag} -> {result.returncode}"


# --------------------------------------------------------------------------- #
# Issue #1262. Each test below was run against 47ddc6c (pre-fix) and FAILED
# there; the PR body records every red and green result.
# --------------------------------------------------------------------------- #

def _write_fake_gh(
    tmp_path: Path,
    *,
    repo_view: str = "",
    default_branch: str | None = "main",
    contexts: list[str] | None = None,
    argv_log: Path | None = None,
) -> Path:
    """A stand-in gh: `repo view`, `api repos/o/r`, and the required-contexts
    endpoint. `contexts=None` makes the protection read FAIL (unreadable)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    body = ["#!/usr/bin/env bash"]
    if argv_log is not None:
        body.append(f'echo "PWD=$PWD ARGV: $*" >> "{argv_log}"')
    body += [
        'if [[ "$1" == "repo" && "$2" == "view" ]]; then',
        f'  [[ -n "{repo_view}" ]] && {{ echo "{repo_view}"; exit 0; }}',
        "  exit 1",
        "fi",
        'if [[ "$1" == "api" ]]; then',
        '  case "$2" in',
        "    */protection/required_status_checks)",
    ]
    if contexts is None:
        body.append("      exit 1 ;;")
    else:
        body += ["      cat <<'CTX'", *contexts, "CTX", "      exit 0 ;;"]
    body += ["    repos/*/*/*) exit 1 ;;", "    repos/*)"]
    if default_branch is None:
        body.append("      exit 1 ;;")
    else:
        body.append(f'      echo "{default_branch}"; exit 0 ;;')
    body += ["  esac", "fi", "exit 1", ""]
    path = tmp_path / "gh"
    path.write_text("\n".join(body), encoding="utf-8")
    path.chmod(0o755)
    return path


def _both_lanes_curl(tmp_path: Path) -> Path:
    return _write_fake_curl(
        tmp_path,
        {
            "/api/repos/lookup/": {"id": 17},
            "pipelines?per_page": [
                _pipeline(90, SHA, "failure", "pull_request"),
                _pipeline(91, SHA, "success", "push"),
            ],
        },
        tmp_path / "argv.log",
    )


@requires_bash
def test_the_REQUIRED_lane_decides_the_default_event(tmp_path):
    """#1262 item 1: only ci/woodpecker/pr/* is required here, yet the helper
    reported the push pipeline's green when both shared the SHA."""
    curl = _both_lanes_curl(tmp_path)
    gh = _write_fake_gh(tmp_path / "bin", contexts=["ci/woodpecker/pr/woodpecker"])
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_PIPELINE"] == ["90"], result.stdout + result.stderr
    assert markers["FLOW_CI_STATUS"] == ["failure"]
    assert markers["FLOW_CI_EVENT"][0].startswith("pull_request (branch-protection on main")


@requires_bash
def test_a_repo_requiring_the_PUSH_lane_keeps_push(tmp_path):
    curl = _both_lanes_curl(tmp_path)
    gh = _write_fake_gh(tmp_path / "bin", contexts=["ci/woodpecker/push/woodpecker"])
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_PIPELINE"] == ["91"], result.stdout + result.stderr
    assert markers["FLOW_CI_EVENT"][0].startswith("push (branch-protection")


@requires_bash
@pytest.mark.parametrize(("contexts", "why"), [
    (None, "unreadable"),
    ([], "no woodpecker lane"),
    (["ci/woodpecker/pr/woodpecker", "ci/woodpecker/push/woodpecker"], "both"),
])
def test_an_UNDECIDABLE_protection_falls_back_to_push_and_says_why(tmp_path, contexts, why):
    curl = _both_lanes_curl(tmp_path)
    gh = _write_fake_gh(tmp_path / "bin", contexts=contexts)
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_PIPELINE"] == ["91"], result.stdout + result.stderr
    event = markers["FLOW_CI_EVENT"][0]
    assert event.startswith("push (default:") and why in event, event


@requires_bash
def test_an_explicit_EVENT_flag_still_wins(tmp_path):
    curl = _both_lanes_curl(tmp_path)
    gh = _write_fake_gh(tmp_path / "bin", contexts=["ci/woodpecker/pr/woodpecker"])
    result = _run(tmp_path, SHA, "--repo", "o/r", "--event", "push",
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_PIPELINE"] == ["91"]
    assert markers["FLOW_CI_EVENT"] == ["push (flag)"]


def _git_checkout(path: Path, origin: str) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "c"], check=True,
    )
    return path


@requires_bash
@pytest.mark.skipif(shutil.which("git") is None, reason="needs git to build the checkout")
def test_the_repo_is_resolved_INSIDE_the_declared_path_not_the_caller_cwd(tmp_path):
    """#1262 item 2: `gh repo view` ran in the caller's cwd. From inside a
    DIFFERENT repository it answered with that repository's name."""
    checkout = _git_checkout(tmp_path / "declared", "https://github.com/owner/declared.git")
    log = tmp_path / "gh.log"
    # The fake answers with whatever repo its cwd belongs to, as gh does.
    gh = tmp_path / "bin" / "gh"
    gh.parent.mkdir()
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "PWD=$PWD ARGV: $*" >> "{log}"\n'
        'if [[ "$1 $2" == "repo view" ]]; then\n'
        '  u=$(git remote get-url origin 2>/dev/null) || exit 1\n'
        '  u=${u%.git}; echo "${u#https://github.com/}"; exit 0\n'
        "fi\nexit 1\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    caller = _git_checkout(tmp_path / "caller", "https://github.com/owner/neighbour.git")
    result = subprocess.run(
        ["bash", str(SCRIPT), "--path", str(checkout)],
        capture_output=True, text=True, cwd=str(caller),
        env={**os.environ, "FLOW_CI_GH": str(gh), "FLOW_CI_CURL": "/nonexistent/curl",
             "FLOW_CI_WPCLI": "/nonexistent/wp", "FLOW_CI_AWS": "/nonexistent/aws"},
    )
    assert _markers(result.stdout)["FLOW_CI_REPO"] == ["owner/declared"], (
        result.stdout + result.stderr)


@requires_bash
@pytest.mark.skipif(shutil.which("git") is None, reason="needs git to build the checkout")
@pytest.mark.parametrize("origin", [
    "https://github.com/owner/name.git",
    "git@github.com:owner/name.git",
    "https://github.com/owner/name",
])
def test_the_origin_fallback_strips_DOT_GIT(tmp_path, origin):
    """#1262 item 2: with gh unable to answer, the sed fallback kept `.git`,
    so the Woodpecker lookup asked for `owner/name.git` and found nothing."""
    checkout = _git_checkout(tmp_path / "co", origin)
    result = _run(tmp_path, "--path", str(checkout),
                  env={"FLOW_CI_GH": "/nonexistent/gh", "FLOW_CI_CURL": "/nonexistent/curl"})
    assert _markers(result.stdout)["FLOW_CI_REPO"] == ["owner/name"], (
        result.stdout + result.stderr)


@requires_bash
def test_an_EXPIRED_wait_is_distinguishable_from_a_single_shot_not_found(tmp_path):
    """#1262 item 3: `--wait` that ran out printed exactly what a one-shot
    lookup of an unregistered SHA prints."""
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(1, OTHER_SHA, "success")]},
        tmp_path / "argv.log",
    )
    once = _run(tmp_path, SHA, "--repo", "o/r", "--event", "push",
                env={"FLOW_CI_CURL": str(curl)})
    waited = _run(tmp_path, SHA, "--repo", "o/r", "--event", "push", "--wait", "0",
                  env={"FLOW_CI_CURL": str(curl)})
    expired = _run(tmp_path, SHA, "--repo", "o/r", "--event", "push", "--wait", "1",
                   env={"FLOW_CI_CURL": str(curl), "FLOW_CI_SLEEP": "/usr/bin/sleep"})
    assert _markers(once.stdout)["FLOW_CI_WAIT"] == ["none"]
    assert _markers(waited.stdout)["FLOW_CI_WAIT"] == ["none"]
    exp = _markers(expired.stdout)
    assert exp["FLOW_CI_STATUS"] == ["not-found"]
    assert exp["FLOW_CI_WAIT"] == ["expired (1s)"], expired.stdout + expired.stderr


@requires_bash
def test_a_wait_that_SETTLES_says_so(tmp_path):
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(5, SHA, "success")]},
        tmp_path / "argv.log",
    )
    result = _run(tmp_path, SHA, "--repo", "o/r", "--event", "push", "--wait", "30",
                  env={"FLOW_CI_CURL": str(curl)})
    assert _markers(result.stdout)["FLOW_CI_WAIT"] == ["settled"]


@requires_bash
def test_a_NEIGHBOURING_providers_push_context_does_not_move_the_lane(tmp_path):
    """Counter-model review of #1262: only ci/woodpecker/* classifies the lane."""
    curl = _both_lanes_curl(tmp_path)
    gh = _write_fake_gh(
        tmp_path / "bin", contexts=["ci/woodpecker/pr/woodpecker", "other-ci/push/tests"])
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_PIPELINE"] == ["90"], result.stdout + result.stderr
    assert markers["FLOW_CI_EVENT"][0].startswith("pull_request (branch-protection on main")


@requires_bash
def test_the_event_is_a_PREFERENCE_so_a_pr_only_sha_is_found_even_on_the_push_fallback(tmp_path):
    """#1262 x the queued CI change that stops `push` pipelines on non-main
    branches: a branch SHA will then carry ONLY a pull_request pipeline. Even
    when the lane cannot be derived and the fallback is `push`, the verdict must
    still find it - the event orders candidates, it never filters them out."""
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17},
         "pipelines?per_page": [_pipeline(90, SHA, "failure", "pull_request")]},
        tmp_path / "argv.log",
    )
    gh = _write_fake_gh(tmp_path / "bin", contexts=None)  # unreadable -> push fallback
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_EVENT"][0].startswith("push (default:")
    assert markers["FLOW_CI_PIPELINE"] == ["90"], result.stdout + result.stderr
    assert markers["FLOW_CI_STATUS"] == ["failure"]


@requires_bash
def test_the_CLI_lane_also_treats_the_event_as_a_preference(tmp_path):
    argv_log = tmp_path / "argv.log"
    wpcli = _write_fake_wpcli(tmp_path, [f"90|failure|{SHA}|pull_request"], [], argv_log)
    result = _run(tmp_path, SHA, "--repo", "o/r", "--event", "push",
                  env={"FLOW_CI_WPCLI": str(wpcli), "WOODPECKER_API_TOKEN": ""})
    markers = _markers(result.stdout)
    assert markers["FLOW_CI_PIPELINE"] == ["90"], result.stdout + result.stderr


@requires_bash
def test_STRICT_EVENT_never_lets_the_other_lane_answer(tmp_path):
    """#1300's wait-then-merge recipe: a green PUSH pipeline must not end a wait
    for the required pull_request lane. Without --strict-event the event is a
    preference (pinned above for #1308's PR-only SHAs); with it, a filter."""
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17},
         "pipelines?per_page": [_pipeline(91, SHA, "success", "push")]},
        tmp_path / "argv.log",
    )
    loose = _run(tmp_path, SHA, "--repo", "o/r", "--event", "pull_request",
                 env={"FLOW_CI_CURL": str(curl)})
    strict = _run(tmp_path, SHA, "--repo", "o/r", "--event", "pull_request", "--strict-event",
                  env={"FLOW_CI_CURL": str(curl)})
    assert _markers(loose.stdout)["FLOW_CI_STATUS"] == ["success"]
    m = _markers(strict.stdout)
    assert m["FLOW_CI_STATUS"] == ["not-found"], strict.stdout + strict.stderr
    assert m["FLOW_CI_EVENT"][0].endswith("; strict)")


@requires_bash
def test_STRICT_EVENT_holds_on_the_CLI_lane_too(tmp_path):
    wpcli = _write_fake_wpcli(tmp_path, [f"91|success|{SHA}|push"], [], tmp_path / "argv.log")
    result = _run(tmp_path, SHA, "--repo", "o/r", "--event", "pull_request", "--strict-event",
                  env={"FLOW_CI_WPCLI": str(wpcli), "WOODPECKER_API_TOKEN": ""})
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["not-found"], result.stdout


def _gha_gh(
    tmp_path: Path,
    runs: list[dict],
    jobs: dict[int, list[dict]] | None = None,
    contexts: list[str] | None = None,
) -> Path:
    """A gh answering the GitHub Actions lane: `run list`, `run view <id>
    --json jobs` (from ``jobs``; an id without an entry fails), and - when
    ``contexts`` is given - the branch-protection reads of derive_event."""
    jobs_dir = tmp_path / "bin" / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    for run_id, run_jobs in (jobs or {}).items():
        (jobs_dir / f"{run_id}.json").write_text(json.dumps({"jobs": run_jobs}), encoding="utf-8")
    path = tmp_path / "bin" / "gh"
    body = [
        "#!/usr/bin/env bash",
        'if [[ "$1 $2" == "run list" ]]; then',
        "cat <<'JSON'",
        json.dumps(runs),
        "JSON",
        "exit 0; fi",
        'if [[ "$1 $2" == "run view" ]]; then',
        f'  f="{jobs_dir}/$3.json"; [[ -f "$f" ]] && cat "$f" && exit 0; exit 1',
        "fi",
    ]
    if contexts is not None:
        body += [
            'if [[ "$1" == "api" ]]; then',
            '  case "$2" in',
            "    *required_status_checks)",
            "      cat <<'CTX'", *contexts, "CTX",
            "      exit 0 ;;",
            "    repos/*/*/*) exit 1 ;;",
            '    repos/*) echo main; exit 0 ;;',
            "  esac",
            "fi",
        ]
    body += ["exit 1", ""]
    path.write_text("\n".join(body), encoding="utf-8")
    path.chmod(0o755)
    return path


def _gha_run(run_id: int, conclusion: str | None, event: str = "pull_request",
             workflow: str = "ci", status: str = "completed", started: str = "2026-10-30T10:00:00Z") -> dict:
    return {"status": status, "conclusion": conclusion or "", "databaseId": run_id,
            "url": f"https://github.com/o/r/actions/runs/{run_id}", "event": event,
            "workflowName": workflow, "startedAt": started}


def _gha(tmp_path: Path, *args: str, gh: Path, env: dict | None = None) -> dict[str, list[str]]:
    result = _run(tmp_path, SHA, "--repo", "o/r", *args,
                  env={"FLOW_CI_GH": str(gh), "WOODPECKER_API_TOKEN": "",
                       "FLOW_CI_CURL": "/nonexistent/curl", **(env or {})})
    markers = _markers(result.stdout)
    assert markers.get("FLOW_CI_PROVIDER") == ["github-actions"], result.stdout + result.stderr
    return markers


@requires_bash
def test_STRICT_EVENT_holds_on_the_GITHUB_ACTIONS_lane(tmp_path):
    """Counter-model review pass 2 of #1300: the Actions fallback took `.[0]`
    whatever its event, so a green push workflow ended a strict pr wait."""
    gh = _gha_gh(tmp_path, [{"status": "completed", "conclusion": "success",
                             "databaseId": 7, "url": "u", "event": "push"}])
    env = {"FLOW_CI_GH": str(gh), "WOODPECKER_API_TOKEN": ""}
    strict = _run(tmp_path, SHA, "--repo", "o/r", "--event", "pull_request", "--strict-event", env=env)
    loose = _run(tmp_path, SHA, "--repo", "o/r", "--event", "pull_request", env=env)
    ms = _markers(strict.stdout)
    assert ms["FLOW_CI_PROVIDER"] == ["github-actions"], strict.stdout + strict.stderr
    assert ms["FLOW_CI_STATUS"] == ["not-found"]
    assert _markers(loose.stdout)["FLOW_CI_STATUS"] == ["success"]


@requires_bash
def test_the_GITHUB_ACTIONS_lane_finds_the_required_event_when_present(tmp_path):
    gh = _gha_gh(tmp_path, [
        {"status": "completed", "conclusion": "success", "databaseId": 7, "url": "u", "event": "push"},
        {"status": "completed", "conclusion": "failure", "databaseId": 8, "url": "v", "event": "pull_request"},
    ])
    result = _run(tmp_path, SHA, "--repo", "o/r", "--event", "pull_request", "--strict-event",
                  env={"FLOW_CI_GH": str(gh), "WOODPECKER_API_TOKEN": ""})
    m = _markers(result.stdout)
    assert m["FLOW_CI_PIPELINE"] == ["8"] and m["FLOW_CI_STATUS"] == ["failure"], result.stdout


# ── Pre-code failure marker (issue #1342) ──────────────────────────────────
#
# A red `clone` step - the checkout that runs before any of the change's code -
# used to read exactly like a red test suite. The shape of these fixtures is the
# REAL Woodpecker API response for CPP pipeline 2935
# (`/api/repos/1/pipelines/2935`): every child carries `type`, and the checkout
# is `{"name": "clone", "type": "clone"}`. No live clone failure exists to copy
# - the 56 most recent failed CPP pipelines all failed in `commands` steps - so
# the failing state is set by hand on that real shape.


def _api_failure(tmp_path: Path, children: list[dict]) -> subprocess.CompletedProcess:
    curl = _write_fake_curl(
        tmp_path,
        {
            "/api/repos/lookup/": {"id": 17},
            "pipelines?per_page": [_pipeline(1275, SHA, "failure")],
            "pipelines/1275": {"workflows": [{"name": "woodpecker", "children": children}]},
        },
        tmp_path / "argv.log",
    )
    return _run(tmp_path, SHA, "--repo", "o/r", env={"FLOW_CI_CURL": str(curl)})


@requires_bash
def test_red_case_a_CLONE_failure_is_marked_pre_code(tmp_path):
    result = _api_failure(tmp_path, [
        {"name": "clone", "type": "clone", "state": "failure", "exit_code": 128},
        {"name": "validate", "type": "commands", "state": "skipped"},
    ])
    m = _markers(result.stdout)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_FAILED_STEP"] == ["clone"], "the existing line is unchanged"
    assert m["FLOW_CI_PRECODE_FAILURE"] == ["clone"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["precode"]
    assert result.stdout.splitlines()[-1] == "FLOW_CI_STATUS: failure"
    assert result.returncode == 0, "no exit-code change"


@requires_bash
def test_the_other_verdict_a_COMMANDS_failure_is_code_and_carries_no_marker(tmp_path):
    result = _api_failure(tmp_path, [
        {"name": "clone", "type": "clone", "state": "success", "exit_code": 0},
        {"name": "validate", "type": "commands", "state": "failure", "exit_code": 2},
    ])
    m = _markers(result.stdout)
    assert m["FLOW_CI_FAILED_STEP"] == ["validate"]
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["code"]


@requires_bash
def test_a_clone_and_a_code_failure_together_are_MIXED(tmp_path):
    result = _api_failure(tmp_path, [
        {"name": "clone", "type": "clone", "state": "failure"},
        {"name": "validate", "type": "commands", "state": "failure"},
    ])
    m = _markers(result.stdout)
    assert m["FLOW_CI_PRECODE_FAILURE"] == ["clone"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["mixed"]


@requires_bash
def test_a_step_with_NO_TYPE_is_unknown_never_code(tmp_path):
    """An older server, or a trimmed response: absence of a type is not `commands`."""
    result = _api_failure(tmp_path, [{"name": "validate", "state": "failure"}])
    m = _markers(result.stdout)
    assert m["FLOW_CI_FAILED_STEP"] == ["validate"]
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["unknown"]


@requires_bash
def test_a_failure_with_NO_FAILED_STEP_is_unknown(tmp_path):
    result = _api_failure(tmp_path, [{"name": "clone", "type": "clone", "state": "success"}])
    m = _markers(result.stdout)
    assert "FLOW_CI_FAILED_STEP" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["unknown"]


@requires_bash
def test_a_SUCCESS_carries_neither_new_line(tmp_path):
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17}, "pipelines?per_page": [_pipeline(1275, SHA, "success")]},
        tmp_path / "argv.log",
    )
    m = _markers(_run(tmp_path, SHA, "--repo", "o/r", env={"FLOW_CI_CURL": str(curl)}).stdout)
    assert m["FLOW_CI_STATUS"] == ["success"]
    assert "FLOW_CI_FAILURE_ORIGIN" not in m and "FLOW_CI_PRECODE_FAILURE" not in m


# ── Fetch-failure exit code (issue #1411) ──────────────────────────────────
#
# `jq-stage` (a `commands`-type step) fetching jq over the network and failing
# used to read as a `code` failure under #1342's clone-only logic, sending a
# worker to bisect its own diff for a network blip. `ci-stage-jq.py`,
# `ci-stage-git.py` and `ci-stage-make.py` now all return 75 (EX_TEMPFAIL,
# BSD sysexits.h) specifically for "could not fetch", distinct from the 1 they
# still return for a sha256/scheme mismatch - a real, code-adjacent finding
# that must never be laundered into precode.


@requires_bash
def test_red_case_a_COMMANDS_step_with_exit_75_is_marked_pre_code(tmp_path):
    """RED on the pre-#1411 script: exit 75 from a `commands` step used to be
    indistinguishable from any other code failure - no step-type signal, and
    no exit-code signal was read at all."""
    result = _api_failure(tmp_path, [
        {"name": "clone", "type": "clone", "state": "success", "exit_code": 0},
        {"name": "jq-stage", "type": "commands", "state": "failure", "exit_code": 75},
    ])
    m = _markers(result.stdout)
    assert m["FLOW_CI_FAILED_STEP"] == ["jq-stage"]
    assert m["FLOW_CI_PRECODE_FAILURE"] == ["jq-stage"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["precode"]


@requires_bash
def test_the_must_not_flip_anchor_exit_1_from_a_COMMANDS_step_stays_code(tmp_path):
    """The hash-mismatch exit code (1) must keep reading `code` - a tampered
    or substituted download is exactly what must NOT be laundered into
    precode. This is the control's GOOD case, not a new behaviour."""
    result = _api_failure(tmp_path, [
        {"name": "clone", "type": "clone", "state": "success", "exit_code": 0},
        {"name": "jq-stage", "type": "commands", "state": "failure", "exit_code": 1},
    ])
    m = _markers(result.stdout)
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["code"]


@requires_bash
def test_exit_75_and_a_genuine_code_failure_together_are_MIXED(tmp_path):
    result = _api_failure(tmp_path, [
        {"name": "jq-stage", "type": "commands", "state": "failure", "exit_code": 75},
        {"name": "validate", "type": "commands", "state": "failure", "exit_code": 2},
    ])
    m = _markers(result.stdout)
    assert m["FLOW_CI_PRECODE_FAILURE"] == ["jq-stage"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["mixed"]


@requires_bash
def test_exit_75_from_a_step_that_is_not_a_stager_stays_code(tmp_path):
    """Counter-model review: EX_TEMPFAIL is a general code, so an application
    command exiting 75 after running the change is a CODE failure. Only a
    `*-stage` step's 75 is a fetch failure."""
    result = _api_failure(tmp_path, [
        {"name": "validate", "type": "commands", "state": "failure", "exit_code": 75},
    ])
    m = _markers(result.stdout)
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["code"]


@requires_bash
def test_a_MISSING_exit_code_never_defaults_to_precode(tmp_path):
    """Absence of the field (an older API, or a shape that omits it) must stay
    `code` for a `commands`-type step - never read as evidence either way."""
    result = _api_failure(tmp_path, [{"name": "validate", "type": "commands", "state": "failure"}])
    m = _markers(result.stdout)
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["code"]


@requires_bash
def test_exit_75_from_a_CLONE_step_still_reports_precode_not_double_counted(tmp_path):
    """A clone step cannot carry this convention's exit code in practice, but
    if it somehow did, the two signals must not double-report or conflict -
    one precode step stays one precode step."""
    result = _api_failure(tmp_path, [
        {"name": "clone", "type": "clone", "state": "failure", "exit_code": 75},
    ])
    m = _markers(result.stdout)
    assert m["FLOW_CI_PRECODE_FAILURE"] == ["clone"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["precode"]


def _typed_wpcli(
    tmp_path: Path,
    name_state: list[str],
    name_type: list[str] | None,
    type_exit: int = 0,
    state_exit: int = 0,
    name_error: list[str] | None = None,
    error_exit: int = 0,
) -> Path:
    """A woodpecker-cli whose `ps` answers per FORMAT: the name|state call, and
    the separate name|type call. `name_type=None` makes the type call FAIL, the
    way a CLI whose template cannot render `.step.Type` would; `type_exit`
    makes it print rows AND fail."""
    type_branch = (
        ["cat <<'ROWS'", *name_type, "ROWS", f"exit {type_exit}"]
        if name_type is not None
        else ["exit 1"]
    )
    body = [
        "#!/usr/bin/env bash",
        'case "$2" in',
        "ls)",
        "cat <<'ROWS'",
        f"1275|failure|{SHA}|push",
        "ROWS",
        ";;",
        "ps)",
        'if [[ "$*" == *".step.Type"* ]]; then',
        *type_branch,
        "fi",
        'if [[ "$*" == *".step.Error"* ]]; then',
        *(["cat <<'ROWS'", *name_error, "ROWS", f"exit {error_exit}"]
          if name_error is not None else ["exit 1"]),
        "fi",
        "cat <<'ROWS'",
        *name_state,
        "ROWS",
        f"exit {state_exit}",
        ";;",
        "*) exit 1 ;;",
        "esac",
        "",
    ]
    path = tmp_path / "woodpecker-cli"
    path.write_text("\n".join(body), encoding="utf-8")
    path.chmod(0o755)
    return path


def _cli_run(tmp_path: Path, wpcli: Path) -> dict[str, list[str]]:
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": "/nonexistent/curl", "FLOW_CI_WPCLI": str(wpcli)})
    return _markers(result.stdout)


@requires_bash
def test_the_CLI_lane_marks_a_clone_failure_from_the_TYPE_call(tmp_path):
    wpcli = _typed_wpcli(tmp_path, ["clone|failure", "validate|skipped"],
                         ["clone|clone", "validate|commands"])
    m = _cli_run(tmp_path, wpcli)
    assert m["FLOW_CI_FAILED_STEP"] == ["clone"]
    assert m["FLOW_CI_PRECODE_FAILURE"] == ["clone"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["precode"]


@requires_bash
def test_the_CLI_lane_marks_a_commands_failure_as_code(tmp_path):
    wpcli = _typed_wpcli(tmp_path, ["clone|success", "validate|failure"],
                         ["clone|clone", "validate|commands"])
    m = _cli_run(tmp_path, wpcli)
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["code"]


@requires_bash
def test_a_FAILED_type_call_keeps_the_step_names_and_says_unknown(tmp_path):
    """`.step.Type` is untested against a real CLI; if it cannot render, the
    failed-step NAMES must survive and the origin must be unknown, not code."""
    wpcli = _typed_wpcli(tmp_path, ["clone|failure", "validate|failure"], None)
    m = _cli_run(tmp_path, wpcli)
    assert m["FLOW_CI_FAILED_STEP"] == ["clone", "validate"]
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["unknown"]


@requires_bash
def test_the_GITHUB_ACTIONS_lane_reads_STEPS_so_a_failed_checkout_is_PRECODE(tmp_path):
    """#1604: failures used to be named by JOB, so a red `actions/checkout`
    step - which runs before any of the change's code - read unknown at best.
    The job's steps are now read, and GitHub's own generated step names for
    the checkout and job setup classify pre-code."""
    gh = _gha_gh(tmp_path, [_gha_run(8, "failure", workflow="test")], jobs={8: [
        {"name": "pytest", "conclusion": "failure", "steps": [
            {"name": "Set up job", "conclusion": "success"},
            {"name": "Run actions/checkout@v4", "conclusion": "failure"},
            {"name": "Run tests", "conclusion": "skipped"},
        ]},
    ]})
    m = _gha(tmp_path, "--event", "pull_request", gh=gh)
    assert m["FLOW_CI_FAILED_STEP"] == ["test / pytest / Run actions/checkout@v4"]
    assert m["FLOW_CI_PRECODE_FAILURE"] == ["test / pytest / Run actions/checkout@v4"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["precode"]


@requires_bash
def test_a_RENAMED_checkout_step_reads_code_not_precode(tmp_path):
    """The step list carries no type, so only GitHub's GENERATED names count
    as pre-code; a guessed `*checkout*` pattern would send a red
    `test checkout flow` step to the infrastructure."""
    gh = _gha_gh(tmp_path, [_gha_run(8, "failure")], jobs={8: [
        {"name": "unit", "conclusion": "failure", "steps": [
            {"name": "test checkout flow", "conclusion": "failure"}]},
    ]})
    m = _gha(tmp_path, gh=gh)
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["code"]


@requires_bash
def test_a_job_with_NO_step_evidence_stays_unknown(tmp_path):
    """A job that failed without a failed step (a startup failure) has no
    classification, and its absence must never read as `code`."""
    gh = _gha_gh(tmp_path, [_gha_run(8, "startup_failure")], jobs={8: [
        {"name": "unit", "conclusion": "failure", "steps": []}]})
    m = _gha(tmp_path, gh=gh)
    assert m["FLOW_CI_FAILED_STEP"] == ["ci / unit"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["unknown"]


@requires_bash
def test_UNREADABLE_jobs_keep_the_failure_and_say_unknown(tmp_path):
    gh = _gha_gh(tmp_path, [_gha_run(8, "failure", workflow="test")])  # run view fails
    m = _gha(tmp_path, gh=gh)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_FAILED_STEP"] == ["test"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["unknown"]


# ── GitHub Actions aggregation (issue #1604) ───────────────────────────────
#
# One commit carries one run per workflow. The lane took `.[0]`, so the
# verdict depended on list order and a green lint run could hide a red test
# run. Each test below FAILS on the pre-#1604 script (measured: the anchor at
# controls/flow-ci-status-gha/anchors/pre-1604-flow-ci-status.sh).


@requires_bash
@pytest.mark.parametrize("order", ["green-first", "red-first"])
def test_ANY_red_run_is_failure_in_EITHER_order(tmp_path, order):
    """The issue's red case: [success, failure] and [failure, success] both
    give failure, and the verdict names the red run."""
    runs = [_gha_run(1, "success", workflow="lint"), _gha_run(2, "failure", workflow="test")]
    if order == "red-first":
        runs.reverse()
    gh = _gha_gh(tmp_path, runs, jobs={2: [
        {"name": "pytest", "conclusion": "failure", "steps": [{"name": "Run tests", "conclusion": "failure"}]}]})
    m = _gha(tmp_path, "--event", "pull_request", gh=gh)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_PIPELINE"] == ["2"]
    assert m["FLOW_CI_FAILED_STEP"] == ["test / pytest / Run tests"]
    assert m["FLOW_CI_RUNS"][0].startswith("2 (")


@requires_bash
@pytest.mark.parametrize("order", ["green-first", "cancel-first"])
def test_a_CANCELLED_run_is_failure_with_the_CANCELED_origin(tmp_path, order):
    runs = [_gha_run(1, "success"), _gha_run(2, "cancelled", workflow="test")]
    if order == "cancel-first":
        runs.reverse()
    gh = _gha_gh(tmp_path, runs, jobs={2: [
        {"name": "pytest", "conclusion": "cancelled", "steps": [{"name": "Run tests", "conclusion": "cancelled"}]}]})
    m = _gha(tmp_path, gh=gh)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["canceled"]


@requires_bash
def test_a_run_cancelled_before_ANY_job_is_still_canceled(tmp_path):
    gh = _gha_gh(tmp_path, [_gha_run(2, "cancelled", workflow="test")], jobs={2: []})
    m = _gha(tmp_path, gh=gh)
    assert m["FLOW_CI_FAILED_STEP"] == ["test"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["canceled"]


@requires_bash
@pytest.mark.parametrize("conclusion", ["failure", "timed_out", "startup_failure", "action_required", "stale"])
def test_every_other_completed_conclusion_is_RED(tmp_path, conclusion):
    """An unrecognised conclusion is red, not green: GitHub adding a value
    must never turn into a merge."""
    gh = _gha_gh(tmp_path, [_gha_run(1, "success"), _gha_run(2, conclusion)])
    assert _gha(tmp_path, gh=gh)["FLOW_CI_STATUS"] == ["failure"]


@requires_bash
@pytest.mark.parametrize("conclusion", ["skipped", "neutral"])
def test_SKIPPED_and_NEUTRAL_pass_beside_a_success(tmp_path, conclusion):
    """GitHub branch protection treats both as passing; a path-filtered
    workflow that skips by design must not block a merge."""
    gh = _gha_gh(tmp_path, [_gha_run(1, conclusion), _gha_run(2, "success")])
    m = _gha(tmp_path, gh=gh)
    assert m["FLOW_CI_STATUS"] == ["success"]
    assert m["FLOW_CI_PIPELINE"] == ["2"]


@requires_bash
def test_a_commit_whose_runs_ALL_skipped_is_UNKNOWN_not_success(tmp_path):
    """Nothing ran, so a green would rest on an empty population."""
    gh = _gha_gh(tmp_path, [_gha_run(1, "skipped"), _gha_run(2, "neutral")])
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_GH": str(gh), "WOODPECKER_API_TOKEN": "", "FLOW_CI_CURL": "/nonexistent/curl"})
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["unknown"], result.stdout
    assert "nothing ran" in result.stderr


@requires_bash
def test_an_UNFINISHED_run_beside_a_green_one_is_RUNNING(tmp_path):
    gh = _gha_gh(tmp_path, [_gha_run(1, "success"),
                            _gha_run(2, None, status="in_progress", started="2099-01-01T00:00:00Z")])
    m = _gha(tmp_path, gh=gh)
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_PIPELINE"] == ["2"]
    assert m["FLOW_CI_STALL_CHECK"] == ["checked"]


@requires_bash
def test_a_RED_run_ends_the_wait_even_while_another_still_runs(tmp_path):
    gh = _gha_gh(tmp_path, [_gha_run(1, None, status="in_progress", started="2099-01-01T00:00:00Z"),
                            _gha_run(2, "failure")])
    m = _gha(tmp_path, "--wait", "30", gh=gh)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_WAIT"] == ["settled"]


@requires_bash
def test_a_NON_WOODPECKER_required_set_means_ANY_event_under_strict(tmp_path):
    """The issue's red case: required `test,lint` with only pull_request runs
    gave not-found under --strict-event (event fell back to `push`), so
    /flow:merge waited out its full 1800s on every PR."""
    gh = _gha_gh(tmp_path, [_gha_run(1, "success", workflow="test"), _gha_run(2, "success", workflow="lint")],
                 contexts=["test", "lint"])
    m = _gha(tmp_path, "--strict-event", gh=gh)
    assert m["FLOW_CI_STATUS"] == ["success"]
    assert m["FLOW_CI_EVENT"][0].startswith("any (branch-protection on main: test,lint")


@requires_bash
def test_ANY_event_counts_a_red_push_run_too(tmp_path):
    """With no lane named, a red on either event is red - the conservative
    direction. The green is on `push` and the red on `pull_request`, so the
    pre-#1604 `push` fallback - which reads only the green - fails this."""
    gh = _gha_gh(tmp_path, [_gha_run(1, "success", event="push"), _gha_run(2, "failure")],
                 contexts=["test"])
    assert _gha(tmp_path, "--strict-event", gh=gh)["FLOW_CI_STATUS"] == ["failure"]


@requires_bash
def test_a_STRICT_pull_request_lane_ignores_a_red_push_run(tmp_path):
    """The filter still holds when a lane IS named."""
    gh = _gha_gh(tmp_path, [_gha_run(1, "success"), _gha_run(2, "failure", event="push")])
    m = _gha(tmp_path, "--event", "pull_request", "--strict-event", gh=gh)
    assert m["FLOW_CI_STATUS"] == ["success"]
    assert m["FLOW_CI_PIPELINE"] == ["1"]


@requires_bash
def test_ANY_event_on_the_WOODPECKER_lane_takes_either_event_under_strict(tmp_path):
    curl = _write_fake_curl(
        tmp_path,
        {"/api/repos/lookup/": {"id": 17},
         "pipelines?per_page": [_pipeline(90, SHA, "failure", "pull_request")]},
        tmp_path / "argv.log",
    )
    result = _run(tmp_path, SHA, "--repo", "o/r", "--event", "any", "--strict-event",
                  env={"FLOW_CI_CURL": str(curl)})
    m = _markers(result.stdout)
    assert m["FLOW_CI_PIPELINE"] == ["90"], result.stdout + result.stderr
    assert m["FLOW_CI_STATUS"] == ["failure"]


@requires_bash
def test_ANY_event_on_the_CLI_lane_lists_each_pipeline_once(tmp_path):
    wpcli = _write_fake_wpcli(tmp_path, [f"90|failure|{SHA}|pull_request", f"91|success|{SHA}|push"],
                              [], tmp_path / "argv.log")
    result = _run(tmp_path, SHA, "--repo", "o/r", "--event", "any", "--strict-event",
                  env={"FLOW_CI_WPCLI": str(wpcli), "WOODPECKER_API_TOKEN": ""})
    assert _markers(result.stdout)["FLOW_CI_PIPELINE"] == ["90"], result.stdout
    assert result.stderr.count("#90 ") == 1, result.stderr


# ── GitHub Actions stall check (issue #1604, #1552 parity) ─────────────────

NOW_2026 = "1793354400"  # 2026-10-30T10:00:00Z


@requires_bash
def test_an_in_progress_job_PAST_the_timeout_is_STALLED(tmp_path):
    started = "2026-10-29T00:00:00Z"  # 34h before NOW_2026
    gh = _gha_gh(tmp_path, [_gha_run(5, None, status="in_progress", started=started, workflow="test")],
                 jobs={5: [{"name": "pytest", "status": "in_progress", "conclusion": "", "startedAt": started}]})
    m = _gha(tmp_path, gh=gh, env={"FLOW_CI_NOW": NOW_2026})
    assert m["FLOW_CI_STATUS"] == ["stalled"]
    assert m["FLOW_CI_STALLED_STEP"] == ["test / pytest"]
    assert m["FLOW_CI_STALLED"][0].startswith("past-timeout (2040m > 360m + 10m grace)")


@requires_bash
def test_a_SLOW_job_inside_a_raised_timeout_is_still_RUNNING(tmp_path):
    started = "2026-10-30T02:00:00Z"  # 8h before NOW_2026, past 360m
    gh = _gha_gh(tmp_path, [_gha_run(5, None, status="in_progress", started=started)],
                 jobs={5: [{"name": "soak", "status": "in_progress", "conclusion": "", "startedAt": started}]})
    stalled = _gha(tmp_path, gh=gh, env={"FLOW_CI_NOW": NOW_2026})
    raised = _gha(tmp_path, gh=gh, env={"FLOW_CI_NOW": NOW_2026, "FLOW_CI_GHA_TIMEOUT_MIN": "720"})
    assert stalled["FLOW_CI_STATUS"] == ["stalled"]
    assert raised["FLOW_CI_STATUS"] == ["running"]
    assert raised["FLOW_CI_STALL_CHECK"] == ["checked"]


@requires_bash
def test_UNREADABLE_jobs_on_an_old_run_are_UNAVAILABLE_not_checked(tmp_path):
    gh = _gha_gh(tmp_path, [_gha_run(5, None, status="in_progress", started="2026-10-29T00:00:00Z")])
    m = _gha(tmp_path, gh=gh, env={"FLOW_CI_NOW": NOW_2026})
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_STALL_CHECK"][0].startswith("unavailable (")


@requires_bash
def test_a_type_call_that_PRINTS_then_FAILS_is_discarded(tmp_path):
    """Counter-model review: a partial answer is not a classification."""
    wpcli = _typed_wpcli(tmp_path, ["clone|failure"], ["clone|clone"], type_exit=1)
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": "/nonexistent/curl", "FLOW_CI_WPCLI": str(wpcli)})
    m = _markers(result.stdout)
    assert m["FLOW_CI_FAILED_STEP"] == ["clone"]
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["unknown"]
    assert result.returncode == 0
    assert result.stdout.splitlines()[-1] == "FLOW_CI_STATUS: failure"


@requires_bash
def test_a_step_NAME_carrying_two_TYPES_does_not_borrow_a_neighbours(tmp_path):
    """Counter-model review: `checkout` in two workflows, one a clone and one a
    commands step. The name join cannot say which failed - unknown, not precode."""
    wpcli = _typed_wpcli(tmp_path, ["checkout|success", "checkout|failure"],
                         ["checkout|clone", "checkout|commands"])
    m = _cli_run(tmp_path, wpcli)
    assert m["FLOW_CI_FAILED_STEP"] == ["checkout"]
    assert "FLOW_CI_PRECODE_FAILURE" not in m
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["unknown"]


@requires_bash
def test_a_name_state_call_that_PRINTS_then_FAILS_keeps_names_and_says_unknown(tmp_path):
    """Counter-model review pass 2: the enumeration stopped after `clone`, so a
    later `validate` failure may be missing and `precode` would be a claim about
    a list nobody saw whole."""
    wpcli = _typed_wpcli(tmp_path, ["clone|failure"], ["clone|clone", "validate|commands"],
                         state_exit=1)
    m = _cli_run(tmp_path, wpcli)
    assert m["FLOW_CI_FAILED_STEP"] == ["clone"], "the names that arrived are kept"
    assert m["FLOW_CI_PRECODE_FAILURE"] == ["clone"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == ["unknown"]


@requires_bash
@pytest.mark.parametrize("error,expected", [
    ("Canceled", "canceled"), (None, "code"), ("", "code"),
    ("canceled", "code"), ("Canceled by user", "code"),
])
def test_api_cancellation_requires_exact_provider_marker(tmp_path, error, expected):
    step = {"name": "validate", "type": "commands", "state": "failure", "exit_code": 126}
    if error is not None:
        step["error"] = error
    result = _api_failure(tmp_path, [step])
    m = _markers(result.stdout)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == [expected]
    assert "FLOW_CI_PRECODE_FAILURE" not in m


@requires_bash
@pytest.mark.parametrize("sibling,expected", [
    ({"type": "commands"}, "mixed"), ({"type": "clone"}, "mixed"),
    ({"error": "Canceled"}, "canceled"), ({}, "unknown"),
])
def test_api_cancellation_aggregate(tmp_path, sibling, expected):
    steps = [
        {"name": "validate", "type": "commands", "state": "failure",
         "exit_code": 126, "error": "Canceled"},
        {"name": "other", "state": "failure", **sibling},
    ]
    assert _markers(_api_failure(tmp_path, steps).stdout)["FLOW_CI_FAILURE_ORIGIN"] == [expected]


@requires_bash
@pytest.mark.parametrize("errors,error_exit,expected", [
    (["validate|Canceled"], 0, "canceled"),
    (["validate|Canceled", "validate|Canceled"], 0, "canceled"),
    (["other|Canceled"], 0, "code"),
    (["validate|Canceled", "validate|"], 0, "code"),
    (["validate|", "validate|Canceled"], 0, "code"),
    (["validate|Canceled"], 1, "code"),
    (None, 0, "code"),
])
def test_cli_cancellation_is_separate_and_joined_without_borrowing(
    tmp_path, errors, error_exit, expected,
):
    wpcli = _typed_wpcli(tmp_path, ["validate|failure"], ["validate|commands"],
                         name_error=errors, error_exit=error_exit)
    m = _cli_run(tmp_path, wpcli)
    assert m["FLOW_CI_FAILED_STEP"] == ["validate"]
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_FAILURE_ORIGIN"] == [expected]


# ── Stalled pipelines (issue #1552) ─────────────────────────────────────────
# Shape measured on CPP pipelines 3372/3374 (Woodpecker 3.19.0, 2026-10-25): an
# agent restart strands the workflow; the server keeps it `running` forever,
# past the repo timeout the AGENT enforces. These tests fix "now" so the
# elapsed time is exact.

STARTED = 1_792_971_725
TIMEOUT_MIN = 60


def _stall_routes(status: str, *, timeout=TIMEOUT_MIN, workflow_state="running",
                  children=None, started=STARTED) -> dict:
    if children is None:
        children = [
            {"name": "shellcheck", "state": "success"},
            {"name": "validate", "state": "running"},
            {"name": "negative-controls", "state": "running"},
            {"name": "mutation-probe", "state": "pending"},
        ]
    repo = {"id": 1}
    if timeout is not None:
        repo["timeout"] = timeout
    return {
        "/api/repos/lookup/": repo,
        "pipelines?per_page": [_pipeline(3374, SHA, status)],
        "pipelines/3374": {
            "number": 3374,
            "status": status,
            "started": started,
            "workflows": [{"name": "woodpecker", "state": workflow_state,
                           "started": started, "children": children}],
        },
    }


def _stall_run(tmp_path: Path, routes: dict, now: int, *args: str):
    curl = _write_fake_curl(tmp_path, routes, tmp_path / "argv.log")
    return _run(tmp_path, SHA, "--repo", "o/r", *args,
                env={"FLOW_CI_CURL": str(curl), "FLOW_CI_NOW": str(now)})


@requires_bash
def test_running_past_repo_timeout_is_stalled_and_names_live_steps(tmp_path):
    """71 min into a 60-min-timeout repo: dead, not slow - and terminal, so a
    --wait ends at once instead of waiting out its whole window."""
    now = STARTED + 71 * 60
    result = _stall_run(tmp_path, _stall_routes("running"), now, "--wait", "1800")
    m = _markers(result.stdout)
    assert m["FLOW_CI_STATUS"] == ["stalled"], result.stdout + result.stderr
    assert m["FLOW_CI_STALL_CHECK"] == ["checked"]
    assert m["FLOW_CI_STALLED"] == ["past-timeout (71m > 60m + 10m grace)"]
    assert m["FLOW_CI_STALLED_STEP"] == ["validate", "negative-controls"]
    assert m["FLOW_CI_WAIT"] == ["settled"]
    assert result.returncode == 0


@requires_bash
@pytest.mark.parametrize("minutes", [5, 59, 70])
def test_long_running_inside_timeout_plus_grace_stays_running(tmp_path, minutes):
    """The healthy long job #1552's acceptance names: NOT reported stalled.
    70 min is exactly timeout + grace, still inside the bound."""
    now = STARTED + minutes * 60
    m = _markers(_stall_run(tmp_path, _stall_routes("running"), now).stdout)
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_STALL_CHECK"] == ["checked"]
    assert "FLOW_CI_STALLED" not in m
    assert "FLOW_CI_STALLED_STEP" not in m


@requires_bash
def test_grace_is_configurable(tmp_path):
    now = STARTED + 71 * 60
    curl = _write_fake_curl(tmp_path, _stall_routes("running"), tmp_path / "argv.log")
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_NOW": str(now),
                       "FLOW_CI_STALL_GRACE_MIN": "30"})
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["running"]


@requires_bash
@pytest.mark.parametrize("routes_kwargs,reason", [
    ({"timeout": None}, "unavailable (repo timeout unreadable)"),
    ({"timeout": 0}, "unavailable (repo timeout unreadable)"),
    ({"started": 0}, "unavailable (workflow start time unreadable)"),
])
def test_unreadable_inputs_leave_running_unchecked_not_cleared(tmp_path, routes_kwargs, reason):
    """Silence must not read as 'checked and not stalled'."""
    now = STARTED + 500 * 60
    m = _markers(_stall_run(tmp_path, _stall_routes("running", **routes_kwargs), now).stdout)
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_STALL_CHECK"] == [reason]
    assert "FLOW_CI_STALLED" not in m


@requires_bash
def test_unreadable_detail_is_unavailable(tmp_path):
    routes = _stall_routes("running")
    del routes["pipelines/3374"]  # the fake curl then answers '{}'
    m = _markers(_stall_run(tmp_path, routes, STARTED + 500 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_STALL_CHECK"] == ["unavailable (pipeline detail unreadable)"]


@requires_bash
def test_killed_pipeline_with_live_children_keeps_failure_and_flags_it(tmp_path):
    """The 3374 shape after an API cancel: pipeline killed, workflow and two
    steps still running. The verdict stays `failure`; the stalled lines say the
    cancel did not land."""
    m = _markers(_stall_run(tmp_path, _stall_routes("killed"), STARTED + 30 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_STALL_CHECK"] == ["checked"]
    assert m["FLOW_CI_STALLED"] == ["terminal-pipeline-live-children"]
    assert m["FLOW_CI_STALLED_STEP"] == ["validate", "negative-controls"]


@requires_bash
def test_killed_pipeline_fully_terminal_has_no_stalled_line(tmp_path):
    children = [{"name": "validate", "state": "killed"},
                {"name": "negative-controls", "state": "killed"}]
    routes = _stall_routes("killed", workflow_state="killed", children=children)
    m = _markers(_stall_run(tmp_path, routes, STARTED + 30 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_STALL_CHECK"] == ["checked"]
    assert "FLOW_CI_STALLED" not in m


@requires_bash
def test_success_runs_no_stall_check(tmp_path):
    routes = _stall_routes("success", workflow_state="success",
                           children=[{"name": "validate", "state": "success"}])
    m = _markers(_stall_run(tmp_path, routes, STARTED + 500 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["success"]
    assert "FLOW_CI_STALL_CHECK" not in m
    assert "FLOW_CI_STALLED" not in m


@requires_bash
def test_timeout_is_measured_per_workflow_not_from_pipeline_start(tmp_path):
    """Counter-model finding: a healthy second workflow that started after a
    50-minute first one is 21 minutes old at pipeline minute 71 - not stalled."""
    routes = _stall_routes("running")
    routes["pipelines/3374"]["workflows"] = [
        {"name": "build", "state": "success", "started": STARTED,
         "children": [{"name": "compile", "state": "success"}]},
        {"name": "deploy", "state": "running", "started": STARTED + 50 * 60,
         "children": [{"name": "rollout", "state": "running"}]},
    ]
    m = _markers(_stall_run(tmp_path, routes, STARTED + 71 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_STALL_CHECK"] == ["checked"]
    assert "FLOW_CI_STALLED" not in m
    # ...and the same second workflow past ITS bound is stalled.
    m = _markers(_stall_run(tmp_path, routes, STARTED + (50 + 71) * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["stalled"]
    assert m["FLOW_CI_STALLED_STEP"] == ["rollout"]


@requires_bash
def test_detail_status_overrides_a_stale_running_list_entry(tmp_path):
    """Counter-model finding: the pipeline finished between the list read and
    the detail read; judge the detail, never the stale list `running`."""
    routes = _stall_routes("running", workflow_state="success",
                           children=[{"name": "validate", "state": "success"}])
    routes["pipelines/3374"]["status"] = "success"
    m = _markers(_stall_run(tmp_path, routes, STARTED + 71 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["success"]
    assert "FLOW_CI_STALLED" not in m


@requires_bash
def test_malformed_children_population_is_unavailable_not_checked(tmp_path):
    """Counter-model finding: a jq failure on the child population must not
    read as 'checked, no live children'."""
    routes = _stall_routes("killed", workflow_state="killed")
    routes["pipelines/3374"]["workflows"][0]["children"] = {}
    m = _markers(_stall_run(tmp_path, routes, STARTED + 30 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["failure"]
    assert m["FLOW_CI_STALL_CHECK"] == ["unavailable (pipeline detail unreadable)"]
    assert "FLOW_CI_STALLED" not in m


@requires_bash
@pytest.mark.parametrize("bad_start", ["unknown", 1792971725.5, None])
def test_non_integer_workflow_start_is_unavailable_not_a_crash(tmp_path, bad_start):
    """Counter-model finding (pass 2): a string or fractional start reached bash
    arithmetic and aborted before any verdict was emitted."""
    routes = _stall_routes("running")
    routes["pipelines/3374"]["workflows"][0]["started"] = bad_start
    result = _stall_run(tmp_path, routes, STARTED + 500 * 60)
    m = _markers(result.stdout)
    assert m["FLOW_CI_STATUS"] == ["running"], result.stdout + result.stderr
    assert m["FLOW_CI_STALL_CHECK"] == ["unavailable (workflow start time unreadable)"]


@requires_bash
def test_workflow_without_state_is_unavailable_not_checked(tmp_path):
    """Counter-model finding (pass 2): a stateless workflow left the timing
    population empty while the line still claimed `checked`."""
    routes = _stall_routes("running")
    del routes["pipelines/3374"]["workflows"][0]["state"]
    m = _markers(_stall_run(tmp_path, routes, STARTED + 500 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_STALL_CHECK"] == ["unavailable (pipeline detail unreadable)"]


@requires_bash
def test_running_pipeline_with_no_running_workflow_is_unavailable(tmp_path):
    routes = _stall_routes("running", workflow_state="pending",
                           children=[{"name": "validate", "state": "pending"}])
    m = _markers(_stall_run(tmp_path, routes, STARTED + 500 * 60).stdout)
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_STALL_CHECK"] == ["unavailable (no running workflow to time)"]


# ── Counter-model review of #1604 ──────────────────────────────────────────


@requires_bash
@pytest.mark.parametrize("order", ["stalled-first", "stalled-second"])
def test_a_STALLED_verdict_names_the_STALLED_run_in_either_order(tmp_path, order):
    """The verdict used to keep the first-listed run's id and URL, so a healthy
    recent run was named while its old sibling was the dead one."""
    old, recent = "2026-10-29T00:00:00Z", "2026-10-30T09:55:00Z"
    runs = [_gha_run(1, None, status="in_progress", started=recent, workflow="fresh"),
            _gha_run(2, None, status="in_progress", started=old, workflow="old")]
    if order == "stalled-first":
        runs.reverse()
    gh = _gha_gh(tmp_path, runs, jobs={
        1: [{"name": "lint", "status": "in_progress", "startedAt": recent}],
        2: [{"name": "tests", "status": "in_progress", "startedAt": old}],
    })
    m = _gha(tmp_path, gh=gh, env={"FLOW_CI_NOW": NOW_2026})
    assert m["FLOW_CI_STATUS"] == ["stalled"]
    assert m["FLOW_CI_PIPELINE"] == ["2"]
    assert m["FLOW_CI_URL"] == ["https://github.com/o/r/actions/runs/2"]
    assert m["FLOW_CI_STALLED_STEP"] == ["old / tests"]


@requires_bash
@pytest.mark.parametrize("jobs", [
    [],                                                        # nothing to time
    [{"name": "build", "status": "queued"}],                   # waiting, not running
    [{"name": "build", "startedAt": "2026-10-29T00:00:00Z"}],  # no status at all
], ids=["empty", "queued-only", "statusless"])
def test_an_old_run_with_NO_timeable_job_is_UNAVAILABLE_not_checked(tmp_path, jobs):
    """`checked` claims the run is inside its timeout; with no running job to
    time, that claim rests on nothing."""
    gh = _gha_gh(tmp_path, [_gha_run(5, None, status="in_progress", started="2026-10-29T00:00:00Z")],
                 jobs={5: jobs})
    m = _gha(tmp_path, gh=gh, env={"FLOW_CI_NOW": NOW_2026})
    assert m["FLOW_CI_STATUS"] == ["running"]
    assert m["FLOW_CI_STALL_CHECK"][0].startswith("unavailable ("), m["FLOW_CI_STALL_CHECK"]


@requires_bash
def test_a_listing_AT_THE_CAP_cannot_report_success(tmp_path):
    """100 greens may be all of the commit's runs or the first 100 of more; a
    red beyond the cap would be invisible, so the green is not complete."""
    gh = _gha_gh(tmp_path, [_gha_run(i, "success", workflow=f"w{i}") for i in range(1, 101)])
    result = _run(tmp_path, SHA, "--repo", "o/r",
                  env={"FLOW_CI_GH": str(gh), "WOODPECKER_API_TOKEN": "", "FLOW_CI_CURL": "/nonexistent/curl"})
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["unknown"], result.stdout
    assert "hit its cap" in result.stderr


@requires_bash
def test_a_RED_inside_a_capped_listing_is_still_failure(tmp_path):
    runs = [_gha_run(i, "success") for i in range(1, 100)] + [_gha_run(100, "failure")]
    gh = _gha_gh(tmp_path, runs)
    assert _gha(tmp_path, gh=gh)["FLOW_CI_STATUS"] == ["failure"]
