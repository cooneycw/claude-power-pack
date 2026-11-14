"""Source-bound delegated approval in a linked worktree; no live model claim."""
import ast
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "controls/delegated-plan-lanes/run-case.py"
pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None
                                or shutil.which(sys.executable) is None, reason="requires git, bash and Python")


@pytest.mark.parametrize("driver", ["codex", "qwen", "gemma"])
@pytest.mark.parametrize("case,code", [("bad-omitted-lane", 1), ("good-every-lane", 0), ("good-no-lane-file", 0)])
def test_driver_approval_uses_existing_lane_refusal(driver, case, code):
    control = ROOT / f"controls/delegated-{driver}-plan-lanes"
    done = subprocess.run([sys.executable, str(RUNNER), driver, str(control / "cases" / case),
                           str(ROOT / "scripts/flow-plan-record.py")], capture_output=True, text=True, timeout=45)
    assert done.returncode == code, done.stdout + done.stderr
    if code:
        assert "unanswered: Harness" in done.stdout
    else:
        assert "FLOW_PLAN_RECORD: baseline stamped" in done.stdout


@pytest.mark.parametrize("driver", ["codex", "qwen", "gemma"])
def test_historical_step3_misses_omitted_lane(driver):
    control = ROOT / f"controls/delegated-{driver}-plan-lanes"
    anchor = next((control / "anchors").glob("*.md"))
    for case in ["bad-omitted-lane", "good-every-lane"]:
        done = subprocess.run([sys.executable, str(RUNNER), driver, str(control / "cases" / case), str(anchor)],
                              capture_output=True, text=True, timeout=45)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "legacy continuation" in done.stdout


@pytest.mark.parametrize("driver", ["codex", "qwen", "gemma"])
@pytest.mark.parametrize("complete", [False, True])
def test_driver_close_reports_lanes_without_changing_advisory_exit(driver, complete):
    control = ROOT / f"controls/delegated-{driver}-plan-lanes"
    case = "close-every-lane-demonstrated" if complete else "close-missing-evidence"
    done = subprocess.run([sys.executable, str(RUNNER), driver, str(control / "cases" / case),
                           str(ROOT / "scripts/flow-plan-record.py"), "compliance"],
                          capture_output=True, text=True, timeout=45)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PLAN_COMPLIANCE: agreement" in done.stdout
    if complete:
        assert "LANES NOT" not in done.stdout
    else:
        assert "LANES NOT DEMONSTRATED (2)" in done.stdout
        assert "Checkout" in done.stderr and "Harness" in done.stderr


@pytest.mark.parametrize("driver", ["codex", "qwen", "gemma"])
def test_rendered_driver_orders_approval_and_preserves_review_direction(driver):
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    step3 = text.split("### Step 3:", 1)[1].split("### Step 4:", 1)[0]
    assert step3.index("Only after the real approval") < step3.index("flow-plan-record.py begin-run 42")
    assert step3.index("flow-plan-record.py begin-run 42") < step3.index("flow-plan-record.py approve 42")
    assert "Exit 1 is STOP: do not invoke" in step3
    assert "Other errors are STOP too" in step3
    step5 = text.split("### Step 5:", 1)[1].split("### Step 6:", 1)[0]
    assert "each listed lane" in step5 and "no test in the diff" in step5
    assert "With no LANE LIST, skip both questions" in step5
    assert "THIS Claude reviewer" in step5
    step7 = text.split("### Step 7:", 1)[1].split("### Step 8:", 1)[0]
    assert step7.index("compliance 42") < step7.index('ACCEPTANCE_COMPLETE=""')
    assert "not a new blocking quality gate" in step7


@pytest.mark.parametrize("driver", ["codex", "qwen", "gemma"])
def test_removing_both_approval_calls_loses_bad_case_discrimination(tmp_path, driver):
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    mutated = text.replace("~/.claude/scripts/flow-plan-record.py begin-run 42\n", "")
    mutated = mutated.replace("~/.claude/scripts/flow-plan-record.py approve 42\n", "")
    assert mutated != text and "~/.claude/scripts/flow-plan-record.py approve 42\n" not in mutated
    candidate = tmp_path / "auto.md"
    candidate.write_text(mutated)
    case = ROOT / f"controls/delegated-{driver}-plan-lanes/cases/bad-omitted-lane"
    done = subprocess.run([sys.executable, str(RUNNER), driver, str(case), str(candidate)],
                          capture_output=True, text=True, timeout=45)
    assert done.returncode == 0 and "legacy continuation" in done.stdout, done.stdout + done.stderr


@pytest.mark.parametrize("driver", ["codex", "qwen", "gemma"])
@pytest.mark.parametrize("install", ["claude", "codex"])
@pytest.mark.parametrize("case,code", [("bad-omitted-lane", 1), ("good-every-lane", 0)])
def test_installed_standalone_helper_on_each_driver(tmp_path, driver, install, case, code):
    source = (ROOT / "scripts/flow-plan-record.py" if install == "claude"
              else ROOT / "codex/skills/flow-auto/scripts/flow-plan-record.py")
    assert source.read_bytes() == (ROOT / "scripts/flow-plan-record.py").read_bytes()
    target = tmp_path / install / "scripts/flow-plan-record.py"
    target.parent.mkdir(parents=True)
    shutil.copy2(source, target)
    control = ROOT / f"controls/delegated-{driver}-plan-lanes"
    done = subprocess.run([sys.executable, str(RUNNER), driver, str(control / "cases" / case), str(target)],
                          capture_output=True, text=True, timeout=45)
    assert done.returncode == code, done.stdout + done.stderr
    assert ("unanswered: Harness" if code else "baseline stamped") in done.stdout


def test_delegated_families_remain_explicitly_unbundled():
    tree = ast.parse((ROOT / "scripts/codex-skill-sync.py").read_text())
    assignment = next(node for node in tree.body if isinstance(node, ast.AnnAssign)
                      and isinstance(node.target, ast.Name) and node.target.id == "UNPACKAGED_FAMILIES")
    excluded = ast.literal_eval(assignment.value)
    assert {"codex", "qwen", "gemma"} <= excluded
    for driver in ["codex", "qwen", "gemma"]:
        assert not (ROOT / f"codex/skills/{driver}-auto").exists()


@pytest.mark.parametrize("driver", ["codex", "qwen", "gemma"])
@pytest.mark.parametrize("product", [False, True])
def test_plan_evidence_is_not_delegated_implementation(driver, product):
    case = "good-product-change" if product else "bad-metadata-only"
    control = ROOT / f"controls/delegated-{driver}-plan-lanes"
    done = subprocess.run([sys.executable, str(RUNNER), driver, str(control / "cases" / case),
                           str(ROOT / "scripts/flow-plan-record.py")], capture_output=True, text=True, timeout=45)
    assert done.returncode == (0 if product else 1), done.stdout + done.stderr
    if not product:
        assert "DELEGATED_PRODUCT_CHANGE: fail" in done.stdout


@pytest.mark.parametrize("driver", ["codex", "qwen", "gemma"])
def test_compliance_resolves_base_in_its_own_fresh_shell(driver):
    case = ROOT / f"controls/delegated-{driver}-plan-lanes/cases/close-every-lane-demonstrated"
    done = subprocess.run([sys.executable, str(RUNNER), driver, str(case),
                           str(ROOT / "scripts/flow-plan-record.py"), "compliance-shell"],
                          capture_output=True, text=True, timeout=45)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PLAN_COMPLIANCE: agreement" in done.stdout
