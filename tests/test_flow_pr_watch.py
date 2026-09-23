"""Tests for scripts/flow-pr-watch.sh - classified PR pipeline watch (#788).

Contract under test:

- A cleared PR's next pipeline is watched to a terminal state, and the red it may
  produce is CLASSIFIED, because the three classes want opposite responses:
  ``cancelled`` (a superseding push killed it - re-pushing only lengthens the
  queue), ``flake`` (already declared flaky - blaming the PR stalls a clean
  merge), ``red`` (a real failure - retrying hides a defect).
- Cancellation is CONJUNCTIVE: supersession alone never excuses a failure. A run
  that was superseded but whose log carries a real pytest summary is still
  classified on its failures. That is the expensive direction of the error and
  it has its own regression test.
- The pipeline is resolved through the check rollup's ``targetUrl``, never
  through a branch grep over ``pipeline ls`` - for a ``pull_request`` event
  Woodpecker records the TARGET branch, not the head. The CLI lane anchors on the
  exact head SHA, never on list position (the #766/#516 lesson).
- Exit codes carry no new value for a new verdict (the #674 rule): 0 for green,
  cancelled, flake and unknown; 1 for red; 5 for timeout; 2 for a usage error.
- The helper never decides what a flake IS. It only reports whether every failed
  id is inside the baseline file the wave declared.

No test touches the network or a real CI provider: ``gh``, ``woodpecker-cli`` and
``sleep`` are replaced through the FLOW_PR_WATCH_* hooks. The suite shells out to
``bash``, ``awk``, ``sort`` and ``grep`` through those fakes, so the module-level
guard names every one of them - the Woodpecker ``validate`` container ships a
slim image and an unguarded test raises ``FileNotFoundError`` rather than
skipping politely (#602, and the blind spot #789 records).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-pr-watch.sh"

HEAD = "aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00"
NEW_HEAD = "ff00ee11dd22cc33bb44aa55ff66ee77dd88cc99"
PR_CONTEXT = "ci/woodpecker/pr/woodpecker"
PUSH_CONTEXT = "ci/woodpecker/push/woodpecker"

requires_bash = pytest.mark.skipif(
    any(
        shutil.which(binary) is None
        for binary in ("bash", "awk", "sort", "grep", "sed")
    ),
    reason="requires bash, awk, sort, grep and sed on PATH (absent in the CI validate container)",
)


def _write_fake_gh(
    tmp_path: Path,
    *,
    heads: list[str],
    rollup: list[str] | None = None,
    rollups: list[list[str]] | None = None,
    repo: str = "o/r",
) -> Path:
    """A stand-in ``gh``.

    ``heads`` is consumed one entry per ``headRefOid`` call (the last entry
    repeats), which is how a mid-watch force-push is simulated. ``rollup`` is the
    already-``--jq``-filtered ``context|url|state`` output, because the real
    invocation always passes its own filter. For backward compatibility, a
    ``url|state`` row is assigned to the default PR context. ``rollups`` gives
    one such block PER POLL (the last repeating), which is how a re-run appearing
    mid-watch is simulated.
    """
    if rollups is None:
        rollups = [rollup or []]
    counter = tmp_path / "gh-head-calls"
    rollup_counter = tmp_path / "gh-rollup-calls"
    heads_file = tmp_path / "gh-heads"
    heads_file.write_text("\n".join(heads) + "\n", encoding="utf-8")
    # One file per poll; a record separator would be ambiguous with empty blocks.
    rollup_dir = tmp_path / "gh-rollups"
    rollup_dir.mkdir(exist_ok=True)
    for index, block in enumerate(rollups, start=1):
        normalized = []
        for row in block:
            separators = row.count("|")
            if separators == 1:
                normalized.append(f"{PR_CONTEXT}|{row}")
            elif separators == 2:
                normalized.append(row)
            else:
                raise ValueError(f"rollup row must have 2 or 3 fields: {row!r}")
        (rollup_dir / str(index)).write_text(
            "\n".join(normalized) + ("\n" if normalized else ""), encoding="utf-8"
        )
    body = f"""#!/usr/bin/env bash
for arg in "$@"; do
  case "$arg" in
    nameWithOwner) echo "{repo}"; exit 0 ;;
    headRefOid)
      n=0
      [ -f "{counter}" ] && n=$(cat "{counter}")
      n=$((n + 1))
      echo "$n" > "{counter}"
      total=$(grep -c . "{heads_file}")
      [ "$n" -gt "$total" ] && n="$total"
      sed -n "${{n}}p" "{heads_file}"
      exit 0
      ;;
    statusCheckRollup)
      n=0
      [ -f "{rollup_counter}" ] && n=$(cat "{rollup_counter}")
      n=$((n + 1))
      echo "$n" > "{rollup_counter}"
      [ "$n" -gt "{len(rollups)}" ] && n="{len(rollups)}"
      with_context=0
      for filter_arg in "$@"; do
        case "$filter_arg" in
          *'.context // .name'*) with_context=1 ;;
        esac
      done
      if [ "$with_context" -eq 1 ]; then
        cat "{rollup_dir}/$n"
      else
        while IFS='|' read -r context url state; do
          printf '%s|%s\n' "$url" "$state"
        done < "{rollup_dir}/$n"
      fi
      exit 0
      ;;
  esac
