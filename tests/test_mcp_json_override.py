"""Pins for the second-opinion URL override (issue #633).

The shipped .mcp.json must carry the env-expansion form - Claude Code expands
${VAR:-default} in .mcp.json url fields (documented feature) - so one export
moves the consumer on a host where 8080 is taken and `git status` stays clean.

WHAT WAS REMOVED HERE AND WHY (issue #943). This module used to carry
`test_convention_parity_with_mcp_evaluate`, which read
`mcp-evaluate/src/config.py` and asserted its SECOND_OPINION_URL default matched
the one in .mcp.json. Its premise was "one variable, TWO consumers"; #943 retired
`mcp-evaluate/`, so the second consumer no longer exists and there is nothing left
for the first to diverge from.

That is a removal, not a relaxation, and the distinction matters: the test drew a
line between two values that could disagree, and one side of the comparison is
gone. A version kept alive by making the file read optional would be strictly
worse than deleting it - it would pass unconditionally while still looking like a
parity check. If a second consumer of SECOND_OPINION_URL is ever added, the parity
assertion should come back with it.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_URL = "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp"


def test_mcp_json_uses_env_expansion_with_default() -> None:
    data = json.loads((ROOT / ".mcp.json").read_text())
    assert data["mcpServers"]["second-opinion"]["url"] == EXPECTED_URL
    assert data["mcpServers"]["second-opinion"]["type"] == "http"


def test_docs_reference_the_override() -> None:
    for rel in (
        "README.md",
        ".claude/commands/cpp/dockers.md",
        ".claude/commands/cpp/load-mcp-docs.md",
        ".claude/commands/flow/doctor.md",
    ):
        assert "SECOND_OPINION_URL" in (ROOT / rel).read_text(), f"{rel} lost the override doc"



# The user-scope registration is the SECOND consumer the module docstring says
# would bring a parity check back (issue #1256). /cpp:init registers
# second-opinion at user scope while the repo's .mcp.json registers it at
# project scope; when the two spell the URL differently - a hardcoded
# 127.0.0.1 beside an exported SECOND_OPINION_URL, or a hand-edited Tailscale
# URL beside the 127.0.0.1 default - Claude Code reports [Conflicting scopes].
# Deriving both from the same expression makes them agree by construction.
INSTALL_DOCS = (
    "README.md",
    ".claude/commands/cpp/init.md",
    ".claude/commands/cpp/update.md",
    ".claude/commands/second-opinion/help.md",
)

# One `claude mcp add` invocation: up to a closing backtick, a shell comment or
# the end of the line. `codex mcp add --url` is Codex's own, valid syntax and
# never matches "claude mcp add".
_ADD = re.compile(r"claude mcp add\b([^`#\n]*)")


def _tokens(segment: str) -> list[str]:
    lex = shlex.shlex(segment, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    out: list[str] = []
    for tok in lex:
        if tok and set(tok) <= set(";&|()<>"):
            break  # the command ends at a control operator (`; then`, `&&`)
        out.append(tok)
    return out


def _split(segment: str) -> list[str]:
    # A command quoted inside `echo "..."` carries the echo's closing quote;
    # drop it rather than skip the line, which would hide it from the checks.
    try:
        return _tokens(segment)
    except ValueError:
        return _tokens(segment.rstrip().rstrip("\"'"))


def _registrations(text: str) -> list[list[str]]:
    return [_split(m.group(1)) for m in _ADD.finditer(text)]


def _second_opinion_url(args: list[str]) -> str | None:
    """The URL positional that follows the server name, or None if absent.

    `claude mcp add [options] <name> <commandOrUrl>`; every option this
    repository passes to it takes a value.
    """
    positionals: list[str] = []
    it = iter(args)
    for tok in it:
        if tok.startswith("-"):
            if "=" not in tok:
                next(it, None)
            continue
        positionals.append(tok)
    if len(positionals) >= 2 and positionals[0] == "second-opinion":
        return positionals[1]
    return None


def test_no_install_doc_uses_the_rejected_url_flag() -> None:
    # `claude mcp add` has no --url option: the URL is a positional after the
    # name. The old documented form failed with "unknown option '--url'" while
    # /cpp:init still printed success.
    offenders = [
        f"{rel}: {args}"
        for rel in INSTALL_DOCS
        for args in _registrations((ROOT / rel).read_text())
        if any(a == "--url" or a.startswith("--url=") for a in args)
    ]
    assert not offenders, "claude mcp add has no --url option:\n" + "\n".join(offenders)


def _second_opinion_registrations(text: str) -> list[list[str]]:
    return [args for args in _registrations(text) if "second-opinion" in args]


def _parity_offenders(text: str) -> list[str]:
    return [
        " ".join(args)
        for args in _second_opinion_registrations(text)
        if _second_opinion_url(args) != EXPECTED_URL
    ]


def test_every_second_opinion_registration_derives_from_the_shared_url() -> None:
    found = {
        rel: _second_opinion_registrations((ROOT / rel).read_text()) for rel in INSTALL_DOCS
    }
    # The scan must find something in every document, or the parity assertion
    # below is vacuously true.
    assert all(found.values()), {rel: len(v) for rel, v in found.items()}
    drifted = [f"{rel}: {o}" for rel in INSTALL_DOCS for o in _parity_offenders((ROOT / rel).read_text())]
    assert not drifted, (
        f"second-opinion must be registered at the same URL as .mcp.json ({EXPECTED_URL}), "
        "or the two scopes conflict:\n" + "\n".join(drifted)
    )


@pytest.mark.parametrize(
    "text",
    [
        "claude mcp add --transport http --scope user second-opinion http://127.0.0.1:8080/mcp",
        # a wrong URL followed by a comment naming the right one
        f'claude mcp add --transport http --scope user second-opinion http://wrong:8080/mcp  # "{EXPECTED_URL}"',
        "claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user",
    ],
)
def test_parity_validator_rejects_a_non_derived_registration(text: str) -> None:
    # Known-bad inputs through the SAME validator the document scan uses.
    assert _parity_offenders(text)


def test_parity_validator_accepts_the_derived_registration() -> None:
    assert not _parity_offenders(f'`claude mcp add --transport http --scope user second-opinion "{EXPECTED_URL}"`')


# Behaviour of /cpp:init step 3c itself, run from the command document with a
# stub `claude`. The guard used to grep `claude mcp list`, which inside a CPP
# checkout always shows the project-scope .mcp.json entry, so the user-scope add
# never ran there (counter-model review, #1256).
def _init_3c_block() -> str:
    text = (ROOT / ".claude/commands/cpp/init.md").read_text()
    section = text[text.index("#### 3c. Register MCP Servers") :]
    start = section.index("```bash\n") + len("```bash\n")
    return section[start : section.index("\n```", start)]


_STUB = """#!/bin/sh
echo "$*" >> "$STUB_LOG"
case "$1 $2" in
  "mcp list") echo "second-opinion: \\${SECOND_OPINION_URL}/mcp (HTTP) - Pending approval"; exit 0 ;;
  "mcp add") case "$*" in *second-opinion*) exit "${STUB_ADD_EXIT:-0}" ;; esac; exit 0 ;;
