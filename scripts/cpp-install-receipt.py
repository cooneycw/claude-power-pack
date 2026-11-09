#!/usr/bin/env python3
#: HOST-SURFACE: none - writes the explicitly selected project receipt, not a user-scope installation surface
"""Persist cpp:init's observed STEP_RESULTS; report recorded state, not live health.

Input is metadata only: fixed step IDs, outcome enums, and reference IDs. Never
pass command output, configuration, endpoints, credentials or environment values.
The project receipt is not a host installation surface or a successful step.
"""
# NEGATIVE-CONTROL: controls/cpp-install-receipt
# NEGATIVE-CONTROL: controls/cpp-host-install-receipt
# NEGATIVE-CONTROL: controls/cpp-capability-selection

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

HOST_CI_OUTCOMES = {"written", "deferred", "failed", "unknown"}
LEGACY_TIER4_STEPS = {"framework-makefile", "cicd-config"}
OUTCOMES = {"installed", "already", "skipped", "declined", "FAILED", "unverified"}
PROFILES = {"Cautious", "Standard", "Trusted", "YOLO", "Custom", "not-selected"}
REFERENCES = {
    "host-ci-record": "<projects>/.claude/cpp-host.json (recorded host capability snapshot)",
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
    "claude-user-settings": "~/.claude/settings.json (user permission/hook declarations)",
    "shell-startup": "user shell startup file (CPP startup blocks)",
    "happy-cli": "user npm global installation (Happy CLI; reference only)",
    "spec-kit-cli": "user uv tool installation (Spec-Kit CLI; reference only)",
    "memory-service": "user common-memory service/container (reference only)",
}
STEP_REFS = {
    "host-ci": ["host-ci-record"],
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
    "user-flow-allowlist": ["claude-user-settings"], "permission-census": ["claude-user-settings"],
    "session-reminders": ["claude-user-settings"], "tmux-autostart": ["shell-startup"],
    "happy-cli": ["happy-cli"], "spec-kit-cli": ["spec-kit-cli"],
    "memory-store-start": ["memory-service"], "memory-store-ping": ["memory-store"],
}
TIER_STEPS = {
    1: ["commands", "stash-guard"],
    2: ["scripts", "permission-profile"],
    3: ["uv", "second-opinion", "playwright", "tavily"],
    4: ["host-ci"],
    5: ["codex-cli", "codex-doctor", "codex-auth", "codex-skills", "memory-harness"],
    6: ["qwen-cli", "qwen-model"],
    7: ["gemma-cli", "gemma-model", "gemma-provider"],
}
TIER_CAPABILITIES = {1: "commands", 2: "scripts", 3: "mcp", 4: "cicd", 5: "codex", 6: "qwen", 7: "gemma"}
OPTIONAL_STEPS = {
    "project-commands", "shell-prompt", "generic-makefile", "browser-pool",
    "health-config", "pipeline", "containers", "codex-second-opinion",
    "codex-playwright", "codex-tavily", "qwen-endpoint", "qwen-smoke",
    "qwen-always-on", "gemma-endpoint", "gemma-smoke", "sequential-thinking",
    "workstation-tuning", "memory-store",
    "stash-guard", "tavily", "user-flow-allowlist", "permission-census", "session-reminders", "tmux-autostart",
    "happy-cli", "spec-kit-cli", "memory-store-start", "memory-store-ping",
}
STEPS = set().union(*TIER_STEPS.values(), OPTIONAL_STEPS, LEGACY_TIER4_STEPS)

