"""The monthly review: one dated, ordinary issue per month (issue #1703).

Standing work in a repository - emptying the Nit Store, the evergreen issues,
the friction retro, a follow-up that has come due - had no clock. It was either
labelled ``evergreen``, which tells ``/project:next`` never to recommend it, or
written down in a document nobody was prompted to reread. This module holds the
rules three callers share, so they cannot disagree:

- ``scripts/monthly-review.py`` (``/monthly:create``, ``/monthly:review``);
- ``scripts/project-next.py``, which reports the review's state on every run.
  That report is the trigger: there is no scheduler.

EVERY SOURCE HAS THREE ANSWERS, NOT TWO. ``due`` (there is something to do),
``clear`` (it was read and there is nothing to do) and ``unread`` (it could not
be read). An unread source is written into the review as an item to resolve; it
is never dropped and never reported as clear. The same holds for the review's
own state: ``unknown`` is never ``none``, because ``none`` asks for a new issue
and a second review for a month that already has one is the failure to avoid.

Nothing here talks to GitHub or reads the clock on its own: callers pass the
listings, the date and a command runner, which is what makes each answer
reachable from a test.
"""

from __future__ import annotations

import calendar
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

LABEL = "monthly-review"
EVERGREEN_LABEL = "evergreen"
FOLLOW_UP_LABEL = "follow-up"
NIT_STORE_TITLE = "Nit Store"
TITLE_PREFIX = "Monthly review: "
TITLE_RE = re.compile(r"^Monthly review: (\d{4}-\d{2})$")
DUE_RE = re.compile(r"^\s*(?:[-*]\s*)?\**Due:?\**:?\s*(\d{4}-\d{2}-\d{2})\b", re.M)
CHECKBOX_RE = re.compile(r"^\s*[-*] \[([ xX])\] ", re.M)
#: The bound on every listing. A listing that FILLS it may have been cut off,
#: so the source is unread rather than a count that could be short.
LIST_LIMIT = 200
ACTIONABLE_FRICTION = ("gate-failure", "red-output", "manual-intervention")

#: (returncode, stdout) for a command run in the repository.
Runner = Callable[[Sequence[str]], tuple[int, str]]


def month_of(today: date) -> str:
    return f"{today.year:04d}-{today.month:02d}"


def title_for(month: str) -> str:
    return f"{TITLE_PREFIX}{month}"


def _month_end(month: str) -> date:
    year, mon = (int(part) for part in month.split("-"))
    return date(year, mon, calendar.monthrange(year, mon)[1])


def _parse_day(value: object) -> date | None:
    text = str(value or "")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# The review's own state


@dataclass(frozen=True)
class ReviewState:
    """``verdict`` is one of ``open``, ``done``, ``none``, ``unknown``."""

    verdict: str
    month: str
    number: int | None = None
    review_month: str = ""
    age_days: int | None = None
    open_items: int | None = None
    total_items: int | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def route(self) -> str:
        if self.verdict == "open":
            return "/monthly:review"
        if self.verdict == "none":
            return "/monthly:create"
        return ""

    def line(self) -> str:
        if self.verdict == "open":
            age = f", {self.age_days}d old" if self.age_days is not None else ""
            items = (
                f", {self.open_items} of {self.total_items} item(s) open"
                if self.total_items is not None
                else ""
            )
            late = (
                f" - OVERDUE, it is now {self.month}"
                if self.review_month and self.review_month < self.month
                else ""
            )
            named = self.review_month or "undated"
            return f"open #{self.number} ({named}{age}{items}){late} - `/monthly:review`"
        if self.verdict == "done":
            return f"done for {self.month} (#{self.number})"
        if self.verdict == "none":
            return f"none for {self.month} - `/monthly:create` writes this month's list"
        return f"unknown - {self.detail}; NOT evidence that no review exists"


def _labels(issue: Mapping[str, object]) -> frozenset[str]:
    out = set()
    raw = issue.get("labels")
    for label in raw if isinstance(raw, (list, tuple)) else ():
        name = label.get("name") if isinstance(label, Mapping) else label
        if name:
            out.add(str(name).strip().lower())
    return frozenset(out)