done
exit 1
"""
    path = tmp_path / "gh"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _write_fake_wpcli(
    tmp_path: Path,
    *,
    ls_rows: list[str] | None = None,
    ls_blocks: list[list[str]] | None = None,
    ps_rows: list[str] | None = None,
    log: str = "",
) -> Path:
    """A stand-in ``woodpecker-cli`` for the ``ls`` / ``ps`` / ``log show`` verbs.

    ``ls_blocks`` gives one ``pipeline ls`` result PER POLL (the last repeating),
    so a re-run that only becomes visible on a later poll can be simulated; the
    helper calls ``ls`` more than once per poll, so blocks advance on a coarse
    counter and a block must describe a whole poll's worth of truth. A three-field
    row is assigned to the default ``pull_request`` event; an explicit four-field
    row passes through unchanged.
    """
    if ls_blocks is None:
        ls_blocks = [ls_rows or []]
    ls_dir = tmp_path / "wp-ls-blocks"
    ls_dir.mkdir(exist_ok=True)
    for index, block in enumerate(ls_blocks, start=1):
        normalized = []
        for row in block:
            separators = row.count("|")
            if separators == 2:
                normalized.append(f"{row}|pull_request")
            elif separators == 3:
                normalized.append(row)
            else:
                raise ValueError(f"pipeline row must have 3 or 4 fields: {row!r}")
        (ls_dir / str(index)).write_text(
            "\n".join(normalized) + ("\n" if normalized else ""), encoding="utf-8"
        )
    ls_counter = tmp_path / "wp-ls-calls"
    ps_file = tmp_path / "wp-ps"
    ps_file.write_text(
        "\n".join(ps_rows or []) + ("\n" if ps_rows else ""), encoding="utf-8"
    )
    log_file = tmp_path / "wp-log"
    log_file.write_text(log, encoding="utf-8")
    body = f"""#!/usr/bin/env bash
case "${{2:-}}" in
  ls)
    n=0
    [ -f "{ls_counter}" ] && n=$(cat "{ls_counter}")
    n=$((n + 1))
    echo "$n" > "{ls_counter}"
    [ "$n" -gt "{len(ls_blocks)}" ] && n="{len(ls_blocks)}"
    with_event=0
    for output_arg in "$@"; do
      case "$output_arg" in
        *'.Event'*) with_event=1 ;;
      esac
    done
    if [ "$with_event" -eq 1 ]; then
      cat "{ls_dir}/$n"
    else
      while IFS='|' read -r number status commit event; do
        printf '%s|%s|%s\n' "$number" "$status" "$commit"
      done < "{ls_dir}/$n"
    fi
    exit 0
    ;;
  ps)  cat "{ps_file}"; exit 0 ;;
  log) cat "{log_file}"; exit 0 ;;
