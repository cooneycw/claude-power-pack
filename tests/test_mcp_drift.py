"""Regression tests for Docker MCP drift/orphan detection + teardown (issue #405).

The core hazard: when a server is removed from docker-compose.yml, a machine that
ran it keeps the old container, mcp-<name>:* images, and a live claude/codex mcp
registration. Detection must fire for exactly those - and NEVER for a server that
is still shipped, nor for a user's own custom (non-CPP) MCP registration. These
tests pin the curated-list-only classifier and the teardown guardrails.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mcp-drift.py"

_spec = importlib.util.spec_from_file_location("mcp_drift", SCRIPT)
assert _spec and _spec.loader
md = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(md)


DEPRECATION = """\
    version: 1
    deprecated:
      - name: mcp-nano-banana
        reason: retired diagram server
        replacement: pptx skill
        port: 8084
        image_prefix: mcp-nano-banana
        containers:
          - mcp-nano-banana
        claude_registrations:
          - nano-banana
          - mcp-nano-banana
        codex_registrations:
          - nano-banana
      - name: mcp-woodpecker-ci
        reason: unused
        port: 8085
        containers:
          - mcp-woodpecker-ci
        claude_registrations:
          - woodpecker-ci
"""


def _depfile(tmp_path: Path, body: str = DEPRECATION) -> Path:
    f = tmp_path / "deprecated-mcps.yaml"
    f.write_text(textwrap.dedent(body), encoding="utf-8")
    return f


def _dep(tmp_path: Path) -> list[dict]:
    return md.load_deprecated_mcps(_depfile(tmp_path))


def _status(findings: list[dict], server: str) -> str:
    return next(f["status"] for f in findings if f["server"] == server)


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def test_orphan_when_removed_from_compose_but_present(tmp_path: Path) -> None:
    """nano-banana gone from compose but still present -> ORPHANED;
    woodpecker still a compose service -> OK (never flagged)."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci", "mcp-second-opinion"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        images={"mcp-nano-banana": [{"tag": "abc", "id": "1", "size": "1GB", "created": "2026-06-30"}]},
        claude_regs={"nano-banana"},
    )
    findings = md.classify(_dep(tmp_path), host)
    assert _status(findings, "mcp-nano-banana") == md.ORPHANED
    assert _status(findings, "mcp-woodpecker-ci") == md.OK
    assert [f["server"] for f in md.removable(findings)] == ["mcp-nano-banana"]


def test_absent_when_nothing_present(tmp_path: Path) -> None:
    host = md.HostState(current_services={"mcp-second-opinion"}, services_known=True)
    findings = md.classify(_dep(tmp_path), host)
    assert _status(findings, "mcp-nano-banana") == md.ABSENT
    assert md.removable(findings) == []


def test_unknown_when_services_undeterminable(tmp_path: Path) -> None:
    """If the current service set can't be read (no docker / compose parse fail),
    nothing is torn down - present servers are UNKNOWN, never ORPHANED."""
    host = md.HostState(
        services_known=False,
        containers={"mcp-nano-banana": "running"},
        claude_regs={"nano-banana"},
    )
    findings = md.classify(_dep(tmp_path), host)
    assert _status(findings, "mcp-nano-banana") == md.UNKNOWN
    assert md.removable(findings) == []


def test_container_prefix_is_matched(tmp_path: Path) -> None:
    """A CPP_CONTAINER_PREFIX'd container (e.g. `ci-mcp-nano-banana`) still matches."""
    host = md.HostState(
        current_services={"mcp-second-opinion"},
        services_known=True,
        containers={"ci-mcp-nano-banana": "exited"},
    )
    findings = md.classify(_dep(tmp_path), host)
    nano = next(f for f in findings if f["server"] == "mcp-nano-banana")
    assert nano["status"] == md.ORPHANED
    assert nano["containers"] == [{"name": "ci-mcp-nano-banana", "state": "exited"}]


def test_user_custom_registration_never_flagged(tmp_path: Path) -> None:
    """A registration CPP never shipped is not in the list -> never a finding,
    never removable, and teardown of it is refused."""
    host = md.HostState(
        current_services={"mcp-second-opinion"},
        services_known=True,
        claude_regs={"my-personal-tool", "some-other-mcp"},
    )
    findings = md.classify(_dep(tmp_path), host)
    assert md.removable(findings) == []
    assert "my-personal-tool" not in {f["server"] for f in findings}
    rc = md.teardown(["my-personal-tool"], findings, execute=True)
    assert rc == 1  # refused: not on the list of record


def test_no_deprecation_file_finds_nothing(tmp_path: Path) -> None:
    host = md.HostState(current_services={"mcp-second-opinion"}, services_known=True,
                        claude_regs={"nano-banana"})
    findings = md.classify(md.load_deprecated_mcps(tmp_path / "missing.yaml"), host)
    assert findings == []


