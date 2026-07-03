#!/usr/bin/env python3
"""playwright-desk.py - Lease-desk ledger for named concurrent browser sessions.

Part of Claude Power Pack (CPP). This is the deterministic core behind the
``/browser:session`` skill (issue #421). It implements the "lease-desk" model
that recovers named concurrent sessions - the one feature upstream
``@playwright/mcp`` lacks (microsoft/playwright-mcp#1530) - WITHOUT carrying a
custom fork.

Model
-----
Upstream playwright-mcp gives one browser context per server connection, so a
fixed POOL of pre-registered upstream instances ("desks", e.g.
``playwright-desk-1``) is registered at Claude Code startup (see
``/cpp:init`` -> browser pool). Any number of user-named SESSIONS come and go;
at any instant only ``len(desks)`` can be seated. Starting a session LEASES a
free desk; closing it RELEASES the desk but keeps the session's cookies /
localStorage filed away as a portable storage-state JSON. Resuming re-leases
whatever desk is free and restores the state into it. So N desks multiplex
unlimited named sessions, and a session survives desk / container restarts as a
state file.

This script owns ONLY the ledger and the state-file bookkeeping - the acquire /
release / idle-cleanup logic. Driving the browser (navigate, restore, save
storage state) is done by the model through each desk's ``browser_*`` MCP tools;
this script tells it which desk to use and where its state file lives.

Design A is the only viable wrapper design: mid-session MCP registration is not
possible in Claude Code (config is read at startup only), so desks must be
pre-registered. See ``docs/reviews/2026-07-03-playwright-spike-419.md``.

Usage
-----
    playwright-desk.py create <name> [--json]
    playwright-desk.py resume <name> [--json]
    playwright-desk.py save   <name> [--json]
    playwright-desk.py close  <name> [--discard] [--json]
    playwright-desk.py list   [--json]
    playwright-desk.py cleanup [--idle-seconds N] [--json]
    playwright-desk.py pool   [--json]

Common flags: ``--root DIR`` (project root; default CWD), ``--pool-config PATH``,
``--ledger PATH``, ``--state-dir PATH``. Environment overrides:
``CPP_PLAYWRIGHT_ROOT``, ``CPP_PLAYWRIGHT_POOL_CONFIG``,
``CPP_PLAYWRIGHT_LEDGER``, ``CPP_PLAYWRIGHT_STATE_DIR``.

Exit codes
----------
    0  success
    1  configuration / unexpected error
    2  usage error (unknown session, name collision, wrong state)
    3  no free desk (pool exhausted)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Built-in default pool used when no .claude/playwright-pool.json exists yet, so
# the skill works immediately and tests need no fixture. /cpp:init seeds a real
# config from templates/playwright-pool.example.json.
DEFAULT_DESKS = ["playwright-desk-1", "playwright-desk-2", "playwright-desk-3"]
DEFAULT_IDLE_TIMEOUT = 1800  # seconds (30 min); replaces the old SESSION_TIMEOUT
DEFAULT_STATE_DIR = ".claude/playwright-state"
LEDGER_VERSION = 1

# Session status values.
ACTIVE = "active"  # currently seated at a desk
DETACHED = "detached"  # no desk held; identity persists as a state file

# Exit codes.
EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_USAGE = 2
EXIT_NO_DESK = 3


class DeskError(Exception):
    """Raised for expected, user-facing failures. Carries an exit code + slug."""

    def __init__(self, code: int, error: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.error = error
        self.message = message


def _now() -> int:
    return int(time.time())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise DeskError(EXIT_CONFIG, "bad_json", f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DeskError(EXIT_CONFIG, "bad_json", f"{path} is not a JSON object")
    return data


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    except OSError as exc:  # pragma: no cover - filesystem failure
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise DeskError(EXIT_CONFIG, "write_failed", f"Cannot write {path}: {exc}") from exc


class Ledger:
    """The lease ledger plus its pool config, bound to one project root."""

    def __init__(self, args: argparse.Namespace) -> None:
        env = os.environ.get
        root = args.root or env("CPP_PLAYWRIGHT_ROOT") or os.getcwd()
        self.root = Path(root).resolve()

        pool_cfg = args.pool_config or env("CPP_PLAYWRIGHT_POOL_CONFIG")
        self.pool_config_path = Path(pool_cfg) if pool_cfg else self.root / ".claude" / "playwright-pool.json"
        ledger = args.ledger or env("CPP_PLAYWRIGHT_LEDGER")
        self.ledger_path = Path(ledger) if ledger else self.root / ".claude" / "playwright-sessions.json"

        cfg = _read_json(self.pool_config_path)
        desks = cfg.get("desks")
        self.desks: list[str] = list(desks) if isinstance(desks, list) and desks else list(DEFAULT_DESKS)
        idle = cfg.get("idle_timeout_seconds")
        self.idle_timeout: int = int(idle) if isinstance(idle, int) and idle > 0 else DEFAULT_IDLE_TIMEOUT

        state_dir = args.state_dir or env("CPP_PLAYWRIGHT_STATE_DIR") or cfg.get("state_dir") or DEFAULT_STATE_DIR
        sd = Path(state_dir)
        self.state_dir = sd if sd.is_absolute() else self.root / sd

        data = _read_json(self.ledger_path)
        sessions = data.get("sessions")
        self.sessions: dict[str, dict[str, Any]] = sessions if isinstance(sessions, dict) else {}

    # -- persistence ----------------------------------------------------------

    def save(self) -> None:
        _write_json_atomic(
            self.ledger_path,
            {"version": LEDGER_VERSION, "updated_at": _now(), "sessions": self.sessions},
        )

    # -- pool state -----------------------------------------------------------

    def leased_desks(self) -> dict[str, str]:
        """Map desk -> session name for every currently-seated session."""
        out: dict[str, str] = {}
        for name, rec in self.sessions.items():
            if rec.get("status") == ACTIVE and rec.get("desk"):
                out[rec["desk"]] = name
        return out

    def free_desks(self) -> list[str]:
        taken = self.leased_desks()
        return [d for d in self.desks if d not in taken]

    def _lease_free_desk(self, name: str) -> str:
        free = self.free_desks()
        if not free:
            leased = self.leased_desks()
            held = ", ".join(f"{d} -> {leased[d]}" for d in self.desks if d in leased)
            raise DeskError(
                EXIT_NO_DESK,
                "no_free_desk",
                f"No free desk: all {len(self.desks)} leased ({held}). "
                f"Close or 'cleanup' a session, or enlarge the pool via /cpp:init.",
            )
        return free[0]

    # -- relative path helper for stable, portable ledger output --------------

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def state_file(self, name: str) -> Path:
        return self.state_dir / f"{name}.json"

    def _desk_result(self, name: str, action: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        rec = self.sessions[name]
        desk = rec.get("desk")
        sf = self.state_file(name)
        result: dict[str, Any] = {
            "ok": True,
            "action": action,
            "session": name,
            "desk": desk,
            "mcp_prefix": f"mcp__{desk}__" if desk else None,
            "state_file": self._rel(sf),
            "state_exists": sf.exists(),
            "status": rec.get("status"),
            "free_desks_remaining": len(self.free_desks()),
        }
        if extra:
            result.update(extra)
        return result

    # -- verbs ----------------------------------------------------------------

    def create(self, name: str) -> dict[str, Any]:
        if name in self.sessions:
            raise DeskError(
                EXIT_USAGE,
                "session_exists",
                f"Session '{name}' already exists - use 'resume {name}' to re-seat it, "
                f"or 'close {name} --discard' first.",
            )
        desk = self._lease_free_desk(name)
        now = _now()
        self.sessions[name] = {
            "desk": desk,
            "status": ACTIVE,
            "created_at": now,
            "last_used_at": now,
        }
        self.save()
        res = self._desk_result(name, "create")
        # A brand-new session has no papers to restore yet.
        res["restore"] = False
        res["message"] = (
            f"Leased {desk} for new session '{name}'. Drive it with {res['mcp_prefix']}browser_* tools. "
            f"Call 'save {name}' to persist login/cookies to {res['state_file']}."
        )
        return res

    def resume(self, name: str) -> dict[str, Any]:
        rec = self.sessions.get(name)
        if rec is None:
            raise DeskError(
                EXIT_USAGE,
                "unknown_session",
                f"No session '{name}'. Use 'create {name}' to start one, or 'list' to see sessions.",
            )
        now = _now()
        if rec.get("status") == ACTIVE and rec.get("desk") in self.desks:
            # Already seated - idempotent.
            rec["last_used_at"] = now
            self.save()
            res = self._desk_result(name, "resume")
            res["restore"] = res["state_exists"]
            res["message"] = f"Session '{name}' already seated at {rec['desk']} (idempotent)."
            return res
        desk = self._lease_free_desk(name)
        rec["desk"] = desk
        rec["status"] = ACTIVE
        rec["last_used_at"] = now
        self.save()
        res = self._desk_result(name, "resume")
        res["restore"] = res["state_exists"]
        if res["restore"]:
            res["message"] = (
                f"Leased {desk} for '{name}'. RESTORE first: read {res['state_file']} and call "
                f"{res['mcp_prefix']}browser_set_storage_state with its contents, then navigate."
            )
        else:
            res["message"] = f"Leased {desk} for '{name}'. No saved state file yet - start fresh, then 'save {name}'."
        return res

    def save_session(self, name: str) -> dict[str, Any]:
        rec = self.sessions.get(name)
        if rec is None:
            raise DeskError(EXIT_USAGE, "unknown_session", f"No session '{name}'.")
        if rec.get("status") != ACTIVE or not rec.get("desk"):
            raise DeskError(
                EXIT_USAGE,
                "not_seated",
                f"Session '{name}' is not seated at a desk - 'resume {name}' before saving.",
            )
        rec["last_used_at"] = _now()
        self.save()
        res = self._desk_result(name, "save")
        res["message"] = (
            f"Persist state now: call {res['mcp_prefix']}browser_storage_state and write the returned "
            f"JSON to {res['state_file']} (the wrapper does not touch the browser itself)."
        )
        return res

    def close(self, name: str, discard: bool = False) -> dict[str, Any]:
        rec = self.sessions.get(name)
        if rec is None:
            raise DeskError(EXIT_USAGE, "unknown_session", f"No session '{name}'.")
        freed = rec.get("desk")
        sf = self.state_file(name)
        if discard:
            del self.sessions[name]
            removed_state = False
            if sf.exists():
                try:
                    sf.unlink()
                    removed_state = True
                except OSError as exc:  # pragma: no cover
                    raise DeskError(EXIT_CONFIG, "unlink_failed", f"Cannot remove {sf}: {exc}") from exc
            self.save()
            return {
                "ok": True,
                "action": "close",
                "session": name,
                "freed_desk": freed,
                "discarded": True,
                "state_retained": False,
                "state_removed": removed_state,
                "free_desks_remaining": len(self.free_desks()),
                "message": f"Closed and DISCARDED '{name}' (desk {freed} freed, state file removed).",
            }
        rec["status"] = DETACHED
        rec["desk"] = None
        rec["last_used_at"] = _now()
        self.save()
        return {
            "ok": True,
            "action": "close",
            "session": name,
            "freed_desk": freed,
            "discarded": False,
            "state_retained": sf.exists(),
            "state_file": self._rel(sf),
            "free_desks_remaining": len(self.free_desks()),
            "message": (
                f"Detached '{name}' (desk {freed} freed). "
                f"State {'kept at ' + self._rel(sf) if sf.exists() else 'not yet saved'}; "
                f"'resume {name}' to re-seat."
            ),
        }

    def list_sessions(self) -> dict[str, Any]:
        now = _now()
        rows = []
        for name in sorted(self.sessions):
            rec = self.sessions[name]
            sf = self.state_file(name)
            last = rec.get("last_used_at", rec.get("created_at", now))
            rows.append(
                {
                    "session": name,
                    "desk": rec.get("desk"),
                    "status": rec.get("status"),
                    "state_exists": sf.exists(),
                    "state_file": self._rel(sf),
                    "idle_seconds": max(0, now - int(last)),
                }
            )
        return {
            "ok": True,
            "action": "list",
            "pool": {
                "desks": self.desks,
                "free": self.free_desks(),
                "leased": self.leased_desks(),
                "idle_timeout_seconds": self.idle_timeout,
            },
            "sessions": rows,
        }

    def cleanup(self, idle_seconds: int | None = None) -> dict[str, Any]:
        threshold = self.idle_timeout if idle_seconds is None else idle_seconds
        now = _now()
        released = []
        for name, rec in self.sessions.items():
            if rec.get("status") != ACTIVE:
                continue
            last = int(rec.get("last_used_at", rec.get("created_at", now)))
            if now - last >= threshold:
                released.append({"session": name, "desk": rec.get("desk"), "idle_seconds": now - last})
                rec["status"] = DETACHED
                rec["desk"] = None
        if released:
            self.save()
        return {
            "ok": True,
            "action": "cleanup",
            "idle_timeout_seconds": threshold,
            "released": released,
            "free_desks_remaining": len(self.free_desks()),
            "message": (
                f"Released {len(released)} idle session(s) (>= {threshold}s); state files kept."
                if released
                else f"Nothing idle beyond {threshold}s."
            ),
        }

    def pool(self) -> dict[str, Any]:
        return {
            "ok": True,
            "action": "pool",
            "desks": self.desks,
            "free": self.free_desks(),
            "leased": self.leased_desks(),
            "idle_timeout_seconds": self.idle_timeout,
            "state_dir": self._rel(self.state_dir),
            "pool_config": self._rel(self.pool_config_path),
            "pool_config_exists": self.pool_config_path.exists(),
            "ledger": self._rel(self.ledger_path),
        }


# -- human-readable rendering (default; --json emits the raw object) -----------


def _render_text(result: dict[str, Any]) -> str:
    action = result.get("action")
    if action == "list":
        pool = result["pool"]
        lines = [
            f"Pool: {len(pool['free'])}/{len(pool['desks'])} desks free (idle timeout {pool['idle_timeout_seconds']}s)",
        ]
        if not result["sessions"]:
            lines.append("  (no sessions)")
        for row in result["sessions"]:
            desk = row["desk"] or "-"
            state = "state" if row["state_exists"] else "no-state"
            lines.append(
                f"  {row['session']:<24} {row['status']:<9} desk={desk:<18} {state:<8} idle={row['idle_seconds']}s"
            )
        return "\n".join(lines)
    if action == "pool":
        return (
            f"Desks: {', '.join(result['desks'])}\n"
            f"Free: {', '.join(result['free']) or '(none)'}\n"
            f"Leased: {result['leased'] or '(none)'}\n"
            f"Idle timeout: {result['idle_timeout_seconds']}s\n"
            f"State dir: {result['state_dir']}\n"
            f"Pool config: {result['pool_config']} "
            f"({'present' if result['pool_config_exists'] else 'using built-in defaults'})"
        )
    if action == "cleanup":
        return result["message"]
    return result.get("message", json.dumps(result))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="playwright-desk.py",
        description="Lease-desk ledger for named concurrent playwright-mcp sessions (issue #421).",
    )
    parser.add_argument("--root", help="Project root (default: $CPP_PLAYWRIGHT_ROOT or CWD)")
    parser.add_argument("--pool-config", help="Path to playwright-pool.json")
    parser.add_argument("--ledger", help="Path to the lease ledger JSON")
    parser.add_argument("--state-dir", help="Directory for per-session storage-state files")
    parser.add_argument("--json", action="store_true", help="Emit the raw JSON result object")

    sub = parser.add_subparsers(dest="command", required=True)
    for verb, help_text in (
        ("create", "Lease a free desk for a new named session"),
        ("resume", "Re-seat an existing session at a free desk"),
        ("save", "Mark a session for state persistence and report its state file"),
        ("list", "List sessions and pool occupancy"),
        ("pool", "Show pool configuration and occupancy"),
    ):
        sp = sub.add_parser(verb, help=help_text)
        if verb in ("create", "resume", "save"):
            sp.add_argument("name", help="Session name")

    sp_close = sub.add_parser("close", help="Release a session's desk (keep state unless --discard)")
    sp_close.add_argument("name", help="Session name")
    sp_close.add_argument("--discard", action="store_true", help="Also delete the state file and forget the session")

    sp_cleanup = sub.add_parser("cleanup", help="Release desks of sessions idle beyond the timeout")
    sp_cleanup.add_argument("--idle-seconds", type=int, default=None, help="Override idle threshold (seconds)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        ledger = Ledger(args)
        if args.command == "create":
            result = ledger.create(args.name)
        elif args.command == "resume":
            result = ledger.resume(args.name)
        elif args.command == "save":
            result = ledger.save_session(args.name)
        elif args.command == "close":
            result = ledger.close(args.name, discard=args.discard)
        elif args.command == "list":
            result = ledger.list_sessions()
        elif args.command == "cleanup":
            result = ledger.cleanup(idle_seconds=args.idle_seconds)
        elif args.command == "pool":
            result = ledger.pool()
        else:  # pragma: no cover - argparse enforces the choices
            parser.error(f"unknown command {args.command}")
            return EXIT_USAGE
    except DeskError as exc:
        payload = {"ok": False, "error": exc.error, "message": exc.message}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"error: {exc.message}", file=sys.stderr)
        return exc.code

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(_render_text(result))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
