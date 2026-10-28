#!/usr/bin/env python3
"""Persist cpp:init's observed STEP_RESULTS; report recorded state, not live health.

Input is metadata only: fixed step IDs, outcome enums, and reference IDs. Never
pass command output, configuration, endpoints, credentials or environment values.
The project receipt is not a host installation surface or a successful step.
"""
# NEGATIVE-CONTROL: controls/cpp-install-receipt

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

OUTCOMES = {"installed", "already", "skipped", "declined", "FAILED", "unverified"}
PROFILES = {"Cautious", "Standard", "Trusted", "YOLO", "Custom", "not-selected"}
REFERENCES = {
    "claude-commands": "~/.claude/commands (CPP family links)",
    "claude-scripts": "~/.claude/scripts (CPP helper links)",
    "shell-prompt": "user shell startup file (CPP prompt block)",
    "claude-second-opinion": "Claude user-scope MCP registration: second-opinion",
    "claude-playwright": "Claude user-scope MCP registration: playwright",
    "claude-tavily": "Claude user-scope MCP registration: tavily",
    "claude-browser-pool": "Claude user-scope MCP registrations: browser desk pool",
    "codex-second-opinion": "Codex user-scope MCP registration: second-opinion",
    "codex-playwright": "Codex user-scope MCP registration: playwright",
    "codex-tavily": "Codex user-scope MCP registration: tavily",
    "codex-skills": "~/.codex/skills (CPP managed skills)",
    "memory-harness": "~/.local/bin/cpp-memory (CPP harness link)",
    "qwen-config": "Qwen Code and user shell configuration (references only)",
    "gemma-config": "OpenCode and user shell configuration (references only)",
    "sequential-thinking": "Claude user-scope MCP registration: sequential-thinking",
    "workstation-tuning": "user workstation tuning (bash-prep)",
    "memory-store": "user common-memory backend configuration (reference only)",
}
STEP_REFS = {
    "commands": ["claude-commands"], "scripts": ["claude-scripts"],
    "shell-prompt": ["shell-prompt"], "second-opinion": ["claude-second-opinion"],
    "playwright": ["claude-playwright"], "tavily": ["claude-tavily"],
    "browser-pool": ["claude-browser-pool"],
    "codex-second-opinion": ["codex-second-opinion"],
    "codex-playwright": ["codex-playwright"], "codex-tavily": ["codex-tavily"],
    "codex-skills": ["codex-skills"], "memory-harness": ["memory-harness"],
    "qwen-endpoint": ["qwen-config"], "qwen-always-on": ["qwen-config"],
    "gemma-endpoint": ["gemma-config"], "gemma-provider": ["gemma-config"],
    "sequential-thinking": ["sequential-thinking"],
    "workstation-tuning": ["workstation-tuning"], "memory-store": ["memory-store"],
}
TIER_STEPS = {
    1: ["commands", "stash-guard"],
    2: ["scripts", "permission-profile"],
    3: ["uv", "second-opinion", "playwright", "tavily"],
    4: ["framework-makefile", "cicd-config"],
    5: ["codex-cli", "codex-doctor", "codex-auth", "codex-skills", "memory-harness"],
    6: ["qwen-cli", "qwen-model"],
    7: ["gemma-cli", "gemma-model", "gemma-provider"],
}
OPTIONAL_STEPS = {
    "project-commands", "shell-prompt", "generic-makefile", "browser-pool",
    "health-config", "pipeline", "containers", "codex-second-opinion",
    "codex-playwright", "codex-tavily", "qwen-endpoint", "qwen-smoke",
    "qwen-always-on", "gemma-endpoint", "gemma-smoke", "sequential-thinking",
    "workstation-tuning", "memory-store",
}
STEPS = set().union(*TIER_STEPS.values(), OPTIONAL_STEPS)