# --------------------------------------------------------------------------- #
# Teardown guardrails
# --------------------------------------------------------------------------- #
def _findings(tmp_path: Path, host: md.HostState) -> list[dict]:
    return md.classify(_dep(tmp_path), host)


def test_teardown_refuses_ok_server(tmp_path: Path) -> None:
    host = md.HostState(current_services={"mcp-woodpecker-ci"}, services_known=True,
                        claude_regs={"woodpecker-ci"})
    rc = md.teardown(["mcp-woodpecker-ci"], _findings(tmp_path, host), execute=True)
    assert rc == 1  # OK (still shipped) -> never torn down


def test_teardown_refuses_absent_and_unknown(tmp_path: Path) -> None:
    absent = md.HostState(current_services={"mcp-second-opinion"}, services_known=True)
    assert md.teardown(["mcp-nano-banana"], _findings(tmp_path, absent), execute=True) == 1
    unknown = md.HostState(services_known=False, containers={"mcp-nano-banana": "running"})
    assert md.teardown(["mcp-nano-banana"], _findings(tmp_path, unknown), execute=True) == 1


# --------------------------------------------------------------------------- #
# Image handling (keep-one restore point vs prune-all)
# --------------------------------------------------------------------------- #
def test_images_to_remove_keep_one_vs_prune_all() -> None:
    images = [
        {"tag": "new", "id": "1", "size": "", "created": "2026-06-30"},
        {"tag": "mid", "id": "2", "size": "", "created": "2026-06-20"},
        {"tag": "old", "id": "3", "size": "", "created": "2026-06-10"},
    ]
    # docker lists newest-first; keep-one keeps index 0 (newest) as restore point.
    assert [i["tag"] for i in md.images_to_remove(images, prune_all=False)] == ["mid", "old"]
    assert [i["tag"] for i in md.images_to_remove(images, prune_all=True)] == ["new", "mid", "old"]
    assert md.images_to_remove([], prune_all=False) == []


