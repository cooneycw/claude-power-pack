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
process status, the output size, and a regex match for the issue reference the model
appears to have selected. That regex is PHRASE DETECTION over the text - it is a
pointer into the transcript, not a finding about what the closing step would publish.
The evidence for that is the raw body, read by a person, together with the real
`gh-pr-merge.sh` guard this runner invokes over the produced bodies. The `mentions`
column is weaker still: it says a string occurs, never that the report understood it.
No completion parser is built here and none is wanted; a scorer that decides whether
a report is "good" is just a second model nobody reviewed.

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
GUARD_PATH = "scripts/gh-pr-merge.sh"
GUARD_CHECK_PATH = f"{FIXTURES}/completion/guard-check.sh"
# The guidance THIS SERIES introduced (#859): the execution fence plus the plan
# revision block. The guided pilots run with it so the question stops being "can a
# generic agent do this" and becomes "does our guidance preserve that freedom".
DELEGATED_GUIDANCE_PATH = ".claude/commands/codex/auto.md"
GUIDANCE_START = "EXECUTION FENCE - MANDATORY CONSTRAINTS"
GUIDANCE_END = "<the rest of the Codex prompt"

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


def export_tree(root: Path, commit: str, path: str, dest: Path) -> Path:
    """Materialise a fixture tree AS OF a reviewed commit, not from the working tree.

    `--commit` used to pin only the guidance and the scripts; the fixtures - the
    spec, the tasks file, the case wording, the pilot sources - were read live. A
    result was therefore reproducible only if nobody had edited a fixture since, and
    nothing said so. Now the whole named input set comes from the commit.
    """
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(root), "archive", commit, path], capture_output=True
    )
    if archive.returncode != 0:
        sys.exit(
            f"could not export {path} at {commit}: "
            f"{archive.stderr.decode(errors='replace').strip()}"
        )
    unpack = subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout,
                            capture_output=True)
    if unpack.returncode != 0:
        sys.exit(f"could not unpack {path}: {unpack.stderr.decode(errors='replace')}")
    return dest / path


def tree_hash(root: Path, commit: str, path: str) -> str:
    """The content hash of the pinned input set, recorded beside every result."""
    done = run(["git", "-C", str(root), "rev-parse", f"{commit}:{path}"])
    return done.stdout.strip() or "unknown"


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


