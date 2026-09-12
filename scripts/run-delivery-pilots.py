#!/usr/bin/env python3
"""Run the bounded delivery pilots for #861 and record what was actually observed.

WHY THIS IS CHECKED IN. The #859 and #860 evidence bundles were runnable only from
the author's machine: their runners pointed at a worktree path that no longer
exists, so a reviewer could read the transcripts but could not re-run anything, and
the claims rested on a path nobody else had. Everything this runner needs is either
in the repository or named on the command line.

WHAT IT BINDS TO. The guidance handed to the model, and the scripts used to build
the input, are read from a REVIEWED COMMIT with `git show`, never from the working
tree. Pass `--commit` to pin one; the default is HEAD. That way the prompt a result
was produced from can be reconstructed from the commit recorded beside it, rather
than from whatever the tree happened to contain that afternoon.

WHAT IT MEASURES, AND WHAT IT DOES NOT. It records mechanical facts only: the
process status, the output size, and which issue reference the model selected. The
selected reference is the decision that acts - it is what the closing step publishes
- so it is a real observation, not a proxy. Everything else is left to a reader of
the transcripts. In particular the `mentions` column is PHRASE PRESENCE and nothing
more: it says a string occurs, never that the report understood it. No completion
parser is built here and none is wanted; a scorer that decides whether a report is
"good" is just a second model nobody reviewed.

An empty output scores as "no Closes", which reads exactly like a correct Refs
result - so the returncode and the character count are recorded on every run and a
failed run is printed as FAILED rather than folded into the totals.

Usage:
    scripts/run-delivery-pilots.py --suite completion --out DIR [--commit SHA]
    scripts/run-delivery-pilots.py --suite completion --out DIR --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RULE_START = "**Acceptance accounting (issue #860).**"
RULE_END = "### Step 3: Check for Changes"
GUIDANCE_PATH = ".claude/commands/flow/finish.md"
CONVERTER_PATH = "scripts/speckit-tasks-to-issues.sh"
HELPER_PATH = "scripts/speckit-context.py"
FIXTURES = "tests/fixtures/delivery_pilots"

# The agreement the revision record points at. It is a REFERENCE to an authority
# decision, not the decision itself - this runner cannot and does not establish that
# anyone was entitled to accept the change.
REVISION_REF = "issue thread, reviewer agreement 2026-09-12"

GH_STUB = r'''#!/usr/bin/env python3
"""Minimal gh stub: enough to let the real converter file one issue locally."""
import json, os, subprocess, sys
from pathlib import Path

STATE = Path(os.environ["GH_STUB_STATE"])
argv = sys.argv[1:]

if argv[:2] == ["issue", "list"]:
    state = json.loads(STATE.read_text())
    rows = [{k: i[k] for k in ("number", "title", "body")} for i in state["issues"]]
    jq_filter = argv[argv.index("--jq") + 1] if "--jq" in argv else "."
    done = subprocess.run(
        ["jq", "-r", jq_filter], input=json.dumps(rows), capture_output=True, text=True
    )
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    sys.exit(done.returncode)

if argv[:2] == ["issue", "create"]:
    state = json.loads(STATE.read_text())
    number = state["next"]
    state["next"] = number + 1
    state["issues"].append({
        "number": number,
        "title": argv[argv.index("--title") + 1],
        "body": argv[argv.index("--body") + 1],
    })
    STATE.write_text(json.dumps(state))
    print("https://github.com/acme/exports/issues/%d" % number)
    sys.exit(0)

sys.exit(0)
'''


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def repo_root() -> Path:
    done = run(["git", "rev-parse", "--show-toplevel"])
    if done.returncode != 0:
        sys.exit("not inside a git checkout; run this from the claude-power-pack repo")
    return Path(done.stdout.strip())


def show(root: Path, commit: str, path: str) -> str:
    """One file, as of a reviewed commit. Never the working tree."""
    done = run(["git", "-C", str(root), "show", f"{commit}:{path}"])
    if done.returncode != 0:
        sys.exit(f"could not read {path} at {commit}: {done.stderr.strip()}")
    return done.stdout


def extract_rule(guidance: str) -> str:
    try:
        rule = guidance[guidance.index(RULE_START) : guidance.index(RULE_END)].strip()
    except ValueError:
        sys.exit(
            f"the accounting rule markers were not found in {GUIDANCE_PATH}. The "
            "guidance moved or was reworded; re-point this runner rather than "
            "letting it silently hand the model a different rule."
        )
    if "ACCEPTANCE_COMPLETE" not in rule:
        sys.exit("the extracted rule is missing the decision it turns on")
    return rule


def build_issue(root: Path, commit: str, workdir: Path) -> tuple[int, str, str, str]:
    """Generate the issue with the REAL converter, then record a revision on it.

    Returns (issue number, body, the checker's report on that body, v2 source digest).

    The body is not written by hand anywhere. It is what the shipped converter
    produces from the fixture spec and tasks file, which is the point: criteria 2
    and 3 are about a decision taken on the artifact criterion 1 produces.
    """
    for tool in ("git", "bash", "jq", "python3"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} is required to build the pilot issue and was not found")

    scripts = workdir / "scripts"
    scripts.mkdir(parents=True)
    for rel in (CONVERTER_PATH, HELPER_PATH):
        dest = scripts / Path(rel).name
        dest.write_text(show(root, commit, rel), encoding="utf-8")
        dest.chmod(0o755)

    project = workdir / "project"
    feature = project / ".specify/specs/exports"
    feature.mkdir(parents=True)
    run(["git", "init", "-q", str(project)])
    run(["git", "-C", str(project), "remote", "add", "origin",
         "https://github.com/acme/exports.git"])

    fixtures = root / FIXTURES / "completion"
    (feature / "tasks.md").write_text((fixtures / "tasks.md").read_text(), encoding="utf-8")
    spec = feature / "spec.md"
    spec.write_text((fixtures / "spec-v1.md").read_text(), encoding="utf-8")

    bindir = workdir / "bin"
    bindir.mkdir()
    stub = bindir / "gh"
    stub.write_text(GH_STUB, encoding="utf-8")
    stub.chmod(0o755)
    state = workdir / "state.json"
    state.write_text(json.dumps({"next": 501, "issues": []}))

    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "GH_STUB_STATE": str(state),
    }
    done = run(
        ["bash", str(scripts / "speckit-tasks-to-issues.sh"),
         "--tasks", ".specify/specs/exports/tasks.md", "--feature", "exports"],
        cwd=project, env=env,
    )
    if done.returncode != 0:
        sys.exit(f"the converter failed while building the pilot issue:\n{done.stderr}")
    issues = json.loads(state.read_text())["issues"]
    if len(issues) != 1:
        sys.exit(f"expected exactly one generated issue, got {len(issues)}")
    number = issues[0]["number"]
    body = issues[0]["body"]
    if "speckit-context:v1" not in body:
        sys.exit("the generated issue carries no context block; there is nothing to hand on")

    # The authorised revision: the spec moves to v2, and the record names the version
    # that was agreed. The helper REPORTS this record; it never rules it authorised,
    # and neither does this runner.
    spec.write_text((fixtures / "spec-v2.md").read_text(), encoding="utf-8")
    digest = run(
        ["python3", "-c",
         "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest()[:12])",
         str(spec)],
    ).stdout.strip()
    body = f"{body.rstrip()}\n\nAcceptance-revision: source-digest={digest} ref={REVISION_REF}\n"

    check = run(
        ["python3", str(scripts / "speckit-context.py"), "check", "--body-file", "-",
         "--root", "."],
        cwd=project, input=body,
    )
    return number, body, (check.stdout + check.stderr).strip(), digest


def build_prompt(rule: str, number: int, issue: str, check: str, work: str) -> str:
    return (
        "You are preparing the pull-request body for completed work.\n\n"
        "The project's reporting rule is:\n\n" + rule + "\n\n"
        # Without the number the model has nothing to reference and echoes the
        # rule's own `#N` placeholder, which no closing guard would ever act on.
        f"----- THE ISSUE (this is issue #{number} in acme/exports), AS GENERATED "
        "AND THEN AMENDED -----\n"
        + issue.strip()
        + "\n\n----- WHAT THE CONTEXT CHECKER REPORTED ON THAT ISSUE -----\n"
        + check
        + "\n\n----- WHAT THE WORK ACTUALLY DID -----\n"
        + work.strip()
        + "\n-----\n\n"
        "Write the PR body you would submit. Output only the body."
    )


def codex_config() -> dict[str, str]:
    """The settings that actually shaped the answers, recorded beside them.

    Only the two keys that matter are read by name. Copying the file wholesale
    would put whatever else lives in it - keys included - into a results file that
    gets attached to an issue.
    """
    wanted = ("model", "model_reasoning_effort")
    found = {k: "unset" for k in wanted}
    config = Path.home() / ".codex" / "config.toml"
    if config.is_file():
        for line in config.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in wanted:
                found[key.strip()] = value.strip().strip('"\'')
    return found


def codex(prompt: str, cwd: Path, timeout: int) -> tuple[int, str]:
    done = subprocess.run(
        ["codex", "exec", "--json", "--sandbox", "read-only",
         "--skip-git-repo-check", "-C", str(cwd), prompt],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
    )
    messages = []
    for line in done.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item") or {}
        if item.get("type") == "agent_message" and item.get("text"):
            messages.append(item["text"])
    return done.returncode, (messages[-1] if messages else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["completion"], default="completion")
    parser.add_argument("--out", required=True, type=Path, help="directory for transcripts")
    parser.add_argument("--commit", default="HEAD", help="commit the guidance is read from")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true",
                        help="build and print the prompts; run no model")
    args = parser.parse_args()

    root = repo_root()
    resolved = run(["git", "-C", str(root), "rev-parse", args.commit]).stdout.strip()
    if not resolved:
        sys.exit(f"could not resolve --commit {args.commit}")
    rule = extract_rule(show(root, resolved, GUIDANCE_PATH))
    cases = json.loads(
        (root / FIXTURES / args.suite / "cases.json").read_text()
    )["cases"]

    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        number, issue, check, digest = build_issue(root, resolved, Path(tmp))
        (args.out / "issue.md").write_text(issue, encoding="utf-8")
        (args.out / "context-check.txt").write_text(check + "\n", encoding="utf-8")

        if args.dry_run:
            for case in cases:
                (args.out / f"{case['name']}.prompt.txt").write_text(
                    build_prompt(rule, number, issue, check, case["work"]),
                    encoding="utf-8",
                )
            print(f"dry run: {len(cases)} prompt(s) written to {args.out}")
            return 0

        if shutil.which("codex") is None:
            sys.exit("codex is not on PATH; use --dry-run to inspect the prompts")
        version = run(["codex", "--version"]).stdout.strip()
        effective = codex_config()

        results: dict[str, dict] = {}
        for case in cases:
            name = case["name"]
            started = time.time()
            code, body = codex(
                build_prompt(rule, number, issue, check, case["work"]),
                Path(tmp), args.timeout,
            )
            (args.out / f"{name}.txt").write_text(body, encoding="utf-8")
            results[name] = {
                "returncode": code,
                "chars": len(body),
                "closes": bool(re.search(r"\bCloses #", body)),
                "refs": bool(re.search(r"\bRefs #", body)),
                "expect_closes": case["expect_closes"],
                # Phrase presence, not comprehension. Recorded so a reader can find
                # the relevant paragraph, never as a score.
                "mentions_cancel": "cancel" in body.lower(),
                "seconds": round(time.time() - started, 1),
            }
            row = results[name]
            if code != 0 or not body:
                print(f"{name:36} FAILED rc={code} chars={len(body)}")
                continue
            agrees = "ok " if row["closes"] == case["expect_closes"] else "DIFFERS"
            print(
                f"{name:36} rc=0 chars={len(body):<5} "
                f"Closes={row['closes']!s:<5} Refs={row['refs']!s:<5} {agrees}"
            )

        (args.out / "results.json").write_text(
            json.dumps(
                {
                    "commit": resolved,
                    "guidance": GUIDANCE_PATH,
                    "runner": version,
                    "config": effective,
                    "issue_number": number,
                    "revision_source_digest": digest,
                    "cases": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    print(f"\ntranscripts and results.json in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
