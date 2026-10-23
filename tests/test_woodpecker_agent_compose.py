"""Checked-in Woodpecker agent compose files must not drift from bootstrap-agent-host.sh (issue #1551).

`woodpecker/bootstrap-agent-host.sh` generates the agent compose file for a
dedicated CI host (kyleci). The static `woodpecker/docker-compose.agent.yml`, which
kyle19's agent runs from, and the downstream template under
`templates/woodpecker/` had drifted from it. They lacked the
`./agent-config:/etc/woodpecker` volume, so the agent could not persist its
server-assigned id, and every restart registered a NEW agent on the server.

The expectations are DERIVED from the bootstrap script's heredoc, not hand-listed:
a volume or env key added to the bootstrap without its static copies fails here.
Keys inside a `${VAR:+...}` expansion are optional by construction (the bootstrap
emits them only when asked) and are not required.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "woodpecker" / "bootstrap-agent-host.sh"
TARGETS = [
    ROOT / "woodpecker" / "docker-compose.agent.yml",
    ROOT / "templates" / "woodpecker" / "docker-compose.agent.yml.example",
]

_HEREDOC = re.compile(
    r'cat > "\$AGENT_DIR/docker-compose\.agent\.yml" <<EOF\n(?P<body>.*?)\nEOF\n', re.S
)

# woodpecker/docker-compose.agent.yml as it stood when #1551 was filed (d33fd6a7):
# the RED case. The check must report it as drifted.
PRE_1551_STATIC = """\
services:
  woodpecker-agent:
    image: woodpeckerci/woodpecker-agent:v3.13.0
    container_name: woodpecker-agent
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    env_file: agent.env
    environment:
      - WOODPECKER_MAX_WORKFLOWS=2
    restart: unless-stopped
"""


def bootstrap_expectations(script: str) -> tuple[set[str], set[str], set[str]]:
    """(required volumes, required env keys, optional env keys) from the heredoc."""
    m = _HEREDOC.search(script)
    if m is None:
        raise AssertionError("bootstrap-agent-host.sh: agent compose heredoc not found")
    volumes: set[str] = set()
    required: set[str] = set()
    optional: set[str] = set()
    section = None
    conditional = False
    for raw in m.group("body").splitlines():
        line = raw.strip()
        if re.match(r"^\$\{\w+:\+", line):
            # An optional block opens here; its items run until the closing brace.
            conditional = not line.endswith("}")
            continue
        if not line or line.startswith("#"):
            continue
        key = re.match(r"^(\w+):\s*$", line)
        if key:
            section = key.group(1)
            continue
        item = re.match(r"^- (\S+)", line)
        if item and section == "volumes":
            volumes.add(item.group(1))
        elif item and section == "environment":
            name = item.group(1).split("=", 1)[0]
            (optional if conditional else required).add(name)
            if conditional and line.endswith("}"):
                conditional = False
        elif not raw.startswith("      "):
            section = None
    return volumes, required, optional


def compose_facts(text: str) -> tuple[set[str], set[str]]:
    """(volumes, env keys) the woodpecker-agent service declares."""
    svc = yaml.safe_load(text)["services"]["woodpecker-agent"]
    env = svc.get("environment") or []
    keys = set(env) if isinstance(env, dict) else {e.split("=", 1)[0] for e in env}
    return set(svc.get("volumes") or []), keys


def drift(script: str, compose: str) -> list[str]:
    want_vols, want_keys, _ = bootstrap_expectations(script)
    have_vols, have_keys = compose_facts(compose)
    return [f"volume {v}" for v in sorted(want_vols - have_vols)] + [
        f"env {k}" for k in sorted(want_keys - have_keys)
    ]


def test_extractor_reads_the_real_heredoc():
    """Guards against a blind extractor: an empty expectation set passes every file."""
    vols, required, optional = bootstrap_expectations(BOOTSTRAP.read_text())
    assert "./agent-config:/etc/woodpecker" in vols
    assert "/var/run/docker.sock:/var/run/docker.sock" in vols
    assert {"WOODPECKER_MAX_WORKFLOWS", "WOODPECKER_AGENT_LABELS",
            "WOODPECKER_HOSTNAME", "WOODPECKER_BACKEND"} <= required
    assert optional == {"WOODPECKER_FILTER_LABELS"}


@pytest.mark.parametrize("target", TARGETS, ids=lambda p: p.name)
def test_checked_in_agent_compose_matches_bootstrap(target: Path):
    assert drift(BOOTSTRAP.read_text(), target.read_text()) == []


def test_pre_1551_static_file_is_reported_as_drifted():
    """RED case: the file kyle19 ran from when #1551 was filed."""
    assert drift(BOOTSTRAP.read_text(), PRE_1551_STATIC) == [
        "volume ./agent-config:/etc/woodpecker",
        "env WOODPECKER_AGENT_LABELS",
        "env WOODPECKER_BACKEND",
        "env WOODPECKER_HOSTNAME",
    ]


def test_a_volume_added_only_to_the_bootstrap_is_reported():
    """Negative control: drift introduced on the bootstrap side fails the fixed files."""
    script = BOOTSTRAP.read_text().replace(
        "      - ./agent-config:/etc/woodpecker\n",
        "      - ./agent-config:/etc/woodpecker\n      - ./extra:/extra\n",
    )
    assert script != BOOTSTRAP.read_text()
    for target in TARGETS:
        assert drift(script, target.read_text()) == ["volume ./extra:/extra"]
