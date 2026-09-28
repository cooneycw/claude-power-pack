#!/usr/bin/env python3
"""Turn a confirmed web-QA bug into a replayable Playwright test (issue #1291).

`/qa:test` explores a site through the Playwright MCP server and files what it
finds as prose. Nothing it leaves behind can be re-run without an agent reading
the prose again. This helper is the handoff: a confirmed bug's reproduction,
written as a small JSON spec, becomes a test file in the CONSUMER's own
Playwright setup, runnable with the consumer's own runner.

Two subcommands:

  export  spec -> test file. Opt-in (`regression_export.enabled: true` in the
          consumer's `.claude/qa.yml`), honours its configured test directory,
          and refuses rather than improvises when the consumer has no Playwright
          runner - it NAMES the missing prerequisite and installs nothing.
  run     executes one exported test with the consumer's runner and classifies
          the outcome. It exists because the runner's own verdict has only two
          colours, and the handoff needs four:

            passed       every test passed                       exit 0
            reproduced   an assertion failed - the bug is there  exit 1
            unavailable  the app could not be reached            exit 4
            error        anything else: no tests ran, the runner
                         or webServer failed, an unexpected throw exit 5

WHY `unavailable` IS NOT `reproduced`. An app that is down makes a test fail,
and a failing regression test reads as "the bug is back". The generated test
therefore loads its start page inside a step that re-throws any failure with a
fixed marker, and `run` classifies on that marker. A reader of the bare runner
output sees the same marker, so the distinction survives without this helper.

WHY ZERO TESTS IS `error`, NOT `passed`. A runner that collected nothing exits
green; that green is about nothing (ADR 0008), so it is never read as a pass.

THE SPEC CANNOT CARRY SESSION STATE, BY CONSTRUCTION. Its schema is a closed
allowlist - unknown keys are refused - with no field for cookies, storage state
or headers, and every generated test resets `storageState` to empty, so it runs
in a fresh context even when the consumer's config sets a logged-in state for
its other tests. Navigation is RELATIVE only: the base URL comes from the
consumer's config, so an exported test cannot be aimed at a production host by
the spec. A literal value typed into a password/secret/token field is refused;
use `value_env` to read it from the environment at run time instead.

Exit codes for `export`: 0 written, 2 bad spec or usage, 3 missing prerequisite,
5 export not enabled, 6 target exists (pass --force to replace).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "cpp.qa-regression/1"

#: The marker the generated test throws when the start page cannot be loaded,
#: and the one `run` classifies on. Changing it here without regenerating the
#: consumer's tests makes every unreachable app read as `error`, not `reproduced`
#: - the safe direction - but it should not change.
UNAVAILABLE_MARKER = "QA-REGRESSION EXECUTION UNAVAILABLE"

CONFIG_NAMES = (
    "playwright.config.ts",
    "playwright.config.mts",
    "playwright.config.cts",
    "playwright.config.js",
    "playwright.config.mjs",
    "playwright.config.cjs",
)

SPEC_KEYS = {"schema", "title", "issue", "start", "steps", "expect"}
STEP_KEYS = {"action", "target", "value", "value_env", "path", "key"}
EXPECT_KEYS = {"target", "toHaveText", "toContainText", "toBeVisible", "toBeHidden"}
TARGET_KEYS = {"testid", "role", "name", "label", "text"}
ACTIONS = {"goto", "click", "fill", "press", "check"}
ASSERTIONS = ("toHaveText", "toContainText", "toBeVisible", "toBeHidden")

#: A field whose name says it holds a credential. Deliberately broad: a false
#: refusal costs one `value_env`; a false acceptance commits a secret.
SECRET_FIELD = re.compile(r"pass(word|code|phrase)?|secret|token|api[ _-]?key|otp|pin\b", re.I)

EXIT_OK, EXIT_SPEC, EXIT_PREREQ, EXIT_NOT_ENABLED, EXIT_EXISTS = 0, 2, 3, 5, 6
RUN_PASSED, RUN_REPRODUCED, RUN_UNAVAILABLE, RUN_ERROR = 0, 1, 4, 5


class SpecError(ValueError):
    """The repro spec is not one this helper will turn into a test."""


# --------------------------------------------------------------------------- spec


def _check_keys(obj: Any, allowed: set[str], where: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise SpecError(f"{where}: expected an object")
    unknown = sorted(set(obj) - allowed)
    if unknown:
        raise SpecError(f"{where}: unknown key(s) {', '.join(unknown)} - the schema is closed")
    return obj


#: A path on the configured origin: RFC 3986 path/query/fragment characters
#: only. A backslash is excluded because the WHATWG URL parser treats it as a
#: slash, so `/\\example.org/x` resolves to ANOTHER HOST (counter-model review);
#: whitespace and control characters are excluded because the parser strips some
#: of them before resolving, which can turn a harmless-looking path into `//host`.
RELATIVE_PATH = re.compile(r"/(?![/\\])[A-Za-z0-9._~!$&'()*+,;=:@%/?#-]*")


def _relative_path(value: Any, where: str) -> str:
    if not isinstance(value, str) or not RELATIVE_PATH.fullmatch(value):
        raise SpecError(
            f"{where}: must be a path on the configured base URL - starting with a single '/', "
            "with no backslash, whitespace or control character"
        )
    return value


def _target(obj: Any, where: str) -> dict[str, str]:
    t = _check_keys(obj, TARGET_KEYS, where)
    if not all(isinstance(v, str) and v for v in t.values()):
        raise SpecError(f"{where}: every locator field must be a non-empty string")
    kinds = [k for k in ("testid", "role", "label", "text") if k in t]
    if len(kinds) != 1:
        raise SpecError(f"{where}: exactly one of testid/role/label/text is required")
    if "name" in t and kinds[0] != "role":
        raise SpecError(f"{where}: 'name' qualifies a 'role' locator only")
    return t


def validate_spec(spec: Any) -> dict[str, Any]:
    """Return the spec if it is exportable, else raise SpecError naming why."""
    spec = _check_keys(spec, SPEC_KEYS, "spec")
    if spec.get("schema") != SCHEMA:
        raise SpecError(f"spec: schema must be {SCHEMA!r}")
    if not isinstance(spec.get("title"), str) or not spec["title"].strip():
        raise SpecError("spec: 'title' is required")
    if "issue" in spec and not isinstance(spec["issue"], str):
        raise SpecError("spec: 'issue' must be a string reference")
    _relative_path(spec.get("start"), "spec.start")

    steps = spec.get("steps", [])
    if not isinstance(steps, list):
        raise SpecError("spec.steps: expected a list")
    for i, step in enumerate(steps):
        where = f"spec.steps[{i}]"
        _check_keys(step, STEP_KEYS, where)
        action = step.get("action")
        if action not in ACTIONS:
            raise SpecError(f"{where}: action must be one of {', '.join(sorted(ACTIONS))}")
        if action == "goto":
            _relative_path(step.get("path"), f"{where}.path")
            continue
        target = _target(step.get("target"), f"{where}.target")
        if action == "fill":
            has_value, has_env = "value" in step, "value_env" in step
            if has_value == has_env:
                raise SpecError(f"{where}: fill needs exactly one of value/value_env")
            if has_value:
                if not isinstance(step["value"], str):
                    raise SpecError(f"{where}.value: must be a string")
                label = " ".join(target.values())
                if SECRET_FIELD.search(label):
                    raise SpecError(
                        f"{where}: refusing a literal value for credential-like field {label!r}; "
                        "use value_env so the value is read at run time and never committed"
                    )
            elif not re.fullmatch(r"[A-Z_][A-Z0-9_]*", str(step["value_env"])):
                raise SpecError(f"{where}.value_env: must be an environment variable name")
        if action == "press" and not isinstance(step.get("key"), str):
            raise SpecError(f"{where}: press needs a 'key'")

    expects = spec.get("expect")
    if not isinstance(expects, list) or not expects:
        raise SpecError("spec.expect: at least one product assertion is required - a test with none cannot fail")
    for i, exp in enumerate(expects):
        where = f"spec.expect[{i}]"
        _check_keys(exp, EXPECT_KEYS, where)
        _target(exp.get("target"), f"{where}.target")
        present = [a for a in ASSERTIONS if a in exp]
        if len(present) != 1:
            raise SpecError(f"{where}: exactly one of {', '.join(ASSERTIONS)} is required")
        kind = present[0]
        if kind in ("toHaveText", "toContainText") and not isinstance(exp[kind], str):
            raise SpecError(f"{where}.{kind}: must be a string")
        if kind in ("toBeVisible", "toBeHidden") and exp[kind] is not True:
            raise SpecError(f"{where}.{kind}: must be true")
    return spec


# ----------------------------------------------------------------------- consumer


def load_qa_config(root: Path) -> dict[str, Any]:
    path = root / ".claude" / "qa.yml"
    if not path.is_file():
        return {}
    import yaml  # pyyaml is a declared runtime dependency (pyproject.toml)

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def find_playwright_config(root: Path) -> Path | None:
    for name in CONFIG_NAMES:
        if (root / name).is_file():
            return root / name
    return None


def runner_prerequisites(root: Path) -> tuple[list[str], str | None]:
    """Return (missing prerequisites, test-runner import module)."""
    missing: list[str] = []
    if shutil.which("node") is None:
        missing.append("node on PATH")
    if find_playwright_config(root) is None:
        missing.append(f"a Playwright config (playwright.config.{{ts,js,mjs,cjs,mts,cts}}) in {root}")
    module = None
    for candidate in ("@playwright/test", "playwright"):
        if (root / "node_modules" / candidate / "package.json").is_file():
            module = candidate if candidate == "@playwright/test" else "playwright/test"
            break
    if module is None:
        missing.append("@playwright/test installed in the project's node_modules (run the project's own install)")
    if not (root / "node_modules" / ".bin" / "playwright").exists():
        if module is not None:
            missing.append("node_modules/.bin/playwright (the runner's CLI)")
    return missing, module


def resolve_test_dir(root: Path, qa: dict[str, Any], config: Path | None) -> Path:
    export_cfg = qa.get("regression_export") or {}
    rel = export_cfg.get("test_dir")
    if not rel and config is not None:
        m = re.search(r"testDir\s*:\s*['\"]([^'\"]+)['\"]", config.read_text(encoding="utf-8"))
        if m:
            rel = m.group(1)
    if not rel:
        raise SpecError("cannot determine where tests live: set regression_export.test_dir in .claude/qa.yml")
    target = (root / rel).resolve()
    if root.resolve() not in (target, *target.parents):
        raise SpecError(f"regression_export.test_dir {rel!r} resolves outside the project")
    return target


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].rstrip("-") or "regression"


# ------------------------------------------------------------------------ render


def _js(value: str) -> str:
    return json.dumps(value)


def _locator(t: dict[str, str]) -> str:
    if "testid" in t:
        return f"page.getByTestId({_js(t['testid'])})"
    if "role" in t:
        opts = f", {{ name: {_js(t['name'])} }}" if "name" in t else ""
        return f"page.getByRole({_js(t['role'])}{opts})"
    if "label" in t:
        return f"page.getByLabel({_js(t['label'])})"
    return f"page.getByText({_js(t['text'])})"


def render_test(spec: dict[str, Any], module: str) -> str:
    lines = [
        "// Generated by claude-power-pack scripts/qa-regression-export.py (issue #1291).",
        "// Regression test for a bug confirmed by exploratory QA. Edit freely; re-export",
        "// only replaces it with --force.",
    ]
    if spec.get("issue"):
        # JSON-escaped, never raw: a newline in the value would otherwise end the
        # comment and put the rest of the string into the file as code.
        lines.append(f"// Issue: {_js(spec['issue'])}")
    lines += [
        f"import {{ test, expect }} from {_js(module)};",
        "",
        f"const UNAVAILABLE = {_js(UNAVAILABLE_MARKER)};",
        "",
        "// Load a route, or fail with the marker that means 'could not run', which the",
        "// handoff never reads as the bug being present.",
        "async function reach(page, path) {",
        "  let response;",
        "  try {",
        "    response = await page.goto(path);",
        "  } catch (err) {",
        "    throw new Error(`${UNAVAILABLE}: ${err.message.split('\\n')[0]}`);",
        "  }",
        "  if (!response || !response.ok()) {",
        "    throw new Error(`${UNAVAILABLE}: HTTP ${response ? response.status() : 'no response'} for ${path}`);",
        "  }",
        "}",
        "",
        "// A fresh, empty context: never the explorer's session, never a logged-in",
        "// state the project config may set for its other tests.",
        "test.use({ storageState: { cookies: [], origins: [] } });",
        "",
        f"test({_js(spec['title'])}, async ({{ page }}) => {{",
    ]
    if spec.get("issue"):
        lines.append(f"  test.info().annotations.push({{ type: 'issue', description: {_js(spec['issue'])} }});")
    lines += [
        "  await test.step('precondition: app reachable', async () => {",
        f"    await reach(page, {_js(spec['start'])});",
        "  });",
    ]
    steps = spec.get("steps", [])
    if steps:
        lines.append("  await test.step('reproduce', async () => {")
        for index, step in enumerate(steps):
            action = step["action"]
            if action == "goto":
                # Every navigation, not just the first: a later route answering
                # 503 must read as unavailable, never as the bug (counter-model).
                lines.append(f"    await reach(page, {_js(step['path'])});")
                continue
            loc = _locator(step["target"])
            if action == "click":
                lines.append(f"    await {loc}.click();")
            elif action == "check":
                lines.append(f"    await {loc}.check();")
            elif action == "press":
                lines.append(f"    await {loc}.press({_js(step['key'])});")
            elif action == "fill":
                if "value_env" in step:
                    # One generated name per STEP, never derived from the variable:
                    # two fills from one variable would redeclare it, and a name
                    # like CLASS lowercases to a reserved word (counter-model review).
                    env, var = step["value_env"], f"fillValue{index}"
                    lines.append(f"    const {var} = process.env[{_js(env)}];")
                    unset = _js(f"set {env} before running this test")
                    lines.append(f"    if (!{var}) throw new Error({unset});")
                    lines.append(f"    await {loc}.fill({var});")
                else:
                    lines.append(f"    await {loc}.fill({_js(step['value'])});")
        lines.append("  });")
    lines.append("  await test.step('assert', async () => {")
    for exp in spec["expect"]:
        loc = _locator(exp["target"])
        if "toHaveText" in exp:
            lines.append(f"    await expect({loc}).toHaveText({_js(exp['toHaveText'])});")
        elif "toContainText" in exp:
            lines.append(f"    await expect({loc}).toContainText({_js(exp['toContainText'])});")
        elif "toBeVisible" in exp:
            lines.append(f"    await expect({loc}).toBeVisible();")
        else:
            lines.append(f"    await expect({loc}).toBeHidden();")
    lines += ["  });", "});", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------ export


def cmd_export(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    try:
        spec = validate_spec(json.loads(Path(args.spec).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"QA_REGRESSION_EXPORT: bad-spec {exc}")
        return EXIT_SPEC
    except SpecError as exc:
        print(f"QA_REGRESSION_EXPORT: bad-spec {exc}")
        return EXIT_SPEC

    qa = load_qa_config(root)
    if (qa.get("regression_export") or {}).get("enabled") is not True:
        print(
            "QA_REGRESSION_EXPORT: not-enabled - set `regression_export: {enabled: true, test_dir: ...}` "
            f"in {root / '.claude' / 'qa.yml'} to opt in"
        )
        return EXIT_NOT_ENABLED

    missing, module = runner_prerequisites(root)
    if missing or module is None:
        for item in missing:
            print(f"QA_REGRESSION_MISSING: {item}")
        print("QA_REGRESSION_EXPORT: missing-prerequisite - no executable handoff was produced; nothing was installed")
        return EXIT_PREREQ

    config = find_playwright_config(root)
    try:
        test_dir = resolve_test_dir(root, qa, config)
    except SpecError as exc:
        print(f"QA_REGRESSION_EXPORT: bad-config {exc}")
        return EXIT_SPEC
    ext = "ts" if config is not None and config.suffix in (".ts", ".mts", ".cts") else "mjs"
    target = test_dir / f"regression-{slugify(spec['title'])}.spec.{ext}"
    if target.exists() and not args.force:
        print(f"QA_REGRESSION_EXPORT: exists {target.relative_to(root)} - pass --force to replace it")
        return EXIT_EXISTS
    test_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(render_test(spec, module), encoding="utf-8")

    rel = target.relative_to(root).as_posix()
    print(f"QA_REGRESSION_TEST: {rel}")
    selector = shlex.quote(_file_filter(Path("/" + rel), anchor_start=False))
    print(f"QA_REGRESSION_RUN: npx playwright test {selector} --trace on")
    print(
        "QA_REGRESSION_TRACE: written under the config's outputDir per run; "
        "open with `npx playwright show-trace <trace.zip>`"
    )
    if spec.get("issue"):
        print(f"QA_REGRESSION_ISSUE: {spec['issue']}")
    print("QA_REGRESSION_EXPORT: ok")
    return EXIT_OK


# --------------------------------------------------------------------------- run


def _target_results(suites: list[dict[str, Any]], root_dir: Path | None, target: Path | None):
    """Yield (belongs_to_target, result) for every result in the report.

    Identity is by FILE: a spec's `file` is relative to the report's
    `config.rootDir`. A report also carries NEIGHBOURS - a project dependency
    (`auth.setup.ts`) runs and is reported even when one file is selected, and a
    failed dependency SKIPS the file asked about. Reading every result as the
    target's let a neighbour's failed assertion read as the bug reproduced
    (counter-model review), so only the target's own results decide.
    """
    for suite in suites or []:
        for spec in suite.get("specs", []) or []:
            mine = False
            if root_dir is not None and target is not None and spec.get("file"):
                mine = (root_dir / spec["file"]).resolve() == target
            for test in spec.get("tests", []) or []:
                for result in test.get("results", []) or []:
                    yield mine, result
        yield from _target_results(suite.get("suites", []) or [], root_dir, target)


ANSI = re.compile(r"\x1b\[[0-9;]*m")

#: Playwright reports an AMBIGUOUS locator under the same `expect(...) failed`
#: header as a real mismatch. It is a defect in the test, not a verdict about the
#: product: once an unrelated change adds a second matching element, a FIXED bug
#: would otherwise read as reproduced (counter-model review, measured on 1.63).
LOCATOR_ERRORS = ("strict mode violation",)


def _messages(result: dict[str, Any]) -> list[str]:
    errors = [result.get("error")] + list(result.get("errors", []) or [])
    return [ANSI.sub("", (e or {}).get("message", "") or "") for e in errors if e]


def classify_report(report: dict[str, Any] | None, target: Path | None) -> tuple[str, str, list[str]]:
    """Map a Playwright JSON report to (verdict, reason, trace paths) for ONE test file."""
    if not isinstance(report, dict):
        return "error", "no JSON report was produced", []
    top_errors = [e.get("message", "") for e in report.get("errors", []) or [] if isinstance(e, dict)]
    root = (report.get("config") or {}).get("rootDir")
    root_dir = Path(root).resolve() if isinstance(root, str) and root else None
    everything = list(_target_results(report.get("suites", []) or [], root_dir, target))
    results = [r for mine, r in everything if mine]
    traces = [
        a["path"]
        for r in results
        for a in r.get("attachments", []) or []
        if isinstance(a, dict) and a.get("name") == "trace" and a.get("path")
    ]
    if top_errors and not results:
        first = top_errors[0].strip().splitlines()[0] if top_errors[0].strip() else "runner error"
        return "error", f"the runner failed before the test ran: {first}", traces
    if root_dir is None and everything:
        return "error", "the report names no rootDir, so the test it describes cannot be identified", traces
    if not results:
        neighbours = len(everything)
        return "error", f"the requested test did not execute ({neighbours} other result(s) in the report)", traces

    statuses = [r.get("status") for r in results]
    messages = [m for r in results for m in _messages(r)]
    if any(s in (None, "skipped", "interrupted") for s in statuses):
        return "error", "the requested test was skipped or interrupted - a blocked test proves nothing", traces
    if any(UNAVAILABLE_MARKER in m for m in messages):
        return "unavailable", "the app could not be reached - this is NOT a bug reproduction", traces
    if all(s == "passed" for s in statuses) and not top_errors:
        return "passed", f"{len(results)} result(s) of the requested test passed", traces
    if any(marker in m for m in messages for marker in LOCATOR_ERRORS):
        return "error", "an assertion locator is ambiguous (strict mode violation) - fix the test; no verdict", traces
    if any(s in ("failed", "timedOut") for s in statuses) and any("expect(" in m for m in messages):
        return "reproduced", "a product assertion failed - the bug is present", traces
    first = next((m.strip().splitlines()[0] for m in messages + top_errors if m.strip()), "unclassified failure")
    return "error", first, traces


def _file_filter(path: Path, *, anchor_start: bool = True) -> str:
    """Playwright reads a positional filter as a REGEX: escape and anchor it.

    `anchor_start=False` is for the command printed to the consumer, which must
    not carry this machine's absolute path: `/<relative path>$` still selects
    exactly that file under the project, and never a similarly named neighbour.
    """
    escaped = re.sub(r"([.*+?^${}()|[\]\\])", r"\\\1", path.as_posix())
    return f"^{escaped}$" if anchor_start else f"{escaped}$"


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    target = (root / args.test).resolve()
    if root not in target.parents or not target.is_file():
        print(f"QA_REGRESSION_RESULT: error - {args.test} is not a file inside {root}")
        return RUN_ERROR
    missing, _module = runner_prerequisites(root)
    if missing:
        for item in missing:
            print(f"QA_REGRESSION_MISSING: {item}")
        print("QA_REGRESSION_RESULT: error - missing prerequisite, nothing was run")
        return RUN_ERROR
    rel = target.relative_to(root).as_posix()
    print(f"QA_REGRESSION_COMMAND: npx playwright test {shlex.quote(_file_filter(target))} --trace on")
    with tempfile.TemporaryDirectory(prefix="qa-regression-") as tmp:
        report_path = Path(tmp) / "report.json"
        env = dict(os.environ)
        env["PLAYWRIGHT_JSON_OUTPUT_FILE"] = str(report_path)
        env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = str(report_path)
        runner = str(root / "node_modules" / ".bin" / "playwright")
        cmd = [runner, "test", _file_filter(target), "--trace", "on", "--reporter=line,json"]
        try:
            proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f"QA_REGRESSION_RESULT: error - the runner did not finish within {args.timeout}s ({rel})")
            return RUN_ERROR
        except OSError as exc:
            print(f"QA_REGRESSION_RESULT: error - the runner could not be started: {exc}")
            return RUN_ERROR
        if args.verbose:
            sys.stdout.write(proc.stdout)
            sys.stderr.write(proc.stderr)
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = None
    verdict, reason, traces = classify_report(report, target)
    for trace in traces:
        print(f"QA_REGRESSION_TRACE: {trace}")
    print(f"QA_REGRESSION_RUNNER_EXIT: {proc.returncode}")
    print(f"QA_REGRESSION_RESULT: {verdict} - {reason}")
    return {"passed": RUN_PASSED, "reproduced": RUN_REPRODUCED, "unavailable": RUN_UNAVAILABLE}.get(verdict, RUN_ERROR)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export", help="write a regression test from a repro spec")
    exp.add_argument("--root", required=True, help="the consumer project root")
    exp.add_argument("--spec", required=True, help="the repro spec (JSON)")
    exp.add_argument("--force", action="store_true", help="replace an existing exported test")
    exp.set_defaults(func=cmd_export)
    run = sub.add_parser("run", help="run one exported test and classify the outcome")
    run.add_argument("--root", required=True, help="the consumer project root")
    run.add_argument("--test", required=True, help="test path relative to the root")
    run.add_argument("--timeout", type=int, default=300)
    run.add_argument("--verbose", action="store_true", help="echo the runner's own output")
    run.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    if args.command != "run":
        return int(args.func(args))
    # An uncaught exception exits 1, which is `reproduced`: a crashed run must
    # never read as the bug coming back (counter-model review).
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - every crash maps to one verdict
        print(f"QA_REGRESSION_RESULT: error - the helper crashed: {type(exc).__name__}: {exc}")
        return RUN_ERROR


if __name__ == "__main__":
    sys.exit(main())
