"""Tests for the QA regression-export helper (issue #1291).

These run in `validate`, which has no node and no browsers, so they check what
the export WRITES and how `run` CLASSIFIES a runner report. Whether the written
test actually fails on the bug is not something a Python test here can observe;
that is `scripts/qa-regression-demo.sh`, run by the `qa-regression-demo` CI step
in the pinned Playwright image, with its own negative control. The last group
pins the wiring between those two halves so neither can drift away silently.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "qa-regression-export.py"
FIXTURE = ROOT / "tests" / "fixtures" / "qa_regression" / "consumer"
FIXTURE_SPEC = FIXTURE / "repro" / "cart-double-increment.json"


def _load():
    spec = importlib.util.spec_from_file_location("qa_regression_export", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qa = _load()


def _spec(**overrides):
    base = json.loads(FIXTURE_SPEC.read_text(encoding="utf-8"))
    base.update(overrides)
    return base


def _consumer(tmp_path: Path, *, enabled=True, runner=True, qa_extra: dict | None = None) -> Path:
    """A consumer project: config, optional opt-in, optional installed runner."""
    root = tmp_path / "consumer"
    root.mkdir()
    (root / "playwright.config.mjs").write_text("export default { testDir: './tests/e2e' };\n")
    cfg: dict = {"project": {"url": "http://127.0.0.1:1"}}
    if enabled is not None:
        cfg["regression_export"] = {"enabled": enabled, "test_dir": "tests/e2e/regressions", **(qa_extra or {})}
    (root / ".claude").mkdir()
    (root / ".claude" / "qa.yml").write_text(yaml.safe_dump(cfg))
    if runner:
        pkg = root / "node_modules" / "@playwright" / "test"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text('{"version": "1.63.0"}')
        (root / "node_modules" / ".bin").mkdir(parents=True)
        (root / "node_modules" / ".bin" / "playwright").write_text("#!/bin/sh\n")
    return root


@pytest.fixture
def node_on_path(monkeypatch):
    """`validate` has no node; the export only needs to SEE one to proceed."""
    monkeypatch.setattr(qa.shutil, "which", lambda name: f"/usr/bin/{name}")


def _export(root: Path, spec: dict) -> Path:
    """Write the spec beside (never inside) the consumer; return its path."""
    spec_path = root.parent / "spec.json"
    spec_path.write_text(json.dumps(spec))
    return spec_path


# ------------------------------------------------------------------ spec schema


def test_the_committed_fixture_spec_is_valid():
    qa.validate_spec(json.loads(FIXTURE_SPEC.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "mutate, reason",
    [
        (lambda s: s.update(cookies=[{"name": "sid", "value": "x"}]), "unknown key"),
        (lambda s: s.update(storageState="state.json"), "unknown key"),
        (lambda s: s.update(start="https://prod.example.com/shop"), "relative"),
        (lambda s: s.update(start="//prod.example.com/shop"), "relative"),
        (lambda s: s.update(expect=[]), "at least one product assertion"),
        (lambda s: s.update(schema="cpp.qa-regression/0"), "schema"),
        (lambda s: s["steps"].append({"action": "goto", "path": "https://evil.example"}), "relative"),
        (lambda s: s["steps"].append({"action": "hover", "target": {"testid": "x"}}), "action must be"),
        (lambda s: s["expect"][0].update(toBeVisible=True), "exactly one of"),
        (lambda s: s["expect"][0].update(target={"testid": "a", "text": "b"}), "exactly one of testid"),
    ],
)
def test_the_schema_refuses(mutate, reason):
    spec = _spec()
    mutate(spec)
    with pytest.raises(qa.SpecError, match=reason):
        qa.validate_spec(spec)


def test_a_literal_password_is_refused_and_value_env_is_accepted():
    literal = _spec(steps=[{"action": "fill", "target": {"label": "Password"}, "value": "hunter2"}])
    with pytest.raises(qa.SpecError, match="credential-like"):
        qa.validate_spec(literal)
    from_env = _spec(steps=[{"action": "fill", "target": {"label": "Password"}, "value_env": "QA_PASSWORD"}])
    qa.validate_spec(from_env)
    rendered = qa.render_test(from_env, "@playwright/test")
    assert "hunter2" not in rendered
    assert 'process.env["QA_PASSWORD"]' in rendered


# ----------------------------------------------------------------------- render


def test_the_rendered_test_resets_state_marks_unavailable_and_asserts_the_product():
    text = qa.render_test(_spec(), "@playwright/test")
    assert 'import { test, expect } from "@playwright/test";' in text
    assert "test.use({ storageState: { cookies: [], origins: [] } });" in text
    assert qa.UNAVAILABLE_MARKER in text
    assert 'await page.goto("/shop");' in text
    assert 'await page.getByRole("button", { name: "Add to cart" }).click();' in text
    assert 'await expect(page.getByTestId("cart-count")).toHaveText("1");' in text
    assert "waitForTimeout" not in text, "no arbitrary sleeps"


def test_literals_are_escaped_as_js_strings():
    spec = _spec(title='quote " and backslash \\ and `tick` ${x}')
    text = qa.render_test(spec, "@playwright/test")
    assert 'test("quote \\" and backslash \\\\ and `tick` ${x}"' in text


# ----------------------------------------------------------------------- export


def test_export_writes_into_the_configured_dir_and_prints_the_handoff(tmp_path, node_on_path, capsys):
    root = _consumer(tmp_path)
    spec_path = _export(root, _spec())
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == 0
    out = capsys.readouterr().out
    written = root / "tests/e2e/regressions/regression-one-click-on-add-to-cart-adds-exactly-one-item.spec.mjs"
    assert written.is_file()
    assert f"QA_REGRESSION_TEST: {written.relative_to(root).as_posix()}" in out
    assert "QA_REGRESSION_RUN: npx playwright test tests/e2e/regressions/" in out
    assert "QA_REGRESSION_TRACE:" in out
    assert out.rstrip().endswith("QA_REGRESSION_EXPORT: ok")


def test_export_is_opt_in(tmp_path, node_on_path, capsys):
    root = _consumer(tmp_path, enabled=None)
    assert "regression_export" not in yaml.safe_load((root / ".claude/qa.yml").read_text())
    spec_path = _export(root, _spec())
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == qa.EXIT_NOT_ENABLED
    assert "not-enabled" in capsys.readouterr().out
    assert not (root / "tests").exists()


def test_a_missing_runner_is_named_and_nothing_is_written_or_installed(tmp_path, node_on_path, capsys):
    root = _consumer(tmp_path, runner=False)
    assert not (root / "node_modules").exists()
    spec_path = _export(root, _spec())
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == qa.EXIT_PREREQ
    out = capsys.readouterr().out
    assert "QA_REGRESSION_MISSING: @playwright/test installed" in out
    assert "no executable handoff" in out
    assert not (root / "tests").exists()
    assert not (root / "node_modules").exists(), "the export must never install a runner"


def test_a_missing_node_is_named(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(qa.shutil, "which", lambda name: None)
    root = _consumer(tmp_path)
    spec_path = _export(root, _spec())
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == qa.EXIT_PREREQ
    assert "QA_REGRESSION_MISSING: node on PATH" in capsys.readouterr().out


def test_the_test_dir_defaults_to_the_config_testdir(tmp_path, node_on_path):
    root = _consumer(tmp_path, qa_extra={})
    cfg = yaml.safe_load((root / ".claude/qa.yml").read_text())
    del cfg["regression_export"]["test_dir"]
    (root / ".claude/qa.yml").write_text(yaml.safe_dump(cfg))
    spec_path = _export(root, _spec())
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == 0
    assert list((root / "tests" / "e2e").glob("regression-*.spec.mjs"))


def test_a_test_dir_outside_the_project_is_refused(tmp_path, node_on_path, capsys):
    root = _consumer(tmp_path, qa_extra={"test_dir": "../elsewhere"})
    spec_path = _export(root, _spec())
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == qa.EXIT_SPEC
    assert "outside the project" in capsys.readouterr().out
    assert not (tmp_path / "elsewhere").exists()


def test_an_existing_test_is_not_overwritten_without_force(tmp_path, node_on_path):
    root = _consumer(tmp_path)
    spec_path = _export(root, _spec())
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == 0
    written = next((root / "tests/e2e/regressions").glob("*.spec.mjs"))
    written.write_text("// hand-edited\n")
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == qa.EXIT_EXISTS
    assert written.read_text() == "// hand-edited\n"
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path), "--force"]) == 0
    assert written.read_text() != "// hand-edited\n"


def test_a_typescript_config_gets_a_typescript_test(tmp_path, node_on_path):
    root = _consumer(tmp_path)
    (root / "playwright.config.mjs").rename(root / "playwright.config.ts")
    spec_path = _export(root, _spec())
    assert qa.main(["export", "--root", str(root), "--spec", str(spec_path)]) == 0
    assert list((root / "tests/e2e/regressions").glob("*.spec.ts"))


# --------------------------------------------------------------- classification


def _report(*results, errors=None):
    return {
        "errors": errors or [],
        "suites": [{"specs": [{"tests": [{"results": list(results)}]}], "suites": []}],
    }


TRACE = {"name": "trace", "path": "test-results/x/trace.zip"}


def test_a_passing_run_is_passed_and_names_its_trace():
    verdict, _, traces = qa.classify_report(_report({"status": "passed", "attachments": [TRACE]}))
    assert verdict == "passed"
    assert traces == ["test-results/x/trace.zip"]


def test_a_failed_product_assertion_is_reproduced():
    failed = {"status": "failed", "error": {"message": "Error: expect(locator).toHaveText(expected) failed"}}
    assert qa.classify_report(_report(failed))[0] == "reproduced"


def test_an_unreachable_app_is_unavailable_not_reproduced():
    down = {
        "status": "failed",
        "error": {"message": f"Error: {qa.UNAVAILABLE_MARKER}: page.goto: net::ERR_CONNECTION_REFUSED"},
        "errors": [{"message": "expect(x) would be irrelevant here"}],
    }
    assert qa.classify_report(_report(down))[0] == "unavailable"


@pytest.mark.parametrize(
    "report, why",
    [
        (None, "no JSON report"),
        ({"errors": [], "suites": []}, "zero tests executed"),
        ({"errors": [{"message": "Error: No tests found."}], "suites": []}, "before any test ran"),
        (
            {"errors": [{"message": "Error: Process from config.webServer was not able to start."}], "suites": []},
            "before any test ran",
        ),
        (_report({"status": "failed", "error": {"message": "TypeError: x is undefined"}}), "TypeError"),
    ],
)
def test_anything_else_is_error_never_passed(report, why):
    verdict, reason, _ = qa.classify_report(report)
    assert verdict == "error"
    assert why in reason


# ----------------------------------------------------------------------- wiring


def _lock_version() -> str:
    lock = json.loads((FIXTURE / "package-lock.json").read_text(encoding="utf-8"))
    return lock["packages"]["node_modules/@playwright/test"]["version"]


def test_the_ci_image_matches_the_fixture_runner_version():
    """A version skew makes every arm fail for an environmental reason."""
    pipeline = yaml.safe_load((ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))
    step = pipeline["steps"]["qa-regression-demo"]
    m = re.match(r"mcr\.microsoft\.com/playwright:v([0-9.]+)-noble@sha256:[0-9a-f]{64}$", step["image"])
    assert m, f"image must be Playwright's, pinned by digest: {step['image']}"
    assert m.group(1) == _lock_version()
    commands = "\n".join(step["commands"])
    assert "bash scripts/qa-regression-demo.sh\n" in commands + "\n"
    assert "bash scripts/qa-regression-demo.sh --negative-control" in commands


def test_the_demo_target_runs_both_arms_and_stays_out_of_verify():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    body = re.search(r"^qa-regression-demo:\n((?:\t.*\n)+)", makefile, re.M)
    assert body, "make qa-regression-demo is missing"
    assert "qa-regression-demo.sh --negative-control" in body.group(1)
    verify = re.search(r"^verify:(.*?)\n\t", makefile, re.M | re.S)
    assert verify and "qa-regression-demo" not in verify.group(1)


def test_the_fixture_has_a_real_bug_and_a_real_fix():
    buggy = (FIXTURE / "public" / "buggy.html").read_text(encoding="utf-8")
    fixed = (FIXTURE / "public" / "fixed.html").read_text(encoding="utf-8")
    # The listener is registered twice with DISTINCT functions: the DOM drops a
    # duplicate registration of the same reference, which made an earlier draft
    # of this fixture a bug that never happened.
    assert buggy.count("addEventListener('click'") == 2
    assert "() => add()" in buggy
    assert fixed.count("addEventListener('click'") == 1
