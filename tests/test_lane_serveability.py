"""Tests for scripts/lane-serveability-check.sh and the preflights that call it (issue #895).

`/qwen:auto` and `/gemma:auto` gated delegation on two questions - is the daemon
up, and is the model in the catalogue - and neither asks whether the model can be
LOADED. On 2026-09-13 the qwen serving host sat exactly between those facts: both
checks passed in ~13ms and the run died ~18s later inside the delegated call with
`{"error":"llama-server process has terminated: signal: killed"}`.

The load-bearing test in this file is
`test_old_gate_passes_while_the_new_probe_fails`. It stands up one stub server
that reproduces that host - `/api/version` and `/api/tags` healthy, `/api/generate`
returning the kill - and runs BOTH gates against it: the literal `curl | grep`
pipeline the preflights used, and the new helper. The old gate passes and the new
one fails, on the same server, in the same test. That is the issue's entire claim,
executed rather than asserted.

The failure is NOT deterministic, which the rest of the file exists to pin. Six
probes at the same endpoint with the same request bytes produced three shapes:
HTTP 500 with the server's error text (17.4s / 18.2s / 18.6s), HTTP 000 with curl
exit 52 and an empty body (16.5s / 17.1s), and an immediate HTTP 000 with curl
exit 56 (0.008s) when a probe landed right after a prior failure. A helper that
recognised only the 500 would have cleared that host on a third of the samples, so
`unreachable` is a first-class verdict here and both callers must refuse on it.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "lane-serveability-check.sh"
COMMANDS = ROOT / ".claude" / "commands"

#: The observed error text from the broken host. Kept verbatim: the point of the
#: DETAIL field is that the server's own words reach the operator, and a
#: paraphrase here would let a helper that mangles them still pass.
KILLED = "llama-server process has terminated: signal: killed"


# --------------------------------------------------------------------------
# Stub server
# --------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    """A configurable ollama stand-in. `behaviour` is set per-server below."""

    behaviour = "serving"

    def log_message(self, *args):  # noqa: D102 - silence the test run
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/version"):
            self._json(200, {"version": "0.33.3"})
        elif self.path.startswith("/api/tags"):
            # Registered, with the shape the real endpoint returns. This is what
            # makes the old gate pass even when the model cannot be loaded.
            self._json(200, {"models": [{"name": "qwen3.8-code:latest", "size": 17_740_000_000}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)

        if self.behaviour == "serving":
            self._json(200, {"model": "m", "response": "Hello", "done": True,
                             "done_reason": "length", "eval_count": 1})
        elif self.behaviour == "killed":
            self._json(500, {"error": KILLED})
        elif self.behaviour == "not_found":
            self._json(404, {"error": 'model "ghost" not found'})
        elif self.behaviour == "drop":
            # curl exit 52: accepted the request, closed without a reply. One of
            # the three real shapes.
            self.close_connection = True
            self.wfile.close()
        elif self.behaviour == "ok_but_error":
            # ollama has paths that return 200 carrying an error field. A check
            # keyed on the status code alone would call this serving.
            self._json(200, {"error": KILLED})
        elif self.behaviour == "ok_but_empty":
            # 200, no error, but no generated token either.
            self._json(200, {"model": "m", "done": True})
        else:  # pragma: no cover - guard against a typo in a test
            raise AssertionError(f"unknown behaviour {self.behaviour!r}")


@pytest.fixture
def stub():
    """Start a stub ollama on a free port; yields a factory taking a behaviour."""
    servers = []

    def _start(behaviour: str) -> str:
        handler = type("H", (_Handler,), {"behaviour": behaviour})
        server = HTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}"

    yield _start

    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_helper(endpoint: str, model: str = "qwen3.8-code:latest", *extra: str):
    return subprocess.run(
        [str(HELPER), "--endpoint", endpoint, "--model", model, *extra],
        capture_output=True, text=True, timeout=180,
    )


def contract(stdout: str) -> dict:
    """Parse the LANE_SERVE_* block into a dict."""
    out = {}
    for line in stdout.splitlines():
        m = re.match(r"^LANE_SERVE_([A-Z]+): (.*)$", line)
        if m:
            out[m.group(1).lower()] = m.group(2)
    return out


# --------------------------------------------------------------------------
# The issue's claim, executed
# --------------------------------------------------------------------------
def test_old_gate_passes_while_the_new_probe_fails(stub):
    """Registration and serveability are separately observable (issue #895).

    One server, two gates. The old preflight's literal `curl /api/tags | grep`
    clears it; the new probe does not. If a future change made the probe key on
    anything the tags endpoint already proves, this test goes green on both
    halves and fails.
    """
    endpoint = stub("killed")

    # The OLD gate, exactly as both auto.md preflights spelled it.
    old = subprocess.run(
        f"curl -sf --max-time 5 '{endpoint}/api/tags' 2>/dev/null | grep -q 'qwen3.8-code'",
        shell=True, capture_output=True, text=True, timeout=30,
    )
    assert old.returncode == 0, (
        "the old registration gate should PASS against this host - if it does not, "
        "the stub no longer reproduces the #895 state and the comparison below is vacuous"
    )

    # The NEW probe, against the same server.
    new = run_helper(endpoint)
    assert new.returncode == 1, f"expected dead (exit 1), got {new.returncode}: {new.stdout}"

    c = contract(new.stdout)
    assert c["status"] == "dead"
    assert KILLED in c["detail"], "the server's own words must reach the operator"


# --------------------------------------------------------------------------
# Positive control: the detector can fire, and can also clear
# --------------------------------------------------------------------------
def test_detector_can_report_serving(stub):
    """A clean verdict is reachable - otherwise `dead` above proves nothing."""
    result = run_helper(stub("serving"))
    assert result.returncode == 0, result.stdout
    c = contract(result.stdout)
    assert c["status"] == "serving"
    assert c["http"] == "200"
    assert "detail" not in c, "DETAIL is omitted when there is nothing to say"


def test_detector_can_report_dead(stub):
    result = run_helper(stub("killed"))
    assert result.returncode == 1
    assert contract(result.stdout)["status"] == "dead"


# --------------------------------------------------------------------------
# All three real failure shapes, and the states a status code cannot express
# --------------------------------------------------------------------------
def test_dropped_connection_is_unreachable_not_serving(stub):
    """curl exit 52 - one of the three shapes the broken host actually produced.

    The trap this closes: a dropped connection carries no error text, so a helper
    that looked for `error` in a body would find nothing and could fall through
    to a clean verdict.
    """
    result = run_helper(stub("drop"))
    assert result.returncode == 3, f"expected unreachable (exit 3): {result.stdout}"
    c = contract(result.stdout)
    assert c["status"] == "unreachable"
    assert c["http"] == "000"
    assert c["detail"], "an absent body still owes the operator a reason"


def test_refused_connection_is_unreachable():
    """Nothing listening at all. Port 1 on loopback is reliably refused."""
    result = run_helper("http://127.0.0.1:1")
    assert result.returncode == 3
    c = contract(result.stdout)
    assert c["status"] == "unreachable"
    assert "refused" in c["detail"].lower()


def test_http_200_carrying_an_error_is_not_serving(stub):
    """A status code is not serveability.

    ollama has paths that answer 200 with an `error` field. A check written as
    `[ "$HTTP" -lt 300 ]` reports this as healthy, which is the same class of
    error as the registration gate: a correct answer to a narrower question.
    """
    result = run_helper(stub("ok_but_error"))
    assert result.returncode == 1, f"expected dead (exit 1): {result.stdout}"
    assert contract(result.stdout)["status"] == "dead"


def test_http_200_with_no_generated_token_is_not_serving(stub):
    """Serveability is asserted from the positive artifact, not from its absence."""
    result = run_helper(stub("ok_but_empty"))
    assert result.returncode == 1
    assert contract(result.stdout)["status"] == "dead"


def test_absent_model_is_distinguishable_from_an_unloadable_one(stub):
    """Detector contract Q2, the ownership boundary.

    A wrong `--model` and a killed loader are different problems with different
    fixes. Both are `dead`, but DETAIL must carry the server's own words so the
    verdict cannot silently absorb "you asked for a name that isn't there".
    """
    result = run_helper(stub("not_found"), "ghost:latest")
    assert result.returncode == 1
    detail = contract(result.stdout)["detail"]
    assert "not found" in detail.lower()
    assert KILLED not in detail


# --------------------------------------------------------------------------
# The state the detector must be able to REPRESENT (contract Q1)
# --------------------------------------------------------------------------
@pytest.fixture
def path_without_curl(tmp_path):
    """A PATH carrying everything the helper needs EXCEPT curl.

    Handing it a genuinely empty directory does not test the helper: the shebang
    cannot find `bash`, the script never starts, and the 127 that comes back is a
    broken instrument wearing the costume of a verdict. The first draft of this
    test did exactly that and "passed" on a script that had never executed.
    """
    import shutil

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    needed = ["bash", "sh", "env", "sed", "grep", "mktemp", "rm", "head", "cut", "python3"]
    for name in needed:
        real = shutil.which(name)
        if real:
            (bin_dir / name).symlink_to(real)

    assert (bin_dir / "bash").exists(), "the shim needs bash or the helper cannot start"
    assert not (bin_dir / "curl").exists(), "the whole point is that curl is absent"
    return bin_dir


def _run_without_curl(path_without_curl, tmp_path):
    return subprocess.run(
        [str(HELPER), "--endpoint", "http://127.0.0.1:1", "--model", "m"],
        capture_output=True, text=True, timeout=60,
        env={"PATH": str(path_without_curl), "HOME": str(tmp_path)},
    )


def test_probe_that_could_not_run_reports_unknown(path_without_curl, tmp_path):
    """No curl means no observation - and that is neither `serving` nor `dead`.

    This is the empty-population case from docs/agents/detector-contracts.md:
    without a distinct state, a host missing curl would read as a clean lane.
    """
    result = _run_without_curl(path_without_curl, tmp_path)
    assert result.returncode == 4, (
        f"expected unknown (exit 4), got {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    c = contract(result.stdout)
    assert c["status"] == "unknown"
    assert c["http"] == "-", "no probe was made, so there is no status code to report"


def test_unknown_prose_does_not_read_as_clean(path_without_curl, tmp_path):
    """The wording is the safeguard: `unknown` must not be mistaken for healthy."""
    result = _run_without_curl(path_without_curl, tmp_path)
    assert "unchecked, not clean" in result.stdout


def test_success_message_does_not_overclaim(stub):
    """Contract Q1, the membership floor.

    One probe supports "it served a token", not "the lane is healthy". The
    message must scope itself, and must not claim the things this probe cannot
    see - tool calling in particular, which is `/gemma:status`'s job.
    """
    result = run_helper(stub("serving"))
    assert "tool-calling" in result.stdout, (
        "the clean verdict must name what it did NOT check, or a reader supplies "
        "the broader claim themselves"
    )


# --------------------------------------------------------------------------
# Contract mechanics
# --------------------------------------------------------------------------
@pytest.mark.parametrize("behaviour,expected", [
    ("serving", "serving"),
    ("killed", "dead"),
    ("drop", "unreachable"),
])
def test_always_emitted_keys_are_always_emitted(stub, behaviour, expected):
    """LANE, ENDPOINT, MODEL, HTTP, ELAPSED and STATUS on every path."""
    c = contract(run_helper(stub(behaviour)).stdout)
    assert c["status"] == expected
    for key in ("lane", "endpoint", "model", "http", "elapsed", "status"):
        assert key in c, f"{key} must be emitted on the {expected} path"


def test_endpoint_is_reported_as_probed(stub):
    """A trailing slash must not make the reported endpoint differ from the probed one."""
    endpoint = stub("serving")
    c = contract(run_helper(endpoint + "/").stdout)
    assert c["endpoint"] == endpoint


def test_quiet_suppresses_prose_but_not_the_contract(stub):
    result = run_helper(stub("killed"), "qwen3.8-code:latest", "--quiet")
    assert contract(result.stdout)["status"] == "dead"
    assert "lane-serveability-check:" not in result.stdout


@pytest.mark.parametrize("args", [
    ["--endpoint", "http://127.0.0.1:1"],                      # no model
    ["--model", "m"],                                          # no endpoint
    ["--endpoint", "http://127.0.0.1:1", "--model", "m", "--lane", "bogus"],
    ["--endpoint", "http://127.0.0.1:1", "--model", "m", "--timeout", "0"],
    ["--endpoint", "http://127.0.0.1:1", "--model", "m", "--timeout", "abc"],
    ["--endpoint", "http://127.0.0.1:1", "--model", "m", "--nonsense"],
])
def test_usage_errors_exit_2(args):
    """Exit 2 is reserved for "you called me wrong" and must never collide with a verdict."""
    result = subprocess.run([str(HELPER), *args], capture_output=True, text=True, timeout=60)
    assert result.returncode == 2, f"{args} -> {result.returncode}: {result.stdout}{result.stderr}"


def test_helper_is_executable():
    assert HELPER.exists(), f"{HELPER} is missing"
    assert HELPER.stat().st_mode & 0o111, (
        "the Tier-2 link loop gates on executability - a non-executable helper is "
        "one the stable-path install never creates"
    )


def test_probe_does_not_send_keep_alive():
    """A preflight reports on the server; it must not reconfigure it.

    The gemma host pins a 19 GB model in VRAM with OLLAMA_KEEP_ALIVE=-1. A
    request-level `keep_alive` overrides that, so a probe shipping one would
    silently un-pin the model and hand the next real run a cold load. Caught in
    review of this very change, where the first draft sent "5m".
    """
    source = HELPER.read_text()
    request_line = next(
        line for line in source.splitlines() if '"stream":false' in line and "printf" in line
    )
    assert "keep_alive" not in request_line, (
        "the probe request must not carry keep_alive - it would override the "
        "operator's OLLAMA_KEEP_ALIVE policy"
    )


# --------------------------------------------------------------------------
# The preflights must actually call it
# --------------------------------------------------------------------------
#: family -> (command doc, the endpoint variable it probes, the delegation heading)
LANES = {
    "qwen": (COMMANDS / "qwen" / "auto.md", "QWEN_ENDPOINT", "### Step 4: Execute Qwen"),
    "gemma": (COMMANDS / "gemma" / "auto.md", "GEMMA_ENDPOINT", "### Step 4: Execute Gemma"),
}


@pytest.mark.parametrize("lane", sorted(LANES))
def test_preflight_invokes_the_serveability_probe(lane):
    """Both preflights call the helper at its stable path.

    These are prompt documents, so the document is the enforceable layer: a
    future editor cannot quietly drop the probe and leave the registration gate
    behind, which is precisely the state #895 describes.
    """
    doc, _, _ = LANES[lane]
    text = doc.read_text()
    assert "~/.claude/scripts/lane-serveability-check.sh" in text, (
        f"{doc.relative_to(ROOT)} must invoke the serveability probe at its stable path"
    )


@pytest.mark.parametrize("lane", sorted(LANES))
def test_probe_runs_before_delegation_not_after(lane):
    """A probe after the delegation is not a preflight.

    The whole value is refusing to spend the run; a check that fires once the
    model has already been handed the task reports a fact nobody can act on.
    """
    doc, _, heading = LANES[lane]
    text = doc.read_text()
    assert heading in text, f"{doc.relative_to(ROOT)} lost its {heading!r} heading"

    probe_at = text.index("~/.claude/scripts/lane-serveability-check.sh")
    step_at = text.index(heading)
    assert probe_at > step_at, "the probe should live inside the Execute step's preflight"

    # The delegating CLI call must come after the probe.
    cli = {"qwen": "--openai-base-url", "gemma": "opencode run"}[lane]
    cli_at = text.index(cli, step_at)
    assert probe_at < cli_at, (
        f"{doc.relative_to(ROOT)}: the serveability probe must run BEFORE the "
        f"delegating {cli!r} invocation, not after it"
    )


@pytest.mark.parametrize("lane", sorted(LANES))
def test_preflight_refuses_on_unreachable_as_well_as_dead(lane):
    """Both failing verdicts must stop the run.

    Not a stylistic pairing: the broken host produced `unreachable` on two of six
    probes (curl 52, and an immediate curl 56). A document that stopped only on
    `dead` would have delegated into a dead lane a third of the time.
    """
    doc, _, _ = LANES[lane]
    text = doc.read_text()
    for verdict in ("dead", "unreachable"):
        assert verdict in text, (
            f"{doc.relative_to(ROOT)} must name the '{verdict}' verdict and refuse on it - "
            "the failure shape is not deterministic"
        )


# --------------------------------------------------------------------------
# /qwen:status must be able to say no
# --------------------------------------------------------------------------
STATUS_DOC = COMMANDS / "qwen" / "status.md"


def test_qwen_status_ready_verdict_consumes_the_probe():
    """The diagnostic surface must not print a failure and then report READY.

    Before #895 `/qwen:status` ran a real generation probe, printed
    `(probe failed or timed out)` when it failed, and then computed `READY` from
    `command -v qwen` plus `/api/version` alone - so on the broken host it
    printed the failure and `Status: READY` underneath it. `/qwen:auto` sends a
    user whose run just died to this command, so that handoff landed on a green
    light.
    """
    text = STATUS_DOC.read_text()
    assert "lane-serveability-check.sh" in text, "the probe must be the shared helper"
    assert "SERVE_EXIT" in text, "the probe's verdict must be captured"

    summary = text[text.index("### Step 5: Summary"):]
    assert "SERVE_EXIT" in summary, (
        "the READY verdict must CONSUME the probe result - a probe whose verdict "
        "the summary ignores is the exact #895 defect"
    )


def test_qwen_status_unverified_cannot_overwrite_a_decided_no():
    """Uncertainty is the weaker claim and must only ever weaken a `true`.

    A missing harness or an unreachable daemon is a definite NOT READY. If the
    `unverified` branch were unguarded, an absent probe would soften that
    settled answer into a maybe.
    """
    text = STATUS_DOC.read_text()
    summary = text[text.index("### Step 5: Summary"):]
    guard = summary.index('if [ "$READY" = "true" ]; then')
    unverified = summary.index("READY=unverified")
    assert guard < unverified, (
        "the READY=unverified assignment must sit INSIDE the "
        '`if [ "$READY" = "true" ]` guard, or it overwrites a decided NOT READY'
    )


def test_qwen_status_reports_unverified_distinctly():
    """`unverified` must be a visible third state, not folded into READY or NOT READY."""
    text = STATUS_DOC.read_text()
    assert "Status: UNVERIFIED" in text, (
        "a probe that could not run is unchecked, not clean - it needs its own "
        "reported state (docs/agents/detector-contracts.md, Q1)"
    )


# --------------------------------------------------------------------------
# Registration in the two hand-maintained lists
# --------------------------------------------------------------------------
def test_helper_is_in_the_stable_path_install_set():
    """Without this the bare invocation resolves to nothing and every run prompts."""
    installer = (ROOT / "scripts" / "flow-helpers-install.sh").read_text()
    assert "lane-serveability-check.sh" in installer


def test_helper_has_an_allowlist_rule():
    template = json.loads((ROOT / "templates" / "claude-settings-permissions.json").read_text())
    rules = template["permissions"]["allow"]
    assert "Bash(~/.claude/scripts/lane-serveability-check.sh:*)" in rules


@pytest.mark.parametrize("lane", sorted(LANES))
def test_preflight_probes_the_lane_model_and_endpoint(lane):
    """Probing some other model would prove nothing about this lane."""
    doc, endpoint_var, _ = LANES[lane]
    text = doc.read_text()
    invocation = next(
        line for line in text.splitlines()
        if "lane-serveability-check.sh" in line and "--endpoint" in line
    )
    assert f"${endpoint_var}" in invocation, f"must probe ${endpoint_var}"
    assert "--model" in invocation and "_MODEL" in invocation, (
        "must probe the lane's own configured model, not a hardcoded name"
    )