def build_issue(root: Path, commit: str, workdir: Path) -> tuple[int, str, str, str, Path]:
    """Generate the issue with the REAL converter, then record a revision on it.

    Returns (issue number, body, the checker's report, v2 source digest, and the
    PINNED fixture directory every completion input must be read from).

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

    fixtures = export_tree(root, commit, f"{FIXTURES}/completion", workdir / "pinned")
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
    # `check` exits 3 for any state other than current/absent - a verdict. Anything
    # else is a broken checker, and presenting its output as a verified revision
    # state would be reporting an instrument failure as a measurement.
    if check.returncode not in (0, 3):
        sys.exit(
            f"the context check failed (exit {check.returncode}); refusing to present "
            f"its output as a verified revision state:\n{check.stdout}{check.stderr}"
        )
    return number, body, (check.stdout + check.stderr).strip(), digest, fixtures


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


def codex(prompt: str, cwd: Path, timeout: int, sandbox: str = "read-only",
          events_path: Path | None = None) -> tuple[int, str]:
    """Returns (status, final message). A timeout is reported, never raised.

    `events_path` retains the RAW event stream. The final message is a summary the
    model wrote about itself; the stream is what it actually did, and it is the only
    way a reader can see whether it stopped to ask for anything on the way.

    An exception here would lose every observation recorded before it, which is the
    opposite of what an evidence runner should do under failure.
    """
    try:
        done = subprocess.run(
            ["codex", "exec", "--json", "--sandbox", sandbox,
             "--skip-git-repo-check", "-C", str(cwd), prompt],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        if events_path is not None:
            events_path.write_text("", encoding="utf-8")
        return -1, ""
    if events_path is not None:
        events_path.write_text(done.stdout, encoding="utf-8")
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


def delegated_guidance(root: Path, commit: str) -> str:
    """The fence and plan-revision block CPP actually sends, from a pinned commit."""
    doc = show(root, commit, DELEGATED_GUIDANCE_PATH)
    try:
        block = doc[doc.index(GUIDANCE_START) : doc.index(GUIDANCE_END)].rstrip()
    except ValueError:
        sys.exit(
            f"the guidance markers were not found in {DELEGATED_GUIDANCE_PATH}; "
            "re-point this runner rather than silently running an unguided pilot"
        )
    if "PLAN REVISION" not in block:
        sys.exit("the extracted guidance is missing the plan-revision block")
    return block


def run_pilots(root: Path, commit: str, out: Path, timeout: int, dry_run: bool,
               variant: str = "baseline") -> dict:
    """Bounded implementation pilots: real edits, then a check the agent never saw.

    The agent gets `task.md` and `src/`. It does NOT get `check.py` - a check visible
    to the implementer measures whether it can satisfy a test it can read, which is a
    different and much easier question. The check is copied in afterwards.
    """
    # Pinned, like the completion inputs: a pilot result names the commit its task
    # wording, starting source and check came from.
    fixtures = export_tree(root, commit, f"{FIXTURES}/pilots", out / ".pinned")
    guidance = delegated_guidance(root, commit) if variant == "guided" else ""
    results: dict[str, dict] = {}
    for pilot in sorted(d for d in fixtures.iterdir() if d.is_dir()):
        name = pilot.name
        workspace = out / name
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(
            pilot / "src", workspace / "src",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        # The guided variant uses the task that does NOT pre-forbid extra files, so
        # an absence of ceremony is an observation rather than something the prompt
        # instructed. The baseline task forbids them, and its result is read that way.
        task_file = pilot / ("task.md" if variant == "baseline" else "task-open.md")
        if not task_file.is_file():
            sys.exit(f"{name}: {task_file.name} is missing for variant {variant}")
        task = task_file.read_text(encoding="utf-8")
        if variant == "guided":
            task = guidance + "\n\n" + task
        # The workspace carries the SAME task the prompt used. Copying task.md
        # regardless left the guided runs looking at a file that forbids extra
        # files while their prompt did not - contradictory inputs, and exactly
        # the variable this variant exists to control.
        shutil.copy2(task_file, workspace / "task.md")
        (out / f"{name}.prompt.txt").write_text(task, encoding="utf-8")

        if dry_run:
            print(f"{name:28} prompt prepared in {workspace}")
            continue

        started = time.time()
        # One codex() for both suites, so a timeout is recorded the same way here as
        # in the completion cases rather than aborting the run.
        code, account = codex(task, workspace, timeout, sandbox="workspace-write",
                              events_path=out / f"{name}.events.jsonl")
        (out / f"{name}.account.txt").write_text(account, encoding="utf-8")

        # The behavioural check, brought in only now. Each pilot names its check
        # distinctly (check_<thing>.py): two files both called check.py are two
        # modules with one name, which the repo's typecheck gate rejects.
        checks = sorted(pilot.glob("check_*.py"))
        if len(checks) != 1:
            sys.exit(f"{name}: expected exactly one check_*.py, found {len(checks)}")
        shutil.copy2(checks[0], workspace / checks[0].name)
        check = run(["python3", str(workspace / checks[0].name)], cwd=workspace)
        (out / f"{name}.check.txt").write_text(
            check.stdout + check.stderr, encoding="utf-8"
        )

        # Bytecode is excluded throughout: running the check compiles the module in
        # place, so a .pyc this runner created would otherwise be reported as a file
        # the agent added - noise that reads exactly like unasked-for ceremony.
        diff = run([
            "diff", "-ru", "-x", "__pycache__",
            str(pilot / "src"), str(workspace / "src"),
        ])
        (out / f"{name}.diff").write_text(diff.stdout, encoding="utf-8")
        # Files the agent added beside the ones it was given. Ceremony a task did not
        # ask for (a plan, a spec, a notes file) shows up here rather than in prose.
        given = {q.name for q in (pilot / "src").iterdir()} | {"task.md"}
        added = sorted(
            q.name for q in workspace.rglob("*")
            if q.is_file()
            and q.name not in given
            and not q.name.startswith("check_")
            and "__pycache__" not in q.parts
        )

        results[name] = {
            "returncode": code,
            "account_chars": len(account),
            "check_passed": check.returncode == 0,
            "check_returncode": check.returncode,
            "diff_lines": len(diff.stdout.splitlines()),
            "files_added": added,
            "events": f"{name}.events.jsonl",
            "seconds": round(time.time() - started, 1),
        }
        row = results[name]
        if code != 0 or not account:
            row["instrument_failed"] = True
            print(f"{name:28} FAILED rc={code} account_chars={len(account)}"
                  + ("  (TIMEOUT)" if code == -1 else ""))
            continue
        row["instrument_failed"] = False
        print(
            f"{name:28} rc=0 check={'pass' if row['check_passed'] else 'FAIL'} "
            f"diff_lines={row['diff_lines']:<4} added={added or 'none'}"
        )
    return results


def run_guard_check(root: Path, commit: str, out: Path, names: list[str]) -> dict:
    """Run the repository's real incidental-close guard over the produced bodies.

    The harness proves its own positive control first: a body that must be refused
    with exit 7. A clean result reported by a harness that is not actually reaching
    the guard is worth nothing, and looks identical to a real pass.
    """
    bodies = [str(out / f"{name}.txt") for name in names]
    if not bodies:
        return {"ran": False, "reason": "no bodies produced"}
    with tempfile.TemporaryDirectory() as tmp:
        pinned = export_tree(root, commit, GUARD_PATH, Path(tmp))
        harness = export_tree(root, commit, GUARD_CHECK_PATH, Path(tmp))
        done = run(["bash", str(harness), str(pinned), *bodies])
    report = (done.stdout + done.stderr).strip()
    (out / "guard-check.txt").write_text(report + "\n", encoding="utf-8")
    print("\n" + report)
    return {
        "ran": True,
        "returncode": done.returncode,
        "all_bodies_pass": done.returncode == 0,
        "control_refused_with_7": "positive control: exit=7" in report,
        # Distinguish "a body would interrupt the merge" from "the harness could not
        # run": both exit 1, and reporting the first when it was the second names a
        # mechanism that was never checked.
        "a_body_tripped": "TRIPPED:" in report,
    }


def pilots_exit_status(results: dict) -> int:
    """Nonzero when the RUN is unusable, not when an agent surprised us.

    An instrument failure and a disappointing result are different things, and a
    runner that returns 0 for both hands a reader a clean summary of nothing.
    """
    broken = [n for n, r in results.items() if r.get("instrument_failed")]
    failed = [n for n, r in results.items() if not r.get("instrument_failed")
              and not r.get("check_passed")]
    for name in broken:
        print(f"INSTRUMENT FAILURE: {name} produced no usable run")
    for name in failed:
        print(f"BEHAVIOURAL CHECK FAILED: {name} ran, but its outcome check did not pass")
    return 1 if (broken or failed) else 0


def completion_exit_status(results: dict, guard: dict) -> int:
    broken = [n for n, r in results.items() if r.get("instrument_failed")]
    for name in broken:
        print(f"INSTRUMENT FAILURE: {name} produced no usable decision")
    if guard.get("ran") and not guard.get("all_bodies_pass"):
        if guard.get("a_body_tripped"):
            print("OBSERVED: a produced body trips the real closing guard "
                  "(see guard-check.txt)")
        else:
            print("INSTRUMENT FAILURE: the real-guard harness did not complete "
                  "(see guard-check.txt)")
    if guard.get("ran") and not guard.get("control_refused_with_7"):
        print("INSTRUMENT FAILURE: the guard harness never proved its positive control")
    # A disposition differing from `expect_closes` is an OBSERVATION, not a broken
    # run: it is reported loudly and does not change the exit status.
    differed = [n for n, r in results.items()
                if not r.get("instrument_failed") and r["closes"] != r["expect_closes"]]
    for name in differed:
        print(f"OBSERVED DIFFERENCE (not a failure): {name} chose the other reference")
    if broken:
        return 1
    if guard.get("ran") and not (guard.get("all_bodies_pass")
                                 and guard.get("control_refused_with_7")):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["completion", "pilots"], default="completion")
    parser.add_argument("--variant", choices=["baseline", "open", "guided"],
                        default="baseline",
                        help="pilots only. baseline: the task that forbids extra "
                             "files, no guidance. open: the same task WITHOUT that "
                             "prohibition, still no guidance. guided: the open task "
                             "plus the pinned CPP delegated guidance. `open` is the "
                             "cell that separates the two variables - without it, a "
                             "baseline/guided difference cannot be attributed to "
                             "either one."),
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
    args.out.mkdir(parents=True, exist_ok=True)
    if args.suite == "pilots":
        if not args.dry_run and shutil.which("codex") is None:
            sys.exit("codex is not on PATH; use --dry-run to stage the workspaces")
        pilot_results = run_pilots(root, resolved, args.out, args.timeout,
                                   args.dry_run, args.variant)
        if not args.dry_run:
            (args.out / "results.json").write_text(
                json.dumps(
                    {
                        "commit": resolved,
                        "runner": run(["codex", "--version"]).stdout.strip(),
                        "config": codex_config(),
                        "fixtures_tree": tree_hash(root, resolved, f"{FIXTURES}/pilots"),
                        "variant": args.variant,
                        "guidance": (DELEGATED_GUIDANCE_PATH
                                     if args.variant == "guided" else "none (baseline)"),
                        "pilots": pilot_results,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"\nworkspaces, diffs and results.json in {args.out}")
        return pilots_exit_status(pilot_results)

    rule = extract_rule(show(root, resolved, GUIDANCE_PATH))

    with tempfile.TemporaryDirectory() as tmp:
        # The case wording is an INPUT, and it comes from the pinned snapshot like
        # every other one. Reading it from the working tree let an uncommitted edit
        # reach a prompt built from a named commit while `commit` and `fixtures_tree`
        # in results.json still claimed that commit - a result nobody could reproduce
        # from what those fields named.
        number, issue, check, digest, pinned = build_issue(root, resolved, Path(tmp))
        cases = json.loads(
            (pinned / "cases.json").read_text(encoding="utf-8")
        )["cases"]
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
                # Instrument failure, kept separate from a decision we disagree with.
                # An empty body scores as "no Closes", which reads exactly like a
                # correct Refs result, so it must never be folded into the totals.
                row["instrument_failed"] = True
                print(f"{name:36} FAILED rc={code} chars={len(body)}"
                      + ("  (TIMEOUT)" if code == -1 else ""))
                continue
            row["instrument_failed"] = False
            agrees = "ok " if row["closes"] == case["expect_closes"] else "DIFFERS"
            print(
                f"{name:36} rc=0 chars={len(body):<5} "
                f"Closes={row['closes']!s:<5} Refs={row['refs']!s:<5} {agrees}"
            )

        # The selected reference is checked by the guard that actually runs at merge,
        # not only by a regex over the text. Extracting `Closes #N` says what the model
        # chose; it does not say what the merge helper would do with it.
        produced = [n for n, r in results.items() if not r.get("instrument_failed")]
        guard = run_guard_check(root, resolved, args.out, produced)
        (args.out / "results.json").write_text(
            json.dumps(
                {
                    "commit": resolved,
                    "guidance": GUIDANCE_PATH,
                    "fixtures_tree": tree_hash(root, resolved, f"{FIXTURES}/completion"),
                    "real_guard": guard,
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
    return completion_exit_status(results, guard)


if __name__ == "__main__":
    raise SystemExit(main())
