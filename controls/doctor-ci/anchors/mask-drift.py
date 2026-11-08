"""Read-only provider consistency diagnostics (#1611).

The verdict functions are stdlib-only and consume normalized evidence. The
collector lazily reuses canonical YAML/check readers, reads protection through
GitHub, and never runs provider credentials, installers, generators or CI probes.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .host import read_host_record
from .providers import PROVIDERS, REMEDY, read_provider_record

#: NEGATIVE-CONTROL: controls/doctor-ci
IDS = ("pipeline-files", "required-checks", "host-capability", "fallback")
PREFIXES = ("CI_PIPELINE_FILES", "CI_REQUIRED_CHECKS", "CI_HOST_CAPABILITY", "CI_FALLBACK")


def row(name: str, status: str, reason: str, **evidence: Any) -> dict[str, Any]:
    return {"id": name, "status": "ok" if status == "drift" else status,
            "reason": reason, "evidence": evidence}


def pipeline_row(names: list[str], inventory: dict[str, list[str]] | None) -> dict[str, Any]:
    if not names or any(not isinstance(name, str) or name not in PROVIDERS for name in names):
        return row(IDS[0], "unknown", "provider record missing or invalid; " + REMEDY)
    if (not isinstance(inventory, dict) or not set(PROVIDERS) <= set(inventory)
            or any(not isinstance(paths, list) or not all(isinstance(p, str) for p in paths)
                   for paths in inventory.values())):
        return row(IDS[0], "unknown", "registered pipeline paths unreadable or inventory incomplete")
    missing = [name for name in names if not inventory.get(name)]
    extra = [name for name, paths in inventory.items() if name in PROVIDERS and name not in names and paths]
    state = "drift" if missing or extra else "ok"
    reason = ("registered pipeline files disagree with provider record" if state == "drift" else
              "registered pipeline files match provider record")
    return row(IDS[0], state, reason, recorded=names, missing=missing, unrecorded=extra,
               files=inventory, scope="registered provider pipeline patterns")


def required_row(declared: dict[str, Any] | None, live: dict[str, Any] | None) -> dict[str, Any]:
    sources = {"declared": declared, "live": live}
    states = [value.get("status", "unknown") if isinstance(value, dict) else "unknown"
              for value in sources.values()]
    state = "drift" if "drift" in states else "ok" if states == ["ok", "ok"] else "unknown"
    reason = ("required checks disagree with unconditional PR contexts" if state == "drift" else
              "declared and live required checks match unconditional PR contexts" if state == "ok" else
              "required-check evidence unreadable or not derivable")
    return row(IDS[1], state, reason, sources=sources, target_branch="main",
               scope="unconditional PR status contexts; other branch policies not examined")


def host_row(names: list[str], record: dict[str, Any] | None) -> dict[str, Any]:
    if not names:
        return row(IDS[2], "unknown", "provider record missing or invalid; " + REMEDY)
    if not isinstance(record, dict) or not isinstance(record.get("providers"), dict):
        return row(IDS[2], "unknown", "host capability record unavailable")
    checked = record.get("checked_at")
    if not isinstance(checked, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T[0-9:.+-]+(?:Z)?", checked):
        checked = None
    states: dict[str, Any] = {}
    for name in names:
        value = record["providers"].get(name, {})
        status = value.get("status") if isinstance(value, dict) else None
        if not isinstance(status, str) or status not in {"ready", "missing", "unknown"} or not checked:
            status = "unknown"
        states[name] = status
    state = "drift" if "missing" in states.values() else "unknown" if "unknown" in states.values() else "ok"
    return row(IDS[2], state, "historical host capability snapshot; refresh with /cpp:init Tier 4 on the host",
               providers=states, checked_at=checked, current_connectivity="not examined")


def report(rows: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    # Missing/foreign/duplicate rows cannot make an incomplete population green.
    if ([value.get("id") for value in rows] != list(IDS)
            or any(value.get("status") not in {"ok", "drift", "unknown"} for value in rows)):
        rows = [row(name, "unknown", "diagnostic evidence population invalid") for name in IDS]
    state = ("drift" if any(value["status"] == "drift" for value in rows) else
             "unknown" if any(value["status"] == "unknown" for value in rows) else "ok")
    return {"schema": 1, "providers": names, "rows": rows, "status": state,
            "exit_code": {"ok": 0, "drift": 1, "unknown": 3}[state]}


@dataclass
class DoctorContext:
    run: Callable[..., Any] = subprocess.run
    which: Callable[[str], str | None] = shutil.which
    host_reader: Callable[[str | Path], dict[str, Any]] = read_host_record

    def command(self, argv: list[str], project: Path):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        return self.run(argv, cwd=project, capture_output=True, text=True, timeout=15, env=env)


def _slug(remote: str) -> str | None:
    if remote.startswith("git@github.com:"):
        path = remote.removeprefix("git@github.com:")
    else:
        parsed = urlsplit(remote)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname != "github.com" or parsed.query or parsed.fragment:
            return None
        path = parsed.path.lstrip("/")
    path = path.removesuffix(".git")
    parts = path.split("/")
    return path if (len(parts) == 2 and all(re.fullmatch(r"[A-Za-z0-9_.-]+", part)
                                          and part not in {".", ".."} for part in parts)) else None


def _api(ctx: DoctorContext, project: Path, endpoint: str) -> tuple[int, Any]:
    result = ctx.command(["gh", "api", "--include", "--hostname", "github.com", endpoint], project)
    header, body = result.stdout.replace("\r\n", "\n").split("\n\n", 1)
    status = header.splitlines()[0].split()
    if len(status) < 2 or not status[0].startswith("HTTP/") or not re.fullmatch(r"\d{3}", status[1]):
        raise ValueError("unreadable HTTP status")
    code = int(status[1])
    if 200 <= code < 300 and result.returncode != 0:
        raise ValueError("failed API transport")
    return code, json.loads(body)


def live_posture(project: Path, ctx: DoctorContext) -> tuple[dict[str, Any] | None, str]:
    """Union classic/ruleset required contexts only when both are examined.

    Missing authentication, permission errors and ambiguous 404s remain unknown.
    Never dump response bodies, stderr, remote URLs or exception text.
    """
    if not ctx.which("git") or not ctx.which("gh"):
        return None, "GitHub protection reader unavailable"
    try:
        remote = ctx.command(["git", "-C", str(project), "remote", "get-url", "origin"], project)
        slug = _slug(remote.stdout.strip()) if remote.returncode == 0 else None
        if not slug:
            return None, "target repository identity unavailable"
        classic_code, classic = _api(ctx, project, f"repos/{slug}/branches/main/protection")
        rules_code, rules = _api(ctx, project, f"repos/{slug}/rules/branches/main")
        if classic_code == 404 and isinstance(classic, dict) and classic.get("message") == "Branch not protected":
            classic = {"required_status_checks": {"contexts": [], "checks": []}}
        elif classic_code != 200:
            return None, "classic protection unreadable"
        if rules_code != 200 or not isinstance(rules, list) or not isinstance(classic, dict):
            return None, "ruleset protection unreadable"
        if "required_status_checks" not in classic:
            raise ValueError("classic check population absent")
        required = classic["required_status_checks"]
        if required is not None and (not isinstance(required, dict) or not {"contexts", "checks"} & set(required)):
            raise ValueError("classic check population unexaminable")
        if required is None:
            required = {"contexts": [], "checks": []}
        if not isinstance(required, dict):
            raise ValueError("malformed classic checks")
        contexts, checks = required.get("contexts", []), required.get("checks", [])
        if not isinstance(contexts, list) or not isinstance(checks, list):
            raise ValueError("malformed classic checks")
        checks = list(checks)
        for rule in rules:
            if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
                raise ValueError("malformed ruleset")
            if rule["type"] != "required_status_checks":
                continue
            values = rule["parameters"]["required_status_checks"]
            if not isinstance(values, list):
                raise ValueError("malformed ruleset checks")
            for value in values:
                if not isinstance(value, dict) or not isinstance(value.get("context"), str):
                    raise ValueError("malformed ruleset context")
                checks.append({"context": value["context"], "app_id": value.get("integration_id")})
        return {"branch": "main", "protection": {"required_status_checks": {
            "contexts": contexts, "checks": checks}}}, "classic and rulesets examined"
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        return None, "GitHub protection evidence unreadable or malformed"


def _posture_fact(derive: Any, posture: Any) -> dict[str, Any]:
    from .checks import check_posture
    if derive.status != "known":
        return {"status": "unknown", "reason": "PR check population not derivable from inspected pipeline shapes"}
    result = check_posture(derive, posture)
    return {"status": result["status"],
            "reason": (result.get("reason", "required check sets differ") if result["status"] != "ok" else
                       "matches derived PR contexts"),
            "missing": result.get("missing", []), "extra": result.get("extra", []),
            "examined_files": derive.examined_files, "required_contexts": len(derive.checks)}


def collect(project: str | Path, ctx: DoctorContext | None = None) -> dict[str, Any]:
    from .checks import derive_required_checks, read_pipeline_files, read_pipeline_inventory
    try:
        root = Path(project).resolve()
    except (OSError, RuntimeError, ValueError):
        return report([row(name, "unknown", "target repository path unavailable") for name in IDS], [])
    ctx = ctx or DoctorContext()
    try:
        names = list(read_provider_record(root).providers)
    except Exception:
        # A diagnostic cannot turn an unreadable/unsupported record into a
        # provider choice, or expose parser exception text as user output.
        names = []
    if not names:
        return report([row(name, "unknown", "provider record missing or invalid; " + REMEDY) for name in IDS], [])
    try:
        inventory = read_pipeline_inventory(root)
        files = read_pipeline_files(root)
        file_row = pipeline_row(names, inventory)
    except (OSError, UnicodeError, ValueError):
        files = None
        file_row = pipeline_row(names, None)
    try:
        derived = derive_required_checks(names, files) if files is not None else None
    except Exception:
        # Provider-owned hooks fail independently of file/host observations.
        derived = None
    declared = live = {"status": "unknown", "reason": "pipeline PR context population unavailable"}
    if derived is not None:
        try:
            posture = json.loads((root / ".claude/branch-protection.json").read_text())
        except (OSError, ValueError, UnicodeError):
            posture = None
        declared = _posture_fact(derived, posture)
        live_data, why = live_posture(root, ctx)
        live = _posture_fact(derived, live_data) if live_data is not None else {"status": "unknown", "reason": why}
    try:
        host_record = ctx.host_reader(root)
    except Exception:
        host_record = None
    rows = [file_row, required_row(declared, live), host_row(names, host_record),
            row(IDS[3], "unknown", "lane plan unavailable (#1610)")]
    return report(rows, names)


def render(value: dict[str, Any]) -> str:
    lines = []
    for prefix, item in zip(PREFIXES, value["rows"], strict=True):
        evidence = item["evidence"]
        details = []
        if item["id"] == "pipeline-files" and evidence:
            details.append("recorded=" + ",".join(evidence["recorded"]))
            details.append("missing=" + (",".join(evidence["missing"]) or "none"))
            details.append("unrecorded=" + (",".join(evidence["unrecorded"]) or "none"))
            details.append(str(sum(len(paths) for paths in evidence["files"].values())) + " registered pipeline files")
        elif item["id"] == "required-checks" and evidence:
            details.append("target main PR contexts")
            for name, source in evidence["sources"].items():
                if not isinstance(source, dict):
                    details.append(name + " unknown")
                    continue
                text = name + " " + source.get("status", "unknown")
                if source.get("missing"):
                    text += ": missing " + ",".join(source["missing"])
                if source.get("extra"):
                    text += ": extra " + ",".join(source["extra"])
                if source.get("status") == "unknown":
                    text += ": " + source.get("reason", "evidence unavailable")
                details.append(text)
        elif item["id"] == "host-capability" and evidence:
            details.append("checked_at=" + str(evidence["checked_at"]))
            details.extend(name + "=" + status for name, status in evidence["providers"].items())
            details.append("not current connectivity")
        suffix = "; " + "; ".join(details) if details else ""
        lines.append(f"{prefix}: {item['status']} ({item['reason']}{suffix})")
    return "\n".join(lines)