def test_plan_teardown_command_sequence(tmp_path: Path) -> None:
    host = md.HostState(
        current_services={"mcp-second-opinion"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        images={"mcp-nano-banana": [
            {"tag": "keep", "id": "1", "size": "1GB", "created": "2026-06-30"},
            {"tag": "drop", "id": "2", "size": "1GB", "created": "2026-06-10"},
        ]},
        claude_regs={"nano-banana"},
        codex_regs={"nano-banana"},
    )
    nano = next(f for f in _findings(tmp_path, host) if f["server"] == "mcp-nano-banana")
    plan = md.plan_teardown(nano, prune_all_images=False)
    assert "docker stop mcp-nano-banana" in plan
    assert "docker rm -f mcp-nano-banana" in plan
    assert "docker rmi mcp-nano-banana:drop" in plan
    assert any("kept restore point: mcp-nano-banana:keep" in c for c in plan)
    assert "docker rmi mcp-nano-banana:keep" not in plan  # newest kept
    assert any(c.startswith("claude mcp remove nano-banana -s ") for c in plan)
    assert "codex mcp remove nano-banana" in plan


# --------------------------------------------------------------------------- #
# Fallback YAML parser parity (structured fields; folded reason text dropped)
# --------------------------------------------------------------------------- #
def test_fallback_parser_matches_real_file() -> None:
    real = (ROOT / ".claude" / "deprecated-mcps.yaml").read_text(encoding="utf-8")
    import yaml

    expected = yaml.safe_load(real)
    got = md._fallback_parse(real)

    exp = {e["name"]: e for e in expected["deprecated"]}
    gotm = {e["name"]: e for e in got["deprecated"]}
    assert set(exp) == set(gotm)
    for name, ee in exp.items():
        ge = gotm[name]
        assert str(ge.get("port", "")) == str(ee.get("port", ""))
        assert (ge.get("image_prefix") or "") == (ee.get("image_prefix") or "")
        for field in ("containers", "claude_registrations", "codex_registrations"):
            assert sorted(ge.get(field) or []) == sorted(ee.get(field) or []), field


def test_load_defaults_container_and_image_prefix_to_name(tmp_path: Path) -> None:
    dep = md.load_deprecated_mcps(_depfile(tmp_path, """\
        version: 1
        deprecated:
          - name: mcp-foo
            reason: gone
    """))
    assert dep[0]["containers"] == ["mcp-foo"]
    assert dep[0]["image_prefix"] == "mcp-foo"


# --------------------------------------------------------------------------- #
# CLI contract + execution path (fake docker/claude/codex on PATH)
# --------------------------------------------------------------------------- #
def _write_exec(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fake_bin(tmp_path: Path, *, services: str, containers: str = "",
              images: str = "", claude_regs: str = "", codex_regs: str = "") -> tuple[Path, Path]:
    """Build fake docker/claude/codex presenting a fixed host scenario. Fixture
    data is written to files the fakes `cat` (so tabs/newlines survive intact).
    Mutating commands (stop/rm/rmi/remove) append their argv to a shared log."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    data = tmp_path / "fixtures"
    data.mkdir()
    (data / "services").write_text(services, encoding="utf-8")
    (data / "containers").write_text(containers, encoding="utf-8")
    (data / "images").write_text(images, encoding="utf-8")
    (data / "claude").write_text(claude_regs, encoding="utf-8")
    (data / "codex").write_text(codex_regs, encoding="utf-8")
    log = tmp_path / "calls.log"

    _write_exec(bin_dir / "docker", f"""
        #!/usr/bin/env bash
        if [[ "$1" == "compose" && "$*" == *"config --profiles"* ]]; then echo "core"; exit 0; fi
        if [[ "$1" == "compose" && "$*" == *"config --services"* ]]; then cat {str(data / "services")!r}; exit 0; fi
        if [[ "$1" == "ps" ]]; then cat {str(data / "containers")!r}; exit 0; fi
        if [[ "$1" == "images" ]]; then cat {str(data / "images")!r}; exit 0; fi
        echo "docker $*" >> {str(log)!r}
        exit 0
    """)
    _write_exec(bin_dir / "claude", f"""
        #!/usr/bin/env bash
        if [[ "$1" == "mcp" && "$2" == "list" ]]; then cat {str(data / "claude")!r}; exit 0; fi
        if [[ "$1" == "mcp" && "$2" == "get" ]]; then echo "Scope: local"; exit 0; fi
        echo "claude $*" >> {str(log)!r}
        exit 0
    """)
    _write_exec(bin_dir / "codex", f"""
        #!/usr/bin/env bash
        if [[ "$1" == "mcp" && "$2" == "list" ]]; then cat {str(data / "codex")!r}; exit 0; fi
        echo "codex $*" >> {str(log)!r}
        exit 0
    """)
    return bin_dir, log


def _run_cli(bin_dir: Path, depfile: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--deprecated-file", str(depfile),
         "--compose-file", str(ROOT / "docker-compose.yml"), *args],
        text=True, capture_output=True, check=False, env=env,
    )


def test_cli_check_and_list_orphans(tmp_path: Path) -> None:
    dep = _depfile(tmp_path)
    # nano-banana removed from compose, still present as a container + registration.
    bin_dir, _ = _fake_bin(
        tmp_path,
        services="mcp-second-opinion\nmcp-woodpecker-ci",
        containers="mcp-nano-banana\trunning\n",
        claude_regs="nano-banana\nmy-tool\n",
    )
    check = _run_cli(bin_dir, dep, "--check")
    assert check.returncode == 1
    assert "ORPHANED DOCKER MCP" in check.stdout
    assert "mcp-nano-banana" in check.stdout

    orphans = _run_cli(bin_dir, dep, "--list-orphans")
    assert orphans.returncode == 0
    assert orphans.stdout.strip() == "mcp-nano-banana"

    data = json.loads(_run_cli(bin_dir, dep, "--json").stdout)
    rec = next(f for f in data if f["server"] == "mcp-nano-banana")
    assert rec["status"] == md.ORPHANED


def test_cli_teardown_executes_and_refuses(tmp_path: Path) -> None:
    dep = _depfile(tmp_path)
    bin_dir, log = _fake_bin(
        tmp_path,
        services="mcp-second-opinion\nmcp-woodpecker-ci",
        containers="mcp-nano-banana\trunning\n",
        # docker images lists most-recently-created first: new, then old.
        images="mcp-nano-banana\tnew\t1\t1GB\t2026-06-30\nmcp-nano-banana\told\t2\t1GB\t2026-06-01\n",
        claude_regs="nano-banana\nmcp-nano-banana\n",
        codex_regs="nano-banana\n",
    )
    res = _run_cli(bin_dir, dep, "--teardown", "mcp-nano-banana")
    assert res.returncode == 0, res.stderr
    calls = log.read_text() if log.exists() else ""
    assert "docker stop mcp-nano-banana" in calls
    assert "docker rm -f mcp-nano-banana" in calls
    assert "docker rmi mcp-nano-banana:old" in calls          # older tag pruned
    assert "docker rmi mcp-nano-banana:new" not in calls      # newest kept as restore point
    assert "claude mcp remove nano-banana -s local" in calls
    assert "codex mcp remove nano-banana" in calls

    # woodpecker is still a compose service -> teardown must be refused (no calls).
    log.unlink(missing_ok=True)
    refused = _run_cli(bin_dir, dep, "--teardown", "mcp-woodpecker-ci")
    assert refused.returncode == 1
    assert "REFUSED" in refused.stderr
    assert not log.exists()


def test_script_is_executable() -> None:
    assert SCRIPT.stat().st_mode & stat.S_IXUSR
