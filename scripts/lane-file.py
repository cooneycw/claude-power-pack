#!/usr/bin/env python3
"""The lane file helper: how old is the last review, and stamp a new one (issue #1696).

    lane-file.py age   [--root DIR] [--threshold-days N] [--today YYYY-MM-DD]
    lane-file.py stamp [--root DIR] [--today YYYY-MM-DD]

A project lists its lanes in `.claude/lanes.md` (docs/agents/lanes.md, #1695).
The list goes stale when the product gains a route nobody added to it, and a
stale list still produces a plan table that looks complete. `age` reads the
`Reviewed: YYYY-MM-DD` line INSIDE the file and says how long ago a person last
read the whole list. `/lane:create` and `/lane:update` call `stamp`; the plan
step (`/flow:eli5`) calls `age` and relays what it says.

Contract (the LAST stdout line, and the exit code):

    LANE_FILE_AGE: fresh - ...     exit 0   reviewed within the threshold
    LANE_FILE_AGE: absent - ...    exit 0   the project has no lane file; say nothing
    LANE_FILE_AGE: stale - ...     exit 3   reviewed longer ago than the threshold
    LANE_FILE_AGE: unknown - ...   exit 4   a lane file exists and its age cannot be read

    LANE_FILE_STAMP: stamped ...   exit 0
    LANE_FILE_STAMP: refused - ... exit 3   nothing was written

IT IS AN ADVISORY, NOT A GATE. Nothing is let through or held back on its
output: a caller relays the verdict line and CONTINUES on every exit code. The
codes exist so a script can tell the four states apart, not so a step can stop.

`unknown` is never `fresh`, and never `absent`. `absent` is said only when the
path is ESTABLISHED not to exist. A file that exists and cannot be used - no
readable date, an impossible or future date, an unreadable file, a directory, a
dangling symlink, a `.claude` directory that cannot be searched - is `unknown`,
because each of those is a project that adopted lanes and whose list nobody can
date. Reading any of them as `absent` would switch the advisory off exactly
where it is owed (the gap recorded against #1695's review hand-over).

The age comes from the date in the file, never from the file's modification
time or git history: a typo fix must not make the list look reviewed, and a
fresh clone must not make it look new.

`--root` defaults to the git checkout the current directory is in, so a run
from a subdirectory or a linked worktree reads THAT tree's own file. Outside a
git checkout the current directory is used, and the `LANE_FILE_ROOT:` line says
which of the two it was.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

#: NEGATIVE-CONTROL: controls/lane-file-age

LANE_FILE = Path(".claude") / "lanes.md"
DEFAULT_THRESHOLD_DAYS = 60
REVIEWED = re.compile(r"^Reviewed:[ \t]*(\S.*?)[ \t]*$", re.MULTILINE)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_STALE = 3
EXIT_UNKNOWN = 4
EXIT_REFUSED = 3


class Unusable(Exception):
    """A lane file exists and cannot be dated. The message is the reason."""


def resolve_root(flag: Path | None) -> tuple[Path, str]:
    """The directory whose `.claude/lanes.md` is read, and how it was chosen."""
    if flag is not None:
        return flag.resolve(), "flag"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return Path.cwd(), "cwd (git could not be run)"
    top = result.stdout.strip()
    if result.returncode == 0 and top:
        return Path(top), "git"
    return Path.cwd(), "cwd (not a git checkout)"


def parse_day(text: str, what: str) -> date:
    if not ISO_DATE.match(text):
        raise ValueError(f"{what} {text!r} is not YYYY-MM-DD")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{what} {text!r} is not a real date") from exc


def read_lane_file(path: Path) -> str | None:
    """The file's text, or None when the path is ESTABLISHED not to exist.

    Everything between those two answers raises `Unusable`: the file is there,
    or may be there, and cannot be read.
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    except NotADirectoryError as exc:
        raise Unusable(f"a parent of {LANE_FILE} is not a directory") from exc
    except OSError as exc:
        raise Unusable(f"{LANE_FILE} could not be examined ({exc.strerror})") from exc
    if stat.S_ISLNK(info.st_mode):
        try:
            info = os.stat(path)
        except OSError as exc:
            raise Unusable(f"{LANE_FILE} is a symlink whose target cannot be read") from exc
    if not stat.S_ISREG(info.st_mode):
        raise Unusable(f"{LANE_FILE} is not a regular file")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Unusable(f"{LANE_FILE} could not be read ({type(exc).__name__})") from exc