def count_items(body: str) -> tuple[int, int]:
    """(open, total) checklist items in a review body."""
    marks = CHECKBOX_RE.findall(body or "")
    return sum(mark == " " for mark in marks), len(marks)


def review_state(
    open_issues: Iterable[Mapping[str, object]] | None,
    closed_reviews: Iterable[Mapping[str, object]] | None,
    today: date,
    *,
    unknown_reason: str = "",
) -> ReviewState:
    """Decide the state from two listings; ``None`` means "could not be read".

    An OPEN review settles it whatever its month and whatever the closed
    listing says: a review left open from last month is the thing to work, and
    opening a second one beside it is not. Only with no open review does the
    closed listing matter, and then an unread one is ``unknown``, never
    ``none``.
    """
    month = month_of(today)
    if open_issues is None:
        return ReviewState("unknown", month, detail=unknown_reason or "the open issues could not be read")
    reviews = sorted(
        (issue for issue in open_issues if LABEL in _labels(issue)),
        key=lambda issue: int(str(issue.get("number") or 0)),
    )
    if reviews:
        issue = reviews[0]
        matched = TITLE_RE.match(str(issue.get("title") or ""))
        created = _parse_day(issue.get("created_at") or issue.get("createdAt"))
        body = issue.get("body")
        opened, total = count_items(str(body)) if body else (None, None)
        return ReviewState(
            "open",
            month,
            number=int(str(issue.get("number"))),
            review_month=matched.group(1) if matched else "",
            age_days=(today - created).days if created else None,
            open_items=opened,
            total_items=total,
            detail=f"{len(reviews)} open reviews; the oldest is reported" if len(reviews) > 1 else "",
        )
    if closed_reviews is None:
        return ReviewState(
            "unknown", month, detail=unknown_reason or "closed monthly reviews could not be read"
        )
    wanted = title_for(month)
    for issue in closed_reviews:
        if str(issue.get("title") or "") == wanted:
            return ReviewState("done", month, number=int(str(issue.get("number"))), review_month=month)
    return ReviewState("none", month)


# --------------------------------------------------------------------------- #
# The scan


@dataclass(frozen=True)
class Item:
    """One line of the monitoring list. ``state``: ``due``, ``clear``, ``unread``."""

    source: str
    state: str
    text: str


def _json_list(runner: Runner, command: Sequence[str]) -> tuple[list[dict[str, object]] | None, str]:
    code, out = runner(command)
    if code != 0:
        return None, f"`{' '.join(command[:3])}` exited {code}"
    try:
        rows = json.loads(out or "null")
    except json.JSONDecodeError as exc:
        return None, f"`{' '.join(command[:3])}` returned unreadable JSON ({exc.msg})"
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return None, f"`{' '.join(command[:3])}` did not return a list of issues"
    if len(rows) >= LIST_LIMIT:
        return None, f"the listing filled its bound of {LIST_LIMIT} and may be cut off"
    return rows, ""


def repo_args(repo: str | None) -> list[str]:
    """`--repo OWNER/NAME` when the repository is known, else gh's own default."""
    return ["--repo", repo] if repo else []


def resolved_repo(resolver_output: str) -> str | None:
    """The repository the resolver worked out from `origin` (None if it could not).

    EVERY read in a scan targets this one repository. In a fork checkout `gh`
    can default to the upstream, so a store resolved in the fork and then read
    by number alone would be some unrelated upstream issue of the same number.
    """
    found = re.search(r"^NIT_STORE_REPO=(\S+/\S+)$", resolver_output or "", re.M)
    return found.group(1) if found else None


