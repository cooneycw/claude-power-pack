#!/usr/bin/env python3
"""Read-only, informational review yield and fix provenance report (#1865).

No result gates monthly creation. Fixture mode performs no GitHub calls.
Canonical answer spellings are loaded from the closing-report contract.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
REPOS = ("cooneycw/kyle", "cooneycw/skillc", "cooneycw/claude-power-pack")


class ReadError(Exception):
    """A source is unavailable or incomplete, never an empty observation."""


def gh_api(args):
    try:
        done = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=120, check=False)
        if done.returncode:
            raise ReadError(f"GitHub API exited {done.returncode}: {args[0]}")
        return json.loads(done.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise ReadError(f"GitHub API unreadable: {args[0]}") from exc


def pages(api, endpoint):
    rows = []
    for page in range(1, 1001):
        value = api([f"{endpoint}{'&' if '?' in endpoint else '?'}per_page=100&page={page}"])
        if not isinstance(value, list):
            raise ReadError(f"non-list page: {endpoint}")
        rows.extend(value)
        if len(value) < 100:
            return rows
    raise ReadError(f"pagination bound reached: {endpoint}")


def closed_issues(api, repo, number):
    owner, name = repo.split("/")
    cursor = None
    result = []
    for _ in range(1000):
        query = '''query($owner:String!,$name:String!,$number:Int!,$cursor:String){
 repository(owner:$owner,name:$name){pullRequest(number:$number){
 closingIssuesReferences(first:100,after:$cursor){nodes{number repository{nameWithOwner}}
 pageInfo{hasNextPage endCursor}}}}}'''
        args = ["graphql", "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"name={name}",
                "-F", f"number={number}"]
        if cursor:
            args += ["-f", f"cursor={cursor}"]
        value = api(args)
        try:
            if value.get("errors"):
                raise ReadError("GraphQL returned errors")
            connection = value["data"]["repository"]["pullRequest"]["closingIssuesReferences"]
            result.extend(connection["nodes"])
            info = connection["pageInfo"]
            if not info["hasNextPage"]:
                return result
            if not info["endCursor"] or info["endCursor"] == cursor:
                raise ReadError("closing issue cursor did not advance")
            cursor = info["endCursor"]
        except (KeyError, TypeError, AttributeError) as exc:
            raise ReadError("closing issues unreadable") from exc
    raise ReadError("closing issue pagination bound reached")


def collect_repo(api, repo, since, until):
    result = {"prs": None, "receipts": None, "errors": []}
    try:
        query = quote(f"repo:{repo} is:pr is:merged merged:{since}..{until}", safe="")
        candidates = []
        for page in range(1, 11):
            listing = api([f"search/issues?q={query}&per_page=100&page={page}"])
            if (not isinstance(listing, dict) or listing.get("incomplete_results") is not False
                    or not isinstance(listing.get("total_count"), int) or listing["total_count"] > 1000
                    or not isinstance(listing.get("items"), list)):
                raise ReadError("merged PR search incomplete or beyond 1000-result bound; narrow period")
            candidates.extend(listing["items"])
            if len(candidates) >= listing["total_count"]:
                break
            if not listing["items"]:
                raise ReadError("merged PR search ended before total_count")
        result["prs"] = []
        for candidate in candidates:
            if not re.match(r"^fix\([^)]+\)(?:!)?:", candidate["title"]):
                continue
            pr = {"number": candidate["number"], "title": candidate["title"], "issues": None}
            result["prs"].append(pr)
            try:
                details = api([f"repos/{repo}/pulls/{pr['number']}"])
                pr["merged_at"] = details["merged_at"]
                refs = closed_issues(api, repo, pr["number"])
                pr["issues"] = []
                for ref in refs:
                    target = ref["repository"]["nameWithOwner"]
                    number = ref["number"]
                    issue = {"repo": target, "number": number, "body": None, "comments": None}
                    pr["issues"].append(issue)
                    body = api([f"repos/{target}/issues/{number}"])
                    comments = pages(api, f"repos/{target}/issues/{number}/comments")
                    issue.update(body=body["body"] or "", comments=[row["body"] for row in comments])
            except (ReadError, KeyError, TypeError) as exc:
                result["errors"].append(f"PR #{pr['number']}: {exc}")
    except (ReadError, KeyError, TypeError) as exc:
        result["errors"].append(f"PR listing: {exc}")
    try:
        # Pin the entire observation to one committed main tree, not moving contents URLs.
        commit = api([f"repos/{repo}/commits/main"])
        tree = api([f"repos/{repo}/git/trees/{commit['sha']}?recursive=1"])
        if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
            raise ReadError("main tree incomplete")
        entries = [row for row in tree["tree"] if row["path"].startswith("docs/measurements/counter-model/")
                   and row["path"].endswith(".json") and row["type"] == "blob"]
        if not entries:
            raise ReadError("no committed counter-model receipt files")
        result["receipts"] = []
        for entry in entries:
            try:
                blob = api([f"repos/{repo}/git/blobs/{entry['sha']}"])
                if blob.get("encoding") != "base64":
                    raise ReadError("unsupported blob encoding")
                receipt = json.loads(base64.b64decode(blob["content"]).decode("utf-8"))
                result["receipts"].append(receipt)
            except (ReadError, ValueError, KeyError, UnicodeError) as exc:
                result["receipts"].append(None)
                result["errors"].append(f"receipt {entry['path']}: {exc}")
        result["receipt_head"] = commit["sha"]
    except (ReadError, KeyError, TypeError) as exc:
        result["errors"].append(f"Receipt listing: {exc}")
    return result


def answer_lists(contract):
    lists = []
    for marker in ("defect-origin-answers", "defect-missed-answers"):
        match = re.search(rf"<!-- {marker} -->(.*?)<!-- /{marker} -->", contract, re.S)
        answers = re.findall(r"^- `([^`]+)`", match[1], re.M) if match else []
        if not answers:
            raise ReadError(f"canonical answer lists missing/unreadable: {marker}")
        lists.append(answers)
    return lists


def classify(value, answers):
    for answer in answers:
        pattern = re.escape(answer).replace(re.escape("<number>"), r"[1-9][0-9]*")
        pattern = pattern.replace(re.escape("<what was tried>"), r"\S.*")
        if re.fullmatch(pattern, value):
            return answer
    return None


def day(timestamp):
    if not isinstance(timestamp, str):
        raise ValueError("missing timestamp")
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()


def provenance(issue, lists):
    if (not isinstance(issue, dict) or not isinstance(issue.get("body"), str)
            or not isinstance(issue.get("comments"), list)
            or not all(isinstance(comment, str) for comment in issue["comments"])):
        raise ReadError("issue body/comments unreadable")
    text = "\n".join([issue["body"], *issue["comments"]]).replace("\r\n", "\n").replace("\r", "\n")
    values = []
    missing, invalid = [], []
    for label, answers in zip(("Origin", "Missed because"), lists):
        found = set(re.findall(rf"^{label}:[ \t]*([^\n]*)", text, re.M))
        if not found or found == {""}:
            missing.append(label)
            values.append(None)
        elif len(found) != 1 or (category := classify(next(iter(found)), answers)) is None:
            invalid.append(label)
            values.append(None)
        else:
            values.append(category)
    state = f"MISSING {', '.join(missing)}" if missing else "recorded"
    if invalid:
        state = f"INVALID {', '.join(invalid)}" + (f"; {state}" if missing else "")
    return state, values


def render(data, since, until, contract):
    lines = [f"# Review yield and fix provenance: {since}..{until}", "",
             "Observation only; missing provenance is not proof of an escaped defect.",
             "Receipt totals use the latest cumulative snapshot per issue recorded in the period.", ""]
    try:
        lists = answer_lists(contract)
    except ReadError as exc:
        return "\n".join([*lines, f"UNKNOWN: canonical answer lists - {exc}", ""])
    if not isinstance(data, dict) or not isinstance(data.get("repos"), dict) or not data["repos"]:
        return "\n".join([*lines, "UNKNOWN: no readable repositories", ""])
    for name, repo in data["repos"].items():
        lines += [f"## {name}", ""]
        if not isinstance(repo, dict):
            lines += ["UNKNOWN: repository unreadable", ""]
            continue
        errors = list(repo.get("errors", [])) if isinstance(repo.get("errors", []), list) else ["errors unreadable"]
        prs = repo.get("prs")
        readable, total = 0, len(prs) if isinstance(prs, list) else "unknown"
        tallies = [Counter(), Counter()]
        missing_count = earlier = 0
        if isinstance(prs, list):
            for pr in prs:
                try:
                    if not isinstance(pr, dict):
                        raise ReadError("PR record malformed")
                    if "merged_at" in pr and not since <= day(pr["merged_at"]) <= until:
                        continue
                    if not isinstance(pr.get("title"), str):
                        raise ReadError("PR title unreadable")
                    if not re.match(r"^fix\([^)]+\)(?:!)?:", pr["title"]):
                        continue
                    number = pr["number"]
                    if "merged_at" not in pr:
                        raise ReadError(f"PR #{number} merge date unreadable")
                    issues = pr.get("issues")
                    if not isinstance(issues, list):
                        raise ReadError(f"PR #{number} closing issues unreadable")
                    observations = [(issue, *provenance(issue, lists)) for issue in issues]
                    readable += 1
                    if not issues:
                        missing_count += 1
                        lines.append(f"- #{number}: MISSING linked closing issue - {pr['title']}")
                    for issue, state, values in observations:
                        lines.append(f"- #{number}: {state} ({issue['repo']}#{issue['number']}) - {pr['title']}")
                        if state != "recorded":
                            missing_count += 1
                        for tally, value in zip(tallies, values):
                            if value:
                                tally[value] += 1
                        if values[0] == lists[0][0] and values[1] and values[1] != lists[1][-1]:
                            earlier += 1
                except (ReadError, ValueError, KeyError, TypeError) as exc:
                    errors.append(str(exc))
        else:
            errors.append("merged PR listing unreadable")
        lines += [f"PRs readable: {readable}/{total} (listed candidates; period fix PRs only in numerator)",
                  f"Missing/invalid provenance records observed: {missing_count}",
                  f"Earlier-work origins: {earlier} observed; total escapes UNKNOWN when provenance is incomplete."]
        if prs == []:
            lines.append("No merged fix(...) PRs in period.")
        for label, tally in zip(("Origin", "Missed because"), tallies):
            lines.append(f"{label} tallies: " + ("; ".join(f"{key}: {count}" for key, count in sorted(tally.items()))
                                               or "none observed"))
        receipts = repo.get("receipts")
        good, skipped, older, selected = 0, 0, 0, {}
        if isinstance(receipts, list):
            for receipt in receipts:
                try:
                    if not isinstance(receipt, dict):
                        raise ValueError("receipt not an object")
                    recorded = day(receipt.get("recorded_at"))
                    if receipt.get("status") not in ("ran", "skipped"):
                        raise ValueError("receipt status invalid")
                    if receipt["status"] == "ran":
                        counts = receipt.get("counts")
                        if (not isinstance(counts, dict) or not all(type(counts.get(k)) is int and counts[k] >= 0
                                                                  for k in ("accepted", "rejected", "deferred"))
                                or type(receipt.get("passes")) is not int or receipt["passes"] < 1
                                or not str(receipt.get("issue", "")).isdigit()):
                            raise ValueError("receipt counts/passes/issue invalid")
                    good += 1
                    if not since <= recorded <= until:
                        continue
                    if receipt["status"] == "skipped":
                        skipped += 1
                        continue
                    issue = str(receipt["issue"])
                    if issue in selected:
                        older += 1
                        if receipt["recorded_at"] <= selected[issue]["recorded_at"]:
                            continue
                    selected[issue] = receipt
                except (ValueError, TypeError) as exc:
                    errors.append(f"receipt unreadable: {exc}")
            sums = Counter()
            for issue, receipt in sorted(selected.items()):
                sums.update(receipt["counts"])
                lines.append(f"- Issue #{issue}: {receipt['passes']} passes")
            yield_line = "; ".join(f"{key}: {sums[key]}" for key in ("accepted", "rejected", "deferred"))
            lines += [f"Review yield: {yield_line}",
                      f"Receipts readable: {good}/{len(receipts)}; {skipped} skipped; "
                      f"{older} older snapshot(s) omitted"]
        else:
            lines += ["Review yield: UNKNOWN", "Receipts readable: 0/unknown"]
            errors.append("receipt source unavailable or not adopted")
        if repo.get("receipt_head"):
            lines.append(f"Receipt main snapshot: {repo['receipt_head']}")
        if errors:
            lines += ["UNKNOWN: partial observation; totals above are readable records only.",
                      *[f"- Could not read: {error}" for error in errors]]
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, type=date.fromisoformat)
    parser.add_argument("--until", required=True, type=date.fromisoformat)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--repo", action="append", help="owner/name; repeatable (default: kyle, skillc, CPP)")
    args = parser.parse_args(argv)
    if args.since > args.until:
        parser.error("--since must not follow --until")
    since, until = args.since.isoformat(), args.until.isoformat()
    try:
        contract = (ROOT / "docs/agents/closing-report-contract.md").read_text(encoding="utf-8")
        if args.fixture:
            data = json.loads(args.fixture.read_text(encoding="utf-8"))
        else:
            data = {"repos": {repo: collect_repo(gh_api, repo, since, until) for repo in (args.repo or REPOS)}}
        print(render(data, since, until, contract))
    except (OSError, ValueError) as exc:
        print(f"UNKNOWN: report input unreadable ({type(exc).__name__})")
    return 0  # Observation, not a gate; UNKNOWN never prevents monthly creation.


if __name__ == "__main__":
    raise SystemExit(main())