esac
exit 0
"""


def _run_3c(
    tmp_path: Path,
    *,
    user_servers: dict,
    add_exit: int = 0,
    url: str | None = None,
    home_servers: dict | None = None,
) -> tuple[str, list[str]]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude"
    stub.write_text(_STUB)
    stub.chmod(0o755)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / ".claude.json").write_text(json.dumps({"mcpServers": user_servers}))
    if home_servers is not None:
        # the default profile, which CLAUDE_CONFIG_DIR makes inactive
        (tmp_path / ".claude.json").write_text(json.dumps({"mcpServers": home_servers}))
    log = tmp_path / "claude.log"
    env = {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "CLAUDE_CONFIG_DIR": str(cfg),
        "CPP_DIR": str(ROOT),
        "STUB_LOG": str(log),
        "STUB_ADD_EXIT": str(add_exit),
    }
    if url is not None:
        env["SECOND_OPINION_URL"] = url
    out = subprocess.run(
        ["bash", "-c", _init_3c_block()], env=env, capture_output=True, text=True, timeout=60
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return out.stdout + out.stderr, [c for c in calls if c.startswith("mcp add") and "second-opinion" in c]


_needs_shell = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("python3") is None, reason="needs bash and python3"
)


@_needs_shell
def test_init_registers_user_scope_even_when_the_project_entry_is_listed(tmp_path: Path) -> None:
    out, adds = _run_3c(tmp_path, user_servers={})
    assert adds == ["mcp add --transport http --scope user second-opinion http://127.0.0.1:8080/mcp"], out
    assert "✓ second-opinion MCP registered" in out


@_needs_shell
def test_init_skips_when_user_scope_already_has_it(tmp_path: Path) -> None:
    out, adds = _run_3c(tmp_path, user_servers={"second-opinion": {"type": "http", "url": "x"}})
    assert adds == [], out
    assert "already registered at user scope" in out


@_needs_shell
def test_init_user_url_follows_SECOND_OPINION_URL(tmp_path: Path) -> None:
    _, adds = _run_3c(tmp_path, user_servers={}, url="http://100.64.0.5:8080")
    assert adds == ["mcp add --transport http --scope user second-opinion http://100.64.0.5:8080/mcp"]


@_needs_shell
def test_init_reports_a_failed_registration_as_failed(tmp_path: Path) -> None:
    out, adds = _run_3c(tmp_path, user_servers={}, add_exit=1)
    assert adds, out
    assert "registration FAILED" in out
    assert "✓ second-opinion MCP registered" not in out


_STDIO = {"second-opinion": {"type": "stdio", "command": "/fixture/server", "args": ["--stdio"]}}
_MATCHING = {"second-opinion": {"type": "http", "url": "http://127.0.0.1:8080/mcp"}}


@_needs_shell
def test_init_scope_check_reads_the_active_profile(tmp_path: Path) -> None:
    # Conflict in the CLAUDE_CONFIG_DIR profile, nothing in the default one.
    out, _ = _run_3c(tmp_path, user_servers=_STDIO, home_servers={})
    assert "SCOPE CONFLICT: second-opinion" in out, out


@_needs_shell
def test_init_scope_check_ignores_an_inactive_profile(tmp_path: Path) -> None:
    # The same conflict, but only in the default profile this session is not using.
    out, _ = _run_3c(tmp_path, user_servers=_MATCHING, home_servers=_STDIO)
    assert "SCOPE CONFLICT" not in out, out
    assert "OK: second-opinion" in out, out