def scan_nit_store(runner: Runner, resolver: Path, today: date) -> tuple[list[Item], int | None]:
    """The Nit Store's line, and its number so the evergreen scan can skip it."""
    source = "nit-store"
    code, out = runner(["bash", str(resolver)])
    repo = resolved_repo(out)
    status = re.search(r"^NIT_STORE_STATUS: (\w+)(?: - (.*))?$", out or "", re.M)
    number = re.search(r"^NIT_STORE=(\d+)$", out or "", re.M)
    if status is None:
        return [Item(source, "unread", f"the Nit Store resolver gave no status (exit {code})")], None
    if status.group(1) == "none":
        return [Item(source, "clear", "this repository has no open Nit Store")], None
    if status.group(1) != "ok" or number is None:
        why = status.group(2) or status.group(1)
        return [Item(source, "unread", f"the Nit Store could not be resolved ({why})")], None
    store = int(number.group(1))
    code, out = runner(["gh", "issue", "view", str(store), *repo_args(repo), "--json", "comments,createdAt"])
    try:
        data = json.loads(out) if code == 0 else None
        comments = len(data["comments"])
        created = _parse_day(data["createdAt"])
    except (json.JSONDecodeError, KeyError, TypeError):
        data = None
    if data is None:
        return [Item(source, "unread", f"Nit Store #{store} could not be read (exit {code})")], store
    age = f", opened {(today - created).days}d ago" if created else ""
    if comments == 0:
        return [Item(source, "clear", f"Nit Store #{store} holds no findings")], store
    return [
        Item(
            source,
            "due",
            f"Roll over the Nit Store (#{store}: {comments} finding(s){age}): aggregate, close, "
            f"then open the successor",
        )
    ], store


def scan_evergreen(runner: Runner, skip: int | None, repo: str | None = None) -> list[Item]:
    source = "evergreen"
    rows, why = _json_list(
        runner,
        ["gh", "issue", "list", *repo_args(repo), "--state", "open", "--label", EVERGREEN_LABEL,
         "--limit", str(LIST_LIMIT), "--json", "number,title"],
    )
    if rows is None:
        return [Item(source, "unread", f"the standing (`{EVERGREEN_LABEL}`) issues could not be listed: {why}")]
    items = [
        Item(source, "due", f"Standing item #{row.get('number')}: {row.get('title')}")
        for row in sorted(rows, key=lambda row: int(str(row.get("number") or 0)))
        if row.get("number") != skip and str(row.get("title") or "") != NIT_STORE_TITLE
    ]
    return items or [Item(source, "clear", f"no open issue is labelled `{EVERGREEN_LABEL}`")]


def scan_follow_ups(runner: Runner, month: str, repo: str | None = None) -> list[Item]:
    source = "follow-up"
    rows, why = _json_list(
        runner,
        ["gh", "issue", "list", *repo_args(repo), "--state", "open", "--label", FOLLOW_UP_LABEL,
         "--limit", str(LIST_LIMIT), "--json", "number,title,body"],
    )
    if rows is None:
        return [Item(source, "unread", f"the dated follow-ups (`{FOLLOW_UP_LABEL}`) could not be listed: {why}")]
    end = _month_end(month)
    items: list[Item] = []
    later = 0
    for row in sorted(rows, key=lambda row: int(str(row.get("number") or 0))):
        found = DUE_RE.search(str(row.get("body") or ""))
        due = _parse_day(found.group(1)) if found else None
        label = f"#{row.get('number')}: {row.get('title')}"
        if due is None:
            # No date is not "not due": nothing says when this one is owed.
            items.append(Item(source, "unread", f"follow-up {label} has no readable `Due: YYYY-MM-DD` line"))
        elif due <= end:
            items.append(Item(source, "due", f"Follow-up due {due.isoformat()} - {label}"))
        else:
            later += 1
    if not items:
        note = f"; {later} not yet due" if later else ""
        return [Item(source, "clear", f"no follow-up is due by {end.isoformat()}{note}")]
    return items


