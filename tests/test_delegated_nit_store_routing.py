"""Parent routing instructions and their actual published resolver call (#1811).

Presence/order checks cannot establish live model obedience or GitHub writes.
Executing the real resolver establishes its verdict, with GitHub the stubbed
network boundary. It does not execute the model's subsequent prose decisions.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
DRIVERS = ("codex", "qwen", "gemma")
CALL = "~/.claude/scripts/nit-store-resolve.sh"
CASES = json.loads((ROOT / "controls/delegated-nit-store-routing/cases.json").read_text())
RESOLVER = ROOT / "scripts/nit-store-resolve.sh"
TOOLS = ("bash", "git", "env", "sed", "grep")
requires_tools = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in TOOLS), reason="requires bash, git, env, sed and grep"
)
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")


def document(driver: str) -> str:
    return (ROOT / f".claude/commands/{driver}/auto.md").read_text()


def step_tokens(text: str, number: int):
    tokens = MarkdownIt("commonmark").parse(text)
    starts = [i for i, token in enumerate(tokens[:-1]) if token.type == "heading_open"
              and token.tag == "h3" and token.level == 0
              and tokens[i + 1].content.startswith(f"Step {number}:")]
    if len(starts) != 1:
        return []
    start = starts[0]
    end = next((i for i in range(start + 3, len(tokens)) if tokens[i].type == "heading_open"
                and tokens[i].tag == "h3" and tokens[i].level == 0), len(tokens))
    return tokens[start + 3:end]


def prose(tokens) -> str:
    return " ".join(" ".join(token.content.split()) for token in tokens if token.type == "inline")


def resolver_block(text: str) -> str:
    blocks = [token.content for token in step_tokens(text, 7) if token.type == "fence"
              and token.info == "bash" and CALL in token.content.splitlines()]
    assert len(blocks) == 1, "one active bare parent resolver block required"
    assert blocks[0].strip() == CALL, "publish the bare resolver, without an exit-masking wrapper"
    return blocks[0]


def routing_contract(text: str) -> bool:
    review = prose(step_tokens(text, 5))
    finish = step_tokens(text, 7)
    policy = prose(finish)
    try:
        block = resolver_block(text)
    except AssertionError:
        return False
    required_review = ("parent retains supplemental findings", "deferred review findings",
                       "file:line or command, defect, consequence, and source issue or PR",
                       "child never writes to GitHub")
    required_policy = (
        "Route supplemental findings (parent only)",
        "`ok` means post one finding per comment",
        "gh issue comment <NIT_STORE> --repo <NIT_STORE_REPO>",
        "`none` (exit 1) means file a normal issue instead, with explicit `--repo`",
        "`unknown` (exit 3), or a missing helper: post nowhere",
        "unrouted and carry it verbatim in the closing report",
        "`unknown` is not `none`",
        "file:line or command, defect, why it matters, and source issue or PR",
        "Live correctness, security, or data-loss problems get their own issue",
        "closing report names each finding with its comment/issue link",
        "NIT_STORE_SOURCE=search", "Nothing to store is ordinary",
        "GitHub writes belong to the parent, never the child",
    )
    if not all(part in review for part in required_review):
        return False
    if not all(part in policy for part in required_policy):
        return False
    link = "../flow/auto.md#step-5b-route-supplemental-findings-to-the-nit-store"
    if not any(child.type == "link_open" and child.attrGet("href") == link
               for token in finish for child in token.children or []):
        return False
    calls = [i for i, token in enumerate(finish) if token.type == "fence" and token.content == block]
    prs = [i for i, token in enumerate(finish) if token.type == "fence" and "gh pr create " in token.content]
    closes = [i for i, token in enumerate(finish) if token.type == "fence"
              and "flow-plan-record.py finish " in token.content]
    reports = [i for i, token in enumerate(finish) if token.type == "inline"
               and token.content.startswith("Report: `Step 7/8:")]
    return bool(prs and closes and reports and max(prs) < max(closes) < calls[0] < min(reports))


@pytest.mark.parametrize("driver", DRIVERS)
def test_actual_driver_retains_and_routes_in_parent_before_cleanup(driver):
    assert routing_contract(document(driver)), driver


@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_committed_procedure_controls(driver, case):
    text = document(driver)
    assert routing_contract(text), "control requires the actual sound document"
    if case["mode"] == "identity":
        changed = text
    elif case["mode"] == "child-retention":
        start = text.index("The parent retains supplemental findings")
        end = text.index("\n\nReport: `Step 5/8:", start)
        changed = text[:start] + "```text\n" + text[start:end] + "\n```" + text[end:]
        assert "```text\nThe parent retains" in changed
    elif case["mode"] == "child-routing":
        start = text.index("5. **Route supplemental findings")
        end = text.index("Report: `Step 7/8:", start)
        changed = text[:start] + "````text\n" + text[start:end] + "````\n\n" + text[end:]
        assert "````text\n5. **Route" in changed
    elif case["mode"] == "late-routing":
        start = text.index("5. **Route supplemental findings")
        end = text.index("Report: `Step 7/8:", start)
        report_end = text.index("\n", end)
        changed = text[:start] + text[end:report_end] + "\n\n" + text[start:end] + text[report_end:]
        assert changed.index("Report: `Step 7/8:") < changed.index("5. **Route supplemental findings")
    else:
        assert case["old"] in text, "mutation precondition"
        changed = text.replace(case["old"], case["new"])
        assert case["old"] not in changed, "known-bad input must lose its required instruction"
    assert routing_contract(changed) is case["good"]


GH_STUB = '''import json, os, sys
from pathlib import Path
state = Path(os.environ["NIT_TEST_STATE"])
data = json.loads(state.read_text())
args = sys.argv[1:]
data["calls"].append(args)
state.write_text(json.dumps(data))
assert args[:2] in (["issue", "view"], ["issue", "list"]), args
assert "--repo" in args, args
if data["mode"] == "transport":
    sys.exit(1)
if args[:2] == ["issue", "list"]:
    print({"none": "TOTAL 0", "ambiguous": "TOTAL 2\\n77\\n78"}.get(data["mode"], "TOTAL 1\\n77"))
else:
    print("OPEN\\tNit Store")
'''


@requires_tools
@requires_git
@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("layout", ("main", "linked"))
@pytest.mark.parametrize("restricted", (False, True), ids=("host-path", "no-python-path"))
@pytest.mark.parametrize("mode", ("mapped", "searched", "none", "transport", "ambiguous", "missing"))
def test_actual_published_resolver_verdict(tmp_path, driver, layout, restricted, mode):
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    repo = "cooneycw/kyle" if mode == "mapped" else "fixture/example"
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", f"https://github.com/{repo}.git"],
                   check=True)
    if layout == "linked":
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "fixture"],
                       check=True)
        caller = tmp_path / "renamed-issue-1811"
        subprocess.run(["git", "-C", str(root), "worktree", "add", "--detach", str(caller)],
                       check=True, capture_output=True)
    else:
        caller = root
    home = tmp_path / "home"
    scripts = home / ".claude/scripts"
    scripts.mkdir(parents=True)
    if mode != "missing":
        (scripts / "nit-store-resolve.sh").symlink_to(RESOLVER)
    else:
        assert not (scripts / "nit-store-resolve.sh").exists()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for tool in TOOLS:
        (bindir / tool).symlink_to(shutil.which(tool))
    gh = bindir / "gh"
    gh.write_text(f"#!{sys.executable}\n" + GH_STUB)
    gh.chmod(0o755)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"mode": mode, "calls": []}))
    env = {**os.environ, "HOME": str(home), "NIT_TEST_STATE": str(state)}
    if restricted:
        env["PATH"] = str(bindir)
        assert shutil.which("python3", path=env["PATH"]) is None
        assert shutil.which("python", path=env["PATH"]) is None
        assert all(shutil.which(tool, path=env["PATH"]) for tool in TOOLS)
    else:
        env["PATH"] = str(bindir) + os.pathsep + os.environ["PATH"]
    result = subprocess.run(["bash", "-c", resolver_block(document(driver))], cwd=caller, env=env,
                            capture_output=True, text=True, check=False, timeout=15)
    expected = {"mapped": (0, "ok"), "searched": (0, "ok"), "none": (1, "none"),
                "transport": (3, "unknown"), "ambiguous": (3, "unknown")}
    calls = json.loads(state.read_text())["calls"]
    if mode == "missing":
        assert result.returncode == 127
        assert not calls
    else:
        code, verdict = expected[mode]
        assert result.returncode == code, result.stdout + result.stderr
        assert f"NIT_STORE_STATUS: {verdict}" in result.stdout
        assert calls
        assert all(call[call.index("--repo") + 1] == repo for call in calls)
        if verdict == "ok":
            assert f"NIT_STORE={1004 if mode == 'mapped' else 77}\n" in result.stdout
            assert calls[-1][:2] == ["issue", "view"], "verify the returned store directly"
        else:
            assert "NIT_STORE=" not in result.stdout