def reviewed_day(text: str) -> date:
    found = REVIEWED.findall(text)
    if not found:
        raise Unusable(f"{LANE_FILE} has no `Reviewed: YYYY-MM-DD` line")
    if len(set(found)) > 1:
        raise Unusable(f"{LANE_FILE} has {len(found)} `Reviewed:` lines that disagree")
    try:
        return parse_day(found[0], "the review date")
    except ValueError as exc:
        raise Unusable(str(exc)) from exc


def cmd_age(root: Path, how: str, threshold: int, today: date) -> int:
    print(f"LANE_FILE_ROOT: {root} ({how})")
    print(f"LANE_FILE_THRESHOLD_DAYS: {threshold}")
    try:
        text = read_lane_file(root / LANE_FILE)
        if text is None:
            print("LANE_FILE_REVIEWED: -")
            print(f"LANE_FILE_AGE: absent - this project has no {LANE_FILE}; nothing is asked")
            return EXIT_OK
        reviewed = reviewed_day(text)
        days = (today - reviewed).days
        if days < 0:
            raise Unusable(f"the review date {reviewed} is after today ({today})")
    except Unusable as exc:
        print("LANE_FILE_REVIEWED: -")
        print(f"LANE_FILE_AGE: unknown - {exc}; its age cannot be read. Run /lane:update")
        return EXIT_UNKNOWN
    print(f"LANE_FILE_REVIEWED: {reviewed}")
    print(f"LANE_FILE_AGE_DAYS: {days}")
    if days > threshold:
        print(
            f"LANE_FILE_AGE: stale - last reviewed {days} days ago, "
            f"over the {threshold}-day threshold. Run /lane:update"
        )
        return EXIT_STALE
    print(f"LANE_FILE_AGE: fresh - last reviewed {days} days ago (threshold {threshold})")
    return EXIT_OK


def stamped_text(text: str, today: date) -> tuple[str, str]:
    """The text with exactly one `Reviewed:` line set to today, and the old value."""
    line = f"Reviewed: {today.isoformat()}"
    found = REVIEWED.findall(text)
    if found:
        first = True

        def replace(match: re.Match[str]) -> str:
            nonlocal first
            if first:
                first = False
                return line
            return ""

        return REVIEWED.sub(replace, text), ", ".join(found)
    lines = text.splitlines(keepends=True)
    for index, existing in enumerate(lines):
        if existing.startswith("# "):
            lines[index + 1 : index + 1] = ["\n", line + "\n"]
            return "".join(lines), "none"
    return line + "\n\n" + text, "none"


def cmd_stamp(root: Path, how: str, today: date) -> int:
    print(f"LANE_FILE_ROOT: {root} ({how})")
    path = root / LANE_FILE
    try:
        text = read_lane_file(path)
    except Unusable as exc:
        print(f"LANE_FILE_STAMP: refused - {exc}")
        return EXIT_REFUSED
    if text is None:
        print(f"LANE_FILE_STAMP: refused - there is no {LANE_FILE} to stamp; run /lane:create")
        return EXIT_REFUSED
    if path.is_symlink():
        print(f"LANE_FILE_STAMP: refused - {LANE_FILE} is a symlink; stamp its target directly")
        return EXIT_REFUSED
    new_text, was = stamped_text(text, today)
    try:
        handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".lanes.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as temp:
                temp.write(new_text)
            os.chmod(temp_name, stat.S_IMODE(os.stat(path).st_mode))
            os.replace(temp_name, path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
    except OSError as exc:
        print(f"LANE_FILE_STAMP: refused - {LANE_FILE} could not be written ({exc.strerror})")
        return EXIT_REFUSED
    print(f"LANE_FILE_STAMP: stamped {today.isoformat()} (was {was})")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="age and stamp a project's lane file")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("age", "stamp"):
        verb = sub.add_parser(name)
        verb.add_argument("--root", type=Path, default=None)
        verb.add_argument("--today", default=None, help="YYYY-MM-DD; default: today")
        if name == "age":
            verb.add_argument("--threshold-days", type=int, default=DEFAULT_THRESHOLD_DAYS)
    args = parser.parse_args(argv)

    try:
        today = parse_day(args.today, "--today") if args.today else date.today()
    except ValueError as exc:
        print(f"lane-file: {exc}", file=sys.stderr)
        return EXIT_USAGE
    root, how = resolve_root(args.root)
    if args.command == "age":
        if args.threshold_days < 0:
            print("lane-file: --threshold-days must not be negative", file=sys.stderr)
            return EXIT_USAGE
        return cmd_age(root, how, args.threshold_days, today)
    return cmd_stamp(root, how, today)


if __name__ == "__main__":
    sys.exit(main())