def required_steps(tier: int) -> list[str]:
    tiers = range(1, tier + 1) if tier <= 5 else (1, tier)
    return [step for number in tiers for step in TIER_STEPS[number]]


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def valid_time(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def revision(args: argparse.Namespace) -> str:
    value = args.revision
    if value is None:
        result = subprocess.run(
            ["git", "-C", str(args.cpp_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode:
            raise ValueError("CPP revision unavailable")
        value = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise ValueError("CPP revision unavailable")
    return value


def permissions(raw: object) -> dict:
    """Keep only the observer's fixed identity and counts, never rule values."""
    if not isinstance(raw, dict):
        raise ValueError("permission observation invalid")
    profile = raw.get("profile", "unknown")
    verification = raw.get("verification", "unverified")
    counts = raw.get("counts", dict.fromkeys(("allow", "ask", "deny")))
    if profile not in PROFILES | {"unknown", "Custom/existing"}:
        raise ValueError("permission observation invalid")
    if verification not in {"verified", "unverified"} or not isinstance(counts, dict):
        raise ValueError("permission observation invalid")
    if set(counts) != {"allow", "ask", "deny"}:
        raise ValueError("permission observation invalid")
    if any(value is not None and (type(value) is not int or value < 0) for value in counts.values()):
        raise ValueError("permission observation invalid")
    return {"profile": profile, "verification": verification, "counts": counts}


def make_receipt(args: argparse.Namespace, cpp_revision: str) -> dict:
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        raise ValueError("STEP_RESULTS must be a list")
    now = timestamp()
    steps = []
    seen = set()
    for item in data:
        if not isinstance(item, dict) or set(item) - {"step", "outcome", "user_scope", "exit_code"}:
            raise ValueError("STEP_RESULTS metadata invalid")
        step, outcome = item.get("step"), item.get("outcome")
        if not isinstance(step, str) or step not in STEPS or step in seen:
            raise ValueError("STEP_RESULTS step invalid or duplicated")
        if not isinstance(outcome, str) or outcome not in OUTCOMES:
            raise ValueError("STEP_RESULTS outcome invalid")
        exit_code = item.get("exit_code")
        if exit_code is not None and (type(exit_code) is not int or not 0 <= exit_code <= 255):
            raise ValueError("STEP_RESULTS exit status invalid")
        if exit_code:
            outcome = "FAILED"
        refs = item.get("user_scope", STEP_REFS.get(step, []))
        if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in STEP_REFS.get(step, []) for ref in refs):
            raise ValueError("STEP_RESULTS reference invalid")
        seen.add(step)
        steps.append({"step": step, "outcome": outcome, "recorded_at": now,
                      "exit_code": exit_code, "user_scope": sorted(set(refs))})
    for step in required_steps(args.tier):
        if step not in seen:
            steps.append({"step": step, "outcome": "unverified", "recorded_at": now,
                          "exit_code": None, "user_scope": STEP_REFS.get(step, [])})
    refs = sorted({ref for step in steps for ref in step["user_scope"]})
    return {
        "schema": 1, "cpp_revision": cpp_revision, "recorded_at": now,
        "selected": {"tier": args.tier, "profile": args.profile}, "steps": steps,
        "user_scope": {ref: REFERENCES[ref] for ref in refs},
        "permissions": permissions(json.loads(args.permission_report)),
    }


def validate(data: object) -> dict:
    if not isinstance(data, dict) or set(data) != {
        "schema", "cpp_revision", "recorded_at", "selected", "steps", "user_scope", "permissions",
    }:
        raise ValueError("receipt shape invalid")
    if type(data["schema"]) is not int or data["schema"] != 1 or not valid_time(data["recorded_at"]):
        raise ValueError("receipt version or timestamp invalid")
    if not isinstance(data["cpp_revision"], str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", data["cpp_revision"]):
        raise ValueError("receipt revision invalid")
    selected = data["selected"]
    if not isinstance(selected, dict) or set(selected) != {"tier", "profile"}:
        raise ValueError("receipt selection invalid")
    if type(selected["tier"]) is not int or selected["tier"] not in TIER_STEPS or selected["profile"] not in PROFILES:
        raise ValueError("receipt selection invalid")
    if not isinstance(data["steps"], list) or not data["steps"]:
        raise ValueError("receipt outcomes absent")
    seen = set()
    refs = set()
    for item in data["steps"]:
        if not isinstance(item, dict) or set(item) != {"step", "outcome", "recorded_at", "user_scope", "exit_code"}:
            raise ValueError("receipt outcome shape invalid")
        step, outcome = item["step"], item["outcome"]
        if not isinstance(step, str) or step not in STEPS or step in seen:
            raise ValueError("receipt step invalid")
        if not isinstance(outcome, str) or outcome not in OUTCOMES or not valid_time(item["recorded_at"]):
            raise ValueError("receipt outcome invalid")
        code = item["exit_code"]
        if code is not None and (type(code) is not int or not 0 <= code <= 255 or (code and outcome != "FAILED")):
            raise ValueError("receipt exit status invalid")
        if not isinstance(item["user_scope"], list) or any(not isinstance(ref, str) or ref not in STEP_REFS.get(step, []) for ref in item["user_scope"]):
            raise ValueError("receipt reference invalid")
        refs.update(item["user_scope"])
        seen.add(step)
    if not set(required_steps(selected["tier"])) <= seen:
        raise ValueError("receipt selected outcomes missing")
    if data["user_scope"] != {ref: REFERENCES[ref] for ref in refs}:
        raise ValueError("receipt references invalid")
    if data["permissions"] != permissions(data["permissions"]):
        raise ValueError("receipt permission metadata invalid")
    return data


def complete(data: dict) -> bool:
    return all(item["outcome"] in {"installed", "already"} or (
        item["step"] in OPTIONAL_STEPS and item["outcome"] in {"skipped", "declined"}
    ) for item in data["steps"])


def report(path: Path, current: str, summary: bool) -> int:
    try:
        data = validate(json.loads(path.read_text()))
    except FileNotFoundError:
        print("CPP_INSTALL_RECEIPT: no receipt - run /cpp:init")
        return 1
    except (OSError, ValueError, TypeError):
        print("CPP_INSTALL_RECEIPT: unreadable or invalid receipt - run /cpp:init")
        return 1
    stale = data["cpp_revision"] != current
    failed = any(item["outcome"] == "FAILED" for item in data["steps"])
    if stale:
        print("CPP_INSTALL_RECEIPT: receipt stale (CPP revision differs)")
    state = "receipt says failed" if failed else "receipt complete" if complete(data) else "receipt incomplete"
    print("CPP_INSTALL_RECEIPT: " + state)
    if summary:
        print("CPP Installation Complete" if complete(data) and not stale else "CPP Installation Incomplete")
        print(f"Recorded CPP revision: {data['cpp_revision']}")
        print(f"Selected tier: {data['selected']['tier']}; selected profile: {data['selected']['profile']}")
        print("Step results (recorded outcomes; not live health probes):")
        for item in data["steps"]:
            print(f"  {item['step']}: {item['outcome']} ({item['recorded_at']})")
        observed = data["permissions"]
        print(f"Permission Profile: {observed['profile']} ({observed['verification']})")
        for field, value in observed["counts"].items():
            print(f"  Declared {field} rules: {'unverified' if value is None else value}")
        print("User-scope references (configuration only; not connectivity):")
        for reference in data["user_scope"].values():
            print("  " + reference)
    return 0 if complete(data) and not stale else 1


def write(path: Path, data: dict) -> None:
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("project receipt path must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".cpp-install-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("write", "summary", "status"))
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--cpp-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--revision", help="explicit CPP revision (otherwise read local checkout HEAD)")
    parser.add_argument("--tier", type=int, choices=range(1, 8))
    parser.add_argument("--profile", choices=sorted(PROFILES))
    parser.add_argument("--permission-report", default="{}", help="permission observer metadata only")
    args = parser.parse_args()
    path = args.project_dir / ".claude/cpp-install.json"
    try:
        current = revision(args)
        if args.command == "write":
            if args.tier is None or args.profile is None:
                raise ValueError("tier and profile required")
            data = validate(make_receipt(args, current))
            write(path, data)
            print("CPP_INSTALL_RECEIPT: saved .claude/cpp-install.json (step outcomes unchanged)")
            return 0
        return report(path, current, args.command == "summary")
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        if args.command == "write":
            print("CPP_INSTALL_RECEIPT: receipt write FAILED - installation incomplete; retain observed STEP_RESULTS and retry")
        else:
            print("CPP_INSTALL_RECEIPT: unverified - CPP revision unavailable or receipt could not be examined")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
