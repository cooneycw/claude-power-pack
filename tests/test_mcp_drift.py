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
from typing import Any

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


def test_absent_compose_file_is_known_empty(tmp_path: Path) -> None:
    """As of #469 CPP ships no docker-compose file. A MISSING compose file is a
    KNOWN-empty service set (known=True), NOT 'unknown' - so a deprecated server
    still present on the host is a genuine orphan. Otherwise post-removal teardown
    would silently never fire once the compose file is gone."""
    services, known = md.collect_current_services(tmp_path / "no-such-compose.yml")
    assert services == set()
    assert known is True


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


# --------------------------------------------------------------------------- #
# Live external container protection (issue #520): a RUNNING container that
# merely shares a deprecated name but belongs to an external compose project (the
# external second-opinion server reuses `mcp-second-opinion`/`aws-secrets-agent`)
# must never be classified orphaned nor torn down.
# --------------------------------------------------------------------------- #
def _nano(findings: list[dict]) -> dict:
    return next(f for f in findings if f["server"] == "mcp-nano-banana")


def test_running_external_container_protected_by_compose_project(tmp_path: Path) -> None:
    """A RUNNING container sharing a deprecated name but carrying a
    com.docker.compose.project label belongs to an external compose project (CPP
    ships none since #469). It is protected: not counted as present -> the entry is
    ABSENT (not orphaned), and teardown is refused."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        container_meta={"mcp-nano-banana": {"image": "mcp-nano-banana:latest",
                                             "project": "second-opinion"}},
    )
    findings = md.classify(_dep(tmp_path), host)
    nano = _nano(findings)
    assert nano["status"] == md.ABSENT
    assert nano["containers"] == []
    assert [c["name"] for c in nano["foreign_containers"]] == ["mcp-nano-banana"]
    assert md.removable(findings) == []
    assert md.teardown(["mcp-nano-banana"], findings, execute=True) == 1  # refused (ABSENT)


def test_running_external_container_protected_by_foreign_image(tmp_path: Path) -> None:
    """With no compose-project label, a RUNNING container on a non-CPP image
    (repo != image_prefix) is still foreign and protected."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        container_meta={"mcp-nano-banana": {"image": "ghcr.io/acme/nano:v2", "project": ""}},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.ABSENT
    assert [c["name"] for c in nano["foreign_containers"]] == ["mcp-nano-banana"]


def test_running_cpp_orphan_on_cpp_image_still_reaped(tmp_path: Path) -> None:
    """A RUNNING leftover on the CPP-built image (repo == image_prefix) with no
    compose-project label is a genuine CPP orphan - still reaped, not protected."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        container_meta={"mcp-nano-banana": {"image": "mcp-nano-banana:abc", "project": ""}},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.ORPHANED
    assert nano["containers"] == [{"name": "mcp-nano-banana", "state": "running"}]
    assert nano["foreign_containers"] == []


def test_exited_external_container_still_reaped(tmp_path: Path) -> None:
    """Protection is RUNNING-only (per the issue): an exited container is not live
    and is the ordinary stale-orphan case, so it is reaped even under an external
    compose-project label - a CPP leftover cannot be told apart from that label."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "exited"},
        container_meta={"mcp-nano-banana": {"image": "ghcr.io/acme/nano:v2",
                                             "project": "second-opinion"}},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.ORPHANED
    assert nano["containers"] == [{"name": "mcp-nano-banana", "state": "exited"}]
    assert nano["foreign_containers"] == []


