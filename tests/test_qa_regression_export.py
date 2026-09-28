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
        (lambda s: s.update(start="https://prod.example.com/shop"), "single '/'"),
        (lambda s: s.update(start="//prod.example.com/shop"), "single '/'"),
        (lambda s: s.update(start="/\\example.org/shop"), "no backslash"),
        (lambda s: s.update(start="/\texample.org"), "no backslash"),
        (lambda s: s.update(start="/shop\n//example.org"), "no backslash"),
        (lambda s: s.update(expect=[]), "at least one product assertion"),
        (lambda s: s.update(schema="cpp.qa-regression/0"), "schema"),
        (lambda s: s["steps"].append({"action": "goto", "path": "https://evil.example"}), "single '/'"),
        (lambda s: s["steps"].append({"action": "goto", "path": "/\\evil.example"}), "no backslash"),
        (lambda s: s["steps"].append({"action": "fill", "target": {"testid": "q"}, "value_env": "QA-X"}), "value_env"),
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
    assert 'await reach(page, "/shop");' in text
    assert 'await page.getByRole("button", { name: "Add to cart" }).click();' in text
    assert 'await expect(page.getByTestId("cart-count")).toHaveText("1");' in text
    assert "waitForTimeout" not in text, "no arbitrary sleeps"


def test_a_multiline_issue_cannot_escape_its_comment():
    """Counter-model finding: a raw newline ended the comment and injected code."""
    text = qa.render_test(_spec(issue='fixture\nthrow new Error("injected");'), "@playwright/test")
    assert not any(line.startswith("throw new Error") for line in text.splitlines())
    assert '// Issue: "fixture\\nthrow new Error(\\"injected\\");"' in text


def test_env_fills_get_unique_safe_identifiers():
    """Counter-model finding: a repeated variable redeclared a const; CLASS became `class`."""
    steps = [
        {"action": "fill", "target": {"label": "Password"}, "value_env": "QA_PASSWORD"},
        {"action": "fill", "target": {"label": "Confirm password"}, "value_env": "QA_PASSWORD"},
        {"action": "fill", "target": {"label": "Class"}, "value_env": "CLASS"},
    ]
    text = qa.render_test(_spec(steps=steps), "@playwright/test")
    declared = re.findall(r"const (\w+) = process\.env", text)
    assert declared == ["fillValue0", "fillValue1", "fillValue2"]
    assert "const class" not in text and "const qa_password" not in text


