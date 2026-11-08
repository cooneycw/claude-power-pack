"""Host CI capability probes and the side-effect-free project consumer (#1609).

A successful probe establishes a host capability, never a project's provider
selection. Only sanitized verdicts cross the persistence boundary; credentials,
API payloads, stderr and exception text never do.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import providers

#: NEGATIVE-CONTROL: controls/cpp-host-ci
REASONS = frozenset({
    "authenticated", "tool-absent", "auth-missing", "repo-scope-missing",
    "scope-not-introspectable", "credentials-missing", "credential-resolution-failed",
    "credential-source-mismatch",
    "probe-failed", "probe-malformed", "hook-unavailable", "container-view",
    "host-root-unavailable", "record-unavailable", "record-invalid", "provider-unrecorded",
})
STATUSES = frozenset({"ready", "missing", "unknown"})


def verdict(status: str, reason: str, versions: dict[str, str] | None = None) -> dict[str, Any]:
    return {"status": status, "reason": reason, "versions": versions or {}}


def in_container() -> bool:
    # A mounted host record cannot attest to the executable/credential namespace
    # that actually runs here. In particular /workspace is not a host locator.
    return (Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()
            or Path.cwd().is_relative_to("/workspace"))


@dataclass
class ProbeContext:
    run: Callable[..., Any] = subprocess.run
    which: Callable[[str], str | None] = shutil.which
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    container: bool = field(default_factory=in_container)

    def command(self, argv: list[str], *, env: dict[str, str] | None = None):
        return self.run(argv, capture_output=True, text=True, timeout=15,
                        env=self.env if env is None else env)


def _version(ctx: ProbeContext, tool: str) -> dict[str, str]:
    try:
        result = ctx.command([tool, "--version"])
        match = re.search(r"(?<![\w.])(\d+\.\d+(?:\.\d+)?)(?![\w.])", result.stdout)
        return {tool: match[1]} if result.returncode == 0 and match else {}
    except (OSError, subprocess.SubprocessError):
        return {}


def check_github(ctx: ProbeContext) -> dict[str, Any]:
    """Introspect real github.com authentication; public origin is no proof."""
    if not ctx.which("gh"):
        return verdict("missing", "tool-absent")
    versions = _version(ctx, "gh")
    try:
        auth = ctx.command(["gh", "auth", "status", "--hostname", "github.com"])
        if auth.returncode:
            return verdict("missing" if auth.returncode == 1 else "unknown",
                           "auth-missing" if auth.returncode == 1 else "probe-failed", versions)
        response = ctx.command(["gh", "api", "--include", "--hostname", "github.com", "user"])
        if response.returncode:
            return verdict("unknown", "probe-failed", versions)
        raw = response.stdout.replace("\r\n", "\n")
        header, body = raw.split("\n\n", 1)
        status = header.splitlines()[0].split()
        user = json.loads(body)
        if (len(status) < 2 or status[1] != "200" or not isinstance(user, dict)
                or not isinstance(user.get("login"), str) or not user["login"]):
            return verdict("unknown", "probe-malformed", versions)
        scopes = [line.split(":", 1)[1].strip() for line in header.splitlines()[1:]
                  if line.partition(":")[0].lower() == "x-oauth-scopes"]
        if not scopes:
            return verdict("unknown", "scope-not-introspectable", versions)
        if len(scopes) != 1:
            return verdict("unknown", "probe-malformed", versions)
        if "repo" in {value.strip() for value in scopes[0].split(",")}:
            return verdict("ready", "authenticated", versions)
        return verdict("missing", "repo-scope-missing", versions)
    except (OSError, subprocess.SubprocessError):
        return verdict("unknown", "probe-failed", versions)
    except (ValueError, TypeError, AttributeError, IndexError):
        return verdict("unknown", "probe-malformed", versions)


def check_woodpecker(ctx: ProbeContext) -> dict[str, Any]:
    if not ctx.which("woodpecker-cli"):
        return verdict("missing", "tool-absent")
    versions = _version(ctx, "woodpecker-cli")
    token = ctx.env.get("WOODPECKER_API_TOKEN") or ctx.env.get("WOODPECKER_TOKEN", "")
    server = ctx.env.get("WOODPECKER_SERVER") or ctx.env.get("WOODPECKER_HOST", "")
    try:
        if (not token or not server) and ctx.which("aws"):
            secret = ctx.command([
                "aws", "secretsmanager", "get-secret-value", "--secret-id",
                ctx.env.get("CPP_WOODPECKER_SECRET", "essent-ai"), "--region",
                ctx.env.get("AWS_REGION", "us-east-1"), "--query", "SecretString", "--output", "text",
            ])
            if secret.returncode:
                return verdict("unknown", "credential-resolution-failed", versions)
            data = json.loads(secret.stdout)
            if not isinstance(data, dict):
                raise ValueError
            secret_token = data.get("WOODPECKER_API_TOKEN", "")
            secret_server = data.get("WOODPECKER_HOST") or data.get("WOODPECKER_URL", "")
            if not isinstance(secret_token, str) or not isinstance(secret_server, str):
                raise ValueError
            if not secret_token or not secret_server:
                return verdict("missing", "credentials-missing", versions)
            # An incomplete environment pair must not borrow a token or server
            # from an unrelated secret. Verify its supplied half before filling.
            if ((token and token != secret_token)
                    or (server and server.rstrip("/") != secret_server.rstrip("/"))):
                return verdict("unknown", "credential-source-mismatch", versions)
            token, server = secret_token, secret_server
        if not isinstance(token, str) or not isinstance(server, str):
            raise ValueError
        if not token or not server:
            return verdict("missing", "credentials-missing", versions)
        # The upstream CLI's common/flags.go supports these environment names.
        # `info` calls the authenticated /user endpoint; no token appears in argv.
        env = {**ctx.env, "WOODPECKER_TOKEN": token, "WOODPECKER_SERVER": server,
               "WOODPECKER_DISABLE_UPDATE_CHECK": "true"}
        response = ctx.command(["woodpecker-cli", "info", "--format", "{{ .Login }}"], env=env)
        if response.returncode == 0 and response.stdout.strip():
            return verdict("ready", "authenticated", versions)
        return verdict("unknown", "probe-failed" if response.returncode else "probe-malformed", versions)
    except (OSError, subprocess.SubprocessError):
        return verdict("unknown", "probe-failed", versions)
    except (ValueError, TypeError):
        return verdict("unknown", "credential-resolution-failed", versions)


def _sanitize(value: Any, tools: tuple[str, ...]) -> dict[str, Any]:
    if (not isinstance(value, dict) or not isinstance(value.get("status"), str)
            or value["status"] not in STATUSES or not isinstance(value.get("reason"), str)
            or value["reason"] not in REASONS):
        return verdict("unknown", "probe-malformed")
    versions = value.get("versions", {})
    safe = {tool: version for tool, version in versions.items()
            if tool in tools and isinstance(version, str)
            and re.fullmatch(r"\d+(?:\.\d+){1,3}", version)} if isinstance(versions, dict) else {}
    # A reason cannot elevate a verdict by accident while loading malformed data.
    if (value["status"] == "ready") != (value["reason"] == "authenticated"):
        return verdict("unknown", "probe-malformed", safe)
    return verdict(value["status"], value["reason"], safe)


def _unknown(reason: str) -> dict[str, Any]:
    return {"schema": 1, "checked_at": None,
            "providers": {name: verdict("unknown", reason) for name in providers.PROVIDERS}}


def probe_host(ctx: ProbeContext | None = None) -> dict[str, Any]:
    ctx = ctx or ProbeContext()
    if ctx.container:
        return _unknown("container-view")
    record = _unknown("hook-unavailable")
    record["checked_at"] = datetime.now(timezone.utc).isoformat()
    for name, provider in providers.PROVIDERS.items():
        hook = providers.HOST_CHECKS.get(provider.host_check)
        if hook is None:
            continue
        try:
            module, function = hook.probe.split(":", 1)
            callback = getattr(importlib.import_module(module), function)
            result = callback(ctx)
            record["providers"][name] = _sanitize(result, hook.tools)
        except Exception:
            # Third-party hooks are independent; their failures and exception
            # strings must not leak credentials or stop another provider probe.
            record["providers"][name] = verdict("unknown", "probe-failed")
    return record


def main_checkout(repo: str | Path) -> Path | None:
    """Locate the main checkout even when cwd is a relocated linked worktree."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        common = subprocess.run(["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, timeout=10, env=env)
        if common.returncode:
            return None
        current = subprocess.run(["git", "-C", str(repo), "rev-parse", "--path-format=absolute",
                                  "--git-dir", "--show-toplevel"],
                                 capture_output=True, text=True, timeout=10, env=env)
        parts = current.stdout.splitlines()
        if current.returncode or len(parts) != 2:
            return None
        if Path(parts[0]).resolve() == Path(common.stdout.strip()).resolve():
            # Main checkout with a separate git dir: worktree list reports the
            # metadata directory, so use this checkout's own top-level instead.
            return Path(parts[1]).resolve()
        result = subprocess.run(["git", "--git-dir", common.stdout.strip(), "worktree", "list", "--porcelain", "-z"],
                                capture_output=True, text=True, timeout=10, env=env)
        entry = result.stdout.split("\0\0", 1)[0].split("\0")
        if result.returncode or not entry or not entry[0].startswith("worktree ") or "bare" in entry:
            return None
        path = Path(entry[0][len("worktree "):]).resolve()
        return path if path.is_dir() and (path / ".git").exists() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def read_host_record(repo: str | Path) -> dict[str, Any]:
    """Stable consumer API: normalized per-provider verdicts, no probes/writes.

    Root is main-checkout.parent, never an ancestor walk from cwd. A container
    receives unknown even if a mounted host record says ready.
    """
    if in_container():
        return _unknown("container-view")
    main = main_checkout(repo)
    if main is None:
        return _unknown("host-root-unavailable")
    try:
        data = json.loads((main.parent / ".claude/cpp-host.json").read_text())
    except OSError:
        return _unknown("record-unavailable")
    except (ValueError, UnicodeError):
        return _unknown("record-invalid")
    if (not isinstance(data, dict) or data.get("schema") != 1
            or not isinstance(data.get("providers"), dict)):
        return _unknown("record-invalid")
    record = _unknown("provider-unrecorded")
    try:
        checked = datetime.fromisoformat(data["checked_at"])
        if checked.tzinfo is None:
            raise ValueError
        record["checked_at"] = checked.astimezone(timezone.utc).isoformat()
    except (KeyError, ValueError, TypeError, OverflowError):
        return _unknown("record-invalid")
    for name, provider in providers.PROVIDERS.items():
        if name in data["providers"]:
            hook = providers.HOST_CHECKS.get(provider.host_check)
            record["providers"][name] = _sanitize(data["providers"][name], hook.tools if hook else ())
    return record


