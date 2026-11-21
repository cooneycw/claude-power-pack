"""Documented parent checkpoints, paired with real helper verdicts; no live model claim."""

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/delegated-pre-child-guards"
DRIVERS = ("codex", "qwen", "gemma")
TARGET = "/path/to/worktree"
LIVE = "~/.claude/scripts/flow-live-driver-guard.sh"
CLAIM = "~/.claude/scripts/flow-worktree-claim.sh"
STALE = "~/.claude/scripts/flow-stale-check.sh"
requires_git = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None,
                                  reason="requires git and bash")


def sections(text):
    tokens = MarkdownIt("commonmark").parse(text)
    found = {}
    title = ""
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h3":
            title = tokens[i + 1].content
            found[title] = {"position": i, "calls": [], "text": "", "events": [], "phrases": []}
        if title and token.type == "inline":
            found[title]["text"] += " " + " ".join(token.content.split())
            found[title]["phrases"].append((i, " ".join(token.content.split())))
        if title and token.type == "fence" and token.info == "bash":
            for line in token.content.splitlines():
                if line.strip().startswith("~/.claude/scripts/"):
                    found[title]["calls"].append(shlex.split(line, comments=True))
                    found[title]["events"].append((i, shlex.split(line, comments=True)))
    return found


def checkpoints(text):
    parts = sections(text)
    def part(prefix):
        hits = [v for k, v in parts.items() if k.startswith(prefix)]
        return hits[0] if len(hits) == 1 else {"position": -1, "calls": [], "text": "", "events": [], "phrases": []}
    approved = part("Step 3:")
    before, child = part("Pre-child checkpoints"), part("Step 4:")
    gates, cleanup = part("Step 6:"), part("Step 8:")
    initial = [[LIVE, TARGET], [CLAIM, "check", TARGET], [STALE, "origin/main", TARGET]]
    def call_before(section, command, phrase):
        calls = [i for i, words in section["events"] if words == command]
        readers = [i for i, words in section["phrases"] if phrase in words]
        return bool(calls and readers) and calls[0] < readers[0]
    # These are documented transitions, not claims that a live model follows them.
    return {
        "before-child": 0 <= approved["position"] < before["position"] < child["position"],
        "initial-calls": before["calls"] == initial,
        "live-stop": "suspected" in before["text"] and "STOP and ask" in before["text"],
        "claim-stop": re.search(r"held.{0,30}foreign.{0,30}STOP", before["text"]) is not None,
        "unknown": "unchecked" in before["text"] and "never clear" in before["text"],
        "stale": "collision" in before["text"] and "clean tree" in before["text"] and "never stash" in before["text"],
        "pre-gate-stale": call_before(gates, [STALE, "origin/main", TARGET], "Run quality gates:"),
        "pre-fix-live": (call_before(gates, [LIVE, TARGET], "Extract the error output")
                         and "before each fix invocation" in gates["text"].lower()),
        "uncertain-claim": [CLAIM, "check", TARGET] in gates["calls"] and "ownership is uncertain" in gates["text"],
        "own-dirt": all(s in gates["text"] for s in (
            "recorded checkpoint", "child's result", "ONLY confirmed-own changes", "CLEAN tree", "never bypass")),
        "mixed-dirt": all(s in gates["text"] for s in (
            "Unexplained dirt", "STOP and ask", "never stage or commit foreign changes")),
        "review-renewal": all(s in gates["text"] for s in (
            "merge changes the reviewed artifact", "Step 5", "review", "receipt")),
        "release": (call_before(cleanup, [CLAIM, "release", TARGET], "Remove worktree and branch")
                    and "only this run's confirmed self claim" in cleanup["text"]
                    and "before removing" in cleanup["text"]),
        "retain": ("Leave for review keeps the worktree and claim" in cleanup["text"]
                   and "never --force" in cleanup["text"]),
    }


@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("check", ("before-child", "initial-calls", "live-stop", "claim-stop", "unknown", "stale",
                                   "pre-gate-stale", "pre-fix-live", "uncertain-claim", "own-dirt", "mixed-dirt",
                                   "review-renewal", "release", "retain"))
def test_actual_parent_checkpoint_contract(driver, check):
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    assert checkpoints(text)[check], f"{driver}: {check}"