@pytest.mark.skipif(qa.shutil.which("node") is None, reason="node not on PATH")
def test_rendered_tests_are_syntactically_valid_javascript(tmp_path):
    steps = [
        {"action": "fill", "target": {"label": "Password"}, "value_env": "QA_PASSWORD"},
        {"action": "fill", "target": {"label": "Confirm"}, "value_env": "QA_PASSWORD"},
        {"action": "fill", "target": {"label": "Class"}, "value_env": "CLASS"},
        {"action": "press", "target": {"testid": "q"}, "key": "Enter"},
        {"action": "goto", "path": "/next?x=1#y"},
    ]
    spec = _spec(steps=steps, issue='line one\nthrow new Error("x"); \u2028 end', title="it's `ok` ${x}")
    out = tmp_path / "t.spec.mjs"
    out.write_text(qa.render_test(qa.validate_spec(spec), "@playwright/test"))
    proc = qa.subprocess.run(["node", "--check", str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_every_navigation_checks_reachability():
    """Counter-model finding: a later route answering 503 read as the bug."""
    steps = [{"action": "goto", "path": "/checkout"}, {"action": "click", "target": {"testid": "buy"}}]
    text = qa.render_test(_spec(steps=steps), "@playwright/test")
    assert 'await reach(page, "/shop");' in text
    assert 'await reach(page, "/checkout");' in text
    assert text.count("page.goto(") == 1, "the only raw goto is inside reach()"
    assert "if (!response || !response.ok())" in text


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
    assert (
        "QA_REGRESSION_RUN: npx playwright test "
        "'/tests/e2e/regressions/regression-one-click-on-add-to-cart-adds-exactly-one-item\\.spec\\.mjs$' --trace on"
    ) in out
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

#: The report's rootDir and the file being asked about. Fixture-owned relative
#: values under a fixed fake root, never a real absolute path.
ROOT_DIR = Path("/consumer/tests/e2e")
TARGET = ROOT_DIR / "regressions" / "regression-x.spec.mjs"
NEIGHBOUR = "auth.setup.mjs"


def _spec_entry(file: str, *results) -> dict:
    return {"file": file, "tests": [{"results": list(results)}]}


def _report(*results, errors=None, neighbour=None, file="regressions/regression-x.spec.mjs"):
    specs = [_spec_entry(file, *results)] if results else []
    suites = [{"file": file, "specs": specs, "suites": []}]
    if neighbour is not None:
        suites.insert(0, {"file": NEIGHBOUR, "specs": [_spec_entry(NEIGHBOUR, neighbour)], "suites": []})
    return {"config": {"rootDir": str(ROOT_DIR)}, "errors": errors or [], "suites": suites}


TRACE = {"name": "trace", "path": "test-results/x/trace.zip"}
PASSED = {"status": "passed", "attachments": [TRACE]}
ASSERTION = {"status": "failed", "error": {"message": "Error: expect(locator).toHaveText(expected) failed"}}
SKIPPED = {"status": "skipped"}


def test_a_passing_run_is_passed_and_names_its_trace():
    verdict, _, traces = qa.classify_report(_report(PASSED), TARGET)
    assert verdict == "passed"
    assert traces == ["test-results/x/trace.zip"]


def test_a_failed_product_assertion_is_reproduced():
    assert qa.classify_report(_report(ASSERTION), TARGET)[0] == "reproduced"


def test_an_unreachable_app_is_unavailable_not_reproduced():
    down = {
        "status": "failed",
        "error": {"message": f"Error: {qa.UNAVAILABLE_MARKER}: page.goto: net::ERR_CONNECTION_REFUSED"},
        "errors": [{"message": "expect(x) would be irrelevant here"}],
    }
    assert qa.classify_report(_report(down), TARGET)[0] == "unavailable"


# Verbatim Playwright 1.63 messages, ANSI colour codes included (measured).
ESC = "\x1b"
HEADER = f"Error: {ESC}[2mexpect({ESC}[22m{ESC}[31mlocator{ESC}[39m{ESC}[2m).{ESC}[22mtoHaveText failed\n\n"
STRICT = HEADER + "Locator: getByTestId('c')\nError: strict mode violation: getByTestId('c') resolved to 2 elements"
MISMATCH = HEADER + f'Locator:  getByTestId(\'c\')\nExpected: {ESC}[32m"1"{ESC}[39m\nReceived: {ESC}[31m"2"{ESC}[39m'
NOT_FOUND = HEADER + "Locator: getByTestId('c')\nError: element(s) not found"


@pytest.mark.parametrize(
    "message, verdict",
    [(MISMATCH, "reproduced"), (NOT_FOUND, "reproduced"), (STRICT, "error")],
)
def test_an_ambiguous_locator_is_error_not_reproduced(message, verdict):
    """Counter-model finding: strict mode shares the `expect(...) failed` header."""
    failed = {"status": "failed", "error": {"message": message}}
    assert qa.classify_report(_report(failed), TARGET)[0] == verdict


def test_a_neighbours_failed_assertion_with_the_target_skipped_is_error_not_reproduced():
    """Counter-model finding: a failed setup dependency SKIPS the target."""
    report = _report(SKIPPED, neighbour=ASSERTION)
    assert qa.classify_report(report, TARGET)[0] == "error"


def test_a_neighbours_failure_does_not_decide_a_passing_target():
    report = _report(PASSED, neighbour=ASSERTION)
    assert qa.classify_report(report, TARGET)[0] == "passed"


def test_a_report_that_holds_only_neighbours_is_error():
    report = _report(ASSERTION, file="regressions/regression-other.spec.mjs")
    verdict, reason, _ = qa.classify_report(report, TARGET)
    assert verdict == "error"
    assert "did not execute" in reason


@pytest.mark.parametrize(
    "report, why",
    [
        (None, "no JSON report"),
        ({"config": {"rootDir": str(ROOT_DIR)}, "errors": [], "suites": []}, "did not execute"),
        ({"errors": [{"message": "Error: No tests found."}], "suites": []}, "before the test ran"),
        (
            {"errors": [{"message": "Error: Process from config.webServer was not able to start."}], "suites": []},
            "before the test ran",
        ),
        (_report({"status": "failed", "error": {"message": "TypeError: x is undefined"}}), "TypeError"),
        ({"errors": [], "suites": _report(PASSED)["suites"]}, "names no rootDir"),
    ],
)
def test_anything_else_is_error_never_passed(report, why):
    verdict, reason, _ = qa.classify_report(report, TARGET)
    assert verdict == "error"
    assert why in reason


# ---------------------------------------------------------------------- run


def test_the_printed_run_command_escapes_the_relative_path():
    """Counter-model finding: the printed command used an unescaped regex."""
    printed = qa._file_filter(Path("/tests/e2e[local]/a.spec.mjs"), anchor_start=False)
    assert printed == r"/tests/e2e\[local\]/a\.spec\.mjs$"
    assert re.search(printed, "/abs/project/tests/e2e[local]/a.spec.mjs")
    assert not re.search(printed, "/abs/project/tests/e2e[local]/aXspec.mjs")
    assert not re.search(printed, "/abs/project/tests/e2e[local]/a.spec.mjs.bak")


def test_the_file_filter_is_an_escaped_anchored_regex():
    assert qa._file_filter(Path("/c/tests/e2e[local]/a.spec.mjs")) == r"^/c/tests/e2e\[local\]/a\.spec\.mjs$"


def _runnable(tmp_path: Path) -> tuple[Path, str]:
    root = _consumer(tmp_path)
    test = root / "tests/e2e/regressions/regression-x.spec.mjs"
    test.parent.mkdir(parents=True)
    test.write_text("// placeholder\n")
    return root, test.relative_to(root).as_posix()


def test_a_runner_timeout_is_error_not_reproduced(tmp_path, node_on_path, monkeypatch, capsys):
    root, rel = _runnable(tmp_path)

    def hang(*args, **kwargs):
        raise qa.subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(qa.subprocess, "run", hang)
    assert qa.main(["run", "--root", str(root), "--test", rel, "--timeout", "1"]) == qa.RUN_ERROR
    assert "QA_REGRESSION_RESULT: error - the runner did not finish within 1s" in capsys.readouterr().out


def test_a_crash_inside_run_is_error_never_exit_one(tmp_path, node_on_path, monkeypatch, capsys):
    root, rel = _runnable(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(qa, "classify_report", boom)
    monkeypatch.setattr(qa.subprocess, "run", lambda *a, **k: qa.subprocess.CompletedProcess(a, 1, "", ""))
    rc = qa.main(["run", "--root", str(root), "--test", rel])
    assert rc == qa.RUN_ERROR and rc != qa.RUN_REPRODUCED
    assert "QA_REGRESSION_RESULT: error - the helper crashed: RuntimeError" in capsys.readouterr().out


def test_run_refuses_a_test_outside_the_project(tmp_path, node_on_path, capsys):
    root, _ = _runnable(tmp_path)
    outside = tmp_path / "elsewhere.spec.mjs"
    outside.write_text("// not in the project\n")
    assert qa.main(["run", "--root", str(root), "--test", "../elsewhere.spec.mjs"]) == qa.RUN_ERROR
    assert "is not a file inside" in capsys.readouterr().out


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
