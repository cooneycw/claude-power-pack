#!/usr/bin/env python3
"""The monthly review helper: status, scan, create (issue #1703).

    monthly-review.py status [--json]     which review, if any, covers this month
    monthly-review.py scan                print the monitoring list a create would write
    monthly-review.py create [--dry-run]  write this month's review issue, once

`/monthly:create` and `/monthly:review` call this; `/project:next` reports the
same state through the shared rules in `lib/monthly_review`.

Contract (the last stdout line of each subcommand, and the exit code):

    MONTHLY_REVIEW: open #N ...           exit 0   work it with /monthly:review
    MONTHLY_REVIEW: done for YYYY-MM ...  exit 0
    MONTHLY_REVIEW: none for YYYY-MM ...  exit 0   /monthly:create is the next step
    MONTHLY_REVIEW: unknown - <why>       exit 3   GitHub could not be read

    MONTHLY_REVIEW_CREATE: created <url>  exit 0
    MONTHLY_REVIEW_CREATE: exists #N      exit 0   nothing was written
    MONTHLY_REVIEW_CREATE: dry-run        exit 0   nothing was written
    MONTHLY_REVIEW_CREATE: refused - ...  exit 3   state unknown, or gh failed

`unknown` is never `none`. `create` REFUSES on `unknown`: it cannot show that
this month has no review, and a second review for one month is the failure this
helper exists to prevent. It is a reporter and a writer, not a gate: nothing is
let through on its output, and `create` re-reads the state itself before
writing rather than trusting an earlier `status`.

Everything runs in `--root` (default: the current directory), and `gh` picks
the repository from that checkout's own remote.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
# `.resolve()` first: this is installed as a symlink under ~/.claude/scripts,
# and `lib` is importable only from the checkout the link points into.
sys.path.insert(0, str(REPO_ROOT))

import lib.monthly_review as mr  # noqa: E402

RESOLVER = REPO_ROOT / "scripts" / "nit-store-resolve.sh"
UNKNOWN_EXIT = 3
USAGE_EXIT = 2
REVIEW_FIELDS = "number,title,state,createdAt,body,labels"


def make_runner(root: Path) -> mr.Runner:
    def run(command: Sequence[str]) -> tuple[int, str]:
        try:
            done = subprocess.run(list(command), cwd=root, capture_output=True, text=True,
                                  check=False, timeout=120)
        except (OSError, subprocess.SubprocessError):
            # Could not START or did not finish: a failure like any other, and
            # never an empty answer.
            return 127, ""
        return done.returncode, done.stdout

    return run


def repo_of(runner: mr.Runner) -> str | None:
    """The one repository every read and write targets (the resolver's reading of `origin`)."""
    _, out = runner(["bash", str(RESOLVER)])
    return mr.resolved_repo(out)


def read_state(runner: mr.Runner, today: date, repo: str | None = None) -> mr.ReviewState:
    """One listing of every review, open and closed, then the shared rule."""
    command = ["gh", "issue", "list", *mr.repo_args(repo), "--label", mr.LABEL, "--state", "all",
               "--limit", str(mr.LIST_LIMIT), "--json", REVIEW_FIELDS]
    code, out = runner(command)
    if code != 0:
        return mr.review_state(None, None, today,
                               unknown_reason=f"`gh issue list` exited {code} in this checkout")
    try:
        rows = json.loads(out or "null")
    except json.JSONDecodeError:
        rows = None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return mr.review_state(None, None, today,
                               unknown_reason="`gh issue list` returned no readable listing")
    if len(rows) >= mr.LIST_LIMIT:
        return mr.review_state(None, None, today,
                               unknown_reason=f"the review listing filled its bound of {mr.LIST_LIMIT}")
    opened = [row for row in rows if str(row.get("state")).upper() == "OPEN"]
    closed = [row for row in rows if str(row.get("state")).upper() != "OPEN"]
    return mr.review_state(opened, closed, today)


def friction_log(runner: mr.Runner, root: Path) -> Path | None:
    """The log `friction-log.sh` writes: `CPP_FRICTION_LOG`, else the main checkout's."""
    override = os.environ.get("CPP_FRICTION_LOG", "").strip()
    if override:
        return Path(override).expanduser()
    code, out = runner(["git", "rev-parse", "--git-common-dir"])
    if code != 0 or not out.strip():
        return None
    common = Path(out.strip())
    if not common.is_absolute():
        common = (root / common).resolve()
    return common.parent / ".claude" / "friction.jsonl"


def do_scan(runner: mr.Runner, root: Path, today: date, repo: str | None = None) -> list[mr.Item]:
    return mr.scan(runner, RESOLVER, friction_log(runner, root), today, root, repo)


def git_root(runner: mr.Runner, root: Path) -> Path:
    """The checkout's top level, so a run from a subdirectory reads the REPOSITORY's
    files. Outside a git checkout the given directory stands."""
    code, out = runner(["git", "rev-parse", "--show-toplevel"])
    top = Path(out.strip()) if code == 0 and out.strip() else None
    return top if top is not None and top.is_dir() else root


class _CreateLock:
    """One create at a time per checkout on this host (flock in the git common dir).

    Two sessions on one host is the ordinary way a month gets two reviews: both
    read `none`, both scan, both write. The lock makes the second wait and then
    re-read. It does nothing across hosts; the re-read under it narrows that
    window and cannot close it.
    """

    def __init__(self, runner: mr.Runner, root: Path):
        self.handle = None
        code, out = runner(["git", "rev-parse", "--git-common-dir"])
        if code == 0 and out.strip():
            common = Path(out.strip())
            self.path: Path | None = (common if common.is_absolute() else root / common) / "monthly-review.lock"
        else:
            self.path = None

    def __enter__(self) -> "_CreateLock":
        if self.path is not None:
            try:
                import fcntl

                self.handle = open(self.path, "w")  # noqa: SIM115 - held until __exit__
                fcntl.flock(self.handle, fcntl.LOCK_EX)
            except OSError:
                self.handle = None  # unlockable: the re-read below still runs
        return self

    def __exit__(self, *exc: object) -> None:
        if self.handle is not None:
            self.handle.close()


def cmd_status(args: argparse.Namespace, runner: mr.Runner, today: date) -> int:
    state = read_state(runner, today, repo_of(runner))
    if args.json:
        print(json.dumps({**state.to_dict(), "route": state.route}, indent=2, sort_keys=True))
    print(f"MONTHLY_REVIEW: {state.line()}")
    return UNKNOWN_EXIT if state.verdict == "unknown" else 0


def cmd_scan(args: argparse.Namespace, runner: mr.Runner, today: date) -> int:
    items = do_scan(runner, Path(args.root), today, repo_of(runner))
    print(mr.render_body(items, today), end="")
    tally = {name: sum(item.state == name for item in items) for name in ("due", "unread", "clear")}
    print(f"MONTHLY_REVIEW_SCAN: {tally['due']} due, {tally['unread']} unread, {tally['clear']} clear")
    return 0


def cmd_create(args: argparse.Namespace, runner: mr.Runner, today: date) -> int:
    repo = repo_of(runner)

    def existing() -> int | None:
        """Exit code when nothing may be written, else None. Prints why."""
        state = read_state(runner, today, repo)
        if state.verdict == "unknown":
            print(f"MONTHLY_REVIEW_CREATE: refused - {state.detail}; whether this month already "
                  f"has a review is not established, so none was written")
            return UNKNOWN_EXIT
        if state.verdict in ("open", "done"):
            print(f"MONTHLY_REVIEW: {state.line()}")
            print(f"MONTHLY_REVIEW_CREATE: exists #{state.number}")
            return 0
        return None

    stop = existing()
    if stop is not None:
        return stop
    items = do_scan(runner, Path(args.root), today, repo)
    body = mr.render_body(items, today)
    title = mr.title_for(mr.month_of(today))
    if args.dry_run:
        print(f"# {title}\n")
        print(body, end="")
        print("MONTHLY_REVIEW_CREATE: dry-run")
        return 0
    with _CreateLock(runner, Path(args.root)):
        # THE SCAN TAKES A WHILE, so the state read before it is stale by now:
        # another session may have created this month's review meanwhile. Read
        # it again, under the lock, immediately before writing.
        stop = existing()
        if stop is not None:
            return stop
        # `--force` makes this an upsert: a label that already exists is not an error.
        code, _ = runner(["gh", "label", "create", mr.LABEL, *mr.repo_args(repo), "--force", "--color", "5319E7",
                          "--description", "This month's monitoring list (/monthly:create, /monthly:review)"])
        if code != 0:
            print(f"MONTHLY_REVIEW_CREATE: refused - the `{mr.LABEL}` label could not be created (exit {code})")
            return UNKNOWN_EXIT
        code, out = runner(["gh", "issue", "create", *mr.repo_args(repo), "--title", title,
                            "--label", mr.LABEL, "--body", body])
    url = (out or "").strip().splitlines()[-1] if (out or "").strip() else ""
    if code != 0 or not url:
        print(f"MONTHLY_REVIEW_CREATE: refused - `gh issue create` exited {code}; check for a "
              f"half-created issue before retrying")
        return UNKNOWN_EXIT
    print(f"MONTHLY_REVIEW_CREATE: created {url}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Monthly review: status, scan, create")
    ap.add_argument("--root", default=".", help="the checkout to work in (default: cwd)")
    ap.add_argument("--today", default=None, metavar="YYYY-MM-DD",
                    help="the date to treat as today (tests, and re-reading a past month)")
    sub = ap.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    sub.add_parser("scan")
    create = sub.add_parser("create")
    create.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        today = date.fromisoformat(args.today) if args.today else date.today()
    except ValueError:
        print(f"monthly-review: --today '{args.today}' is not YYYY-MM-DD", file=sys.stderr)
        return USAGE_EXIT
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"monthly-review: --root '{args.root}' is not a directory", file=sys.stderr)
        return USAGE_EXIT
    runner = make_runner(root)
    root = git_root(runner, root)
    if str(root) != str(Path(args.root).resolve()):
        runner = make_runner(root)
    args.root = str(root)
    return {"status": cmd_status, "scan": cmd_scan, "create": cmd_create}[args.command](args, runner, today)


if __name__ == "__main__":
    _code = main()
    sys.stdout.flush()
    print(f"MONTHLY_REVIEW_EXIT={_code}", file=sys.stderr)
    raise SystemExit(_code)