@pytest.mark.parametrize("case", ("good", "late-initial", "missing-initial", "commented-live", "suspected-proceeds",
                                  "held-proceeds", "missing-fix", "mixed-dirt-swept",
                                  "missing-renewal", "foreign-release", "before-approval",
                                  "late-stale", "late-fix", "late-release"))
def test_committed_document_controls(case):
    text = (FIXTURES / f"{case}.md").read_text()
    checks = checkpoints(text)
    if case == "good":
        assert all(checks.values()), checks
    else:
        assert text != (FIXTURES / "good.md").read_text()
        assert not all(checks.values()), checks


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
                           "user.email=fixture@example.invalid", *args], check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture(params=("main", "linked"))
def project(tmp_path, request):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    (main / "own.txt").write_text("original\n")
    (main / "foreign.txt").write_text("original\n")
    git(main, "add", ".")
    git(main, "commit", "-qm", "base")
    if request.param == "linked":
        target = tmp_path / "worktree"
        git(main, "worktree", "add", "-qb", "issue-42-test", str(target))
    else:
        target = main
    return main, target


def actual_call(driver, helper, target, cwd):
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    pre = sections(text).get("Pre-child checkpoints (parent)")
    assert pre is not None, "actual driver lacks pre-child commands"
    calls = [call for call in pre["calls"] if call[0] == helper]
    assert len(calls) == 1
    command = [str(ROOT / "scripts" / Path(calls[0][0]).name),
               *[str(target) if arg == TARGET else arg for arg in calls[0][1:]]]
    env = dict(os.environ, FLOW_CLAIM_SESSION_ID="fixture", FLOW_CLAIM_PID=str(os.getpid()))
    return subprocess.run(["bash", *command], cwd=cwd, env=env, capture_output=True, text=True, check=False)


@requires_git
@pytest.mark.parametrize("driver", DRIVERS)
def test_actual_live_command_distinguishes_clean_own_and_mixed_dirt(project, driver):
    main, target = project
    clear = actual_call(driver, LIVE, target, ROOT)
    assert "FLOW_LIVE_DRIVER: clear" in clear.stdout
    assert f"FLOW_LIVE_DRIVER_PATH: {target}" in clear.stdout
    checkpoint = git(target, "rev-parse", "HEAD")
    (target / "own.txt").write_text("this child's confirmed edit\n")
    own = actual_call(driver, LIVE, target, main)
    assert "FLOW_LIVE_DRIVER: suspected" in own.stdout
    # Parent knows this file from its recorded child result; checkpoint ONLY that path.
    git(target, "add", "--", "own.txt")
    git(target, "commit", "-qm", "confirmed own checkpoint")
    assert git(target, "rev-parse", "HEAD") != checkpoint
    assert "FLOW_LIVE_DRIVER: clear" in actual_call(driver, LIVE, target, ROOT).stdout
    (target / "own.txt").write_text("next confirmed edit\n")
    (target / "foreign.txt").write_text("unexplained edit from another driver\n")
    mixed_head = git(target, "rev-parse", "HEAD")
    before = git(target, "diff", "--", "foreign.txt")
    assert before and "unexplained" in before  # Establish foreign-dirt precondition.
    mixed = actual_call(driver, LIVE, target, ROOT)
    assert "FLOW_LIVE_DRIVER: suspected" in mixed.stdout and "foreign.txt" in mixed.stderr
    assert checkpoints((ROOT / f".claude/commands/{driver}/auto.md").read_text())["mixed-dirt"]
    # STOP before any checkpoint: neither a new commit nor staged foreign bytes.
    assert git(target, "rev-parse", "HEAD") == mixed_head
    assert git(target, "diff", "--cached") == ""
    assert git(target, "diff", "--", "foreign.txt") == before


@requires_git
@pytest.mark.parametrize("driver", DRIVERS)
def test_actual_claim_and_stale_calls_name_the_declared_checkout(project, driver):
    main, target = project
    claim = actual_call(driver, CLAIM, target, ROOT)
    assert any(f"FLOW_CLAIM: {state}" in claim.stdout for state in ("free", "unsupported")), claim.stdout
    git(target, "update-ref", "refs/remotes/origin/main", "HEAD")
    stale = actual_call(driver, STALE, target, main)
    assert f"FLOW_STALE_PATH: {target}" in stale.stdout
    assert "FLOW_STALE_BASE: current" in stale.stdout, stale.stdout + stale.stderr