# Installation capabilities are independent. Only real prerequisites belong in
# this graph; the historical tier ladder survives exclusively as preset data.
CAPABILITY_ORDER = ("commands", "scripts", "mcp", "cicd", "codex", "qwen", "gemma", "extras")
CAPABILITY_DEPENDENCIES = {
    "commands": (), "scripts": (), "mcp": (), "cicd": (),
    "codex": ("commands", "scripts"), "qwen": ("commands",), "gemma": ("commands",), "extras": (),
}
CAPABILITY_REQUIRED = {TIER_CAPABILITIES[number]: tuple(steps) for number, steps in TIER_STEPS.items()}
CAPABILITY_REQUIRED["extras"] = ()
CAPABILITY_OPTIONAL = {
    "commands": ("project-commands",),
    "scripts": ("shell-prompt", "user-flow-allowlist", "permission-census", "session-reminders",
                "tmux-autostart", "happy-cli", "spec-kit-cli"),
    "mcp": ("browser-pool",),
    "cicd": (),
    "codex": ("codex-second-opinion", "codex-playwright", "codex-tavily"),
    "qwen": ("qwen-endpoint", "qwen-smoke", "qwen-always-on"),
    "gemma": ("gemma-endpoint", "gemma-smoke"),
    "extras": ("sequential-thinking", "codex-second-opinion", "codex-playwright", "codex-tavily",
               "workstation-tuning", "memory-store", "memory-store-start", "memory-store-ping"),
}
CAPABILITY_PRESETS = {
    number: tuple(TIER_CAPABILITIES[tier] for tier in (range(1, number + 1) if number <= 5 else (1, number)))
    + ("extras",) for number in TIER_STEPS
}


def capability_plan(requested: object = None, *, preset: int | None = None) -> dict:
    """Resolve a validated selection in dependency order, without host writes."""
    if preset is not None:
        if type(preset) is not int or preset not in CAPABILITY_PRESETS or requested is not None:
            raise ValueError("choose capabilities or one preset")
        requested = list(CAPABILITY_PRESETS[preset])
    if (not isinstance(requested, list) or not requested
            or any(not isinstance(cap, str) or cap not in CAPABILITY_DEPENDENCIES for cap in requested)):
        raise ValueError("capability selection invalid")
    selected: set[str] = set()
    visiting: set[str] = set()

    def include(cap: str) -> None:
        if cap in visiting:
            raise ValueError("capability dependency cycle")
        if cap in selected:
            return
        visiting.add(cap)
        for dependency in CAPABILITY_DEPENDENCIES[cap]:
            include(dependency)
        visiting.remove(cap)
        selected.add(cap)

    for cap in requested:
        include(cap)
    capabilities = [cap for cap in CAPABILITY_ORDER if cap in selected]
    sections = []
    for cap in capabilities:
        if cap in {"qwen", "gemma"} and "local-seam" not in sections:
            sections.append("local-seam")
        sections.append(cap)
    required = [step for cap in capabilities for step in CAPABILITY_REQUIRED[cap]]
    allowed = list(dict.fromkeys([*required, *(step for cap in capabilities for step in CAPABILITY_OPTIONAL[cap])]))
    return {"preset": preset, "requested": [cap for cap in CAPABILITY_ORDER if cap in requested],
            "capabilities": capabilities, "sections": sections,
            "required_steps": required, "allowed_steps": allowed}


def required_steps(tier: int, *, legacy: bool = False) -> list[str]:
    tiers = range(1, tier + 1) if tier <= 5 else (1, tier)
    return [step for number in tiers for step in
            (sorted(LEGACY_TIER4_STEPS) if legacy and number == 4 else TIER_STEPS[number])]


def selected_capabilities(tier: int) -> list[str]:
    """Record the existing preset selection, independently of step outcomes."""
    tiers = range(1, tier + 1) if tier <= 5 else (1, tier)
    return [TIER_CAPABILITIES[number] for number in tiers]


def offered_steps(raw: object, tier: int) -> list[str]:
    if not isinstance(raw, str):
        raise ValueError("offered step population required")
    values = json.loads(raw)
    if (not isinstance(values, list) or any(not isinstance(step, str) or step not in STEPS for step in values)
            or len(set(values)) != len(values)):
        raise ValueError("offered step population invalid")
    return list(dict.fromkeys([*required_steps(tier), *values]))


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


