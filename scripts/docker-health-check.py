"""Fail if Docker Compose services are not running and healthy."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


def _decode_compose_ps(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if not text:
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _compose_ps(profiles: list[str]) -> list[dict[str, Any]]:
    cmd = ["docker", "compose"]
    for profile in profiles:
        cmd.extend(["--profile", profile])
    cmd.extend(["ps", "--format", "json"])

    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "docker compose ps failed"
        raise RuntimeError(stderr)
    return _decode_compose_ps(result.stdout)


def _service_name(row: dict[str, Any]) -> str:
    return str(row.get("Service") or row.get("Name") or row.get("ID") or "unknown")


def _state(row: dict[str, Any]) -> str:
    return str(row.get("State") or row.get("Status") or "unknown").lower()


def _health(row: dict[str, Any]) -> str:
    return str(row.get("Health") or row.get("HealthStatus") or "").lower()


def _is_healthy(row: dict[str, Any]) -> bool:
    state = _state(row)
    health = _health(row)

    if "running" not in state and "up" not in state:
        return False
    if health in {"unhealthy", "starting"}:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profiles",
        default="core",
        help="Space-separated Docker Compose profiles to inspect",
    )
    args = parser.parse_args()

    profiles = [profile for profile in args.profiles.split() if profile]
    try:
        rows = _compose_ps(profiles)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not rows:
        print("ERROR: no Docker Compose services found for requested profiles", file=sys.stderr)
        return 1

    print("")
    print("Docker health summary:")
    failed: list[str] = []
    for row in rows:
        service = _service_name(row)
        state = _state(row) or "unknown"
        health = _health(row) or "no healthcheck"
        ok = _is_healthy(row)
        marker = "OK" if ok else "FAIL"
        print(f"  {marker} {service}: state={state}, health={health}")
        if not ok:
            failed.append(service)

    if failed:
        print("")
        print("ERROR: unhealthy Docker services: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
