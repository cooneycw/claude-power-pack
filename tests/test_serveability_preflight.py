"""Pin: a delegated lane's readiness gate asks whether the model can SERVE (issue #895).

Every local-model surface asked whether the daemon was up and the model was
REGISTERED. Those are different facts from "can this lane run", and the failure
sits exactly between them: the model is in the manifest and the `llama-server`
worker is SIGKILLed during weight load, so the gate passes in ~13ms and the run
dies ~18s later inside the delegated call with an opaque HTTP 500.

Four surfaces, and only one of them was right:

- `qwen/auto.md`   preflight: `/api/version` + `/api/tags`, no generate
- `gemma/auto.md`  preflight: identical, latent only because that host is healthy
- `qwen/status.md` verdict:  probe present but UNASSERTED - `curl -s`, failure
  swallowed by `|| echo "(probe failed or timed out)"`, result never reaching
  READY. It printed "(probe failed or timed out)" and then "Status: READY".
  `auto.md` sends users there after a failed run, so the remediation path
  carried the defect it was meant to diagnose.
- `gemma/status.md` verdict: the reference - and it had its own narrower
  version of the same bug. The display branch required exit 0 AND `tool_use`
  AND `completed`; the verdict tested only `$SMOKE_EXIT`. A dropped tool call
  printed "FAILED: no tool call observed" above "Status: READY".

**Both kinds of test are here on purpose.** The text probes pin that each
surface still reaches a real generate and still feeds its verdict. The
EXECUTION tests actually run the shipped bash against stub servers, because a
text assertion cannot tell a probe that discriminates from one that merely
mentions `/api/generate` - and the first draft of this fix passed every text
check while printing an EMPTY "the server's own error:" heading, since its
extraction pattern did not tolerate `"error": "` with a space.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands"

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)
requires_curl = pytest.mark.skipif(
    shutil.which("curl") is None, reason="requires curl on PATH"
)

LANES = ("qwen", "gemma")


def bash_blocks(text: str) -> list[str]:
    """Every ```bash fence, indented ones included (the #798 lesson)."""
    return [
        textwrap.dedent(b)
        for b in re.findall(r"^[ \t]*```bash\n(.*?)^[ \t]*```", text, re.M | re.S)
    ]


def _doc(lane: str, kind: str) -> str:
    return (COMMANDS / lane / f"{kind}.md").read_text(encoding="utf-8")


def _block_containing(text: str, needle: str) -> str:
    for block in bash_blocks(text):
        if needle in block:
            return block
    raise AssertionError(f"no bash block containing {needle!r}")


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


@pytest.mark.parametrize("lane", LANES)
def test_auto_preflight_probes_serveability_not_just_registration(lane: str) -> None:
    """`/api/tags` answers a narrower question than "can this lane run"."""
    block = _block_containing(_doc(lane, "auto"), "/api/tags")
    assert "/api/generate" in block, (
        f"{lane}/auto.md gates on registration alone - /api/tags reports the "
        "manifest and cannot report whether the weights load"
    )
    assert "num_predict" in block, (
        f"{lane}/auto.md's probe does not bound the generation to one token"
    )


@pytest.mark.parametrize("lane", LANES)
def test_the_auto_preflight_probe_can_actually_stop_the_run(lane: str) -> None:
    """A probe whose result is not acted on is a report, which is the defect."""
    block = _block_containing(_doc(lane, "auto"), "/api/generate")
    var = lane.upper()
    assert f"{var}_PROBE_CODE" in block, "the probe's status is not captured"
    assert re.search(rf'\[ "\${var}_PROBE_CODE" != "200" \]', block), (
        "the probe result is not compared against success"
    )
    assert "exit 1" in block, "a failed probe does not stop the run"


@pytest.mark.parametrize("lane", LANES)
def test_the_status_verdict_includes_serveability(lane: str) -> None:
    """READY must not be computable while the lane cannot serve.

    This is the half that made the remediation path useless: `/qwen:auto` tells
    a user to run `/qwen:status` after a failed run.
    """
    block = _block_containing(_doc(lane, "status"), "READY=true")
    gate = {"qwen": "QWEN_SERVES", "gemma": "SMOKE_OK"}[lane]
    assert gate in block, (
        f"{lane}/status.md computes READY without consulting {gate} - it can "
        "print a failed probe and 'Status: READY' underneath it"
    )


def test_the_gemma_verdict_uses_the_payload_assertions_its_display_makes() -> None:
    """The display and the verdict must not disagree about what passing means.

    The display branch required exit 0 AND a tool_use AND completed; the verdict
    tested only $SMOKE_EXIT. A run that exited 0 with the tool call silently
    dropped - the #752 failure this smoke test exists to catch - printed FAILED
    and READY at once.
    """
    # The VERDICT block, not the smoke block - both mention SMOKE_OK, and the
    # first draft of this probe matched the wrong one and passed vacuously.
    block = _block_containing(_doc("gemma", "status"), "READY=true")
    assert not re.search(r'\[ "\$SMOKE_EXIT" = "0" \] \|\| READY=false', block), (
        "the verdict is back to consulting only the exit status"
    )
    assert re.search(r'\[ "\$SMOKE_OK" = "true" \] \|\| READY=false', block)


# --------------------------------------------------------------------------
# Execution - the half a text assertion cannot do
# --------------------------------------------------------------------------


class _Stub(BaseHTTPRequestHandler):
    payload: bytes = b""
    code: int = 200

    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(self.code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, *a: object) -> None:
        pass


def _serve(code: int, payload: bytes):
    handler = type("H", (_Stub,), {"code": code, "payload": payload})
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _run_probe(lane: str, endpoint: str) -> subprocess.CompletedProcess[str]:
    """Run the SHIPPED preflight probe, extracted from the document verbatim."""
    var = lane.upper()
    block = _block_containing(_doc(lane, "auto"), "/api/generate")
    snippet = block[block.index("# Registration is not serveability") :]
    snippet = snippet[: snippet.index("\nfi\n") + 4]
    return subprocess.run(
        ["bash", "-c", snippet],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            f"{var}_ENDPOINT": endpoint,
            f"{var}_MODEL": "probe:latest",
        },
        check=False,
        timeout=120,
    )


@requires_bash
@requires_curl
@pytest.mark.parametrize("lane", LANES)
def test_probe_passes_a_serving_host(lane: str) -> None:
    httpd = _serve(200, json.dumps({"response": "OK", "done": True}).encode())
    try:
        res = _run_probe(lane, f"http://127.0.0.1:{httpd.server_port}")
        assert res.returncode == 0, res.stdout + res.stderr
    finally:
        httpd.shutdown()
        httpd.server_close()


@requires_bash
@requires_curl
@pytest.mark.parametrize("lane", LANES)
@pytest.mark.parametrize(
    "payload",
    [
        b'{"error":"llama-server process has terminated: signal: killed"}',
        b'{"error": "llama-server process has terminated: signal: killed"}',
    ],
    ids=["compact", "spaced"],
)
def test_probe_stops_a_registered_but_unservable_host_and_names_the_cause(
    lane: str, payload: bytes
) -> None:
    """Both JSON spacings, because the first draft handled only one.

    It printed an empty "the server's own error:" heading against the other -
    a blank where the diagnosis goes, which is the failure this check exists to
    remove, reproduced inside the fix for it. Every text assertion still passed.
    """
    httpd = _serve(500, payload)
    try:
        res = _run_probe(lane, f"http://127.0.0.1:{httpd.server_port}")
        assert res.returncode == 1, "an unservable model must stop the run"
        assert "cannot serve" in res.stdout
        assert "llama-server process has terminated: signal: killed" in res.stdout, (
            "the server's own error text is not surfaced - the operator gets a "
            f"labelled heading with nothing under it:\n{res.stdout}"
        )
    finally:
        httpd.shutdown()
        httpd.server_close()


@requires_bash
@requires_curl
@pytest.mark.parametrize("lane", LANES)
def test_probe_stops_when_nothing_answers_at_all(lane: str) -> None:
    """No response is not a server error, and must not print an empty heading."""
    httpd = _serve(200, b"{}")
    port = httpd.server_port
    httpd.shutdown()
    # server_close() as well: shutdown() only stops serve_forever and leaves the
    # listening socket OPEN, so the probe connected, got no answer, and burned
    # the full 90s timeout instead of being refused - ~180s of suite time for a
    # case that should take milliseconds, and it was measuring the wrong thing.
    httpd.server_close()
    res = _run_probe(lane, f"http://127.0.0.1:{port}")
    assert res.returncode == 1
    assert "No response at all" in res.stdout
    assert "The server's own error:" not in res.stdout, (
        "printed a 'server's own error' heading when there was no server"
    )
