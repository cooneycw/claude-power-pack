"""Rendered finish procedure and its real wrapper boundary (#1811).

The shell tests execute the generated bare invocation. Policy assertions check
the instructions a parent reads; they do not simulate or prove model obedience.
The faulty no-verdict executable deliberately models a missing/broken install.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import test_counter_model_adapters as adapters
from tests.test_counter_model_adapters import git, runtime, write

receipt_evidence = adapters.evidence

ROOT = Path(__file__).resolve().parents[1]
CALL = "~/.claude/scripts/flow-finish-gate.sh"
DRIVERS = ("codex", "qwen", "gemma")
requires_tools = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None or shutil.which("make") is None,
    reason="the rendered invocation runs bash, git and Makefile gates",
)


def step6(driver: str) -> str:
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    return text.split("### Step 6:", 1)[1].split("### Step 7:", 1)[0]


def invocation(step: str) -> str:
    marker = "Run quality gates:"
    reader = "Read the actual `FLOW_FINISH_GATE:` verdict AND exit status"
    assert step.count(marker) == 1, "one operative quality-gate instruction required"
    after = step.split(marker, 1)[1]
    assert reader in after, "operative invocation must precede verdict admission"
    operative = after.split(reader, 1)[0]
    blocks = re.findall(r"```bash\n(.*?)\n```", operative, re.S)
    assert len(blocks) == 1 and blocks[0].strip() == CALL, "operative gate must be the bare audited wrapper"
    assert not any(old in operative for old in ("-m lib.cicd", "make lint", "make test")), "legacy operative route"
    return blocks[0].strip()


def assert_verdict(output: str, verdict: str, code: int) -> None:
    records = re.findall(r"^FLOW_FINISH_GATE:.*$", output, re.M)
    assert len(records) == 1, f"expected one verdict record: {records}"
    record = re.fullmatch(r"FLOW_FINISH_GATE: (ok|warn|fail|skipped)(?: \([^\n]*\))?", records[0])
    assert record is not None, records[0]
    assert record[1] == verdict
    assert code == {"ok": 0, "warn": 3, "fail": 1, "skipped": 4}[record[1]]


@pytest.mark.parametrize("case", json.loads(
    (ROOT / "tests/fixtures/delegated-finish-gate/output-cases.json").read_text()
), ids=lambda case: case["name"])
def test_committed_verdict_records(case: dict) -> None:
    if case["valid"]:
        assert_verdict(case["output"], case["verdict"], case["exit"])
    else:
        with pytest.raises(AssertionError):
            assert_verdict(case["output"], case["verdict"], case["exit"])


@pytest.mark.parametrize("driver", DRIVERS)
def test_missing_verdict_never_retries_an_invoked_wrapper(driver: str) -> None:
    step = " ".join(step6(driver).split())
    assert "An invoked wrapper without a verdict is indeterminate: STOP" in step
    assert "Try another copy only when the executable could not launch" in step


@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("verdict,code", [("ok", 0), ("warn", 3), ("fail", 1), ("skipped", 4)])
def test_rendered_reader_preserves_each_verdict(driver: str, verdict: str, code: int) -> None:
    step = step6(driver)
    invocation(step)
    assert f"`{verdict}` / {code}:" in step
    assert "Read the actual `FLOW_FINISH_GATE:` verdict AND exit status" in step
    assert 'Report: `Step 6/8: FLOW_FINISH_GATE: {ok|warn|skipped}' in step
    assert "Report: `Step 6/8: Quality gates passed" not in step
    if verdict == "warn":
        assert "Repeat warning lines and counts" in step
        assert "never call a rerun a clean pass" in step
    if verdict == "skipped":
        assert "no runnable gates, no evidence; never pass" in step
    if verdict == "fail":
        assert "`fail` / 1: STOP" in step
        assert "Non-zero alone never authorizes retry" in step


@requires_tools
@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("layout", ("main", "linked"))
@pytest.mark.parametrize("scenario,code", [
    ("fail", 1), ("warn", 3), ("skipped", 4), ("ok", 0), ("no-verdict", 0), ("interrupted", 143),
])
def test_execute_actual_rendered_invocation(
    tmp_path: Path, driver: str, layout: str, scenario: str, code: int,
) -> None:
    step = step6(driver)
    command = invocation(step)
    home = tmp_path / "home"
    installed = home / ".claude/scripts/flow-finish-gate.sh"
    installed.parent.mkdir(parents=True)
    if scenario in ("no-verdict", "interrupted"):
        installed.write_text(f"#!/bin/bash\necho FLOW_FINISH_GATE_EXIT={code}\nexit {code}\n")
        installed.chmod(0o755)
    else:
        installed.parent.rmdir()
        installed.parent.symlink_to(ROOT / "scripts", target_is_directory=True)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    git(consumer, "init", "-q")
    if layout == "linked":
        git(consumer, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "--allow-empty", "-qm", "base")
        linked = tmp_path / "consumer-linked"
        git(consumer, "worktree", "add", "-qb", "fixture-linked", str(linked))
        consumer = linked
        assert (consumer / ".git").is_file(), "precondition: linked worktree layout"
    if scenario not in ("skipped", "no-verdict", "interrupted"):
        targets = ["lint", "test", "typecheck"] + (["verify"] if scenario != "warn" else [])
        (consumer / "Makefile").write_text("".join(
            f"{target}:\n\t{'false' if scenario == 'fail' else 'true'}\n" for target in targets
        ))
    env = {
        "HOME": str(home), "PATH": os.environ["PATH"], "FLOW_GATE_CPP_DIR": "",
        "FLOW_GATE_RERUN": "0", "CPP_COORDINATION_ADMISSION_FILE": str(tmp_path / "absent-admission"),
    }
    result = subprocess.run(["bash", "-c", command], cwd=consumer, env=env,
                            capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode == code, output
    if scenario in ("no-verdict", "interrupted"):
        assert f"FLOW_FINISH_GATE_EXIT={code}" in output
        assert not re.search(r"^FLOW_FINISH_GATE:", output, re.M), "precondition: no gate verdict"
        assert "Missing verdict, even exit 0" in step
        assert "No verdict from any copy: report unavailable; never ship" in step
    else:
        assert_verdict(output, scenario, result.returncode)
        if scenario == "warn":
            assert "skipped gates: verify" in output
        if scenario in ("warn", "skipped"):
            assert "FLOW_FINISH_GATE: ok" not in output


@pytest.mark.parametrize("driver", DRIVERS)
def test_fix_returns_to_review_before_regating(driver: str) -> None:
    step = " ".join(step6(driver).split())
    assert "Step 5 must finish first" in step
    assert "Missing or refused receipt: STOP" in step
    assert "Invalidate the prior receipt after any implementation fix" in step
    assert "Do not re-gate yet: return to Step 5" in step
    assert "derive and commit a fresh receipt" in step
    assert "**Fix Loop (max 2 retries):**" in step
    assert "At most two implementation fix attempts" in step
    assert 'git push -u origin "$BRANCH"' in step
    assert "resume" in step and "admission" in step


@requires_tools
@pytest.mark.parametrize("driver", DRIVERS)
def test_old_review_cannot_mint_receipt_after_fix(receipt_evidence: dict, driver: str) -> None:
    """Real writer rejects stale review bytes, then accepts a fresh review.

    Runtime logs are fixture-owned; receipt identity/artifact derivation is real.
    This proves receipt binding, not that a live parent follows the procedure.
    """
    evidence = receipt_evidence
    assert "Invalidate the prior receipt" in step6(driver)
    args = runtime(evidence, "implementer", "codex", "model-a")
    args += runtime(evidence, "reviewer", "claude", "model-b", patch=evidence["patch"])
    before = write(evidence, *args)
    assert before.returncode == 0, before.stderr
    repo = evidence["repo"]
    (repo / "file").write_text("fixed after review\n")
    git(repo, "commit", "-qam", "implementation fix")
    fresh = subprocess.check_output(["git", "diff", "origin/main...HEAD"], cwd=repo).decode()
    assert fresh != evidence["patch"], "precondition: fix changes reviewed artifact"
    stale = write(evidence, *args)
    assert stale.returncode != 0
    assert "captured reviewer patch differs" in stale.stderr
    refreshed = runtime(evidence, "implementer", "codex", "model-a")
    refreshed += runtime(evidence, "reviewer", "claude", "model-b", patch=fresh)
    after = write(evidence, *refreshed)
    assert after.returncode == 0, after.stderr


def reader_contract(step: str) -> None:
    """Narrow policy pin, not a general parser or proof of live execution."""
    invocation(step)
    flat = " ".join(step.split())
    for clause in (
        "Missing verdict, even exit 0", "`fail` / 1: STOP",
        "no runnable gates, no evidence; never pass", "never call a rerun a clean pass",
        "Invalidate the prior receipt", "derive and commit a fresh receipt",
        "require one unambiguous verdict record, never prefixed lookalikes or conflicting lines.",
        "Unknown verdict, mismatched exit, interruption or admission refusal: STOP;",
        "Non-zero alone never authorizes retry.",
    ):
        assert clause in flat, f"missing policy: {clause}"


@pytest.mark.parametrize("driver", DRIVERS)
def test_actual_reader_contract(driver: str) -> None:
    reader_contract(step6(driver))


@pytest.mark.parametrize("name", ("good", "missing-verdict", "stale-receipt"))
def test_committed_reader_controls(name: str) -> None:
    text = (ROOT / f"tests/fixtures/delegated-finish-gate/{name}.md").read_text()
    if name == "good":
        reader_contract(text)
    else:
        absent = "Missing verdict, even exit 0" if name == "missing-verdict" else "Invalidate the prior receipt"
        assert absent not in text, "precondition: bad fixture omits its stopping policy"
        with pytest.raises(AssertionError, match="missing policy"):
            reader_contract(text)


@pytest.mark.parametrize("name", ("accepts-conflicting-status", "mixed-route"))
def test_rendered_route_and_rejection_controls(name: str) -> None:
    text = (ROOT / f"tests/fixtures/delegated-finish-gate/{name}.md").read_text()
    if name == "accepts-conflicting-status":
        for verdict, code in (("ok", 0), ("warn", 3), ("fail", 1), ("skipped", 4)):
            assert f"`{verdict}` / {code}:" in text, "precondition: all valid verdict labels retained"
        assert "Conflicting records or mismatched exit: proceed" in text
        with pytest.raises(AssertionError, match="missing policy"):
            reader_contract(text)
    else:
        assert CALL in text and "-m lib.cicd run --plan finish" in text, "precondition: both routes retained"
        assert text.index("-m lib.cicd") < text.index(CALL), "precondition: active runner before dormant wrapper"
        with pytest.raises(AssertionError, match="operative"):
            invocation(text)
