#!/usr/bin/env python3
"""Observe CPP host prerequisites without installing, authenticating, or configuring."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

SENTINEL = "__cpp_preflight_fields__"
REQUIRED_FIELDS = {
    "issue": {"blockedBy", "blocking", "parent", "subIssues", "assignees"},
    "pr": {"closingIssuesReferences"},
}
CHECK_IDS = ("gh", "uv", "cpp_python", "user.name", "user.email", "codex", "engine")


def parse_checks(value):
    if value == "all":
        return CHECK_IDS
    names = value.split(",")
    if not names or any(name not in CHECK_IDS for name in names) or len(set(names)) != len(names):
        raise argparse.ArgumentTypeError("--checks requires distinct known check IDs, or all")
    return tuple(name for name in CHECK_IDS if name in names)


def report_for(checks, selected):
    gaps = sum(c["required"] and c["status"] in ("missing", "unsupported") for c in checks)
    unknown = sum(c["required"] and c["status"] == "unknown" for c in checks)
    code = 1 if gaps else 3 if unknown else 0
    full = tuple(selected) == CHECK_IDS
    status = "gaps" if gaps else "unknown" if unknown else "ready"
    return dict(
        schema=1,
        status=status if full else "selected_" + status,
        scope="full" if full else "selected",
        full_host_ready=code == 0 if full else None,
        selected_checks=list(selected),
        unexamined_checks=[name for name in CHECK_IDS if name not in selected],
        required_gaps=gaps,
        required_unknown=unknown,
        checks=checks,
    ), code


def validate_report(raw, exit_code, selected):
    """Validate population, observations and verdict together, without probes.

    Consumers must call this even after exit zero. Provider text is never
    included in validation errors, including malformed/duplicate JSON keys.
    """

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate preflight report key")
            result[key] = value
        return result

    try:
        report = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(report, dict) or type(report.get("schema")) is not int or report["schema"] != 1:
            raise ValueError("Invalid preflight schema")
        checks = report["checks"]
        if not isinstance(checks, list) or [c["id"] for c in checks] != list(selected):
            raise ValueError("Preflight population mismatch")
        for item in checks:
            required = item["id"] != "codex"
            states = ("ok", "missing", "unsupported", "unknown") if required else ("ok", "warning")
            if item["required"] is not required or item["status"] not in states:
                raise ValueError("Invalid preflight observation")
            if not all(isinstance(item[key], str) for key in ("message", "remediation")):
                raise ValueError("Invalid preflight diagnostic")
            if not isinstance(item["evidence"], dict):
                raise ValueError("Invalid preflight evidence")
        expected, code = report_for(checks, selected)
        for key, value in expected.items():
            if key not in report or type(report[key]) is not type(value) or report[key] != value:
                raise ValueError("Contradictory preflight report")
        if type(exit_code) is not int or exit_code != code:
            raise ValueError("Preflight exit disagrees with observations")
        return report
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Preflight report is unverified (schema, population or verdict mismatch)") from exc


def run(argv, cwd, env=None):
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout, result.stderr
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None, "", ""


def check(name, status, message, remediation="", required=True, **evidence):
    return dict(id=name, status=status, required=required, message=message, remediation=remediation, evidence=evidence)


def gh_check(repo):
    if not shutil.which("gh"):
        return check(
            "gh", "missing", "GitHub CLI is absent", "Install gh from cli.github.com; standard releases need >=2.94.0"
        )
    env = os.environ.copy()
    for key in ("GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HTTP_UNIX_SOCKET"):
        env.pop(key, None)
    # A non-credential skips gh's auth-presence check. The invalid field must
    # terminate in local argument validation, before a repository/API lookup.
    env.update(
        GH_TOKEN="cpp-local-probe-not-a-credential",
        GH_HOST="github.com",
        GH_CONFIG_DIR=str(Path.home() / ".config/cpp-preflight-gh-unused"),
        GH_PROMPT_DISABLED="1",
        GH_DEBUG="api",
        GH_TELEMETRY="off",
        DO_NOT_TRACK="1",
        GH_NO_UPDATE_NOTIFIER="1",
        GH_NO_EXTENSION_UPDATE_NOTIFIER="1",
        HTTP_PROXY="http://127.0.0.1:9",
        HTTPS_PROXY="http://127.0.0.1:9",
        ALL_PROXY="http://127.0.0.1:9",
        NO_PROXY="",
        LC_ALL="C",
    )
    code, out, _ = run(["gh", "--version"], Path.home(), env)
    version = re.search(r"gh version (\d+\.\d+\.\d+)", out)
    version_text = version.group(1) if code == 0 and version else "unknown"
    for kind, required in REQUIRED_FIELDS.items():
        code, out, err = run(["gh", kind, "list", "--json", SENTINEL], Path.home(), env)
        lines = (err + out).strip().splitlines()
        prefix = [f'Unknown JSON field: "{SENTINEL}"', "Available fields:"]
        if code != 1 or lines[:2] != prefix or len(lines) < 3:
            return check(
                "gh",
                "unknown",
                "Local gh field enumeration could not be verified",
                "Inspect gh installation locally; do not infer capability from authentication errors",
                version=version_text,
            )
        if any(not re.fullmatch(r"  [A-Za-z][A-Za-z0-9]*", line) for line in lines[2:]):
            return check("gh", "unknown", "Unrecognized gh field enumeration grammar", version=version_text)
        fields = {line.strip() for line in lines[2:]}
        missing = sorted(required - fields)
        if missing:
            return check(
                "gh",
                "unsupported",
                "Required gh JSON fields are unavailable",
                "Upgrade gh; standard-source capability floor is 2.94.0",
                version=version_text,
                command=kind,
                missing_fields=missing,
            )
    return check(
        "gh", "ok", "Required local gh JSON fields are available (not an auth/API check)", version=version_text
    )


def engine_check(harness, engine, home):
    if not engine:
        if harness == "auto":
            native = [
                name
                for name, key in (("codex", "CODEX_THREAD_ID"), ("claude", "CLAUDE_CODE_SESSION_ID"))
                if os.environ.get(key)
            ]
            if len(native) != 1:
                return check(
                    "engine", "unknown", "Active harness is ambiguous", "Pass --harness claude or --harness codex"
                )
            harness = native[0]
        if harness == "claude":
            engine = home / ".claude/scripts/project-next.py"
        else:
            engine = (
                Path(os.environ.get("CODEX_HOME", str(home / ".codex"))) / "skills/project-next/scripts/project-next.py"
            )
    entry = Path(engine)
    try:
        real = entry.resolve(strict=True)
        if real.name != "project-next.py" or real.parent.name != "scripts" or not real.is_file():
            return check("engine", "unknown", "Selected entry point is not the supported project-next layout")
        tree = ast.parse(real.read_text())
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level == 0]
        if not any(module == "lib.project_next" or module.startswith("lib.project_next.") for module in imports):
            return check("engine", "unknown", "Selected entry point does not identify the CPP engine")
        root = real.parent.parent
        manifest = root / "lib/project_next/ownership.json"
        data = json.loads(manifest.read_text())
        if data.get("owner") != "cooneycw/claude-power-pack":
            return check("engine", "unsupported", "Selected engine ownership does not match CPP")
        declared = data.get("contract_version")
        if not isinstance(declared, str) or not declared:
            return check("engine", "unknown", "Selected ownership manifest has no valid contract version")
        rank = ast.parse((root / "lib/project_next/rank.py").read_text())
        versions = [
            node.value.value
            for node in rank.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "CONTRACT_VERSION" for t in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ]
        if len(versions) != 1:
            return check("engine", "unknown", "Engine contract binding could not be read")
        if versions[0] != declared:
            return check("engine", "unsupported", "Selected engine and ownership contract versions disagree")
        return check(
            "engine", "ok", "Selected resolved engine has matching CPP ownership", contract=declared, harness=harness
        )
    except FileNotFoundError:
        return check(
            "engine",
            "missing",
            "Selected engine or colocated ownership data is missing",
            "Repair the active harness installation; keep scripts and lib together",
        )
    except (OSError, ValueError, SyntaxError, AttributeError, RuntimeError):
        return check("engine", "unknown", "Selected engine ownership is unreadable or malformed")


def python_check(repo, home):
    unknown = False
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def verifies(candidates):
        nonlocal unknown
        for candidate in dict.fromkeys(candidates):
            code, out, err = run([candidate, "--version"], repo, env)
            version = re.fullmatch(r"Python (\d+)\.(\d+)\.(\d+)\s*", out or err)
            if code != 0 or not version:
                unknown = True
            elif version.group(1, 2) == ("3", "11"):
                return True
        return False

    def ready():
        return check(
            "cpp_python",
            "ok",
            "Installed CPP runner Python 3.11 is available",
            policy="CPP runner only; target project Python is independent",
        )

    candidates = [p for name in ("python3.11", "python3") if (p := shutil.which(name))]
    if verifies(candidates):
        return ready()
    data_root = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
    managed = Path(os.environ.get("UV_PYTHON_INSTALL_DIR", str(data_root / "uv/python")))
    candidates = []
    try:
        try:
            directories = list(managed.iterdir())
        except FileNotFoundError:
            directories = []
        for directory in directories:
            if not directory.name.startswith("cpython-3.11."):
                continue
            candidate = directory / "bin/python3.11"
            try:
                candidate.stat()
            except FileNotFoundError:
                continue
            except OSError:
                unknown = True
                continue
            candidates.append(str(candidate))
    except OSError:
        return check("cpp_python", "unknown", "Installed managed Python directory is unreadable")
    if verifies(candidates):
        return ready()
    return check(
        "cpp_python",
        "unknown" if unknown else "missing",
        "CPP runner Python 3.11 was not verified in PATH or the selected uv install directory",
        "Provide Python 3.11 for CPP's runner; do not change target-project or global pins",
        policy="CPP runner 3.11; project declaration remains >=3.11; no invented upper bound",
    )


def observe(args):
    try:
        repo = Path(args.repo).resolve()
    except (OSError, RuntimeError, ValueError):
        repo = None
    home = Path.home()
    selected = getattr(args, "checks", CHECK_IDS)

    def identity(key):
        code, out, _ = run(["git", "config", "--get", key], repo) if repo is not None else (None, "", "")
        status = "ok" if code == 0 and out.strip() else "missing" if code in (0, 1) else "unknown"
        return check(
            key,
            status,
            "Effective git identity presence (value withheld)",
            f"Set {key} explicitly for this repository; use an account-provided noreply address if desired",
        )

    probes = {
        "gh": lambda: gh_check(repo),
        "uv": lambda: check(
            "uv",
            "ok" if shutil.which("uv") else "missing",
            "uv executable presence only",
            "Install uv explicitly if missing; this observer never installs it",
        ),
        "cpp_python": lambda: python_check(repo or home, home),
        "user.name": lambda: identity("user.name"),
        "user.email": lambda: identity("user.email"),
        "codex": lambda: check(
            "codex",
            "ok" if shutil.which("codex") else "warning",
            "Optional Codex executable presence only; auth/readiness untested",
            "Install/login only if choosing the optional review stage",
            required=False,
        ),
        "engine": lambda: engine_check(args.harness, args.engine, home),
    }
    return report_for([probes[name]() for name in selected], selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--harness", choices=("auto", "claude", "codex"), default="auto")
    parser.add_argument("--engine")
    parser.add_argument(
        "--checks",
        type=parse_checks,
        default=CHECK_IDS,
        help="comma-separated check IDs, or all (default); unselected checks are unexamined",
    )
    parser.add_argument(
        "--validate-exit", type=int, help="validate a JSON report on stdin against this original exit; no probes"
    )
    args = parser.parse_args()
    if args.validate_exit is not None:
        try:
            report = validate_report(sys.stdin.read(), args.validate_exit, args.checks)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 3
        if args.json:
            print(json.dumps(report, sort_keys=True))
        if args.validate_exit != 0:
            print("Preflight readiness unestablished: " + report["status"], file=sys.stderr)
            return args.validate_exit
        return 0
    report, code = observe(args)
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        for item in report["checks"]:
            print(f"{item['status'].upper()} {item['id']}: {item['message']}")
            if item["status"] != "ok" and item["remediation"]:
                print("  " + item["remediation"])
        print("FLOW_PREFLIGHT: " + report["status"])
    return code


if __name__ == "__main__":
    # Preserve stderr ordering and exit status on usage, exceptions and failed
    # output flushes, following the installed helper family contract (#1031).
    _code = 1
    try:
        _code = main()
    except SystemExit as _exc:
        _code = _exc.code if isinstance(_exc.code, int) else int(bool(_exc.code))
    except BaseException:  # noqa: BLE001 - diagnostic retained before marker
        traceback.print_exc()
        _code = 1
    _flush_failed = False
    try:
        sys.stdout.flush()
    except BaseException:  # noqa: BLE001 - reported, then exited
        traceback.print_exc()
        _flush_failed = True
        if _code == 0:
            _code = 1
    print(f"FLOW_PREFLIGHT_EXIT={_code}", file=sys.stderr)
    if _flush_failed:
        try:
            sys.stderr.flush()
        except BaseException:  # noqa: BLE001 - no remaining reporting channel
            pass
        os._exit(_code)
    raise SystemExit(_code)