esac
exit 1
"""
    path = tmp_path / "woodpecker-cli"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _run(tmp_path: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    full_env.update(
        {
            "FLOW_PR_WATCH_GH": "/nonexistent/gh",
            "FLOW_PR_WATCH_WPCLI": "/nonexistent/woodpecker-cli",
            "FLOW_PR_WATCH_SLEEP": "/bin/true",
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


def _fields(out: str) -> dict[str, list[str]]:
    """Parse the contract: ``KEY=value`` detail lines plus the ``FLOW_PR_WATCH: v`` verdict."""
    found: dict[str, list[str]] = {}
    for line in out.splitlines():
        if line.startswith("FLOW_PR_WATCH: "):
            found.setdefault("VERDICT", []).append(line.split(": ", 1)[1])
        elif line.startswith("FLOW_PR_WATCH_"):
            key, _, value = line.partition("=")
            found.setdefault(key, []).append(value)
    return found


# A log that reached its own conclusion: pytest printed a summary.
def _pytest_log(*failed: str, passed: int = 40) -> str:
    lines = ["============================= test session starts =============================="]
    lines.append(f"collected {passed + len(failed)} items")
    for test_id in failed:
        short = test_id.split("::")[-1]
        lines += [
            f"_________________________________ {short} _________________________________",
            "    assert result.exit_code == 0",
            "E   AssertionError: assert 1 == 0",
        ]
    lines.append("=========================== short test summary info ============================")
    for test_id in failed:
        lines.append(f"FAILED {test_id} - AssertionError: assert 1 == 0")
    lines.append(f"======================== {len(failed)} failed, {passed} passed =========================")
    return "\n".join(lines) + "\n"


# A log killed mid-suite: collection started, nothing concluded, no summary.
TRUNCATED_LOG = (
    "============================= test session starts ==============================\n"
    "collected 812 items\n"
    "tests/test_core.py ..........................\n"
)


@requires_bash
def test_green_pipeline_reports_green_and_exits_zero(tmp_path):
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1354|SUCCESS"]
    )
    result = _run(tmp_path, "42", "--repo", "o/r", env={"FLOW_PR_WATCH_GH": str(gh)})
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["green"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["1354"]
    assert fields["FLOW_PR_WATCH_URL"] == ["https://wp.example/repos/7/pipeline/1354"]
    assert fields["FLOW_PR_WATCH_HEAD"] == [HEAD]
    assert result.returncode == 0


@requires_bash
def test_disagreeing_contexts_report_the_named_context_not_the_higher_number(tmp_path):
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD],
        rollup=[
            f"{PR_CONTEXT}|https://wp.example/repos/7/pipeline/2100|SUCCESS",
            f"{PUSH_CONTEXT}|https://wp.example/repos/7/pipeline/2101|FAILURE",
        ],
    )
    result = _run(tmp_path, "42", "--repo", "o/r", env={"FLOW_PR_WATCH_GH": str(gh)})
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["green"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["2100"]
    assert result.returncode == 0


@requires_bash
def test_disagreeing_contexts_inverse_reports_named_context_not_lower_number(tmp_path):
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD],
        rollup=[
            f"{PUSH_CONTEXT}|https://wp.example/repos/7/pipeline/2110|SUCCESS",
            f"{PR_CONTEXT}|https://wp.example/repos/7/pipeline/2111|FAILURE",
        ],
    )
    result = _run(tmp_path, "42", "--repo", "o/r", env={"FLOW_PR_WATCH_GH": str(gh)})
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["2111"]
    assert result.returncode == 1


@requires_bash
def test_named_context_is_polled_until_its_own_state_is_terminal(tmp_path):
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD],
        rollups=[
            [
                f"{PR_CONTEXT}|https://wp.example/repos/7/pipeline/2115|PENDING",
                f"{PUSH_CONTEXT}|https://wp.example/repos/7/pipeline/2116|SUCCESS",
            ],
            [
                f"{PR_CONTEXT}|https://wp.example/repos/7/pipeline/2115|SUCCESS",
                f"{PUSH_CONTEXT}|https://wp.example/repos/7/pipeline/2116|SUCCESS",
            ],
        ],
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        "--timeout",
        "30",
        "--interval",
        "1",
        env={"FLOW_PR_WATCH_GH": str(gh)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["green"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["2115"]
    assert result.returncode == 0


@requires_bash
@pytest.mark.parametrize(
    "context_args", [("--context", PUSH_CONTEXT), (f"--context={PUSH_CONTEXT}",)]
)
def test_context_option_selects_the_other_lane(tmp_path, context_args):
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD],
        rollup=[
            f"{PUSH_CONTEXT}|https://wp.example/repos/7/pipeline/2120|SUCCESS",
            f"{PR_CONTEXT}|https://wp.example/repos/7/pipeline/2121|FAILURE",
        ],
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        *context_args,
        env={"FLOW_PR_WATCH_GH": str(gh)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["green"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["2120"]
    assert result.returncode == 0


@requires_bash
def test_wpcli_lane_does_not_override_a_correctly_scoped_pipeline_with_the_wrong_event(
    tmp_path,
):
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD],
        rollup=[f"{PR_CONTEXT}|https://wp.example/repos/7/pipeline/2130|SUCCESS"],
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"2131|failure|{HEAD}|push"],
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["green"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["2130"]
    assert result.returncode == 0


@requires_bash
def test_real_failure_is_red_with_ids_and_assertions_and_exits_one(tmp_path):
    """The class the worker must hear about before it retries."""
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1327|FAILURE"]
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1327|failure|{HEAD}"],
        ps_rows=["validate|failure|2026-09-05T22:04:11Z", "secret-scan|success|2026-09-05T22:01:02Z"],
        log=_pytest_log("tests/test_ui.py::test_typing_after_enlarge_renders_cleanly"),
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_FAILED"] == [
        "tests/test_ui.py::test_typing_after_enlarge_renders_cleanly"
    ]
    assert fields["FLOW_PR_WATCH_ASSERT"] == [
        "tests/test_ui.py::test_typing_after_enlarge_renders_cleanly: "
        "AssertionError: assert 1 == 0"
    ]
    assert result.returncode == 1


@requires_bash
def test_declared_flake_is_flake_not_red_and_exits_zero(tmp_path):
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "# fixed 2 s sleep races the steward writer\n"
        "test_steward_session_creates_correct_record\n"
        "\n"
        "# memory tile renders before the poll lands\n"
        "tests/test_dash.py::test_memory_health_tile\n",
        encoding="utf-8",
    )
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1374|FAILURE"]
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1374|failure|{HEAD}"],
        ps_rows=["validate|failure|2026-09-05T22:14:11Z"],
        log=_pytest_log(
            "tests/test_dash.py::test_memory_health_tile",
            "tests/test_steward.py::test_steward_session_creates_correct_record",
        ),
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        "--baseline",
        str(baseline),
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["flake"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_BASELINE"] == [str(baseline)]
    assert result.returncode == 0


@requires_bash
def test_one_id_outside_the_baseline_makes_the_whole_run_red(tmp_path):
    """A baseline hit does not excuse its neighbours - all-or-nothing, by design."""
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("test_memory_health_tile\n", encoding="utf-8")
    assert "test_typing_after_enlarge" not in baseline.read_text(encoding="utf-8")
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1380|FAILURE"]
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1380|failure|{HEAD}"],
        ps_rows=["validate|failure|2026-09-05T22:20:00Z"],
        log=_pytest_log(
            "tests/test_dash.py::test_memory_health_tile",
            "tests/test_ui.py::test_typing_after_enlarge_renders_cleanly",
        ),
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        "--baseline",
        str(baseline),
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert result.returncode == 1


@requires_bash
def test_superseding_push_with_kill_signature_is_cancelled(tmp_path):
    """kyle 1372/1375: identical stop timestamps, no summary, a newer run exists."""
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD, NEW_HEAD],
        rollup=["https://wp.example/repos/7/pipeline/1372|FAILURE"],
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1375|running|{NEW_HEAD}", f"1372|failure|{HEAD}"],
        ps_rows=[
            "validate|failure|2026-09-05T21:47:03Z",
            "codex-skills-check|failure|2026-09-05T21:47:03Z",
            "secret-scan|failure|2026-09-05T21:47:03Z",
        ],
        log=TRUNCATED_LOG,
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["cancelled"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_SUPERSEDED_BY"] == ["1375"]
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["1372"]
    assert result.returncode == 0


@requires_bash
def test_superseded_run_with_a_real_pytest_summary_is_still_red(tmp_path):
    """The expensive direction: supersession must never excuse a genuine defect.

    The run below WAS superseded by a newer push, but its log reached a pytest
    summary naming a failure - so the suite ran to a conclusion and was not
    killed mid-flight. Classifying it as ``cancelled`` would silently clear a
    real defect, which is exactly what the conjunctive rule exists to prevent.
    """
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD, NEW_HEAD],
        rollup=["https://wp.example/repos/7/pipeline/1390|FAILURE"],
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1391|running|{NEW_HEAD}", f"1390|failure|{HEAD}"],
        # Identical stop timestamps on their own would satisfy half the
        # signature; the summary line in the log is what denies it.
        ps_rows=[
            "validate|failure|2026-09-05T23:00:00Z",
            "codex-skills-check|failure|2026-09-05T23:00:00Z",
        ],
        log=_pytest_log("tests/test_auth.py::test_login_redirect"),
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_FAILED"] == ["tests/test_auth.py::test_login_redirect"]
    assert fields["FLOW_PR_WATCH_SUPERSEDED_BY"] == ["1391"]
    assert result.returncode == 1


@requires_bash
def test_killed_state_is_cancelled_even_with_one_stopped_step(tmp_path):
    """``killed`` is unambiguous on its own; the timestamp heuristic is the fallback."""
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD, NEW_HEAD],
        rollup=["https://wp.example/repos/7/pipeline/1310|FAILURE"],
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1311|pending|{NEW_HEAD}", f"1310|killed|{HEAD}"],
        ps_rows=["validate|killed|2026-09-05T20:10:00Z"],
        log=TRUNCATED_LOG,
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["cancelled"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_SUPERSEDED_BY"] == ["1311"]
    assert result.returncode == 0


@requires_bash
def test_rerun_on_the_same_head_supersedes_the_watched_pipeline(tmp_path):
    """A newer pipeline on the SAME head supersedes too - not only a new push.

    Poll 1 latches onto #1400 while it is still running. Poll 2 sees #1401 for
    the same head, so #1400 is the superseded run - and the verdict must describe
    #1400, the run the caller asked about, never the re-run that replaced it.
    """
    gh = _write_fake_gh(
        tmp_path,
        heads=[HEAD],
        rollups=[
            ["https://wp.example/repos/7/pipeline/1400|PENDING"],
            ["https://wp.example/repos/7/pipeline/1401|PENDING"],
        ],
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_blocks=[
            # Poll 1: only the run we latch onto exists, and it is still going.
            [f"1400|running|{HEAD}"],
            # Poll 2: the re-run is visible and the first run has been killed.
            [f"1401|running|{HEAD}", f"1400|killed|{HEAD}"],
        ],
        ps_rows=["validate|killed|2026-09-05T23:30:00Z"],
        log=TRUNCATED_LOG,
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        "--timeout",
        "30",
        "--interval",
        "1",
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["cancelled"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["1400"]
    assert fields["FLOW_PR_WATCH_SUPERSEDED_BY"] == ["1401"]
    assert result.returncode == 0


@requires_bash
def test_pipeline_that_never_finishes_times_out_with_exit_five(tmp_path):
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1500|PENDING"]
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        "--timeout",
        "1",
        "--interval",
        "1",
        env={"FLOW_PR_WATCH_GH": str(gh)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["timeout"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["1500"]
    assert result.returncode == 5


@requires_bash
def test_no_pipeline_for_the_head_is_unknown_and_fails_open(tmp_path):
    gh = _write_fake_gh(tmp_path, heads=[HEAD], rollup=[])
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        "--timeout",
        "0",
        env={"FLOW_PR_WATCH_GH": str(gh)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["unknown"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_PIPELINE"] == ["-"]
    assert result.returncode == 0


@requires_bash
def test_missing_gh_is_unknown_and_fails_open(tmp_path):
    """A watch that cannot see must never be the reason a wave stops."""
    missing = Path("/nonexistent/gh")
    assert not missing.exists()
    result = _run(tmp_path, "42", "--repo", "o/r")
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["unknown"], result.stdout + result.stderr
    assert result.returncode == 0


@requires_bash
def test_red_without_the_cli_reports_red_without_inventing_ids(tmp_path):
    """Honest degradation: the run is red, the refinement is simply unavailable."""
    missing = Path("/nonexistent/woodpecker-cli")
    assert not missing.exists()
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1600|FAILURE"]
    )
    result = _run(tmp_path, "42", "--repo", "o/r", env={"FLOW_PR_WATCH_GH": str(gh)})
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_FAILED"] == ["-"]
    assert result.returncode == 1


@requires_bash
def test_red_step_with_no_pytest_ids_names_the_failed_step(tmp_path):
    """A red `secret-scan` is not a red test suite; the step name is the diagnosis."""
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1700|FAILURE"]
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1700|failure|{HEAD}"],
        ps_rows=["secret-scan|failure|2026-09-05T18:00:00Z"],
        log="leak detected in config.yml\n",
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_FAILED"] == ["-"]
    assert "failed step: secret-scan" in result.stderr
    assert result.returncode == 1


@requires_bash
def test_the_word_error_in_log_prose_is_not_a_failed_test_id(tmp_path):
    """The id must contain `::`, so ordinary log prose cannot fabricate a failure."""
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1800|FAILURE"]
    )
    noisy = (
        "ERROR could not resolve host cdn.example.com\n"
        "ERROR retrying (1/3)\n"
        "make: *** [Makefile:21: test] Error 2\n"
    )
    assert "::" not in noisy
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1800|failure|{HEAD}"],
        ps_rows=["validate|failure|2026-09-05T19:00:00Z"],
        log=noisy,
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_FAILED"] == ["-"]
    assert result.returncode == 1


@requires_bash
def test_parametrized_ids_survive_baseline_matching_and_assertion_lookup(tmp_path):
    """Brackets and dots in an id must not be read as regex metacharacters."""
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("tests/test_p.py::test_case[a.b-c]\n", encoding="utf-8")
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/1900|FAILURE"]
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"1900|failure|{HEAD}"],
        ps_rows=["validate|failure|2026-09-05T19:30:00Z"],
        log=_pytest_log("tests/test_p.py::test_case[a.b-c]"),
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        "--baseline",
        str(baseline),
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["flake"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_FAILED"] == ["tests/test_p.py::test_case[a.b-c]"]
    assert result.returncode == 0


@requires_bash
def test_default_baseline_is_read_from_the_declared_checkout(tmp_path):
    """`--path` declares the checkout; the default baseline hangs off it (#614)."""
    checkout = tmp_path / "repo"
    (checkout / ".claude").mkdir(parents=True)
    (checkout / ".claude" / "flow-flake-baseline.txt").write_text(
        "test_memory_health_tile\n", encoding="utf-8"
    )
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/2000|FAILURE"]
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"2000|failure|{HEAD}"],
        ps_rows=["validate|failure|2026-09-05T20:00:00Z"],
        log=_pytest_log("tests/test_dash.py::test_memory_health_tile"),
    )
    result = _run(
        tmp_path,
        "42",
        "--repo",
        "o/r",
        "--path",
        str(checkout),
        env={"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)},
    )
    fields = _fields(result.stdout)
    assert fields["VERDICT"] == ["flake"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_BASELINE"] == [
        str(checkout / ".claude" / "flow-flake-baseline.txt")
    ]
    assert result.returncode == 0


@requires_bash
@pytest.mark.parametrize(
    "args",
    [
        (),
        ("not-a-number",),
        ("42", "--timeout", "soon"),
        ("42", "--context", ""),
        ("42", "--context="),
        ("42", "--frobnicate"),
    ],
)
def test_usage_errors_exit_two(tmp_path, args):
    result = _run(tmp_path, *args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "usage: flow-pr-watch.sh" in result.stderr


@requires_bash
def test_help_prints_the_header_without_leaking_code(tmp_path):
    result = _run(tmp_path, "--help")
    assert result.returncode == 0
    assert "flow-pr-watch.sh - Watch ONE PR's pipeline" in result.stdout
    assert "FLOW_PR_WATCH_SLEEP" in result.stdout
    assert "set -uo pipefail" not in result.stdout


def test_helper_is_executable_and_installed_at_the_stable_path():
    """The #581 contract: bare invocation at ~/.claude/scripts needs both halves.

    A permissions rule that blesses a path nothing installs is inert (#669/#677),
    so the installer array and the template must name this helper together.
    """
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK), "the link loop gates on executability"
    installer = (ROOT / "scripts" / "flow-helpers-install.sh").read_text(encoding="utf-8")
    assert "flow-pr-watch.sh" in installer
    template = (ROOT / "templates" / "claude-settings-permissions.json").read_text(
        encoding="utf-8"
    )
    assert "Bash(~/.claude/scripts/flow-pr-watch.sh:*)" in template


# ── #1190 defect 1: a negative control's echo scraped as the pipeline's own ──
#
# Reconstructed from the measurement in the issue (pipeline 2512, PR #1310).
# `scripts/check-xdist-isolation.sh` runs a two-sided control and `tail`s its
# BAD-case log, so the BAD case's deliberate `FAILED ...::...` lines appear in
# the step log. The scrape walked the WHOLE log and harvested them alongside the
# one real failure, reporting four.
#
# It is not cosmetic. `--baseline` matches declared-flaky ids against
# FLOW_PR_WATCH_FAILED, so the natural response to seeing a control's test named
# red on an unrelated PR is to add it to the baseline - and from then on that
# test's REAL failures are excused. A misattribution that feeds an excuse list
# is a route to a hidden defect, and the more thoroughly a repo commits its red
# cases the more of this there is.

CONTROL_ECHO_LOG = (
    "============================= test session starts ==============================\n"
    "collected 6433 items\n"
    "tests/test_core.py ..........................\n"
    "\n"
    "-- BAD case: worker scoping collapsed, same invocation --\n"
    "FAILED tests/test_xdist_isolation.py::test_worker_scoped_paths_carry_this_worker_id\n"
    "FAILED tests/test_xdist_isolation.py::test_the_collapse_override_is_not_set_in_this_run\n"
    "FAILED tests/test_xdist_isolation.py::test_no_two_workers_named_the_same_database_or_tmux_socket\n"
    "XDIST_ISOLATION: ok\n"
    "\n"
    "____________________________ test_unlock ____________________________\n"
    "    assert 'secret' not in session\n"
    "E   AssertionError: assert 1 == 0\n"
    "=========================== short test summary info ============================\n"
    "FAILED journal/tests/test_views.py::TestNoSecretsInSession::test_unlock - AssertionError\n"
    "======================== 1 failed, 6432 passed =========================\n"
)

REAL_FAILURE = "journal/tests/test_views.py::TestNoSecretsInSession::test_unlock"
CONTROL_ECHOED = "tests/test_xdist_isolation.py::test_the_collapse_override_is_not_set_in_this_run"


def _failing_pipeline(tmp_path, log: str):
    """A red pipeline whose step log is ``log``."""
    gh = _write_fake_gh(
        tmp_path, heads=[HEAD], rollup=["https://wp.example/repos/7/pipeline/2512|FAILURE"]
    )
    wpcli = _write_fake_wpcli(
        tmp_path,
        ls_rows=[f"2512|failure|{HEAD}"],
        ps_rows=["validate|failure|2026-09-21T19:29:21Z"],
        log=log,
    )
    return {"FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wpcli)}


@requires_bash
def test_a_controls_echoed_failures_are_not_the_pipelines_own(tmp_path):
    """THE RED CASE. Four `FAILED ...::...` lines in the log, one real failure.

    Pre-fix this reported all four, including the control's own BAD-case tests -
    whose whole job is to fail on purpose so the checker can prove it still
    detects a failure.
    """
    env = _failing_pipeline(tmp_path, CONTROL_ECHO_LOG)
    result = _run(tmp_path, "42", "--repo", "o/r", env=env)
    fields = _fields(result.stdout)

    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_FAILED"] == [REAL_FAILURE], (
        "the control's echoed BAD-case failures were scraped as the pipeline's own"
    )
    assert CONTROL_ECHOED not in result.stdout, (
        "a deliberately-failing control test was named as a pipeline failure - "
        "adding it to the flake baseline would excuse its real failures forever"
    )


@requires_bash
def test_the_scrape_reports_which_region_it_read(tmp_path):
    """A bounded scrape and an unbounded one must be distinguishable.

    The count is emitted beside the ids so four named failures and `1 failed`
    can be seen to disagree, which is the issue's own minimum ask.
    """
    env = _failing_pipeline(tmp_path, CONTROL_ECHO_LOG)
    result = _run(tmp_path, "42", "--repo", "o/r", env=env)
    fields = _fields(result.stdout)

    assert fields["FLOW_PR_WATCH_SCRAPE_SCOPE"] == ["summary"]
    assert fields["FLOW_PR_WATCH_SUMMARY_FAILED"] == ["1"]


@requires_bash
def test_a_log_with_no_summary_reports_itself_unbounded_never_clean(tmp_path):
    """A killed or truncated log has no summary region to bound to.

    The scrape stays whole-log there - losing a real failure would be worse -
    but it must SAY so. Unbounded rendering as clean is the defect one level up,
    and is exactly what this issue is about.
    """
    env = _failing_pipeline(tmp_path, TRUNCATED_LOG)
    result = _run(tmp_path, "42", "--repo", "o/r", env=env)
    fields = _fields(result.stdout)

    assert fields["FLOW_PR_WATCH_SCRAPE_SCOPE"] == ["whole-log"]
    assert fields["FLOW_PR_WATCH_SUMMARY_FAILED"] == ["-"], (
        "a log with no summary has no authoritative count; it must not report one"
    )


@requires_bash
def test_an_ordinary_failure_is_still_reported_in_full(tmp_path):
    """The other side of the guard: bounding the scrape must not lose failures
    that pytest genuinely summarised. Two real failures, both named."""
    log = _pytest_log(
        "tests/test_a.py::test_one",
        "tests/test_b.py::test_two",
    )
    env = _failing_pipeline(tmp_path, log)
    result = _run(tmp_path, "42", "--repo", "o/r", env=env)
    fields = _fields(result.stdout)

    assert fields["VERDICT"] == ["red"], result.stdout + result.stderr
    assert fields["FLOW_PR_WATCH_FAILED"] == ["tests/test_a.py::test_one tests/test_b.py::test_two"]
    assert fields["FLOW_PR_WATCH_SUMMARY_FAILED"] == ["2"]


# ── #1190 round 2: defects the FIRST CUT of the bounding fix introduced ──────
#
# All three were found by counter-model review and reproduced before being
# fixed. They are kept as named cases because each is a way the repair
# reintroduced the harm it was written to remove.

TWO_RUN_LOG = (
    "=========================== short test summary info ============================\n"
    "FAILED tests/test_real.py::test_regression_nobody_baselined - AssertionError\n"
    "======================== 1 failed, 40 passed =========================\n"
    "=========================== short test summary info ============================\n"
    "FAILED journal/tests/test_views.py::TestNoSecretsInSession::test_unlock - AssertionError\n"
    "======================== 1 failed, 6432 passed =========================\n"
)

TRAILING_ECHO_LOG = (
    "=========================== short test summary info ============================\n"
    "FAILED journal/tests/test_views.py::TestNoSecretsInSession::test_unlock - AssertionError\n"
    "======================== 1 failed, 6432 passed =========================\n"
    "-- BAD case: control echo AFTER the run concluded --\n"
    "FAILED tests/test_control.py::test_deliberate\n"
)

ERROR_ONLY_LOG = (
    "=========================== short test summary info ============================\n"
    "ERROR tests/test_boot.py::test_fixture - fixture 'db' not found\n"
    "======================== 1 error in 0.40s =========================\n"
)


@requires_bash
def test_an_earlier_runs_failure_is_not_discarded_by_a_later_summary(tmp_path):
    """A false FLAKE is worse than the false RED this issue is about.

    Two pytest runs in one log: the first carries a regression nobody
    baselined, the second only a baselined failure. Taking the LAST summary
    region dropped the first, so every reported id was in the baseline and the
    verdict became `flake` at exit 0 - a real failure silently excused, by the
    very fix meant to stop failures being mis-attributed.

    Over-reporting is noisy and gets noticed; this is a silent green.
    """
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "journal/tests/test_views.py::TestNoSecretsInSession::test_unlock\n", encoding="utf-8"
    )
    env = _failing_pipeline(tmp_path, TWO_RUN_LOG)
    result = _run(tmp_path, "42", "--repo", "o/r", "--baseline", str(baseline), env=env)
    fields = _fields(result.stdout)

    assert "tests/test_real.py::test_regression_nobody_baselined" in \
        fields["FLOW_PR_WATCH_FAILED"][0], "an earlier run's failure was discarded"
    assert fields["VERDICT"] == ["red"], (
        "a non-baselined regression was excused as a flake"
    )
    assert fields["FLOW_PR_WATCH_SUMMARY_FAILED"] == ["2"], "totals must sum both runs"


