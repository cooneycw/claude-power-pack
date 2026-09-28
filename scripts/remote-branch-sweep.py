#!/usr/bin/env python3
"""remote-branch-sweep.py - classify every remote branch; delete only provably-landed ones (#1262).

WHY THIS EXISTS
---------------
The per-merge path stopped leaving branches behind in #848/#852: gh-pr-merge.sh
deletes the head branch itself and verifies it went. The backlog from before
that did not go anywhere - 101 remote branches besides `main` on 2026-09-28 -
and nothing owned it, because deleting a remote branch is destructive and a
branch can hold the only copy of someone's work.

So this is REPORT-FIRST. `report` classifies every branch and deletes nothing.
`plan` prints the per-branch decision the deleter would take. `delete` re-derives
every input of every decision per branch, immediately before that branch's
push - never from an earlier report - deletes only category (a), under a git
lease, and only through a checkout whose origin pushes to `--repo` itself. The
lease covers the tip alone; see `run_delete` for the window it does not cover.

THE AUTHORITY, STATED ONCE
--------------------------
The operator authorised the cleanup with "do 1262". The category rules below,
the 24-hour exclusion, and the never-main/never-protected rule are MASTER's
narrowing of that authorisation, adjusted for a repository that squash-merges.
They are not the operator's wording and are not quoted as such.

  (a) DELETABLE - a MERGED PR whose recorded head (`head.sha`) IS the branch's
      current tip, AND whose `merge_commit_sha` is reachable from the default
      branch's tip. "Contained in main" by ancestry is impossible after a squash
      (the branch's commits are rewritten onto main under new shas), so the
      nearest provable reading is: the exact commit GitHub recorded as merged is
      still the tip - nothing was pushed after the merge - and the merge commit
      itself is on main.
  (b) report only - its PR(s) were closed WITHOUT merging.
  (c) report only - no PR has ever used this branch.
  (d) report only - an OPEN PR uses it, or a worktree in a --checkout uses it.
  excluded - the default branch, a protected branch, a branch pushed in the
      last 24 hours, or a merged branch that fails (a)'s two extra conditions
      (moved after merge, or merge commit not on main).

"Pushed in the last 24 hours" is read from GitHub's repository activity API when
it answers (the push timestamps GitHub itself recorded) and from the tip
commit's committer date otherwise; when both answer, the NEWER one decides. The
source is printed per branch. The committer date alone never licenses a
deletion: it cannot see a push (a branch recreated today at an old commit keeps
that commit's date), so a branch whose activity record does not answer is
excluded, not deleted.

WHAT THIS CANNOT SEE
--------------------
A worktree on another host. `--checkout` scans only the checkouts it is given,
and the report says how many it scanned; zero scanned is stated, not implied
clean.

Exit: 0 report: ran to completion. plan: every examined branch is deletable.
        delete: every attempted deletion succeeded
      1 plan: at least one examined branch is refused. delete: at least one (a)
        branch was refused on re-verification, or its delete failed
      2 usage error
      3 the API could not be read - UNKNOWN, never an empty clean report
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

#: NEGATIVE-CONTROL: controls/remote-branch-sweep
#:
#: ADR 0008: this is a gate that lets DELETIONS through, and nothing downstream
#: re-derives a deleted branch. The committed cases each carry one branch that
#: must be REFUSED (moved after merge, merge commit off main, name reused by an
#: open PR, pushed within 24h, closed unmerged, never had a PR) plus the one
#: branch that must be deleted. The anchor deletes every branch whose PR merged.

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_UNKNOWN = 3

RECENT = timedelta(hours=24)

CATEGORY_A = "a"
CATEGORY_B = "b"
CATEGORY_C = "c"
CATEGORY_D = "d"
EXCLUDED = "excluded"

LABELS = {
    CATEGORY_A: "(a) merged, tip IS the merged head, merge commit on the default branch - DELETABLE",
    CATEGORY_B: "(b) PR closed without merging - report only",
    CATEGORY_C: "(c) no PR has ever used this branch - report only",
    CATEGORY_D: "(d) open PR, or a scanned local worktree uses it - report only",
    EXCLUDED: "excluded - default/protected, pushed in the last 24h, or merged but not provably landed",
}

HEADER = """\
**Remote-branch sweep report** (`scripts/remote-branch-sweep.py`, issue #1262)

Authority: the operator authorised this cleanup with "do 1262". The rules below
are master's narrowing of that authorisation, adjusted for squash merges - they
are not the operator's own wording.

Deletion rule, in plain words: a branch is deleted only if its pull request
MERGED, the branch still points at exactly the commit GitHub recorded as merged
(nothing was pushed after the merge), and that PR's merge commit is on the
default branch. Everything else is reported and left alone: branches whose PR
was closed unmerged, branches that never had a PR, branches with an open PR or a
live local worktree, the default and protected branches, and anything pushed in
the last 24 hours. Every deletion is re-checked against the GitHub API at the
moment it happens, not taken from this report, and is recorded with its tip sha
so it can be restored with `git push origin <sha>:refs/heads/<name>`.
"""


class ApiUnreadable(Exception):
    """The API did not answer; the caller must report UNKNOWN, never clean."""


@dataclass
class Branch:
    name: str
    tip: str
    protected: bool
    category: str = ""
    reason: str = ""
    pr: int | None = None
    pushed_at: str = "-"
    pushed_source: str = "-"
    notes: list[str] = field(default_factory=list)


Api = Callable[[str], Any]


def gh_api(gh_bin: str) -> Api:
    """A GET against the GitHub REST API through `gh`, paginated for lists."""

    def call(path: str) -> Any:
        cmd = [gh_bin, "api", "-H", "Accept: application/vnd.github+json", path]
        # Paginate only the two listings that must be COMPLETE (every branch,
        # every PR for a head). The activity lookup wants the newest entry only.
        list_like = "/branches?" in path or "/pulls?" in path
        if list_like:
            # `--jq '.[]'` gives one object per line across every page; `--slurp`
            # would be tidier but needs a newer gh than hosts here carry (2.45).
            cmd[2:2] = ["--paginate", "--jq", ".[]"]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ApiUnreadable(f"{path}: {exc}") from exc
        if out.returncode != 0:
            if "Not Found" in (out.stdout + out.stderr) or "HTTP 404" in out.stderr:
                return None
            raise ApiUnreadable(f"{path}: gh exited {out.returncode}: {out.stderr.strip()[:200]}")
        try:
            if list_like:
                return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
            return json.loads(out.stdout or "null")
        except ValueError as exc:
            raise ApiUnreadable(f"{path}: unparseable response: {exc}") from exc

    return call


def fixture_api(path_to_json: Path) -> Api:
    """Canned responses for tests and the negative control - never the network.

    The file maps a request path to its response. A path that is not in the
    file is a 404 (None), which is how a fixture says "no such thing".
    """
    table = json.loads(path_to_json.read_text(encoding="utf-8"))
    unreadable = set(table.pop("__unreadable__", []))

    def call(path: str) -> Any:
        if path in unreadable:
            raise ApiUnreadable(f"{path}: fixture marks this path unreadable")
        return table.get(path)

    return call


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def last_push(api: Api, repo: str, branch: Branch) -> tuple[datetime | None, str]:
    """The newest of GitHub's recorded push time and the tip's committer date."""
    ref = quote(f"refs/heads/{branch.name}", safe="")
    activity = api(f"repos/{repo}/activity?ref={ref}&per_page=1")
    from_activity = None
    if isinstance(activity, list) and activity and isinstance(activity[0], dict):
        from_activity = _parse_time(activity[0].get("timestamp"))
    commit = api(f"repos/{repo}/commits/{branch.tip}")
    from_commit = None
    if isinstance(commit, dict):
        from_commit = _parse_time(((commit.get("commit") or {}).get("committer") or {}).get("date"))
    if from_activity and from_commit:
        newest = max(from_activity, from_commit)
        return newest, "activity" if newest == from_activity else "committer-date (newer than activity)"
    if from_activity:
        return from_activity, "activity"
    if from_commit:
        return from_commit, "committer-date (activity API did not answer)"
    return None, "unreadable"


def merge_commit_on_default(api: Api, repo: str, merge_sha: str, default: str) -> bool | None:
    """True if `merge_sha` is an ancestor of the default branch's tip."""
    cmp = api(f"repos/{repo}/compare/{merge_sha}...{default}")
    if not isinstance(cmp, dict):
        return None
    return cmp.get("status") in ("ahead", "identical") and cmp.get("behind_by") == 0


def local_worktree_branches(checkouts: list[Path]) -> tuple[set[str], list[str]]:
    """Branches held by any worktree of the given checkouts, and any failures."""
    held: set[str] = set()
    failures: list[str] = []
    for checkout in checkouts:
        try:
            out = subprocess.run(
                ["git", "-C", str(checkout), "worktree", "list", "--porcelain"],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            failures.append(f"{checkout}: {exc}")
            continue
        if out.returncode != 0:
            failures.append(f"{checkout}: git worktree list exited {out.returncode}")
            continue
        for line in out.stdout.splitlines():
            if line.startswith("branch refs/heads/"):
                held.add(line[len("branch refs/heads/"):])
    return held, failures


def classify(
    api: Api,
    repo: str,
    owner: str,
    branch: Branch,
    default: str,
    held: set[str],
    now: datetime,
) -> Branch:
    """Decide one branch. Order matters: the refusals come before (a)."""
    if branch.name == default:
        branch.category, branch.reason = EXCLUDED, "the default branch"
        return branch
    if branch.protected:
        branch.category, branch.reason = EXCLUDED, "protected"
        return branch
    head = quote(f"{owner}:{branch.name}", safe=":")
    prs = api(f"repos/{repo}/pulls?state=all&head={head}&per_page=100")
    if prs is None:
        prs = []
    if not isinstance(prs, list):
        raise ApiUnreadable(f"pulls for {branch.name}: unexpected shape")
    open_prs = [p for p in prs if p.get("state") == "open"]
    if open_prs:
        branch.category, branch.pr = CATEGORY_D, open_prs[0].get("number")
        branch.reason = f"open PR #{branch.pr}"
        return branch
    if branch.name in held:
        branch.category, branch.reason = CATEGORY_D, "checked out in a scanned local worktree"
        return branch
    pushed, source = last_push(api, repo, branch)
    branch.pushed_source = source
    branch.pushed_at = pushed.strftime("%Y-%m-%dT%H:%M:%SZ") if pushed else "-"
    if pushed is None:
        branch.category, branch.reason = EXCLUDED, "last push time unreadable"
        return branch
    if now - pushed < RECENT:
        branch.category, branch.reason = EXCLUDED, f"pushed within 24h ({source})"
        return branch
    # A COMMITTER DATE CANNOT SEE A PUSH (counter-model review). A branch
    # recreated or force-pushed an hour ago to an OLD commit - its previously
    # merged head, say - carries that commit's old date and still satisfies
    # every other (a) condition. So deletion eligibility requires GitHub's own
    # push record; without it the recency rule cannot be enforced, and a rule
    # that cannot be enforced does not license a deletion.
    if "activity API did not answer" in source:
        branch.category = EXCLUDED
        branch.reason = "push recency unestablished (activity API did not answer; a committer date cannot see a push)"
        return branch
    merged = [p for p in prs if p.get("merged_at")]
    if merged:
        at_tip = [p for p in merged if (p.get("head") or {}).get("sha") == branch.tip]
        if not at_tip:
            branch.pr = merged[0].get("number")
            branch.category = EXCLUDED
            branch.reason = f"PR #{branch.pr} merged, but the branch moved after the merge"
            return branch
        pr = at_tip[0]
        branch.pr = pr.get("number")
        merge_sha = pr.get("merge_commit_sha") or ""
        on_default = merge_commit_on_default(api, repo, merge_sha, default) if merge_sha else None
        if on_default is not True:
            branch.category = EXCLUDED
            branch.reason = (
                f"PR #{branch.pr} merged at this tip, but its merge commit is "
                + ("NOT on the default branch" if on_default is False else "unverifiable")
            )
            return branch
        branch.category = CATEGORY_A
        branch.reason = f"PR #{branch.pr} merged at this tip; merge commit {merge_sha[:12]} on {default}"
        return branch
    if prs:
        branch.pr = prs[0].get("number")
        branch.category, branch.reason = CATEGORY_B, f"PR #{branch.pr} closed without merging"
        return branch
    branch.category, branch.reason = CATEGORY_C, "no PR has ever used this branch"
    return branch


def list_branches(api: Api, repo: str) -> list[Branch]:
    raw = api(f"repos/{repo}/branches?per_page=100")
    if not isinstance(raw, list):
        raise ApiUnreadable("branch list did not answer")
    return [
        Branch(name=b["name"], tip=(b.get("commit") or {}).get("sha", ""), protected=bool(b.get("protected")))
        for b in raw
        if isinstance(b, dict) and b.get("name")
    ]


def sweep(api: Api, repo: str, checkouts: list[Path], now: datetime) -> tuple[list[Branch], str, list[str]]:
    info = api(f"repos/{repo}")
    if not isinstance(info, dict) or not info.get("default_branch"):
        raise ApiUnreadable("repository metadata did not answer")
    default = info["default_branch"]
    owner = repo.split("/", 1)[0]
    held, failures = local_worktree_branches(checkouts)
    branches = [classify(api, repo, owner, b, default, held, now) for b in list_branches(api, repo)]
    return branches, default, failures


def render_markdown(branches: list[Branch], repo: str, default: str, checkouts: list[Path],
                    failures: list[str]) -> str:
    lines = [HEADER]
    counts = {k: sum(1 for b in branches if b.category == k) for k in LABELS}
    lines.append(f"Repository `{repo}`, default branch `{default}`. {len(branches)} branch(es) examined:")
    for key, label in LABELS.items():
        lines.append(f"- {label}: **{counts[key]}**")
    scanned = len(checkouts) - len(failures)
    lines.append(
        f"\nLocal worktrees scanned for category (d): {scanned} checkout(s)"
        + (f"; UNREADABLE: {'; '.join(failures)}" if failures else "")
        + ". Worktrees on other hosts are not visible to this report."
    )
    for key, label in LABELS.items():
        rows = [b for b in branches if b.category == key]
        if not rows:
            continue
        lines.append(f"\n### {label}\n")
        lines.append("| branch | tip | PR | last push (source) | why |")
        lines.append("|---|---|---|---|---|")
        for b in sorted(rows, key=lambda r: r.name):
            pr = f"#{b.pr}" if b.pr else "-"
            lines.append(f"| `{b.name}` | `{b.tip[:12]}` | {pr} | {b.pushed_at} ({b.pushed_source}) | {b.reason} |")
    return "\n".join(lines) + "\n"


def push_destination(checkout: Path, repo: str) -> tuple[str | None, str]:
    """The checkout's `origin` push URL, IF it is exactly `repo` (counter-model review).

    Every safety check reads `--repo` through the API, but the deletion is a
    `git push` to the checkout's `origin`. A checkout whose origin is a fork -
    same branch names, same shas - would pass the lease and delete a branch none
    of those checks ever looked at. So the push destination is read (all push
    URLs, since `pushurl` can override `url` and there can be several), must be
    exactly one, and must name the same owner/name. Returns (url, "") or
    (None, reason).
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(checkout), "remote", "get-url", "--push", "--all", "origin"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"cannot read origin's push URL: {exc}"
    urls = [u.strip() for u in out.stdout.splitlines() if u.strip()]
    if out.returncode != 0 or not urls:
        return None, "origin has no readable push URL"
    if len(urls) > 1:
        return None, f"origin has {len(urls)} push URLs; refusing an ambiguous destination"
    url = urls[0]
    tail = url.rstrip("/")
    tail = tail[:-4] if tail.endswith(".git") else tail
    named = "/".join(tail.replace(":", "/").split("/")[-2:])
    if named.lower() != repo.lower():
        return None, f"origin pushes to {named!r}, not {repo!r}"
    return url, ""


def delete_branch(checkout: Path, name: str, tip: str) -> tuple[bool, str]:
    """Delete under a lease: the remote ref must still be exactly `tip`."""
    out = subprocess.run(
        ["git", "-C", str(checkout), "push", "origin", "--delete", name,
         f"--force-with-lease=refs/heads/{name}:{tip}"],
        capture_output=True, text=True, timeout=120,
    )
    return out.returncode == 0, (out.stderr or out.stdout).strip()[:300]


def run_delete(
    api: Api,
    repo: str,
    candidates: list[Branch],
    checkouts: list[Path],
    now: Callable[[], datetime],
    pusher: Callable[[Path, str, str], tuple[bool, str]] = delete_branch,
    destination: Callable[[Path, str], tuple[str | None, str]] = push_destination,
) -> int:
    """Delete the (a) candidates, re-deriving EVERY input of each decision.

    Per branch, immediately before its push: the branch itself, the repository's
    default branch, its PRs, its push record, the merge commit's reachability,
    and a fresh scan of every supplied checkout's worktrees (counter-model
    review - the first cut reused the default and the worktree set from before
    the loop). A scan that fails refuses; it is not an empty scan.

    WHAT IS NOT ATOMIC, stated rather than implied: the lease protects only the
    branch's tip. A default-branch change or a new local checkout of the branch
    in the moment between the final re-check and the push is not seen.
    """
    checkout = checkouts[0]
    url, why = destination(checkout, repo)
    if url is None:
        print(f"SWEEP_REFUSED: * - {why}; nothing deleted")
        print("SWEEP: delete deleted=0 refused=all")
        return EXIT_REFUSED
    owner = repo.split("/", 1)[0]
    refused = deleted = 0
    for b in candidates:
        try:
            info = api(f"repos/{repo}")
            default = info.get("default_branch") if isinstance(info, dict) else None
            if not default:
                raise ApiUnreadable("repository metadata did not answer")
            held, failures = local_worktree_branches(checkouts)
            if failures:
                print(f"SWEEP_REFUSED: {b.name} - worktree scan failed: {'; '.join(failures)}")
                refused += 1
                continue
            live_raw = api(f"repos/{repo}/branches/{quote(b.name, safe='')}")
            if not isinstance(live_raw, dict):
                print(f"SWEEP_REFUSED: {b.name} - no longer readable at deletion time")
                refused += 1
                continue
            live = Branch(name=b.name, tip=(live_raw.get("commit") or {}).get("sha", ""),
                          protected=bool(live_raw.get("protected")))
            classify(api, repo, owner, live, default, held, now())
        except ApiUnreadable as exc:
            print(f"SWEEP_REFUSED: {b.name} - re-verification unreadable: {exc}")
            refused += 1
            continue
        if live.category != CATEGORY_A or live.tip != b.tip:
            print(f"SWEEP_REFUSED: {b.name} - re-verification now says [{live.category}] {live.reason}")
            refused += 1
            continue
        ok, detail = pusher(checkout, live.name, live.tip)
        if ok:
            deleted += 1
            print(f"SWEEP_DELETED: {live.name} {live.tip} (restore: git push origin {live.tip}:refs/heads/{live.name})")
        else:
            refused += 1
            print(f"SWEEP_REFUSED: {live.name} - delete failed: {detail}")
    print(f"SWEEP: delete deleted={deleted} refused={refused}")
    return EXIT_REFUSED if refused else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("report", "plan", "delete"))
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--checkout", action="append", default=[], type=Path,
                    help="a local checkout whose worktrees count as category (d); repeatable")
    ap.add_argument("--api-fixture", type=Path, help="canned API responses (tests and the control)")
    ap.add_argument("--now", help="override the current time (tests and the control)")
    ap.add_argument("--confirm", action="store_true", help="required by `delete`")
    args = ap.parse_args(argv)

    if args.mode == "delete" and (not args.confirm or not args.checkout or args.api_fixture):
        print("remote-branch-sweep: `delete` needs --confirm and a --checkout whose origin is the "
              "repository (deletion is a leased `git push`), and never runs against a fixture",
              file=sys.stderr)
        return EXIT_USAGE
    api = fixture_api(args.api_fixture) if args.api_fixture else gh_api(os.environ.get("CPP_SWEEP_GH", "gh"))
    now = _parse_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        print(f"remote-branch-sweep: --now {args.now!r} is not a timestamp", file=sys.stderr)
        return EXIT_USAGE

    try:
        branches, default, failures = sweep(api, args.repo, args.checkout, now)
    except ApiUnreadable as exc:
        print(f"remote-branch-sweep: UNKNOWN - {exc}. Nothing was classified, so nothing is "
              "reported clean and nothing is deleted.", file=sys.stderr)
        print("SWEEP: unknown")
        return EXIT_UNKNOWN

    if args.mode == "report":
        sys.stdout.write(render_markdown(branches, args.repo, default, args.checkout, failures))
        counts = " ".join(f"{k}={sum(1 for b in branches if b.category == k)}" for k in LABELS)
        print(f"SWEEP: report examined={len(branches)} {counts}")
        return EXIT_OK

    if args.mode in ("plan", "delete") and failures:
        # A FAILED SCAN IS NOT AN EMPTY ONE (counter-model review): a branch held
        # by a checkout that could not be read would otherwise plan as deletable.
        print(f"remote-branch-sweep: UNKNOWN - worktree scan failed: {'; '.join(failures)}. "
              "Nothing is planned or deleted.", file=sys.stderr)
        print("SWEEP: unknown")
        return EXIT_UNKNOWN

    if args.mode == "plan":
        for b in sorted(branches, key=lambda r: r.name):
            if b.category == CATEGORY_A:
                print(f"SWEEP_DELETE: {b.name} {b.tip} - {b.reason}")
            else:
                print(f"SWEEP_REFUSED: {b.name} [{b.category}] - {b.reason}")
        deletable = sum(1 for b in branches if b.category == CATEGORY_A)
        refused_n = len(branches) - deletable
        print(f"SWEEP: plan examined={len(branches)} delete={deletable} refused={refused_n}")
        # Exit 1 when anything was refused, the same meaning it has for `delete`:
        # "at least one branch will not be deleted". A plan over a whole
        # repository always refuses the default branch, so 1 is the ordinary
        # answer there; 0 says every examined branch is deletable.
        return EXIT_REFUSED if refused_n else EXIT_OK

    # delete: every (a) decision is RE-DERIVED here, per branch, from the live
    # API - the report is what a human checked, this is what is true now.
    return run_delete(
        api, args.repo, [b for b in branches if b.category == CATEGORY_A],
        args.checkout, lambda: datetime.now(timezone.utc),
    )


if __name__ == "__main__":
    sys.exit(main())