def _invoked_checkout(repo: str | Path) -> Path | None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, timeout=10, env=env)
        return Path(result.stdout.strip()).resolve() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def write_host_record(record: dict[str, Any], projects_root: str | Path,
                      repo: str | Path, ctx: ProbeContext | None = None) -> str:
    """Persist through the shared defer-aware seam; return its actual outcome."""
    ctx = ctx or ProbeContext()
    if ctx.container:
        return "unavailable"
    main = main_checkout(repo)
    root = Path(projects_root).expanduser().resolve()
    invoked = _invoked_checkout(repo)
    target = root / ".claude/cpp-host.json"
    if (main is None or invoked is None or root.is_relative_to(invoked) or root.is_relative_to(main)
            or target.resolve().is_relative_to(invoked) or target.resolve().is_relative_to(main)):
        return "failed"
    # Re-sanitize the complete payload even if a caller bypassed probe_host.
    safe = _unknown("provider-unrecorded")
    safe["checked_at"] = datetime.now(timezone.utc).isoformat()
    for name, provider in providers.PROVIDERS.items():
        hook = providers.HOST_CHECKS.get(provider.host_check)
        value = record.get("providers", {}).get(name)
        safe["providers"][name] = _sanitize(value, hook.tools if hook else ())
    helper = Path(__file__).resolve().parents[2] / "scripts/cpp-host-write.sh"
    try:
        result = ctx.run(["bash", str(helper), "file-write-atomic", str(target)],
                         input=json.dumps(safe, indent=2) + "\n", capture_output=True,
                         text=True, timeout=15, env=ctx.env)
        return {0: "written", 3: "deferred", 1: "failed"}.get(result.returncode, "unknown")
    except subprocess.TimeoutExpired:
        # A timeout can race the atomic commit. Even with the direct writer
        # killed, absence of its receipt cannot certify preservation.
        return "unknown"
    except OSError:
        return "failed"
    except subprocess.SubprocessError:
        return "unknown"