@requires_bash
def test_output_after_the_totals_line_is_not_part_of_the_summary(tmp_path):
    """Each region ends at its own totals line.

    Running a region to end-of-log re-admitted exactly the contamination the
    bounding exists to exclude - a control echoing `FAILED <id>` after the run
    concluded - while the scope label still said `summary`, so the caveat
    overstated its own coverage.
    """
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "journal/tests/test_views.py::TestNoSecretsInSession::test_unlock\n", encoding="utf-8"
    )
    env = _failing_pipeline(tmp_path, TRAILING_ECHO_LOG)
    result = _run(tmp_path, "42", "--repo", "o/r", "--baseline", str(baseline), env=env)
    fields = _fields(result.stdout)

    assert "tests/test_control.py::test_deliberate" not in result.stdout, (
        "a control echo after the totals line was scraped as a pipeline failure"
    )
    assert fields["VERDICT"] == ["flake"], (
        "the trailing echo flipped a baselined failure from flake to red"
    )


@requires_bash
def test_a_concluded_run_with_no_failures_reports_zero_not_absent(tmp_path):
    """`0` is an observation; `-` is the absence of one.

    An error-only run concluded and reported no FAILED tests. Rendering that as
    `-` conflates a measured zero with no measurement - the absent-is-not-empty
    confusion this issue exists to remove, reappearing in its own fix.
    """
    env = _failing_pipeline(tmp_path, ERROR_ONLY_LOG)
    result = _run(tmp_path, "42", "--repo", "o/r", env=env)
    fields = _fields(result.stdout)

    assert fields["FLOW_PR_WATCH_SUMMARY_FAILED"] == ["0"], (
        "a concluded run with zero failures must report 0, never '-'"
    )
    assert fields["FLOW_PR_WATCH_SCRAPE_SCOPE"] == ["summary"]