def host_ci_valid(outcome: object, code: object) -> bool:
    """Only an actual successful write completes this step; scope checks do not."""
    return ((outcome == "written" and type(code) is int and code == 0)
            or (outcome in {"deferred", "unknown"} and type(code) is int and code == 3)
            or (outcome == "unknown" and type(code) is int and code == 0)
            or (outcome == "failed" and type(code) is int and 0 < code <= 255 and code != 3)
            or (outcome == "unverified" and code is None))


def observation(item: object) -> dict:
    if not isinstance(item, dict) or set(item) - {"step", "outcome", "user_scope", "exit_code"}:
        raise ValueError("STEP_RESULTS metadata invalid")
    step, outcome = item.get("step"), item.get("outcome")
    if not isinstance(step, str) or step not in STEPS or not isinstance(outcome, str):
        raise ValueError("STEP_RESULTS step or outcome invalid")
    code = item.get("exit_code")
    if code is not None and (type(code) is not int or not 0 <= code <= 255):
        raise ValueError("STEP_RESULTS exit status invalid")
    if step == "host-ci":
        if not host_ci_valid(outcome, code):
            raise ValueError("host-ci outcome does not match observed write status")
    elif outcome not in OUTCOMES:
        raise ValueError("STEP_RESULTS outcome invalid")
    elif code:
        outcome = "FAILED"
    refs = item.get("user_scope", STEP_REFS.get(step, []))
    if (not isinstance(refs, list)
            or any(not isinstance(ref, str) or ref not in STEP_REFS.get(step, []) for ref in refs)):
        raise ValueError("STEP_RESULTS reference invalid")
    return {**item, "step": step, "outcome": outcome}


def host_ci_results(raw: str, code: int, previous: object) -> list[dict]:
    """Replace only the host observation from the actual CLI receipt + status.

    Ignore provider verdicts and discard raw probe text. Missing, duplicate or
    contradictory receipt lines cannot prove persistence, even on exit zero.
    """
    if not isinstance(previous, list):
        raise ValueError("STEP_RESULTS must be a list")
    preserved = [observation(item) for item in previous if not isinstance(item, dict) or item.get("step") != "host-ci"]
    states = [line for line in raw.splitlines() if line.startswith("HOST_CI_RECORD:")]
    state = states[0].removeprefix("HOST_CI_RECORD: ") if len(states) == 1 else None
    if code == 0 and state == "written":
        outcome = "written"
    elif code == 3 and state == "deferred":
        outcome = "deferred"
    elif code not in {0, 3}:
        outcome = "failed"
    else:
        outcome = "unknown"
    return [*preserved, {"step": "host-ci", "outcome": outcome, "exit_code": code}]


def make_receipt(args: argparse.Namespace, cpp_revision: str) -> dict:
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        raise ValueError("STEP_RESULTS must be a list")
    now = timestamp()
    custom = getattr(args, "capabilities", None) is not None or getattr(args, "preset", None) is not None
    if custom:
        plan = capability_plan(json.loads(args.capabilities) if args.capabilities is not None else None,
                               preset=args.preset)
        offered = json.loads(args.offered_steps)
        if (not isinstance(offered, list) or any(not isinstance(step, str) or step not in plan["allowed_steps"]
                                               for step in offered) or len(set(offered)) != len(offered)):
            raise ValueError("offered steps outside selected capabilities")
        offered = list(dict.fromkeys([*plan["required_steps"], *offered]))
        selection = {"preset": plan["preset"], "requested": plan["requested"],
                     "capabilities": plan["capabilities"], "profile": args.profile}
    else:
        offered = offered_steps(args.offered_steps, args.tier)
        selection = {"tier": args.tier, "profile": args.profile, "capabilities": selected_capabilities(args.tier)}
    steps: list[dict] = []
    seen = set()
    for item in data:
        item = observation(item)
        step, outcome = item["step"], item["outcome"]
        if step in seen:
            raise ValueError("STEP_RESULTS step duplicated")
        if step not in offered:
            raise ValueError("STEP_RESULTS observation outside offered population")
        exit_code = item.get("exit_code")
        refs = item.get("user_scope", STEP_REFS.get(step, []))
        seen.add(step)
        steps.append({"step": step, "outcome": outcome, "recorded_at": now,
                      "exit_code": exit_code, "user_scope": sorted(set(refs))})
    for step in offered:
        if step not in seen:
            steps.append({"step": step, "outcome": "unverified", "recorded_at": now,
                          "exit_code": None, "user_scope": STEP_REFS.get(step, [])})
    refs = sorted({ref for step in steps for ref in step["user_scope"]})
    return {
        "schema": 2 if custom else 1, "cpp_revision": cpp_revision, "recorded_at": now,
        "selected": selection,
        "offered_steps": offered, "steps": steps,
        "user_scope": {ref: REFERENCES[ref] for ref in refs},
        "permissions": permissions(json.loads(args.permission_report)),
    }


