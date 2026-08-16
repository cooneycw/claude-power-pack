"""Tests for scripts/gh-pr-merge.sh - layout-aware PR squash-merge (issue #461).

Contract:
- In a LINKED worktree (cwd's ``.git`` is a file), merge WITHOUT --delete-branch
  and delete the remote branch ourselves, so gh never attempts the local branch
  switch that fails with "fatal: 'main' is already checked out".
- In the PRIMARY repo (cwd's ``.git`` is a directory), keep --delete-branch.
- Verify the PR reached MERGED before returning failure, so a non-zero gh exit on
  a local post-merge step never masks a successful remote merge.
- When the squash fails with "Base branch was modified" (a sibling PR merged in
  the poll->merge race window, issue #502), refetch + retry a bounded number of
  times; any other failure is not retried.
- Required status checks on the base branch are WAITED FOR before the squash and
  never auto-overridden (issue #577): a pending check is polled, a red one is a
  hard stop, one that never reports times out into a stop naming the --admin
  break-glass, and a required-check block is excluded from the #517 --admin
  auto-retry (a review block still triggers it). A base with no required checks
  takes the original path unchanged.
- Required contexts are resolved from BOTH mechanisms GitHub offers - classic
  branch protection and repository RULESETS - and only a successful response
  counts as data (issue #610). An error body is never mistaken for a context, a
  base with no protection of either kind skips the wait outright, and when
  neither source is readable the PR's own checks decide: green merges, red stops,
  pending waits then fails open (GitHub enforces the posture server-side anyway).
- Return non-zero only when the PR genuinely did not merge - and non-zero on
  EVERY refusal to merge, since /flow:auto Step 7 trusts the exit code.

``gh`` and ``git`` are stubbed via the GH_PR_MERGE_GH / GH_PR_MERGE_GIT env hooks;
each stub appends its argv to a call log the tests assert against.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gh-pr-merge.sh"


def _write_stub(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(0o755)


def _make_stubs(
    tmp_path: Path,
    *,
    merge_exit: int = 0,
    pr_state: str = "MERGED",
    mergeable: str | list[str] = "MERGEABLE",
    merge_outcomes: list[tuple[int, str]] | None = None,
    viewer_permission: str = "ADMIN",
    required_contexts: list[str] | None = None,
    protection_ok: bool = True,
    ruleset_contexts: list[str] | None = None,
    ruleset_ok: bool = True,
    check_rollup: list[list[tuple[str, str]]] | None = None,
    review_decision: str = "",
    pr_title: str = "",
    pr_body: str = "",
    title_ok: bool = True,
    pr_deletions: list[str] | None = None,
    deletions_ok: bool = True,
    merge_commit: str = "",
    pr_files: list[str] | None = None,
    landed_paths: list[str] | None = None,
    repo_full: str = "cooneycw/claude-power-pack",
    head_sha: str = "deadfeed0000000000000000000000000000face",
    pr_up_to_date: bool = False,
    tested_tree: str = "0f00d0f00d0f00d0f00d0f00d0f00d0f00d0f00",
    woodpecker_lookup_ok: bool = True,
    woodpecker_repo_id: str = "42",
    woodpecker_pipeline_statuses: list[str] | None = None,
) -> dict:
    """Create fake gh/git that log their args and honour a scripted outcome.

    ``mergeable`` scripts the ``gh pr view --json mergeable`` poll (issue #485):
    pass a single value, or a sequence consumed one value per poll (staying on
    the last once exhausted) to model a transient UNKNOWN that resolves.

    ``merge_outcomes`` scripts successive ``gh pr merge`` calls (issue #502) as
    ``(exit_code, stderr_message)`` pairs consumed one per call, staying on the
    last once exhausted. Defaults to ``[(merge_exit, "")]``.

    ``viewer_permission`` scripts ``gh repo view --json viewerPermission`` - the
    repo-admin check that gates the branch-protection --admin retry (issue #517).

    ``required_contexts`` scripts the base branch's CLASSIC branch-protection
    required status checks (issue #577); empty (the default) means the branch
    requires none, so the pre-merge wait is inert and every pre-#577 test
    exercises the original path unchanged. ``ruleset_contexts`` scripts the same
    thing for the RULESETS endpoint (issue #610), the mechanism classic
    protection cannot see.

    ``protection_ok`` / ``ruleset_ok`` control whether each endpoint ANSWERS.
    Setting one False makes that ``gh api`` call behave the way the real one does
    on a 404: the error body goes to STDOUT (unfiltered by --jq) and gh exits
    non-zero - the exact shape that, pre-#610, was mapped into the required-context
    list and waited on until it timed out.

    ``check_rollup`` scripts ``gh pr view --json statusCheckRollup`` as a list of
    polls, each a list of ``(name, state)`` pairs, consumed one poll per call and
    staying on the last once exhausted.

    ``review_decision`` scripts ``gh pr view --json reviewDecision`` (issue
    #579). Empty (the default) models a repo with no review protection - the
    review gate fails open and every pre-#579 test exercises its original path
    unchanged.

    ``pr_title`` / ``pr_body`` script ``gh pr view --json title`` / ``--json
    body`` - the squash subject/body derivation (issue #655). An empty title
    (the default) rides the fail-open path (no --subject/--body added), so
    every pre-#655 test exercises its original merge argv unchanged.
    ``title_ok=False`` makes the title fetch FAIL (exit 1, no output), the API
    hiccup the fail-open exists for. Each ``gh pr merge`` call also dumps its
    exact argv (NUL-separated) to ``merge_argv_<n>`` so tests can assert arg
    BOUNDARIES - a multiline --body must arrive as one argument.

    ``pr_deletions`` scripts the pre-squash ``git diff --diff-filter=D`` read
    (issue #657); ``deletions_ok=False`` makes that diff FAIL (exit 1), the
    unreadable-input case that must print ``skipped``. ``merge_commit`` /
    ``pr_files`` / ``landed_paths`` script the post-merge completeness read:
    the PR's merge-commit sha, its file list, and the paths the landed squash
    actually touched. The empty defaults ride the ``skipped`` fail-open path,
    so every pre-#657 test exercises its original behavior unchanged.

    ``pr_up_to_date`` scripts the ``git merge-base --is-ancestor`` ancestry
    check behind the #716 tested-tree trailer; ``tested_tree`` is what
    ``git rev-parse HEAD^{tree}`` answers. Default ``False`` is the SAFE
    default (no trailer), so every pre-#716 test exercises its original
    argv unchanged without needing to know this parameter exists.

    ``repo_full`` / ``head_sha`` script ``gh repo view --json nameWithOwner``
    and ``git rev-parse HEAD`` - both consulted by the #717 Woodpecker
    queue-wait, which itself only activates when ``WOODPECKER_API_TOKEN`` is
    set via ``extra_env`` (the default test env has it popped, so the whole
    feature is a no-op unless a test opts in). ``woodpecker_lookup_ok=False``
    makes the repo-id lookup curl call FAIL (the token-set-but-unresolvable
    case). ``woodpecker_pipeline_statuses`` scripts successive
    ``.../pipelines`` polls (one status consumed per call, staying on the
    last once exhausted); the default ``None`` answers "running" so an
    opted-in test that does not care about queuing sees an instant pass-through.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    call_log = tmp_path / "calls.log"

    # Persist the mergeability sequence + a counter the gh stub advances per poll.
    seq_file = tmp_path / "mergeable_seq"
    ctr_file = tmp_path / "mergeable_ctr"
    vals = [mergeable] if isinstance(mergeable, str) else list(mergeable)
    seq_file.write_text("\n".join(vals) + "\n")

    # Same scheme for the per-call merge outcomes (`exit_code|stderr` lines).
    merge_seq_file = tmp_path / "merge_seq"
    merge_ctr_file = tmp_path / "merge_ctr"
    outcomes = merge_outcomes if merge_outcomes is not None else [(merge_exit, "")]
    merge_seq_file.write_text("".join(f"{code}|{msg}\n" for code, msg in outcomes))

    # Issue #577: the base branch's required contexts, and the per-poll rollup.
    # Issue #610: the same, from the rulesets endpoint. Both hold the POST-jq
    # output (one context per line); the stub ignores the --jq filter, exactly as
    # the pre-existing required-contexts stub does.
    req_file = tmp_path / "required_contexts"
    req_file.write_text("".join(f"{c}\n" for c in (required_contexts or [])))
    rules_file = tmp_path / "ruleset_contexts"
    rules_file.write_text("".join(f"{c}\n" for c in (ruleset_contexts or [])))
    # The verbatim 404 body GitHub returns for a branch with no CLASSIC protection
    # - including one guarded by a ruleset, which this endpoint cannot see.
    not_protected = (
        '{"message":"Branch not protected","documentation_url":'
        '"https://docs.github.com/rest/branches/branch-protection'
        '#get-status-checks-protection","status":"404"}'
    )
    rollup_seq_file = tmp_path / "rollup_seq"
    rollup_ctr_file = tmp_path / "rollup_ctr"
    # One line per poll; states within a poll are comma-separated `name=state`.
    rollup_polls = check_rollup if check_rollup is not None else [[]]
    rollup_seq_file.write_text(
        "".join(",".join(f"{n}={s}" for n, s in poll) + "\n" for poll in rollup_polls)
    )

    # Issue #655: the PR title/body the squash subject derivation reads. Files,
    # not inline echo, so a multiline body (or one full of shell metacharacters)
    # round-trips byte-exact through the stub.
    title_file = tmp_path / "pr_title"
    title_file.write_text(pr_title)
    body_file = tmp_path / "pr_body"
    body_file.write_text(pr_body)

    # Issue #657: the deletion-surfacing and completeness reads.
    deletions_file = tmp_path / "pr_deletions"
    deletions_file.write_text("".join(f"{p}\n" for p in (pr_deletions or [])))
    files_file = tmp_path / "pr_files"
    files_file.write_text("".join(f"{p}\n" for p in (pr_files or [])))
    landed_file = tmp_path / "landed_paths"
    landed_file.write_text("".join(f"{p}\n" for p in (landed_paths or [])))

    # gh: log argv; `pr merge` honours the next scripted (exit, stderr) outcome;
    # `pr view --json mergeable` echoes the next scripted mergeable value; any
    # other `pr view` echoes pr_state.
    _write_stub(
        bin_dir / "gh",
        f'echo "gh $*" >> "{call_log}"\n'
        'if [[ "$1 $2" == "pr merge" ]]; then\n'
        f'  ctr=$(cat "{merge_ctr_file}" 2>/dev/null || echo 0)\n'
        # Exact argv capture for this merge call (issue #655): NUL-separated so
        # a multiline --body stays one recoverable argument.
        f'  printf \'%s\\0\' "$@" > "{tmp_path}/merge_argv_$ctr"\n'
        f'  mapfile -t lines < "{merge_seq_file}"\n'
        "  idx=$ctr\n"
        "  if (( idx >= ${#lines[@]} )); then idx=$(( ${#lines[@]} - 1 )); fi\n"
        f'  echo $(( ctr + 1 )) > "{merge_ctr_file}"\n'
        '  IFS="|" read -r code msg <<< "${lines[$idx]}"\n'
        '  if [[ -n "$msg" ]]; then echo "$msg" >&2; fi\n'
        '  exit "$code"\n'
        'elif [[ "$1" == "api" ]]; then\n'
        # Match on the PATH, not on "$*": the rulesets jq filter also contains the
        # string `required_status_checks`, so a naive match routes it wrongly.
        '  if [[ "$2" == *"/protection/required_status_checks" ]]; then\n'
        + ("    " + f'cat "{req_file}"\n' if protection_ok else f"    echo '{not_protected}'\n    exit 1\n")
        + '  elif [[ "$2" == *"/rules/branches/"* ]]; then\n'
        + (
            "    " + f'cat "{rules_file}"\n'
            if ruleset_ok
            else '    echo \'{"message":"Not Found","status":"404"}\'\n    exit 1\n'
        )
        + "  fi\n"
        "  exit 0\n"
        'elif [[ "$1 $2" == "pr view" ]]; then\n'
        '  if [[ "$*" == *baseRefName* ]]; then\n'
        '    echo "main"\n'
        '  elif [[ "$*" == *statusCheckRollup* ]]; then\n'
        f'    ctr=$(cat "{rollup_ctr_file}" 2>/dev/null || echo 0)\n'
        f'    mapfile -t polls < "{rollup_seq_file}"\n'
        "    idx=$ctr\n"
        "    if (( idx >= ${#polls[@]} )); then idx=$(( ${#polls[@]} - 1 )); fi\n"
        f'    echo $(( ctr + 1 )) > "{rollup_ctr_file}"\n'
        '    IFS="," read -ra entries <<< "${polls[$idx]}"\n'
        '    for e in "${entries[@]}"; do\n'
        '      [[ -z "$e" ]] && continue\n'
        '      echo "${e%%=*}|${e##*=}"\n'
        "    done\n"
        '  elif [[ "$*" == *mergeable* ]]; then\n'
        f'    ctr=$(cat "{ctr_file}" 2>/dev/null || echo 0)\n'
        f'    mapfile -t vals < "{seq_file}"\n'
        "    idx=$ctr\n"
        "    if (( idx >= ${#vals[@]} )); then idx=$(( ${#vals[@]} - 1 )); fi\n"
        '    echo "${vals[$idx]}"\n'
        f'    echo $(( ctr + 1 )) > "{ctr_file}"\n'
        '  elif [[ "$*" == *reviewDecision* ]]; then\n'
        f'    echo "{review_decision}"\n'
        '  elif [[ "$*" == *"--json title"* ]]; then\n'
        + (f'    cat "{title_file}"; echo\n' if title_ok else "    exit 1\n")
        + '  elif [[ "$*" == *"--json body"* ]]; then\n'
        f'    cat "{body_file}"; echo\n'
        '  elif [[ "$*" == *mergeCommit* ]]; then\n'
        f'    echo "{merge_commit}"\n'
        '  elif [[ "$*" == *"--json files"* ]]; then\n'
        f'    cat "{files_file}"\n'
        "  else\n"
        f'    echo "{pr_state}"\n'
        "  fi\n"
        "  exit 0\n"
        'elif [[ "$1 $2" == "repo view" ]]; then\n'
        '  if [[ "$*" == *nameWithOwner* ]]; then\n'
        f'    echo "{repo_full}"\n'
        "  else\n"
        f'    echo "{viewer_permission}"\n'
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )
    # git: log argv. rev-parse --show-toplevel answers with the cwd (a real
    # root, so the #657 ref-scoped reads proceed); the deletion diff and the
    # landed-paths diff answer from their fixture files; the tree/ancestor/HEAD
    # checks (issues #716, #717) answer from the scripted knobs above;
    # everything else succeeds silently.
    _write_stub(
        bin_dir / "git",
        f'echo "git $*" >> "{call_log}"\n'
        'if [[ "$*" == *"rev-parse --show-toplevel"* ]]; then\n'
        "  pwd\n"
        'elif [[ "$*" == *"rev-parse"*"HEAD^{tree}"* ]]; then\n'
        f'  echo "{tested_tree}"\n'
        'elif [[ "$*" == *"merge-base --is-ancestor"* ]]; then\n'
        + ("  exit 0\n" if pr_up_to_date else "  exit 1\n")
        + 'elif [[ "$*" == "rev-parse HEAD" ]]; then\n'
        f'  echo "{head_sha}"\n'
        'elif [[ "$*" == *"--diff-filter=D"* ]]; then\n'
        + (f'  cat "{deletions_file}"\n' if deletions_ok else "  exit 1\n")
        + 'elif [[ "$*" == *"diff --name-only"* ]]; then\n'
        f'  cat "{landed_file}"\n'
        "fi\n"
        "exit 0\n",
    )

    # curl: log argv. Only consulted by the #717 Woodpecker queue-wait, which
    # itself only fires when WOODPECKER_API_TOKEN is set (via extra_env) - so
    # this stub is inert for every test that does not opt in.
    wp_seq_file = tmp_path / "woodpecker_statuses"
    wp_ctr_file = tmp_path / "woodpecker_status_ctr"
    wp_statuses = woodpecker_pipeline_statuses if woodpecker_pipeline_statuses is not None else ["running"]
    wp_seq_file.write_text("\n".join(wp_statuses) + "\n")
    _write_stub(
        bin_dir / "curl",
        f'echo "curl $*" >> "{call_log}"\n'
        'if [[ "$*" == *"/api/repos/lookup/"* ]]; then\n'
        + (
            f'  echo \'{{"id": "{woodpecker_repo_id}"}}\'\n'
            if woodpecker_lookup_ok
            else "  exit 22\n"
        )
        + 'elif [[ "$*" == *"/pipelines?per_page=5"* ]]; then\n'
        f'  ctr=$(cat "{wp_ctr_file}" 2>/dev/null || echo 0)\n'
        f'  mapfile -t statuses < "{wp_seq_file}"\n'
        "  idx=$ctr\n"
        "  if (( idx >= ${#statuses[@]} )); then idx=$(( ${#statuses[@]} - 1 )); fi\n"
        f'  echo $(( ctr + 1 )) > "{wp_ctr_file}"\n'
        f'  echo "[{{\\"commit\\": \\"{head_sha}\\", \\"status\\": \\"${{statuses[$idx]}}\\"}}]"\n'
        "fi\n"
        "exit 0\n",
    )

    return {
        "GH_PR_MERGE_GH": str(bin_dir / "gh"),
        "GH_PR_MERGE_GIT": str(bin_dir / "git"),
        "GH_PR_MERGE_CURL": str(bin_dir / "curl"),
        "_call_log": call_log,
    }


def _run(
    cwd: Path, stubs: dict, *args: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("GH_PR_MERGE_STRICT_DELETIONS", None)  # host setting must not leak in
    # A real WOODPECKER_API_TOKEN/SERVER on the host must never leak into a test -
    # it would make the #717 queue-wait code hit the real Woodpecker server
    # instead of the stub (issue #716/#717 test isolation).
    env.pop("WOODPECKER_API_TOKEN", None)
    env.pop("WOODPECKER_SERVER", None)
    if extra_env:
        env.update(extra_env)
    env["GH_PR_MERGE_GH"] = stubs["GH_PR_MERGE_GH"]
    env["GH_PR_MERGE_GIT"] = stubs["GH_PR_MERGE_GIT"]
    env["GH_PR_MERGE_CURL"] = stubs["GH_PR_MERGE_CURL"]
    env["GH_PR_MERGE_POLL_DELAY"] = "0"  # keep the mergeability poll instant in tests
    env["GH_PR_MERGE_BASE_RETRY_DELAY"] = "0"  # keep the base-modified retry instant too
    env["GH_PR_MERGE_CHECK_DELAY"] = "0"  # and the #577 required-check wait
    env["GH_PR_MERGE_CHECK_ATTEMPTS"] = "3"  # bounded, so the timeout path is testable
    env["GH_PR_MERGE_QUEUE_WAIT_DELAY"] = "0"  # and the #717 queue-wait budget
    env["GH_PR_MERGE_QUEUE_WAIT_ATTEMPTS"] = "3"  # bounded, so the timeout path is testable
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        check=False,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _linked_worktree(tmp_path: Path) -> Path:
    """A cwd whose .git is a FILE - what a linked/native worktree looks like."""
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: /repo/.git/worktrees/wt\n")
    return wt


def _primary_repo(tmp_path: Path) -> Path:
    """A cwd whose .git is a DIRECTORY - the primary checkout."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def _calls(stubs: dict) -> list[str]:
    log = stubs["_call_log"]
    return log.read_text().splitlines() if log.exists() else []


def _merge_argvs(tmp_path: Path) -> list[list[str]]:
    """Exact argv of each `gh pr merge` call, recovered from the NUL dumps.

    Unlike the space-joined call log, these preserve argument BOUNDARIES, so a
    multiline --body can be asserted to have arrived as one argument (#655).
    """
    argvs: list[list[str]] = []
    n = 0
    while (dump := tmp_path / f"merge_argv_{n}").exists():
        argvs.append(dump.read_bytes().decode().split("\0")[:-1])
        n += 1
    return argvs


def test_script_is_executable():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK), "gh-pr-merge.sh must be executable"


def test_usage_error_without_args(tmp_path: Path):
    stubs = _make_stubs(tmp_path)
    result = _run(_primary_repo(tmp_path), stubs, "42")  # missing branch
    assert result.returncode == 2
    assert "Usage" in result.stderr


def test_linked_worktree_omits_delete_branch_and_deletes_remote(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 0, result.stderr
    calls = _calls(stubs)
    merge = next(c for c in calls if c.startswith("gh pr merge"))
    assert "--delete-branch" not in merge, "linked worktree must NOT pass --delete-branch"
    assert "--squash" in merge
    # Remote branch deleted by us, not by gh.
    assert any(c == "git push origin --delete issue-461-fix" for c in calls), calls


def test_primary_repo_keeps_delete_branch(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_primary_repo(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 0, result.stderr
    calls = _calls(stubs)
    merge = next(c for c in calls if c.startswith("gh pr merge"))
    assert "--delete-branch" in merge, "primary repo must keep --delete-branch"
    # We must NOT issue a manual remote-branch delete in the primary repo.
    assert not any("push origin --delete" in c for c in calls), calls


def test_nonzero_gh_but_merged_is_success(tmp_path: Path):
    # The exact #461 trap: gh exits non-zero on the local post-merge step, but the
    # remote squash succeeded (PR is MERGED). Must be treated as success.
    stubs = _make_stubs(tmp_path, merge_exit=1, pr_state="MERGED")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout


def test_genuinely_unmerged_returns_failure(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=1, pr_state="OPEN")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 1
    assert "did not merge" in result.stderr


def test_primary_repo_nonzero_but_merged_is_success(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=1, pr_state="MERGED")
    result = _run(_primary_repo(tmp_path), stubs, "42", "issue-461-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout


def test_transient_unknown_then_mergeable_proceeds(tmp_path: Path):
    # Issue #485: right after a push, mergeable is UNKNOWN for a beat, then
    # resolves to MERGEABLE. The poll must wait it out and still merge.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        mergeable=["UNKNOWN", "UNKNOWN", "MERGEABLE"],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-485-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    calls = _calls(stubs)
    # Polled mergeability more than once (waited out the transient) ...
    poll_calls = [c for c in calls if c.startswith("gh pr view") and "mergeable" in c]
    assert len(poll_calls) >= 2, calls
    # ... and did go on to attempt the squash-merge.
    assert any(c.startswith("gh pr merge") for c in calls), calls


def test_conflicting_stops_before_merge(tmp_path: Path):
    # A genuinely CONFLICTING PR must stop with a clear message and never attempt
    # the merge.
    stubs = _make_stubs(tmp_path, mergeable="CONFLICTING")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-485-fix")
    assert result.returncode == 1
    assert "CONFLICTING" in result.stderr
    calls = _calls(stubs)
    assert not any(c.startswith("gh pr merge") for c in calls), "must not merge a CONFLICTING PR"


def test_persistent_unknown_fails_open_and_merges(tmp_path: Path):
    # If mergeability never resolves (stays UNKNOWN through every attempt), fail
    # open: attempt the merge anyway and let the post-merge MERGED check decide.
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED", mergeable="UNKNOWN")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-485-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    assert "UNKNOWN" in result.stderr  # surfaced the fail-open note
    calls = _calls(stubs)
    # Exhausted the default 5 attempts, then merged anyway.
    poll_calls = [c for c in calls if c.startswith("gh pr view") and "mergeable" in c]
    assert len(poll_calls) == 5, poll_calls
    assert any(c.startswith("gh pr merge") for c in calls), calls


# The exact stderr GitHub returns when a sibling PR merged in the poll->merge
# race window (issue #502).
BASE_MODIFIED = (
    "X Pull request #42 is not mergeable: "
    "Base branch was modified. Review and try the merge again."
)


def test_base_modified_retries_then_succeeds(tmp_path: Path):
    # Issue #502: the squash fails because the base moved under us; a refetch +
    # single retry succeeds (the live-observed shape). Must not report failure.
    stubs = _make_stubs(
        tmp_path,
        pr_state="MERGED",
        merge_outcomes=[(1, BASE_MODIFIED), (0, "")],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-502-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    calls = _calls(stubs)
    merge_calls = [c for c in calls if c.startswith("gh pr merge")]
    assert len(merge_calls) == 2, merge_calls
    # Refetched the base before re-attempting the squash.
    assert any(c == "git fetch origin" for c in calls), calls


def test_base_modified_bounded_retries_then_fails(tmp_path: Path):
    # A persistent base-modified error must stop after the BOUNDED retries
    # (1 initial + 2 by default), with the MERGED-state check reporting the
    # genuine failure - never an unbounded loop.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        merge_outcomes=[(1, BASE_MODIFIED)],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-502-fix")
    assert result.returncode == 1
    assert "did not merge" in result.stderr
    calls = _calls(stubs)
    merge_calls = [c for c in calls if c.startswith("gh pr merge")]
    assert len(merge_calls) == 3, merge_calls


def test_other_merge_failure_does_not_retry(tmp_path: Path):
    # Only the base-modified race is retried; any other merge failure keeps the
    # single-attempt behavior (the MERGED-state check remains the arbiter).
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        merge_outcomes=[(1, "GraphQL: Pull Request is not mergeable (mergePullRequest)")],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-502-fix")
    assert result.returncode == 1
    calls = _calls(stubs)
    merge_calls = [c for c in calls if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls


def test_flow_commands_wire_the_helper():
    # Both merge surfaces must call the guard (helper preferred, inline fallback),
    # not the raw `gh pr merge --squash --delete-branch` that trips #461.
    for rel in (".claude/commands/flow/auto.md", ".claude/commands/flow/merge.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "gh-pr-merge.sh" in text, f"{rel} must reference the merge helper"
        # The inline fallback keeps the linked-worktree guard even without the helper.
        assert "git push origin --delete" in text, f"{rel} missing remote-branch delete fallback"
        assert "MERGED" in text, f"{rel} must verify PR state, not just the exit code"


# The stderr GitHub returns when branch protection blocks a merge (issue #517):
# the sole-owner case is a required review that cannot be satisfied.
PROTECTION_BLOCKED = (
    "failed to merge pull request: GraphQL: At least 1 approving review is "
    "required by reviewers with write access. (mergePullRequest)"
)


def test_admin_flag_passthrough_primary_repo(tmp_path: Path):
    # Issue #517: --admin opt-in forces the override from the first attempt; the
    # primary repo still keeps --delete-branch. One merge call, no auto-retry.
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_primary_repo(tmp_path), stubs, "--admin", "42", "issue-517-fix")
    assert result.returncode == 0, result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls
    assert "--admin" in merge_calls[0]
    assert "--delete-branch" in merge_calls[0]


def test_admin_flag_passthrough_linked_worktree(tmp_path: Path):
    # --admin in a linked worktree carries --admin but NOT --delete-branch (the
    # #461 guard still applies); the remote branch is deleted by us.
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_linked_worktree(tmp_path), stubs, "--admin", "42", "issue-517-fix")
    assert result.returncode == 0, result.stderr
    calls = _calls(stubs)
    merge_calls = [c for c in calls if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls
    assert "--admin" in merge_calls[0]
    assert "--delete-branch" not in merge_calls[0]
    assert any(c == "git push origin --delete issue-517-fix" for c in calls), calls


def test_review_block_at_squash_clean_stops_never_admin(tmp_path: Path):
    # Issue #579 (rewrite of the old #517 pin, whose stub message IS the
    # review-required message): a review-blocked squash is a CLEAN STOP (exit 3),
    # never an automatic --admin bypass - even for a repo admin. Exactly one
    # merge attempt, zero --admin retries.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        viewer_permission="ADMIN",
        merge_outcomes=[(1, PROTECTION_BLOCKED)],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-579-fix")
    assert result.returncode == 3, result.stderr
    assert "CLEAN STOP" in result.stderr
    assert "/flow:merge" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls
    assert not any("--admin" in c for c in merge_calls)


def test_review_block_non_admin_same_clean_stop(tmp_path: Path):
    # The clean stop does not depend on actor permission: a non-admin hits the
    # identical handoff (previously this was a bare exit-1 "failure").
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        viewer_permission="WRITE",
        merge_outcomes=[(1, PROTECTION_BLOCKED)],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-579-fix")
    assert result.returncode == 3
    assert "CLEAN STOP" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls
    assert not any("--admin" in c for c in merge_calls)


ADMIN_PROTECTION_BLOCKED = (
    "failed to merge pull request: GraphQL: You're not authorized to push to "
    "this branch. (mergePullRequest)"
)


def test_administrative_block_admin_still_retries_with_admin(tmp_path: Path):
    # The #517 residual survives #579's narrowing: an ADMINISTRATIVE protection
    # block (no review, no required check being bypassed) still gets the single
    # admin-gated --admin retry.
    stubs = _make_stubs(
        tmp_path,
        pr_state="MERGED",
        viewer_permission="ADMIN",
        merge_outcomes=[(1, ADMIN_PROTECTION_BLOCKED), (0, "")],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-517-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 2, merge_calls
    assert "--admin" not in merge_calls[0], "first attempt must not force --admin"
    assert "--admin" in merge_calls[1], "administrative-block retry must add --admin"


def test_administrative_block_non_admin_does_not_retry(tmp_path: Path):
    # A non-admin actor cannot use --admin, so the administrative block is left
    # to the MERGED-state check (genuine failure). No --admin retry is attempted.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        viewer_permission="WRITE",
        merge_outcomes=[(1, ADMIN_PROTECTION_BLOCKED)],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-517-fix")
    assert result.returncode == 1
    assert "did not merge" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls
    assert not any("--admin" in c for c in merge_calls)


def test_review_required_pre_gate_stops_before_any_merge(tmp_path: Path):
    # Issue #579, the primary path: reviewDecision REVIEW_REQUIRED is detected
    # BEFORE the squash - clean stop, ZERO merge attempts, actionable handoff.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        review_decision="REVIEW_REQUIRED",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-579-fix")
    assert result.returncode == 3
    assert "CLEAN STOP" in result.stderr
    assert "REVIEW_REQUIRED" in result.stderr
    assert "/flow:merge" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert merge_calls == [], "the review gate must stop before any merge attempt"


def test_changes_requested_pre_gate_stops(tmp_path: Path):
    # CHANGES_REQUESTED is the same handoff family as REVIEW_REQUIRED.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        review_decision="CHANGES_REQUESTED",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-579-fix")
    assert result.returncode == 3
    assert "CHANGES_REQUESTED" in result.stderr
    assert not [c for c in _calls(stubs) if c.startswith("gh pr merge")]


def test_admin_flag_skips_review_gate(tmp_path: Path):
    # An explicit, human-typed --admin is the conscious override (issue #579):
    # it skips the review gate and the merge proceeds.
    stubs = _make_stubs(
        tmp_path,
        pr_state="MERGED",
        review_decision="REVIEW_REQUIRED",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "--admin", "42", "issue-579-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert merge_calls, "explicit --admin must proceed to the merge"
    assert "--admin" in merge_calls[0]


def test_empty_review_decision_fails_open_and_merges(tmp_path: Path):
    # A repo without review protection returns an empty reviewDecision - the
    # gate fails open and the merge proceeds (GitHub enforces server-side).
    stubs = _make_stubs(
        tmp_path,
        pr_state="MERGED",
        review_decision="",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-579-fix")
    assert result.returncode == 0, result.stderr
    assert [c for c in _calls(stubs) if c.startswith("gh pr merge")]


def test_non_protection_failure_no_admin_retry(tmp_path: Path):
    # Only a branch-protection block triggers the --admin override. A different
    # merge failure must not, even when the actor is a repo admin.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        viewer_permission="ADMIN",
        merge_outcomes=[(1, "GraphQL: Pull Request is not mergeable (mergePullRequest)")],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-517-fix")
    assert result.returncode == 1
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls
    assert not any("--admin" in c for c in merge_calls)


# --- Required status checks are waited for, never overridden (issue #577) -----

WOODPECKER = "ci/woodpecker/pr/woodpecker"

# The stderr GitHub returns when the block is a required STATUS CHECK rather than
# a review - the family that must NOT trigger the #517 --admin auto-retry.
CHECK_BLOCKED = (
    "failed to merge pull request: GraphQL: Required status check "
    '"ci/woodpecker/pr/woodpecker" is expected. (mergePullRequest)'
)


def test_no_required_contexts_skips_the_wait(tmp_path: Path):
    # An unprotected base branch (or one with no required checks) must behave
    # exactly as before #577: no rollup polling, straight to the squash.
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED", required_contexts=[])
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-577-fix")
    assert result.returncode == 0, result.stderr
    assert not any("statusCheckRollup" in c for c in _calls(stubs)), "must not poll checks"


def test_waits_for_pending_required_check_then_merges(tmp_path: Path):
    # The core #577 case: the squash is attempted the instant after a push, so the
    # required check is still PENDING. Wait for it, then merge - do not --admin
    # past it.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        required_contexts=[WOODPECKER],
        check_rollup=[
            [(WOODPECKER, "PENDING")],
            [(WOODPECKER, "PENDING")],
            [(WOODPECKER, "SUCCESS")],
        ],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-577-fix")
    assert result.returncode == 0, result.stderr
    assert "waiting for required status check" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls
    assert "--admin" not in merge_calls[0]


def test_red_required_check_stops_without_merging(tmp_path: Path):
    # A genuinely failing required check is a hard stop: never attempt the merge,
    # never reach for --admin.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        viewer_permission="ADMIN",
        required_contexts=[WOODPECKER],
        check_rollup=[[(WOODPECKER, "FAILURE")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-577-fix")
    assert result.returncode == 1
    assert "RED" in result.stderr
    assert not any(c.startswith("gh pr merge") for c in _calls(stubs)), "must not merge"


def test_required_check_that_never_reports_times_out_without_merging(tmp_path: Path):
    # A required context missing from the rollup entirely (skipped pipeline,
    # renamed context) must time out into a stop that names the break-glass -
    # not into a silent --admin merge.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        viewer_permission="ADMIN",
        required_contexts=[WOODPECKER],
        check_rollup=[[]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-577-fix")
    assert result.returncode == 1
    assert "never reported" in result.stderr
    assert "--admin" in result.stderr, "the stop must name the documented break-glass"
    assert not any(c.startswith("gh pr merge") for c in _calls(stubs)), "must not merge"


def test_explicit_admin_skips_the_check_wait(tmp_path: Path):
    # An explicit --admin is a conscious owner override, so it bypasses the wait -
    # otherwise the break-glass would be blocked by the very check it overrides.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        required_contexts=[WOODPECKER],
        check_rollup=[[(WOODPECKER, "FAILURE")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "--admin", "42", "issue-577-fix")
    assert result.returncode == 0, result.stderr
    assert not any("statusCheckRollup" in c for c in _calls(stubs))


def test_required_check_block_does_not_trigger_admin_retry(tmp_path: Path):
    # The #577 narrowing of the #517 auto-retry: when the squash is rejected by a
    # required STATUS CHECK, an admin actor must NOT be auto-escalated to --admin -
    # that would defeat the required check on every run. (A review block still is;
    # see test_protection_block_admin_retries_with_admin above.)
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        viewer_permission="ADMIN",
        required_contexts=[WOODPECKER],
        check_rollup=[[(WOODPECKER, "SUCCESS")]],
        merge_outcomes=[(1, CHECK_BLOCKED)],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-577-fix")
    assert result.returncode == 1
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, merge_calls
    assert not any("--admin" in c for c in merge_calls)
    assert "NOT retrying" in result.stderr


def test_check_run_conclusion_shape_is_understood(tmp_path: Path):
    # The rollup mixes commit STATUSes (context/state) with CHECK RUNs
    # (name/conclusion). A green check run must satisfy the required context, or
    # a GitHub-Actions-style required check would wait forever.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        required_contexts=["build"],
        check_rollup=[[("build", "SUCCESS")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-577-fix")
    assert result.returncode == 0, result.stderr


def test_neutral_and_skipped_states_count_as_green(tmp_path: Path):
    # GitHub treats NEUTRAL/SKIPPED as satisfying a required check; mirroring that
    # keeps a conditionally-skipped pipeline from deadlocking every PR.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        required_contexts=[WOODPECKER],
        check_rollup=[[(WOODPECKER, "SKIPPED")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-577-fix")
    assert result.returncode == 0, result.stderr


# --- Contexts that cannot be enumerated never become a hard stop (issue #610) --
#
# The #577 resolver read ONE endpoint (classic branch protection) and discarded
# its exit code. `gh api` prints an error body on STDOUT with --jq unapplied, so a
# 404 became a "required context" named after the JSON itself - unreportable by
# construction - and the wait timed out into a refusal. It fired two ways: on a
# repo with no protection at all, and on one guarded by a RULESET, which the
# legacy endpoint cannot see. 25 flow:auto runs, ~4h of wall-clock, every one
# ending in a manual `gh pr merge --squash`.


def test_unprotected_base_skips_the_wait_entirely(tmp_path: Path):
    # No protection of EITHER kind: classic 404s, the rulesets endpoint answers
    # with an empty list. That is a definitive "nothing is required", so the wait
    # must be skipped outright - not merely survived. Zero rollup polls.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        protection_ok=False,
        ruleset_contexts=[],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 0, result.stderr
    assert not any("statusCheckRollup" in c for c in _calls(stubs)), "must not poll checks"
    assert "never reported" not in result.stderr


def test_error_body_is_never_treated_as_a_required_context(tmp_path: Path):
    # The regression itself: with BOTH endpoints erroring, the 404 payload must
    # not surface as a context to wait for. Pre-#610 this produced
    #   waiting for required status check(s): {"message":"Branch not protected"...}
    # followed by a timeout refusal.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        protection_ok=False,
        ruleset_ok=False,
        check_rollup=[[]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 0, result.stderr
    assert "Branch not protected" not in result.stderr, "an error body is not a context"
    assert "never reported" not in result.stderr


def test_ruleset_required_context_is_resolved_and_waited_for(tmp_path: Path):
    # The now-dominant shape: classic protection 404s because the branch is
    # guarded by a RULESET. The context must still be found - and waited on - via
    # the rulesets endpoint, or the posture would be silently skipped.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        protection_ok=False,
        ruleset_contexts=[WOODPECKER],
        check_rollup=[[(WOODPECKER, "PENDING")], [(WOODPECKER, "SUCCESS")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 0, result.stderr
    assert "waiting for required status check" in result.stderr
    assert WOODPECKER in result.stderr
    assert any("/rules/branches/" in c for c in _calls(stubs)), "must consult the rulesets API"


def test_ruleset_required_context_that_is_red_stops(tmp_path: Path):
    # A ruleset-declared context is exactly as binding as a classic one.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        protection_ok=False,
        ruleset_contexts=[WOODPECKER],
        check_rollup=[[(WOODPECKER, "FAILURE")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 1
    assert "RED" in result.stderr
    assert not any(c.startswith("gh pr merge") for c in _calls(stubs)), "must not merge"


def test_classic_protection_survives_an_unreadable_rulesets_endpoint(tmp_path: Path):
    # Older GHES, or a token without the scope: the rulesets call fails. Classic
    # protection answered, so its contexts still bind - the new source is additive,
    # never a precondition.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        required_contexts=[WOODPECKER],
        ruleset_ok=False,
        check_rollup=[[(WOODPECKER, "FAILURE")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 1
    assert "RED" in result.stderr


def test_contexts_from_both_mechanisms_are_unioned(tmp_path: Path):
    # A repo can carry classic protection AND a ruleset. Every declared context
    # binds, so greening only one of them must not release the merge.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        required_contexts=["build"],
        ruleset_contexts=[WOODPECKER],
        check_rollup=[[("build", "SUCCESS")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 1
    assert "never reported" in result.stderr
    assert WOODPECKER in result.stderr
    assert not any(c.startswith("gh pr merge") for c in _calls(stubs)), "must not merge"


def test_context_declared_by_both_mechanisms_is_waited_on_once(tmp_path: Path):
    # The same context from both sources must dedupe, not double.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        required_contexts=[WOODPECKER],
        ruleset_contexts=[WOODPECKER],
        check_rollup=[[(WOODPECKER, "PENDING")], [(WOODPECKER, "SUCCESS")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 0, result.stderr
    waiting = next(ln for ln in result.stderr.splitlines() if "waiting for required" in ln)
    assert waiting.count(WOODPECKER) == 1, waiting


def test_unresolvable_contexts_with_green_checks_merges(tmp_path: Path):
    # Neither mechanism readable, but the PR itself reports a terminal green
    # check. Observed reality outranks a failed enumeration: merge.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        protection_ok=False,
        ruleset_ok=False,
        check_rollup=[[(WOODPECKER, "SUCCESS")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 0, result.stderr
    assert "never reported" not in result.stderr


def test_unresolvable_contexts_with_red_check_stops(tmp_path: Path):
    # The one case that still stops when nothing could be enumerated: a check the
    # PR reports as genuinely red is authoritative on its own.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        protection_ok=False,
        ruleset_ok=False,
        check_rollup=[[(WOODPECKER, "FAILURE")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 1
    assert "RED" in result.stderr
    assert not any(c.startswith("gh pr merge") for c in _calls(stubs)), "must not merge"


def test_unresolvable_contexts_with_pending_checks_fails_open(tmp_path: Path):
    # Pending forever, with the posture never enumerable: wait out the budget,
    # then ATTEMPT the merge. GitHub enforces any ruleset server-side at squash
    # time, so a client-side guess must not be what blocks the PR.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        protection_ok=False,
        ruleset_ok=False,
        check_rollup=[[(WOODPECKER, "PENDING")]],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-610-fix")
    assert result.returncode == 0, result.stderr
    assert "still pending" in result.stderr
    assert any(c.startswith("gh pr merge") for c in _calls(stubs)), "must attempt the merge"


def test_every_refusal_to_merge_exits_non_zero(tmp_path: Path):
    # A refusal that exits 0 is worse than a false STOP: /flow:auto Step 7 trusts
    # the exit code, so a phantom success carries the run into Step 8 against an
    # unmerged PR. Pin every path that declines to merge.
    refusals = {
        "conflicting": {"mergeable": "CONFLICTING", "pr_state": "OPEN"},
        "red required check": {
            "pr_state": "OPEN",
            "required_contexts": [WOODPECKER],
            "check_rollup": [[(WOODPECKER, "FAILURE")]],
        },
        "required check never reports": {
            "pr_state": "OPEN",
            "required_contexts": [WOODPECKER],
            "check_rollup": [[]],
        },
        "red check, contexts unresolvable": {
            "pr_state": "OPEN",
            "protection_ok": False,
            "ruleset_ok": False,
            "check_rollup": [[(WOODPECKER, "FAILURE")]],
        },
        "squash failed, PR not merged": {"merge_exit": 1, "pr_state": "OPEN"},
    }
    for label, kwargs in refusals.items():
        case_dir = tmp_path / label.replace(" ", "_").replace(",", "")
        case_dir.mkdir()
        stubs = _make_stubs(case_dir, **kwargs)  # type: ignore[arg-type]
        result = _run(_linked_worktree(case_dir), stubs, "42", "issue-610-fix")
        assert result.returncode != 0, f"{label}: refused to merge but exited 0"


# The shape GitHub's rulesets API actually returns, so the jq filter in the script
# is pinned against real data rather than against the stub's post-jq shortcut.
REAL_RULESET_PAYLOAD = """[
  {"type": "deletion", "ruleset_source_type": "Repository", "ruleset_id": 1},
  {"type": "non_fast_forward", "ruleset_source_type": "Repository", "ruleset_id": 1},
  {"type": "pull_request", "ruleset_id": 1,
   "parameters": {"required_approving_review_count": 0, "dismiss_stale_reviews_on_push": false}},
  {"type": "required_status_checks", "ruleset_id": 1,
   "parameters": {"do_not_enforce_on_create": false,
                  "strict_required_status_checks_policy": false,
                  "required_status_checks": [
                    {"context": "ci/woodpecker/pr/woodpecker", "integration_id": null}]}}
]"""


def _ruleset_jq_filter() -> str:
    """The rulesets jq filter, read out of the script so the test cannot drift."""
    import re

    match = re.search(
        r"\[\.\[\] \| select\(\.type == \"required_status_checks\"\).*?\| unique \| \.\[\]",
        SCRIPT.read_text(),
        re.DOTALL,
    )
    assert match, "could not locate the rulesets jq filter in gh-pr-merge.sh"
    return match.group(0)


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_ruleset_jq_filter_extracts_contexts_from_the_real_shape():
    result = subprocess.run(
        ["jq", "-r", _ruleset_jq_filter()],
        input=REAL_RULESET_PAYLOAD,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["ci/woodpecker/pr/woodpecker"]


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_ruleset_jq_filter_is_empty_when_no_rule_requires_checks():
    # A branch with rules but no required-checks rule, and a branch with no rules
    # at all, must both yield nothing - and, crucially, exit 0 so the lookup counts
    # as ANSWERED (that is what separates "nothing required" from "unreadable").
    for payload in ("[]", '[{"type": "pull_request", "parameters": {}}]'):
        result = subprocess.run(
            ["jq", "-r", _ruleset_jq_filter()],
            input=payload,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert result.returncode == 0, f"{payload}: {result.stderr}"
        assert result.stdout.strip() == "", payload


# Explicit squash subject/body (issue #655): with no --subject, GitHub may title
# the squash commit from the branch's FIRST commit - and #635's commit-first
# stale-base handling makes WIP-first branches routine, so finished features
# landed on main as "WIP: ...". The helper now derives --subject/--body from the
# PR itself; on a failed or empty title read it fails OPEN, omitting BOTH flags
# together (never one without the other) and merging exactly as before.

# Deliberately multiline WITH a line starting with "-": pins that the body is
# passed as ONE quoted argument, never re-parsed as flags (gate condition 2).
MULTILINE_BODY = (
    "Summary of the fix.\n"
    "\n"
    "- WIP-first branches are routine since #635\n"
    "- the squash subject now comes from the PR title\n"
    "\n"
    "Closes #655"
)


def test_squash_passes_pr_title_and_body_explicitly(tmp_path: Path):
    # The default path: subject is "<PR title> (#N)" (the web squash-button
    # convention) and the body is the PR body, byte-exact, as single arguments.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_title="fix(flow): stop WIP squash subjects",
        pr_body=MULTILINE_BODY,
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-655-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    assert len(argvs) == 1, argvs
    argv = argvs[0]
    assert argv[argv.index("--subject") + 1] == "fix(flow): stop WIP squash subjects (#42)"
    assert argv[argv.index("--body") + 1] == MULTILINE_BODY


def test_empty_title_omits_subject_and_body_together(tmp_path: Path):
    # An empty title read fails open: BOTH flags are omitted (never --body
    # alone) and the merge proceeds exactly as pre-#655.
    stubs = _make_stubs(
        tmp_path, merge_exit=0, pr_state="MERGED", pr_body=MULTILINE_BODY
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-655-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    assert len(argvs) == 1, argvs
    assert "--subject" not in argvs[0]
    assert "--body" not in argvs[0]


def test_title_fetch_failure_fails_open_and_merges(tmp_path: Path):
    # A FAILED title read (API hiccup) is the same fail-open: no flags, and the
    # merge is never blocked by the metadata read.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_title="fix(flow): never used",
        pr_body=MULTILINE_BODY,
        title_ok=False,
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-655-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    assert len(argvs) == 1, argvs
    assert "--subject" not in argvs[0]
    assert "--body" not in argvs[0]


# Deletion surfacing + post-merge completeness (issue #657): a collapse onto a
# moved base silently records deletions of a sibling's merged work, and every
# downstream check passes because the damaged tree is internally CONSISTENT -
# nothing verified it was COMPLETE. The helper now surfaces the PR's deletions
# BEFORE the squash (greppable marker, opt-in strict clean stop, exit 4) and
# verifies AFTER a confirmed merge that the landed squash touched only paths in
# the PR's file list (loud on violation, never exit-code-changing). Both are
# fail-open per component: unreadable input prints `skipped`, never silence.


def test_deletions_surfaced_and_merge_proceeds(tmp_path: Path):
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_deletions=["retired/old.py", "docs/gone.md"],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-657-fix")
    assert result.returncode == 0, result.stderr
    assert "GH_PR_MERGE_DELETIONS: 2 retired/old.py docs/gone.md" in result.stdout
    assert "confirm they are" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert len(merge_calls) == 1, "surfacing alone must never block the merge"


def test_no_deletions_prints_zero_marker(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-657-fix")
    assert result.returncode == 0, result.stderr
    assert "GH_PR_MERGE_DELETIONS: 0" in result.stdout


def test_strict_deletions_is_clean_pre_squash_stop(tmp_path: Path):
    # Exit 4: a documented CLEAN STOP - the PR is left open and UNTOUCHED
    # (no merge attempt at all), mirroring the #579 exit-3 handoff semantics.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        pr_deletions=["lib/feature.py"],
    )
    result = _run(
        _linked_worktree(tmp_path),
        stubs,
        "42",
        "issue-657-fix",
        extra_env={"GH_PR_MERGE_STRICT_DELETIONS": "1"},
    )
    assert result.returncode == 4, result.stderr
    assert "GH_PR_MERGE_DELETIONS: 1 lib/feature.py" in result.stdout
    assert "CLEAN STOP" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert merge_calls == [], "strict stop must leave the PR untouched"


def test_negated_close_keyword_refuses_before_squash(tmp_path: Path):
    # Exit 5: a documented CLEAN STOP - the PR is left open and UNTOUCHED.
    # Zero merge calls pins the #726 guard ahead of both run_squash call sites.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        pr_title="docs: clarify follow-up scope",
        pr_body="Does not close #99",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-726-fix")
    assert result.returncode == 5, result.stderr
    assert "CLEAN STOP" in result.stderr
    assert "#99" in result.stderr
    assert "Does not close #99" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert merge_calls == [], "negated-close stop must leave the PR untouched"


def test_plain_close_keyword_passes(tmp_path: Path):
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_title="fix: complete issue work",
        pr_body="Closes #99",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-726-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    assert any(c.startswith("gh pr merge") for c in _calls(stubs))


def test_negated_close_override_flag_bypasses_guard(tmp_path: Path):
    # The per-merge override proceeds, but detection and consumption stay loud
    # so the exceptional decision remains visible in the merge transcript.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_title="docs: clarify follow-up scope",
        pr_body="Does not close #99",
    )
    result = _run(
        _linked_worktree(tmp_path),
        stubs,
        "--allow-negated-close",
        "42",
        "issue-726-fix",
    )
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    assert "#99" in result.stderr
    assert "Does not close #99" in result.stderr
    assert "override consumed: --allow-negated-close bypassed" in result.stderr
    assert any(c.startswith("gh pr merge") for c in _calls(stubs))


def test_negated_close_colon_form_refuses(tmp_path: Path):
    # GitHub's own matcher accepts the colon form ("Fixes: #123" auto-closes),
    # so the guard's `:?` tolerance must catch a negated colon-form match too -
    # a gate condition on #726, pinned here rather than left implicit in the regex.
    stubs = _make_stubs(
        tmp_path,
        pr_state="OPEN",
        pr_title="docs: clarify follow-up scope",
        pr_body="does not close: #42",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-726-fix")
    assert result.returncode == 5, result.stderr
    assert "CLEAN STOP" in result.stderr
    assert "#42" in result.stderr
    merge_calls = [c for c in _calls(stubs) if c.startswith("gh pr merge")]
    assert merge_calls == [], "negated colon-form stop must leave the PR untouched"


def test_plain_close_colon_form_passes(tmp_path: Path):
    # Companion to the refusal above: a non-negated colon-form close keyword
    # ("Fixes: #123", GitHub's own documented syntax) must merge normally.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_title="fix: complete issue work",
        pr_body="Fixes: #42",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-726-fix")
    assert result.returncode == 0, result.stderr
    assert "merged" in result.stdout
    assert any(c.startswith("gh pr merge") for c in _calls(stubs))


def test_unreadable_deletion_diff_fails_open_as_skipped(tmp_path: Path):
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_deletions=["never-read.py"],
        deletions_ok=False,
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-657-fix")
    assert result.returncode == 0, result.stderr
    assert "GH_PR_MERGE_DELETIONS: skipped" in result.stdout
    assert "merged" in result.stdout


def test_completeness_ok_when_landed_paths_match_file_list(tmp_path: Path):
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        merge_commit="abc1234def",
        pr_files=["lib/x.py", "tests/test_x.py"],
        landed_paths=["lib/x.py", "tests/test_x.py"],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-657-fix")
    assert result.returncode == 0, result.stderr
    assert "GH_PR_MERGE_COMPLETENESS: ok" in result.stdout


def test_completeness_violation_is_loud_but_exit_zero(tmp_path: Path):
    # Condition pin: the merge already landed, so a violation NEVER flips the
    # exit code - loud, never obstructive.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        merge_commit="abc1234def",
        pr_files=["lib/x.py"],
        landed_paths=["lib/x.py", "ui/rogue.js"],
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-657-fix")
    assert result.returncode == 0, result.stderr
    assert "GH_PR_MERGE_COMPLETENESS: violation" in result.stdout
    assert "ui/rogue.js" in result.stderr
    assert "merged" in result.stdout


def test_completeness_unreadable_inputs_fail_open_as_skipped(tmp_path: Path):
    # No mergeCommit resolvable (and no file list): each is independently a
    # skipped, never silence and never a failure.
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-657-fix")
    assert result.returncode == 0, result.stderr
    assert "GH_PR_MERGE_COMPLETENESS: skipped" in result.stdout


# --- Tested-tree trailer (issue #716) ------------------------------------
#
# When the PR branch was up to date with its base at squash time, a
# self-verifying `Woodpecker-Tested-Tree: <hash>` trailer is appended so the
# consumer (poker-measure's push pipeline) can skip the full suite by
# recomputing the same hash on what it actually checked out. Default
# (`pr_up_to_date=False`, exercised by every prior test in this file) is the
# safe no-trailer path - proven by the full pre-#716 suite passing unchanged.


def test_tested_tree_trailer_appended_when_up_to_date(tmp_path: Path):
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_up_to_date=True,
        tested_tree="cafef00dcafef00dcafef00dcafef00dcafef00d",
        pr_title="fix(flow): add tested-tree trailer",
        pr_body="Summary.",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-716-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    assert len(argvs) == 1, argvs
    body = argvs[0][argvs[0].index("--body") + 1]
    assert body == "Summary.\n\nWoodpecker-Tested-Tree: cafef00dcafef00dcafef00dcafef00dcafef00d"


def test_tested_tree_trailer_omitted_when_behind_base(tmp_path: Path):
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_up_to_date=False,
        pr_title="fix(flow): add tested-tree trailer",
        pr_body="Summary.",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-716-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    body = argvs[0][argvs[0].index("--body") + 1]
    assert body == "Summary."
    assert "Woodpecker-Tested-Tree" not in body


def test_tested_tree_trailer_alone_when_title_empty(tmp_path: Path):
    # The #655 fail-open path (no PR title) normally omits --subject/--body
    # TOGETHER - but when the tree is provably tested, the trailer still must
    # reach the squash message, so --body is passed alone.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_up_to_date=True,
        tested_tree="beadedbeadedbeadedbeadedbeadedbeadedbead",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-716-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    assert "--subject" not in argvs[0]
    assert argvs[0][argvs[0].index("--body") + 1] == "Woodpecker-Tested-Tree: beadedbeadedbeadedbeadedbeadedbeadedbead"


def test_tested_tree_trailer_omitted_with_empty_pr_body(tmp_path: Path):
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        pr_up_to_date=True,
        tested_tree="0000feed0000feed0000feed0000feed0000feed",
        pr_title="fix(flow): add tested-tree trailer",
        pr_body="",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-716-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    assert argvs[0][argvs[0].index("--body") + 1] == "Woodpecker-Tested-Tree: 0000feed0000feed0000feed0000feed0000feed"


def test_tested_tree_trailer_survives_admin_retry(tmp_path: Path):
    # The trailer rides BASE_FLAGS, so the #517 --admin retry carries it too.
    stubs = _make_stubs(
        tmp_path,
        pr_state="MERGED",
        viewer_permission="ADMIN",
        merge_outcomes=[(1, ADMIN_PROTECTION_BLOCKED), (0, "")],
        pr_up_to_date=True,
        tested_tree="1111feed1111feed1111feed1111feed1111feed",
        pr_title="fix(flow): add tested-tree trailer",
        pr_body="Summary.",
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-716-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    assert len(argvs) == 2, argvs
    for argv in argvs:
        body = argv[argv.index("--body") + 1]
        assert "Woodpecker-Tested-Tree: 1111feed1111feed1111feed1111feed1111feed" in body


# --- Woodpecker queue wait (issue #717) -----------------------------------
#
# WOODPECKER_API_TOKEN must be popped from the host env by `_run` and only
# reintroduced via `extra_env`, so every test in the rest of this file (which
# never sets it) exercises this feature's default no-op path implicitly - the
# full pre-#717 suite passing unchanged above is the proof.


def test_queue_wait_skipped_without_token(tmp_path: Path):
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-717-fix")
    assert result.returncode == 0, result.stderr
    assert not any(c.startswith("curl") for c in _calls(stubs)), "must not call curl without a token"
    assert "queued" not in result.stderr


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_queue_wait_polls_until_running_then_proceeds(tmp_path: Path):
    # woodpecker_repo_id()/woodpecker_pipeline_status() shell out to a real,
    # unstubbed `jq` (gh/git/curl are stubbed, but jq is not - see the module
    # docstring's `pr_up_to_date`/`woodpecker_*` note); the CI `validate` image
    # (uv:python3.11-bookworm-slim) ships none of git/docker/gitleaks/curl/jq,
    # so this must guard exactly like test_ruleset_jq_filter_* below (#716/#717
    # is what surfaced this: this dev box HAS jq, so it passed locally and only
    # went red in CI - the precise failure mode the binary-guard gate exists
    # for, #602).
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        woodpecker_pipeline_statuses=["pending", "pending", "running"],
    )
    result = _run(
        _linked_worktree(tmp_path),
        stubs,
        "42",
        "issue-717-fix",
        extra_env={"WOODPECKER_API_TOKEN": "test-token"},
    )
    assert result.returncode == 0, result.stderr
    assert "is queued" in result.stderr
    calls = _calls(stubs)
    pipeline_polls = [c for c in calls if "/pipelines?per_page=5" in c]
    assert len(pipeline_polls) == 3, calls
    # And the merge still proceeds after the queue clears.
    assert any(c.startswith("gh pr merge") for c in calls), calls


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_queue_wait_never_reports_running_still_proceeds(tmp_path: Path):
    # Bounded budget (GH_PR_MERGE_QUEUE_WAIT_ATTEMPTS=3 in tests): even if the
    # pipeline is STILL pending when the budget runs out, this is advisory -
    # fall through to the unchanged required-check poll rather than blocking.
    # Guarded for the same reason as the test above: without jq this would
    # pass VACUOUSLY (woodpecker_repo_id fails at the jq check, so the
    # exhaustion path it means to exercise never runs) rather than actually
    # proving the intended behavior - the CLAUDE.md "assert the precondition"
    # spirit, applied to a real binary instead of a constructed fixture.
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        woodpecker_pipeline_statuses=["pending"],
    )
    result = _run(
        _linked_worktree(tmp_path),
        stubs,
        "42",
        "issue-717-fix",
        extra_env={"WOODPECKER_API_TOKEN": "test-token"},
    )
    assert result.returncode == 0, result.stderr
    assert any(c.startswith("gh pr merge") for c in _calls(stubs))


def test_queue_wait_fails_open_on_unresolvable_repo(tmp_path: Path):
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        woodpecker_lookup_ok=False,
    )
    result = _run(
        _linked_worktree(tmp_path),
        stubs,
        "42",
        "issue-717-fix",
        extra_env={"WOODPECKER_API_TOKEN": "test-token"},
    )
    assert result.returncode == 0, result.stderr
    assert "is queued" not in result.stderr
    calls = _calls(stubs)
    assert not any("/pipelines?per_page=5" in c for c in calls), "must not poll pipelines on a failed lookup"
    assert any(c.startswith("gh pr merge") for c in calls)


def test_queue_wait_skipped_with_admin_flag(tmp_path: Path):
    # --admin skips the required-check wait AND the queue wait that precedes
    # it (issue #579's existing precedent, extended by #717).
    stubs = _make_stubs(
        tmp_path,
        merge_exit=0,
        pr_state="MERGED",
        woodpecker_pipeline_statuses=["pending"],
    )
    result = _run(
        _linked_worktree(tmp_path),
        stubs,
        "--admin",
        "42",
        "issue-717-fix",
        extra_env={"WOODPECKER_API_TOKEN": "test-token"},
    )
    assert result.returncode == 0, result.stderr
    assert not any(c.startswith("curl") for c in _calls(stubs)), "admin must skip the queue wait entirely"


def test_admin_retry_keeps_subject_and_body(tmp_path: Path):
    # The #517 administrative --admin retry routes through the same BASE_FLAGS,
    # so the retry carries the identical subject/body (gate condition 1c).
    stubs = _make_stubs(
        tmp_path,
        pr_state="MERGED",
        viewer_permission="ADMIN",
        merge_outcomes=[(1, ADMIN_PROTECTION_BLOCKED), (0, "")],
        pr_title="feat(flow): explicit squash subject",
        pr_body=MULTILINE_BODY,
    )
    result = _run(_linked_worktree(tmp_path), stubs, "42", "issue-655-fix")
    assert result.returncode == 0, result.stderr
    argvs = _merge_argvs(tmp_path)
    assert len(argvs) == 2, argvs
    for argv in argvs:
        assert argv[argv.index("--subject") + 1] == "feat(flow): explicit squash subject (#42)"
        assert argv[argv.index("--body") + 1] == MULTILINE_BODY
    assert "--admin" not in argvs[0]
    assert "--admin" in argvs[1]