def scan_friction(log: Path | None) -> list[Item]:
    """The friction log is one file on ONE host; the line says so."""
    source = "friction"
    if log is None:
        return [Item(source, "unread", "the friction log's location could not be worked out (not a git checkout?)")]
    if not log.exists():
        return [Item(source, "clear", "no friction log on this host")]
    try:
        lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError) as exc:
        return [Item(source, "unread", f"the friction log could not be read ({exc})")]
    actionable = broken = 0
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            broken += 1
            continue
        if isinstance(record, dict) and record.get("class") in ACTIONABLE_FRICTION:
            actionable += 1
    items: list[Item] = []
    if broken:
        items.append(Item(source, "unread", f"{broken} friction record(s) on this host are not valid JSON"))
    if actionable:
        items.append(
            Item(source, "due",
                 f"Run `/self-improvement:retro`: {actionable} friction signal(s) waiting on this host "
                 f"(other hosts keep their own log)")
        )
    return items or [Item(source, "clear", "no actionable friction signal on this host")]


def scan_command_budget(root: Path | None) -> list[Item]:
    """Command documents against their declared word budgets (issue #1669).

    A repository with no budget file has no such surface: that is clear, and
    says so. A budget file that is present but cannot be applied - an
    unparseable row, a listed document that is missing - is unread, because
    "nothing over budget" was not established.
    """
    source = "command-budget"
    if root is None:
        return [Item(source, "unread", "the repository root is not known, so command budgets were not examined")]
    table = root / ".claude" / "command-word-budgets.tsv"
    if not table.exists():
        return [Item(source, "clear", "this repository declares no command-document word budget")]
    try:
        rows = [line for line in table.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    except (OSError, UnicodeDecodeError) as exc:
        return [Item(source, "unread", f"the command word-budget file could not be read ({exc})")]
    over: list[str] = []
    for row in rows:
        budget, _, rel = row.partition("\t")
        doc = root / ".claude" / "commands" / rel.strip()
        try:
            words = len(doc.read_text(encoding="utf-8").split())
            limit = int(budget)
        except (OSError, UnicodeDecodeError, ValueError):
            return [Item(source, "unread",
                         f"the command word budget could not be applied (row `{row.strip()[:60]}`)")]
        if words > limit:
            over.append(f"{rel.strip()} ({words} > {limit})")
    if over:
        shown = ", ".join(over[:5]) + (f" and {len(over) - 5} more" if len(over) > 5 else "")
        return [Item(source, "due", f"Trim {len(over)} command document(s) over their word budget: {shown}")]
    return [Item(source, "clear", f"all {len(rows)} budgeted command document(s) are within budget")]


def scan(
    runner: Runner, resolver: Path, friction_log: Path | None, today: date, root: Path | None = None,
    repo: str | None = None,
) -> list[Item]:
    nit, store = scan_nit_store(runner, resolver, today)
    return [
        *nit,
        *scan_evergreen(runner, store, repo),
        *scan_command_budget(root),
        *scan_friction(friction_log),
        *scan_follow_ups(runner, month_of(today), repo),
    ]


def render_body(items: Sequence[Item], today: date) -> str:
    month = month_of(today)
    due = [item for item in items if item.state == "due"]
    unread = [item for item in items if item.state == "unread"]
    clear = [item for item in items if item.state == "clear"]
    lines = [
        f"Monitoring list for {month}, written by `/monthly:create` on {today.isoformat()} "
        f"from a scan of this repository.",
        "",
        "Work it with `/monthly:review`. Tick an item with a one-line record of what was done, "
        "or leave it open and say why it is carried to next month.",
        "",
        "## Checklist",
    ]
    lines.extend(f"- [ ] {item.text}" for item in due)
    if not due:
        lines.append("- nothing was found due")
    if unread:
        lines.extend(("", "## Could not be read", ""))
        lines.append("Each of these is unexamined, not clear. Read it by hand and record what you found.")
        lines.append("")
        lines.extend(f"- [ ] UNREAD - {item.text}" for item in unread)
    lines.extend(("", "## Read, nothing due"))
    lines.extend(f"- {item.text}" for item in clear)
    if not clear:
        lines.append("- none")
    return "\n".join(lines) + "\n"