def test_unknown_provenance_running_container_still_orphan(tmp_path: Path) -> None:
    """Back-compat: with no provenance (container_meta empty, e.g. old docker) a
    running container has no positive foreign evidence and is classified exactly as
    before - ORPHANED."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.ORPHANED
    assert nano["foreign_containers"] == []


def test_teardown_plan_excludes_live_external_but_prunes_stale_image(tmp_path: Path) -> None:
    """When a live external container AND a stale CPP image share the name, the
    entry is ORPHANED for the image, but the teardown plan must NOT stop/remove the
    live container - only prune the dangling image tag."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        container_meta={"mcp-nano-banana": {"image": "ghcr.io/acme/nano:v2",
                                             "project": "second-opinion"}},
        images={"mcp-nano-banana": [
            {"tag": "keep", "id": "1", "size": "1GB", "created": "2026-06-30"},
            {"tag": "drop", "id": "2", "size": "1GB", "created": "2026-06-10"},
        ]},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.ORPHANED  # the stale image is a real orphan artifact
    assert [c["name"] for c in nano["foreign_containers"]] == ["mcp-nano-banana"]
    plan = md.plan_teardown(nano, prune_all_images=False)
    assert not any(c.startswith(("docker stop", "docker rm -f")) for c in plan)  # live one untouched
    assert "docker rmi mcp-nano-banana:drop" in plan  # stale tag still pruned


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
def _findings(tmp_path: Path, host) -> list[dict]:
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
              images: str = "", claude_regs: str = "", codex_regs: str = "",
              docker_error: str = "", sudo_reads: bool = False) -> tuple[Path, Path]:
    """Build fake docker/claude/codex/sudo presenting a fixed host scenario. Fixture
    data is written to files the fakes `cat` (so tabs/newlines survive intact).
    Mutating commands (stop/rm/rmi/remove) append their argv to a shared log.

    `docker_error` (issue #673) makes the daemon-backed reads (`ps`, `images`) fail
    with that text on stderr while `compose config` keeps working - which is exactly
    how a refused docker socket behaves, since parsing a compose file needs no
    daemon. That isolation matters: it proves an UNKNOWN verdict came from the
    unreadable socket and not from an unreadable service set.

    A fake `sudo` is ALWAYS installed so a test can never reach the host's real one:
    it serves the fixture data when `sudo_reads` is set, and otherwise fails the way
    a box without passwordless sudo does."""
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

    daemon_reads = f"""
        if [[ "$1" == "ps" ]]; then cat {str(data / "containers")!r}; exit 0; fi
        if [[ "$1" == "images" ]]; then cat {str(data / "images")!r}; exit 0; fi
    """
    if docker_error:
        daemon_reads = f"""
        if [[ "$1" == "ps" || "$1" == "images" ]]; then echo {docker_error!r} >&2; exit 1; fi
    """

    _write_exec(bin_dir / "docker", f"""
        #!/usr/bin/env bash
        if [[ "$1" == "compose" && "$*" == *"config --profiles"* ]]; then echo "core"; exit 0; fi
        if [[ "$1" == "compose" && "$*" == *"config --services"* ]]; then cat {str(data / "services")!r}; exit 0; fi
        {daemon_reads}
        echo "docker $*" >> {str(log)!r}
        exit 0
    """)
    if sudo_reads:
        _write_exec(bin_dir / "sudo", f"""
            #!/usr/bin/env bash
            [[ "$1" == "-n" ]] && shift
            [[ "$1" == "docker" ]] || exit 1
            shift
            if [[ "$1" == "ps" ]]; then cat {str(data / "containers")!r}; exit 0; fi
            if [[ "$1" == "images" ]]; then cat {str(data / "images")!r}; exit 0; fi
            echo "sudo -n docker $*" >> {str(log)!r}
            exit 0
        """)
    else:
        _write_exec(bin_dir / "sudo", """
            #!/usr/bin/env bash
            echo "sudo: a password is required" >&2
            exit 1
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


def _run_cli(bin_dir: Path, depfile: Path, *args: str,
             port_probe: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    # The NAME COLLISION port probe (issue #673) connects to real localhost ports.
    # Off by default here so an unrelated service on the fixture's 8084/8085 can
    # never flip a classification mid-suite; collision tests opt in with a port
    # they bound themselves.
    extra = () if port_probe else ("--no-port-probe",)
    # CPP no longer ships a repo docker-compose.yml (#469). These CLI tests still
    # need the "compose file present" path, so the fake docker's `config --services`
    # is consulted and a still-listed server stays OK. Point --compose-file at a stub
    # beside the deprecation file; the fake docker ignores its contents.
    compose = depfile.parent / "docker-compose.yml"
    if not compose.exists():
        compose.write_text("services: {}\n", encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--deprecated-file", str(depfile),
         "--compose-file", str(compose), *extra, *args],
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


def test_cli_running_external_container_protected(tmp_path: Path) -> None:
    """End-to-end (issue #520): a RUNNING container under an external compose
    project (a 4-field `docker ps` line: name/state/image/project) sharing a
    deprecated name is protected - not listed as an orphan, and surfaced under the
    report's Protected section."""
    dep = _depfile(tmp_path)
    bin_dir, _ = _fake_bin(
        tmp_path,
        services="mcp-second-opinion\nmcp-woodpecker-ci",
        containers="mcp-nano-banana\trunning\tghcr.io/acme/nano\text-second-opinion\n",
    )
    check = _run_cli(bin_dir, dep, "--check")
    assert check.returncode == 0, check.stdout   # nothing to reap
    assert "Protected" in check.stdout
    assert "mcp-nano-banana" in check.stdout

    orphans = _run_cli(bin_dir, dep, "--list-orphans")
    assert orphans.returncode == 0
    assert orphans.stdout.strip() == ""


def test_script_is_executable() -> None:
    assert SCRIPT.stat().st_mode & stat.S_IXUSR


# --------------------------------------------------------------------------- #
# Image-tag provenance (issue #634, the image half of #520): a tag run by a
# foreign-live container is protected; a tag referenced by nothing, or only by
# a stale CPP container, stays a legitimate orphan.
# --------------------------------------------------------------------------- #
def test_tag_run_by_foreign_live_container_is_protected(tmp_path: Path) -> None:
    """The exact #634 repro: external stack up, its :dev image present ->
    entry reads ABSENT (no eternal nag), tag excluded from teardown."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        container_meta={"mcp-nano-banana": {"image": "mcp-nano-banana:dev",
                                            "project": "second-opinion"}},
        images={"mcp-nano-banana": [
            {"tag": "dev", "id": "1", "size": "1GB", "created": "2026-08-01"},
        ]},
    )
    findings = md.classify(_dep(tmp_path), host)
    nano = _nano(findings)
    assert nano["status"] == md.ABSENT
    assert nano["images"] == []
    assert [im["tag"] for im in nano["protected_images"]] == ["dev"]
    assert md.removable(findings) == []


def test_unreferenced_tag_stays_orphaned_beside_protected_one(tmp_path: Path) -> None:
    """Mixed case: only the unreferenced tag is presence- and teardown-eligible."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        container_meta={"mcp-nano-banana": {"image": "mcp-nano-banana:dev",
                                            "project": "second-opinion"}},
        images={"mcp-nano-banana": [
            {"tag": "dev", "id": "1", "size": "1GB", "created": "2026-08-01"},
            {"tag": "old", "id": "2", "size": "1GB", "created": "2026-05-01"},
        ]},
    )
    findings = md.classify(_dep(tmp_path), host)
    nano = _nano(findings)
    assert nano["status"] == md.ORPHANED
    assert [im["tag"] for im in nano["images"]] == ["old"]
    assert [im["tag"] for im in nano["protected_images"]] == ["dev"]
    report = md.render_table(findings, verbose=False)
    assert "1 protected: run by external stack" in report


