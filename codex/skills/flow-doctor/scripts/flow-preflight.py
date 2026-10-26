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
from pathlib import Path

SENTINEL = "__cpp_preflight_fields__"
REQUIRED_FIELDS = {
    "issue": {"blockedBy", "blocking", "parent", "subIssues", "assignees"},
    "pr": {"closingIssuesReferences"},
}


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
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        if not any(module.startswith("lib.project_next") for module in imports):
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
    except (OSError, ValueError, SyntaxError, AttributeError):
        return check("engine", "unknown", "Selected engine ownership is unreadable or malformed")


def python_check(repo, home):
    candidates = [p for name in ("python3.11", "python3") if (p := shutil.which(name))]
    data_root = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
    managed = Path(os.environ.get("UV_PYTHON_INSTALL_DIR", str(data_root / "uv/python")))
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
            candidates.append(str(candidate))
    except OSError:
        return check("cpp_python", "unknown", "Installed managed Python directory is unreadable")
    unknown = False
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for candidate in dict.fromkeys(candidates):
        code, out, err = run([candidate, "--version"], repo, env)
        version = re.fullmatch(r"Python (\d+)\.(\d+)\.(\d+)\s*", out or err)
        if code != 0 or not version:
            unknown = True
        elif version.group(1, 2) == ("3", "11"):
            return check(
                "cpp_python",
                "ok",
                "Installed CPP runner Python 3.11 is available",
                policy="CPP runner only; target project Python is independent",
            )
    return check(
        "cpp_python",
        "unknown" if unknown else "missing",
        "CPP runner Python 3.11 was not verified in PATH or the selected uv install directory",
        "Provide Python 3.11 for CPP's runner; do not change target-project or global pins",
        policy="CPP runner 3.11; project declaration remains >=3.11; no invented upper bound",
    )


def observe(args):
    repo = Path(args.repo).resolve()
    home = Path.home()
    checks = [gh_check(repo)]
    checks.append(
        check(
            "uv",
            "ok" if shutil.which("uv") else "missing",
            "uv executable presence only",
            "Install uv explicitly if missing; this observer never installs it",
        )
    )
    checks.append(python_check(repo, home))
    for key in ("user.name", "user.email"):
        code, out, _ = run(["git", "config", "--get", key], repo)
        status = "ok" if code == 0 and out.strip() else "missing" if code in (0, 1) else "unknown"
        checks.append(
            check(
                key,
                status,
                "Effective git identity presence (value withheld)",
                f"Set {key} explicitly for this repository; use an account-provided noreply address if desired",
            )
        )
    checks.append(
        check(
            "codex",
            "ok" if shutil.which("codex") else "warning",
            "Optional Codex executable presence only; auth/readiness untested",
            "Install/login only if choosing the optional review stage",
            required=False,
        )
    )
    checks.append(engine_check(args.harness, args.engine, home))
    gaps = sum(c["required"] and c["status"] in ("missing", "unsupported") for c in checks)
    unknown = sum(c["required"] and c["status"] == "unknown" for c in checks)
    code = 1 if gaps else 3 if unknown else 0
    return dict(
        schema=1,
        status="gaps" if gaps else "unknown" if unknown else "ready",
        required_gaps=gaps,
        required_unknown=unknown,
        checks=checks,
    ), code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--harness", choices=("auto", "claude", "codex"), default="auto")
    parser.add_argument("--engine")
    args = parser.parse_args()
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
    raise SystemExit(main())