# ── #1190 round 3: defects the SECOND cut introduced, from the re-review ─────

HEADER_PHRASE_LOG = (
    "=========================== short test summary info ============================\n"
    "FAILED tests/test_real.py::test_regression - AssertionError: expected short test summary info\n"
    "FAILED journal/tests/test_views.py::TestNoSecretsInSession::test_unlock - AssertionError\n"
    "======================== 2 failed, 40 passed =========================\n"
)

QUIET_TOTALS_LOG = (
    "=========================== short test summary info ============================\n"
    "FAILED journal/tests/test_views.py::TestNoSecretsInSession::test_unlock - AssertionError\n"
    "1 failed, 40 passed in 0.40s\n"
    "-- BAD case: control echo after quiet totals --\n"
    "FAILED tests/test_control.py::test_deliberate\n"
)


@requires_bash
def test_the_header_phrase_inside_an_assertion_does_not_delete_that_failure(tmp_path):
    """The section header is matched by SHAPE, not as a substring.

    An unanchored match also fired on an assertion message quoting the phrase,
    which reset the region and discarded the failure carrying it - so a real
    regression vanished while the count still said two.
    """
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "journal/tests/test_views.py::TestNoSecretsInSession::test_unlock\n", encoding="utf-8"
    )
    env = _failing_pipeline(tmp_path, HEADER_PHRASE_LOG)
    result = _run(tmp_path, "42", "--repo", "o/r", "--baseline", str(baseline), env=env)
    fields = _fields(result.stdout)

    assert "tests/test_real.py::test_regression" in fields["FLOW_PR_WATCH_FAILED"][0], (
        "a failure was deleted because its assertion text quoted the header phrase"
    )
    assert fields["VERDICT"] == ["red"]


@requires_bash
def test_quiet_mode_totals_close_the_region(tmp_path):
    """`pytest -q` prints `N failed, M passed in 0.4s` with no `=` decoration.

    Requiring the decorated form left the region open, so a later control echo
    stayed inside it and the count read `-` for a run that had concluded.
    """
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "journal/tests/test_views.py::TestNoSecretsInSession::test_unlock\n", encoding="utf-8"
    )
    env = _failing_pipeline(tmp_path, QUIET_TOTALS_LOG)
    result = _run(tmp_path, "42", "--repo", "o/r", "--baseline", str(baseline), env=env)
    fields = _fields(result.stdout)

    assert "tests/test_control.py::test_deliberate" not in result.stdout, (
        "an echo after quiet-mode totals stayed inside the region"
    )
    assert fields["FLOW_PR_WATCH_SUMMARY_FAILED"] == ["1"], (
        "quiet-mode totals were not read as a concluded run"
    )
    assert fields["VERDICT"] == ["flake"]