def validate(data: object) -> dict:
    if not isinstance(data, dict) or set(data) != {
        "schema", "cpp_revision", "recorded_at", "selected", "offered_steps", "steps", "user_scope", "permissions",
    }:
        raise ValueError("receipt shape invalid")
    if type(data["schema"]) is not int or data["schema"] not in {1, 2} or not valid_time(data["recorded_at"]):
        raise ValueError("receipt version or timestamp invalid")
    if (not isinstance(data["cpp_revision"], str)
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", data["cpp_revision"])):
        raise ValueError("receipt revision invalid")
    selected = data["selected"]
    if not isinstance(selected, dict) or selected.get("profile") not in PROFILES:
        raise ValueError("receipt selection invalid")
    if data["schema"] == 1:
        if (set(selected) != {"tier", "profile", "capabilities"}
                or type(selected["tier"]) is not int or selected["tier"] not in TIER_STEPS):
            raise ValueError("receipt selection invalid")
        if selected["capabilities"] != selected_capabilities(selected["tier"]):
            raise ValueError("receipt selected capabilities invalid")
        plan = None
    else:
        if set(selected) != {"preset", "requested", "profile", "capabilities"}:
            raise ValueError("receipt selection invalid")
        preset = selected["preset"]
        plan = capability_plan(preset=preset) if preset is not None else capability_plan(selected["requested"])
        if selected["requested"] != plan["requested"] or selected["capabilities"] != plan["capabilities"]:
            raise ValueError("receipt selected capabilities invalid")
    offered = data["offered_steps"]
    if (not isinstance(offered, list)
            or any(not isinstance(step, str) or step not in STEPS for step in offered)
            or len(set(offered)) != len(offered)):
        raise ValueError("receipt offered population invalid")
    legacy = (data["schema"] == 1 and selected["tier"] in {4, 5} and "host-ci" not in offered
              and LEGACY_TIER4_STEPS <= set(offered))
    required = plan["required_steps"] if plan is not None else required_steps(selected["tier"], legacy=legacy)
    if (not set(required) <= set(offered)
            or (plan is not None and not set(offered) <= set(plan["allowed_steps"]))):
        raise ValueError("receipt offered population invalid")
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
        if (not isinstance(outcome, str) or not valid_time(item["recorded_at"])
                or (step != "host-ci" and outcome not in OUTCOMES)):
            raise ValueError("receipt outcome invalid")
        code = item["exit_code"]
        if step == "host-ci":
            if not host_ci_valid(outcome, code):
                raise ValueError("host-ci receipt exit status invalid")
        elif code is not None and (type(code) is not int or not 0 <= code <= 255 or (code and outcome != "FAILED")):
            raise ValueError("receipt exit status invalid")
        if (not isinstance(item["user_scope"], list)
                or any(not isinstance(ref, str) or ref not in STEP_REFS.get(step, []) for ref in item["user_scope"])):
            raise ValueError("receipt reference invalid")
        refs.update(item["user_scope"])
        seen.add(step)
    if set(offered) != seen:
        raise ValueError("receipt offered outcomes missing or unexpected")
    if data["user_scope"] != {ref: REFERENCES[ref] for ref in refs}:
        raise ValueError("receipt references invalid")
    if data["permissions"] != permissions(data["permissions"]):
        raise ValueError("receipt permission metadata invalid")
    return data


def complete(data: dict) -> bool:
    return all((item["step"] == "host-ci" and item["outcome"] == "written")
               or item["outcome"] in {"installed", "already"} or (
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
    failed = any(item["outcome"] == "FAILED" or (item["step"] == "host-ci" and item["outcome"] == "failed")
                 for item in data["steps"])
    if stale:
        print("CPP_INSTALL_RECEIPT: receipt stale (CPP revision differs)")
    state = "receipt says failed" if failed else "receipt complete" if complete(data) else "receipt incomplete"
    print("CPP_INSTALL_RECEIPT: " + state)
    if summary:
        print("CPP Installation Complete" if complete(data) and not stale else "CPP Installation Incomplete")
        print(f"Recorded CPP revision: {data['cpp_revision']}")
        if data["schema"] == 1:
            print(f"Selected tier: {data['selected']['tier']}; selected profile: {data['selected']['profile']}")
        else:
            print(f"Selected preset: {data['selected']['preset'] or 'custom'}; "
                  f"selected profile: {data['selected']['profile']}")
        print("Selected capabilities: " + ", ".join(data["selected"]["capabilities"]))
        print(f"Recorded outcomes for {len(data['offered_steps'])} offered steps (not live health probes):")
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
    parser.add_argument("command", choices=("write", "summary", "status", "host-ci-outcome", "plan", "section"))
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--cpp-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--revision", help="explicit CPP revision (otherwise read local checkout HEAD)")
    parser.add_argument("--tier", type=int, choices=range(1, 8))
    parser.add_argument("--capabilities", help="JSON array of independent capability names")
    parser.add_argument("--preset", type=int, choices=range(1, 8))
    parser.add_argument("--section", help="capability section identifier (section command only)")
    parser.add_argument("--profile", choices=sorted(PROFILES))
    parser.add_argument("--offered-steps", help="JSON array of fixed step IDs offered by this run; required for write")
    parser.add_argument("--permission-report", default="{}", help="permission observer metadata only")
    parser.add_argument("--exit-code", type=int, choices=range(256), help="observed host-ci launcher exit")
    parser.add_argument("--steps-json", default="[]", help="prior general metadata outcomes for host-ci replacement")
    args = parser.parse_args()
    path = args.project_dir / ".claude/cpp-install.json"
    try:
        if args.command in {"plan", "section"}:
            requested = json.loads(args.capabilities) if args.capabilities is not None else None
            plan = capability_plan(requested, preset=args.preset)
            if args.command == "section":
                if args.section not in {*CAPABILITY_ORDER, "local-seam"}:
                    raise ValueError("unknown capability section")
                return 0 if args.section in plan["sections"] else 3
            print(json.dumps(plan))
            return 0
        if args.command == "host-ci-outcome":
            if args.exit_code is None:
                raise ValueError("observed exit status required")
            print(json.dumps(host_ci_results(sys.stdin.read(), args.exit_code, json.loads(args.steps_json))))
            return 0
        current = revision(args)
        if args.command == "write":
            if (args.profile is None or (args.tier is None and args.capabilities is None and args.preset is None)
                    or (args.tier is not None and (args.capabilities is not None or args.preset is not None))):
                raise ValueError("one selection and profile required")
            data = validate(make_receipt(args, current))
            write(path, data)
            print("CPP_INSTALL_RECEIPT: saved .claude/cpp-install.json (step outcomes unchanged)")
            return 0
        return report(path, current, args.command == "summary")
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        if args.command == "write":
            print("CPP_INSTALL_RECEIPT: receipt write FAILED - installation incomplete; "
                  "retain observed STEP_RESULTS and retry")
        elif args.command == "host-ci-outcome":
            print("CPP_INSTALL_HOST_CI: unverified - observation metadata invalid")
        elif args.command in {"plan", "section"}:
            print("CPP_INSTALL_SELECTION: invalid capability selection or section")
        else:
            print("CPP_INSTALL_RECEIPT: unverified - CPP revision unavailable or receipt could not be examined")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