def test_stopped_foreign_container_protects_nothing(tmp_path: Path) -> None:
    """Liveness rides the #520 rule: an exited container is the ordinary
    stale-orphan case and its image stays teardown-eligible."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "exited"},
        container_meta={"mcp-nano-banana": {"image": "mcp-nano-banana:dev",
                                            "project": "second-opinion"}},
        images={"mcp-nano-banana": [
            {"tag": "dev", "id": "1", "size": "1GB", "created": "2026-08-01"},
        ]},
    )
    findings = md.classify(_dep(tmp_path), host)
    nano = _nano(findings)
    assert nano["status"] == md.ORPHANED
    assert [im["tag"] for im in nano["images"]] == ["dev"]
    assert nano["protected_images"] == []


def test_owned_cpp_container_tag_stays_orphaned(tmp_path: Path) -> None:
    """A running container with NO foreign provenance (no label, CPP image) is
    an owned orphan candidate - its tag is not protected."""
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        container_meta={"mcp-nano-banana": {"image": "mcp-nano-banana:dev",
                                            "project": ""}},
        images={"mcp-nano-banana": [
            {"tag": "dev", "id": "1", "size": "1GB", "created": "2026-08-01"},
        ]},
    )
    findings = md.classify(_dep(tmp_path), host)
    nano = _nano(findings)
    assert nano["status"] == md.ORPHANED
    assert [im["tag"] for im in nano["images"]] == ["dev"]
    assert nano["protected_images"] == []


def test_bare_repo_ref_protects_latest(tmp_path: Path) -> None:
    host = md.HostState(
        current_services={"mcp-woodpecker-ci"},
        services_known=True,
        containers={"mcp-nano-banana": "running"},
        container_meta={"mcp-nano-banana": {"image": "mcp-nano-banana",
                                            "project": "second-opinion"}},
        images={"mcp-nano-banana": [
            {"tag": "latest", "id": "1", "size": "1GB", "created": "2026-08-01"},
        ]},
    )
    findings = md.classify(_dep(tmp_path), host)
    nano = _nano(findings)
    assert nano["status"] == md.ABSENT
    assert [im["tag"] for im in nano["protected_images"]] == ["latest"]


def test_image_tag_parsing_survives_registry_ports() -> None:
    assert md._image_tag("mcp-nano-banana:dev") == "dev"
    assert md._image_tag("mcp-nano-banana") == ""
    assert md._image_tag("registry:5000/repo") == ""
    assert md._image_tag("registry:5000/repo:tag") == "tag"


# --------------------------------------------------------------------------- #
# Unreadable docker socket is not an empty host (issue #673)
#
# The reported failure: `docker ps` refused for permission emptied the container
# inventory, every curated server classified ABSENT, and the report printed
# "No orphaned Docker MCP servers detected." while `sudo docker ps` on the same
# host showed two of the listed containers running. "Clean" and "I could not
# look" were indistinguishable to the caller, and /cpp:update relayed the former.
# --------------------------------------------------------------------------- #
PERMISSION_DENIED = (
    "permission denied while trying to connect to the Docker daemon socket at "
    "unix:///var/run/docker.sock"
)


def _unreadable_host(**kw: Any) -> Any:
    # Return type is Any because `md` is loaded via importlib, so mypy cannot
    # resolve md.HostState as a type (it resolves fine as a call).
    return md.HostState(
        services_known=True,
        docker_state=md.DOCKER_UNREADABLE,
        docker_error=PERMISSION_DENIED,
        **kw,
    )


def test_unreadable_docker_classifies_every_server_unknown(tmp_path: Path) -> None:
    """The regression itself: a refused docker read must NOT read as an empty
    host. Every curated server is UNKNOWN (the contract the script already
    honored for an unreadable service set), so nothing is ever offered for
    teardown on evidence that was never collected."""
    findings = md.classify(_dep(tmp_path), _unreadable_host())
    assert {f["status"] for f in findings} == {md.UNKNOWN}
    assert md.removable(findings) == []
    assert all(f["docker_state"] == md.DOCKER_UNREADABLE for f in findings)
    assert all(PERMISSION_DENIED in f["docker_error"] for f in findings)


def test_unreadable_docker_outranks_a_readable_service_set(tmp_path: Path) -> None:
    """`services_known=True` must not rescue an unreadable socket. Before the fix
    this was the live shape: no compose file -> services known-empty, docker
    refused -> containers {} -> ABSENT for everything -> 'clean'."""
    host = _unreadable_host(current_services=set())
    assert host.services_known is True
    findings = md.classify(_dep(tmp_path), host)
    assert _status(findings, "mcp-nano-banana") == md.UNKNOWN


def test_unreadable_docker_report_never_says_clean(tmp_path: Path) -> None:
    findings = md.classify(_dep(tmp_path), _unreadable_host())
    report = md.render_table(findings, verbose=False, host=_unreadable_host())
    assert "No orphaned Docker MCP servers detected." not in report
    assert "DOCKER UNREADABLE" in report
    assert PERMISSION_DENIED in report
    assert "Cannot assess 2 curated server(s)" in report
    assert "INCOMPLETE" in report


def test_teardown_refused_for_every_server_when_docker_unreadable(tmp_path: Path) -> None:
    """The safety consequence of UNKNOWN: teardown's status guard refuses each
    name, so an unreadable host can never have anything torn down from it."""
    findings = md.classify(_dep(tmp_path), _unreadable_host())
    assert md.teardown(["mcp-nano-banana"], findings, execute=True) == 1


def test_docker_absent_is_a_known_empty_read_not_unknown(tmp_path: Path) -> None:
    """A MISSING docker binary is the other thing (deliberate deviation from the
    issue text, decided at the #673 gate): nothing can run under a runtime that is
    not installed, so the inventory is empty as a FACT. CPP has shipped no
    container runtime since #469, so treating every docker-less host as
    'could not look' would trade one wrong answer for permanent noise."""
    host = md.HostState(
        services_known=True,
        docker_state=md.DOCKER_ABSENT,
        docker_error="docker command not found",
    )
    assert host.docker_readable is True
    findings = md.classify(_dep(tmp_path), host)
    assert {f["status"] for f in findings} == {md.ABSENT}

    report = md.render_table(findings, verbose=False, host=host)
    assert "No orphaned Docker MCP servers detected." in report
    # Named, not hidden - the reader is told which question was answered by
    # absence rather than by inspection.
    assert "docker is not installed" in report
    assert "DOCKER UNREADABLE" not in report


def test_probe_docker_reports_absent_without_a_binary(monkeypatch) -> None:
    monkeypatch.setattr(md, "_has", lambda cmd: False)
    state, error, prefix, out = md.probe_docker()
    assert state == md.DOCKER_ABSENT
    assert prefix == ("docker",)
    assert out == ""
    assert "not found" in error


def test_permission_error_signatures() -> None:
    assert md._looks_like_permission_error(PERMISSION_DENIED)
    assert md._looks_like_permission_error("Got permission denied while trying to connect")
    # A dead daemon is not a permission problem - sudo cannot start one, so no
    # retry is attempted for it.
    assert not md._looks_like_permission_error(
        "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"
    )


def test_cli_unreadable_docker_exits_three_and_says_so(tmp_path: Path) -> None:
    """End-to-end: the exact reported scenario. Exit 3 is distinct from both 0
    (clean) and 1 (orphans found) so a caller can branch on 'could not assess'."""
    dep = _depfile(tmp_path)
    bin_dir, _ = _fake_bin(
        tmp_path,
        services="mcp-second-opinion\nmcp-woodpecker-ci",
        containers="mcp-nano-banana\trunning\n",
        docker_error=PERMISSION_DENIED,
    )
    check = _run_cli(bin_dir, dep, "--check")
    assert check.returncode == 3, check.stdout
    assert "DOCKER UNREADABLE" in check.stdout
    assert "No orphaned Docker MCP servers detected." not in check.stdout
    assert "UNKNOWN" in check.stdout

    data = json.loads(_run_cli(bin_dir, dep, "--json").stdout)
    assert {rec["status"] for rec in data} == {md.UNKNOWN}


def test_cli_list_orphans_keeps_stdout_clean_but_exits_three(tmp_path: Path) -> None:
    """--list-orphans is line-parsed by /cpp:status and drift-detect.sh, so the
    warning goes to stderr and the exit code carries the signal. Silence on
    stdout must never again be read as 'nothing found'."""
    dep = _depfile(tmp_path)
    bin_dir, _ = _fake_bin(
        tmp_path,
        services="mcp-second-opinion",
        containers="mcp-nano-banana\trunning\n",
        docker_error=PERMISSION_DENIED,
    )
    res = _run_cli(bin_dir, dep, "--list-orphans")
    assert res.returncode == 3
    assert res.stdout.strip() == ""
    assert "could not look" in res.stderr
    assert "UNKNOWN" in res.stderr


def test_cli_sudo_fallback_recovers_the_inventory(tmp_path: Path) -> None:
    """Fix 2: a permission-refused read is retried once via non-interactive
    `sudo -n`. When that works the host IS assessed - the two containers the
    reporter saw with `sudo docker ps` become visible."""
    dep = _depfile(tmp_path)
    bin_dir, _ = _fake_bin(
        tmp_path,
        services="mcp-second-opinion",
        containers="mcp-nano-banana\trunning\tmcp-nano-banana:dev\t\n",
        images="mcp-nano-banana\tdev\t1\t1GB\t2026-06-30\n",
        docker_error=PERMISSION_DENIED,
        sudo_reads=True,
    )
    check = _run_cli(bin_dir, dep, "--check")
    assert check.returncode == 1, check.stdout
    assert "ORPHANED DOCKER MCP" in check.stdout
    assert "sudo -n docker" in check.stdout


def test_cli_sudo_read_prefixes_the_teardown_plan(tmp_path: Path) -> None:
    """What --plan prints is what --teardown runs: if the inventory needed
    elevation, so does the teardown, and the elevation is visible BEFORE the
    user confirms rather than discovered as a wall of permission-denied warns."""
    dep = _depfile(tmp_path)
    bin_dir, _ = _fake_bin(
        tmp_path,
        services="mcp-second-opinion",
        containers="mcp-nano-banana\trunning\tmcp-nano-banana:dev\t\n",
        images="mcp-nano-banana\tdev\t1\t1GB\t2026-06-30\n",
        docker_error=PERMISSION_DENIED,
        sudo_reads=True,
    )
    plan = _run_cli(bin_dir, dep, "--plan", "mcp-nano-banana")
    assert plan.returncode == 0, plan.stderr
    assert "sudo -n docker stop mcp-nano-banana" in plan.stdout
    assert "sudo -n docker rm -f mcp-nano-banana" in plan.stdout
    assert "inventory read via: sudo -n docker" in plan.stdout


def test_cli_sudo_refused_still_reports_unreadable(tmp_path: Path) -> None:
    """`sudo -n` fails on a box without passwordless sudo (it never prompts, so a
    drift check can never block on a TTY). The verdict stays 'could not look'."""
    dep = _depfile(tmp_path)
    bin_dir, _ = _fake_bin(
        tmp_path,
        services="mcp-second-opinion",
        containers="mcp-nano-banana\trunning\n",
        docker_error=PERMISSION_DENIED,
        sudo_reads=False,
    )
    check = _run_cli(bin_dir, dep, "--check")
    assert check.returncode == 3
    assert "sudo -n retry also failed" in check.stdout


def test_cli_no_sudo_flag_skips_the_retry(tmp_path: Path) -> None:
    dep = _depfile(tmp_path)
    bin_dir, log = _fake_bin(
        tmp_path,
        services="mcp-second-opinion",
        containers="mcp-nano-banana\trunning\n",
        docker_error=PERMISSION_DENIED,
        sudo_reads=True,
    )
    check = _run_cli(bin_dir, dep, "--check", "--no-sudo")
    assert check.returncode == 3
    assert "sudo -n retry" not in check.stdout
    assert not log.exists()


def test_plan_teardown_prefix_defaults_to_plain_docker(tmp_path: Path) -> None:
    """Back-compat: without an elevated read the emitted commands are unchanged."""
    host = md.HostState(
        current_services=set(), services_known=True,
        containers={"mcp-nano-banana": "running"},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert md.plan_teardown(nano, prune_all_images=False)[0] == "docker stop mcp-nano-banana"


# --------------------------------------------------------------------------- #
# NAME COLLISION - a retired name that live evidence says is in use (issue #673)
#
# The #520/#634 provenance guards answer this from the container, which needs the
# container to be visible AND docker-managed. A retired name can also be live as a
# plain host process or a proxy - there, an answering port or a live registration
# aimed at it is the only signal, and the curated list would otherwise call the
# user's own deployment an orphan.
# --------------------------------------------------------------------------- #
def test_answering_port_downgrades_orphan_to_name_collision(tmp_path: Path) -> None:
    host = md.HostState(
        current_services=set(),
        services_known=True,
        containers={"mcp-nano-banana": "exited"},
        listening_ports={8084},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.COLLISION
    assert nano["collision_evidence"] == ["port 8084 answers on localhost"]


def test_live_registration_url_on_the_port_downgrades_to_collision(tmp_path: Path) -> None:
    """The user's own server keeps the retired NAME and its port. A registration
    pointing there is evidence of a live deployment even with no container."""
    host = md.HostState(
        current_services=set(),
        services_known=True,
        containers={"mcp-nano-banana": "exited"},
        registration_targets={"http://127.0.0.1:8084/mcp - connected"},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.COLLISION
    assert "live registration targets port 8084" in nano["collision_evidence"][0]


def test_name_collision_is_not_an_orphan_and_teardown_refuses_it(tmp_path: Path) -> None:
    host = md.HostState(
        current_services=set(),
        services_known=True,
        containers={"mcp-nano-banana": "exited"},
        listening_ports={8084},
    )
    findings = md.classify(_dep(tmp_path), host)
    assert md.removable(findings) == []
    assert md.teardown(["mcp-nano-banana"], findings, execute=True) == 1

    report = md.render_table(findings, verbose=False, host=host)
    assert "Name collisions" in report
    assert "port 8084 answers on localhost" in report
    assert "NOT" in report and "orphans" in report


def test_collision_needs_something_present_absent_stays_absent(tmp_path: Path) -> None:
    """An answering port with nothing of CPP's left behind is just ABSENT - there
    is no teardown offer to suppress, so no collision needs reporting."""
    host = md.HostState(current_services=set(), services_known=True, listening_ports={8084})
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.ABSENT
    assert nano["collision_evidence"] == []


def test_quiet_port_leaves_a_genuine_orphan_reapable(tmp_path: Path) -> None:
    """The downgrade must not swallow the case the script exists for."""
    host = md.HostState(
        current_services=set(),
        services_known=True,
        containers={"mcp-nano-banana": "exited"},
        listening_ports={9999},
        registration_targets={"http://127.0.0.1:9999/mcp"},
    )
    nano = _nano(md.classify(_dep(tmp_path), host))
    assert nano["status"] == md.ORPHANED


def test_probe_listening_ports_sees_a_bound_port_and_not_a_quiet_one() -> None:
    import socket as _socket

    with _socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        assert md.probe_listening_ports({port}) == {port}
    # Closed again: the same port must no longer read as answering.
    assert md.probe_listening_ports({port}) == set()


def test_cli_answering_port_reports_collision_not_orphan(tmp_path: Path) -> None:
    """End-to-end with a real bound port, so the probe path itself is exercised."""
    import socket as _socket

    with _socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        dep = _depfile(tmp_path, f"""\
            version: 1
            deprecated:
              - name: mcp-nano-banana
                reason: retired diagram server
                port: {port}
                containers:
                  - mcp-nano-banana
        """)
        bin_dir, _ = _fake_bin(
            tmp_path,
            services="mcp-second-opinion",
            containers="mcp-nano-banana\texited\n",
        )
        check = _run_cli(bin_dir, dep, "--check", port_probe=True)
        assert check.returncode == 0, check.stdout
        assert md.COLLISION in check.stdout
        assert f"port {port} answers" in check.stdout

        orphans = _run_cli(bin_dir, dep, "--list-orphans", port_probe=True)
        assert orphans.stdout.strip() == ""
