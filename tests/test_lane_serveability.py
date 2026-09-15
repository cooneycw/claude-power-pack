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
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "lane-serveability-check.sh"
COMMANDS = ROOT / ".claude" / "commands"

#: CLAUDE.md: a test that shells out to a real binary needs a `shutil.which`
#: guard, INCLUDING when it reaches that binary by running a repo shell script.
#: The Woodpecker `validate` image (`uv:python3.11-bookworm-slim`) ships no
#: `curl`, and this dev box does, so an unguarded probe test is invisible
#: locally and red only in CI - which is exactly how it was found here, on the
#: first pipeline run of this change.
#:
#: The tests that synthesize an ABSENT curl are deliberately NOT guarded: they
#: assert the `unknown` verdict, need no curl to do it, and are the ones worth
#: having run on an image that genuinely lacks it.
requires_curl = pytest.mark.skipif(
    shutil.which("curl") is None,
    reason="needs curl: the probe shells out to it (CLAUDE.md binary-guard directive)",
)

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
    """Parse the LANE_SERVE_* block into a dict.

    `[A-Z_]+`, not `[A-Z]+` (issue #921). The original stopped at the first
    underscore, so `LANE_SERVE_VALID_FOR` matched nothing and was dropped
    SILENTLY - every assertion about it would have read as a missing key rather
    than a parser fault. `test_the_contract_parser_can_see_an_underscored_key`
    is the control on this line, because a parser that cannot see a field makes
    every test of that field vacuous in the same direction.
    """
    out = {}
    for line in stdout.splitlines():
        m = re.match(r"^LANE_SERVE_([A-Z_]+): (.*)$", line)
        if m:
            out[m.group(1).lower()] = m.group(2)
    return out


# --------------------------------------------------------------------------
# The issue's claim, executed
# --------------------------------------------------------------------------
@requires_curl
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
@requires_curl
def test_detector_can_report_serving(stub):
    """A clean verdict is reachable - otherwise `dead` above proves nothing."""
    result = run_helper(stub("serving"))
    assert result.returncode == 0, result.stdout
    c = contract(result.stdout)
    assert c["status"] == "serving"
    assert c["http"] == "200"
    assert "detail" not in c, "DETAIL is omitted when there is nothing to say"


@requires_curl
def test_detector_can_report_dead(stub):
    result = run_helper(stub("killed"))
    assert result.returncode == 1
    assert contract(result.stdout)["status"] == "dead"


# --------------------------------------------------------------------------
# All three real failure shapes, and the states a status code cannot express
# --------------------------------------------------------------------------
@requires_curl
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


@requires_curl
def test_refused_connection_is_unreachable():
    """Nothing listening at all. Port 1 on loopback is reliably refused."""
    result = run_helper("http://127.0.0.1:1")
    assert result.returncode == 3
    c = contract(result.stdout)
    assert c["status"] == "unreachable"
    assert "refused" in c["detail"].lower()


@requires_curl
def test_http_200_carrying_an_error_is_not_serving(stub):
    """A status code is not serveability.

    ollama has paths that answer 200 with an `error` field. A check written as
    `[ "$HTTP" -lt 300 ]` reports this as healthy, which is the same class of
    error as the registration gate: a correct answer to a narrower question.
    """
    result = run_helper(stub("ok_but_error"))
    assert result.returncode == 1, f"expected dead (exit 1): {result.stdout}"
    assert contract(result.stdout)["status"] == "dead"


@requires_curl
def test_http_200_with_no_generated_token_is_not_serving(stub):
    """Serveability is asserted from the positive artifact, not from its absence."""
    result = run_helper(stub("ok_but_empty"))
    assert result.returncode == 1
    assert contract(result.stdout)["status"] == "dead"


@requires_curl
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
    # `date` joined this list in #921: the helper timestamps every verdict, and
    # a fixture missing it would make the no-curl tests fail for a reason that
    # is not the absence under test. One absence per fixture - see
    # `path_without_date` below for the clock's own.
    needed = ["bash", "sh", "env", "sed", "grep", "mktemp", "rm", "head", "cut",
              "tr", "date", "python3"]
    for name in needed:
        real = shutil.which(name)
        if real:
            (bin_dir / name).symlink_to(real)

    assert (bin_dir / "bash").exists(), "the shim needs bash or the helper cannot start"
    assert not (bin_dir / "curl").exists(), "the whole point is that curl is absent"
    return bin_dir


def _run_without_curl(path_without_curl, tmp_path):
    # Asserted here, not only in the fixture (#933). `shutil.which` rather than
    # `.exists()` on purpose: a file that is present but not executable, or a
    # PATH assembled with the wrong separator, passes an existence check and
    # fails a lookup - and it is the LOOKUP the helper under test performs.
    assert shutil.which("curl", path=str(path_without_curl)) is None, (
        "fixture must lack curl or this proves nothing about the unperformable case"
    )
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


@requires_curl
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
#: The probe contract, EXACTLY. `AT` and `VALID_FOR` joined it in #921.
_PROBE_KEYS = {"lane", "endpoint", "model", "http", "elapsed", "at", "valid_for", "status"}


@pytest.mark.parametrize("behaviour,expected,extra", [
    ("serving", "serving", set()),
    ("killed", "dead", {"detail"}),
    ("drop", "unreachable", {"detail"}),
])
@requires_curl
def test_the_probe_contract_is_exactly_these_keys(stub, behaviour, expected, extra):
    """An EXACT set, not a subset - because the failure here is an ADDED key.

    The original asserted `key in c` for six names, which cannot fail when a
    seventh appears. That is how this contract's only written-down enumeration
    (prose in docs/scripts.md, plus the header of the script itself) goes stale
    with every test still green: #921 added two always-emitted keys and nothing
    in this file objected. An exact set makes the next addition stop here, where
    the author can still see which documents name the old set.

    DETAIL stays conditional on purpose - a field that is always present teaches
    readers to ignore it - so it is asserted per-path rather than folded in.
    """
    c = contract(run_helper(stub(behaviour)).stdout)
    assert c["status"] == expected
    assert set(c) == _PROBE_KEYS | extra, (
        f"the {expected} path emits {sorted(set(c))}, expected "
        f"{sorted(_PROBE_KEYS | extra)} - if this is a deliberate contract "
        f"change, docs/scripts.md and the script header enumerate it too"
    )


@requires_curl
def test_endpoint_is_reported_as_probed(stub):
    """A trailing slash must not make the reported endpoint differ from the probed one."""
    endpoint = stub("serving")
    c = contract(run_helper(endpoint + "/").stdout)
    assert c["endpoint"] == endpoint


@requires_curl
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
    ["--endpoint", "http://127.0.0.1:1", "--model", "m", "--valid-for", "0"],
    ["--endpoint", "http://127.0.0.1:1", "--model", "m", "--valid-for", "abc"],
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


# --------------------------------------------------------------------------
# /gemma:status must not disagree with itself
#
# The sibling of the two tests above, and the surface #903 did not reach: #895
# closed with `gemma/status.md`'s verdict still computed from a NARROWER
# question than its own display asserts.
# --------------------------------------------------------------------------
GEMMA_STATUS_DOC = COMMANDS / "gemma" / "status.md"


def test_gemma_status_verdict_uses_the_payload_assertions_its_display_makes():
    """A run can print FAILED and READY at once, and that is the #752 case.

    `gemma/status.md`'s smoke branch requires three things - exit 0, a
    `"type":"tool_use"` event, and `"status":"completed"` - and prints
    `[ ] FAILED: no tool call observed` when any is missing. Its verdict tested
    only `$SMOKE_EXIT`.

    So a run that exits 0 with the tool call SILENTLY DROPPED printed the
    failure and then printed `Status: READY` underneath it. That dropped tool
    call is the exact #752 `/v1` failure this smoke test was BUILT to catch, so
    the check detected its own founding defect, displayed it, and passed the run
    anyway.

    Same shape as `test_qwen_status_ready_verdict_consumes_the_probe` above - a
    verdict computed from less than the display asserts - which is why it lives
    beside it rather than in a file of its own.
    """
    text = GEMMA_STATUS_DOC.read_text()
    summary = text[text.index("### Step 5: Summary"):]

    assert not re.search(r'\[ "\$SMOKE_EXIT" = "0" \]\s*\|\|\s*READY=false', summary), (
        "the verdict consults only the exit status again - a dropped tool call "
        "reports READY while the smoke output above says FAILED"
    )
    assert re.search(r'\[ "\$SMOKE_OK" = "true" \]\s*\|\|\s*READY=false', summary), (
        "the verdict must consume the same three-part result the display asserts"
    )


def test_gemma_smoke_result_is_computed_once_for_display_and_verdict():
    """One variable, so the two cannot drift apart again.

    The defect was not that the verdict was wrong in isolation - it was that two
    places computed "did the smoke test pass" from different inputs. Deriving
    both from a single `SMOKE_OK` is what makes the agreement structural rather
    than something a future editor has to remember.
    """
    text = GEMMA_STATUS_DOC.read_text()
    assert text.count("SMOKE_OK=true") == 1, (
        "SMOKE_OK must be decided in exactly one place"
    )
    assert re.search(
        r'SMOKE_OK=false\s*\n\s*if \[ "\$SMOKE_EXIT" -eq 0 \].*tool_use.*completed',
        text,
        re.S,
    ), "SMOKE_OK must default to false and be set only by the full three-part check"
    assert 'if [ "$SMOKE_OK" = "true" ]; then' in text, (
        "the display branch must read the same variable the verdict does"
    )


# --------------------------------------------------------------------------
# Freshness: how long a recorded verdict may be READ AS CURRENT (issue #921)
# --------------------------------------------------------------------------
# A probe is a point observation. Nothing in the contract said how long it kept
# being true, so a pass taken at minute 0 read exactly like a pass taken a
# second ago, and a 30-minute run leaned on a 30-minute-old fact.
#
# The two axes are kept apart on purpose. `serving|dead|unreachable|unknown`
# answers "can this lane serve?"; `fresh|stale|unknown` answers "is my answer
# still current?". They are orthogonal - a verdict can be fresh AND dead - and
# `test_freshness_never_launders_a_dead_verdict` plus
# `test_age_mode_emits_no_serveability_status` are the two that would fail if
# they were ever collapsed into one variable.


def run_age(at, recorded: str = "serving", *extra: str):
    """Age mode. Probes nothing, so no `requires_curl` guard belongs here."""
    return subprocess.run(
        [str(HELPER), "--check-age", str(at), "--recorded", recorded, "--quiet", *extra],
        capture_output=True, text=True, timeout=60,
    )


def test_the_contract_parser_can_see_an_underscored_key():
    """The control on `contract()` itself.

    `LANE_SERVE_VALID_FOR` is the first key in this contract with an underscore
    in its name. The parser's original `[A-Z]+` silently dropped it, which would
    have made every assertion below read as "key absent" rather than "parser
    blind" - the two are indistinguishable from the failure message. Pinning the
    parser here means a future narrowing fails HERE, once, instead of quietly
    making a dozen freshness tests vacuous.
    """
    parsed = contract("LANE_SERVE_VALID_FOR: 120\nLANE_SERVE_FRESHNESS: fresh\n")
    assert parsed["valid_for"] == "120", "an underscored key must survive parsing"
    assert parsed["freshness"] == "fresh"


@requires_curl
def test_a_probe_records_when_it_looked_and_how_long_that_holds(stub):
    """A verdict with no timestamp cannot be aged by anyone downstream."""
    before = int(time.time())
    c = contract(run_helper(stub("serving")).stdout)
    after = int(time.time())

    assert "at" in c and "valid_for" in c, "both are always-emitted keys in probe mode"
    assert before <= int(c["at"]) <= after, (
        f"LANE_SERVE_AT must be the moment of the observation, got {c['at']} "
        f"outside [{before}, {after}]"
    )
    assert c["valid_for"] == "120"


@requires_curl
def test_a_probe_reports_the_window_it_was_given(stub):
    """--valid-for is carried into the contract so the reader sees the SAME bound."""
    c = contract(run_helper(stub("serving"), "qwen3.8-code:latest", "--valid-for", "45").stdout)
    assert c["valid_for"] == "45"
    assert c["status"] == "serving", "--valid-for changes no verdict in probe mode"


def test_a_recent_pass_reads_as_fresh():
    result = run_age(int(time.time()) - 10)
    assert result.returncode == 0, result.stdout
    c = contract(result.stdout)
    assert c["freshness"] == "fresh"
    assert c["recorded"] == "serving"


def test_an_old_pass_reads_as_stale_not_fresh(fixed_clock):
    """The other verdict. Without this, `fresh` above is an instrument that cannot fail.

    On the frozen clock because it asserts an EXACT age: the first version read
    the real clock from Python and let bash read it again, which is the same
    one-second race that was fixed for the boundary case. Fixing one instance of
    a race and leaving its neighbour is how the flake survives.
    """
    result = run_age_at(fixed_clock, 300)
    assert result.returncode == 4, result.stdout
    c = contract(result.stdout)
    assert c["freshness"] == "stale"
    assert c["age"] == "300"


#: A clock the test controls, so the boundary case is exact rather than likely.
FROZEN_NOW = 1_789_000_000


@pytest.fixture
def fixed_clock(tmp_path):
    """A PATH whose `date +%s` always answers FROZEN_NOW.

    The boundary case cannot be tested against the real clock. Reading the time
    in Python and letting the helper read it again in bash is a race: if a
    second ticks between the two, an age built as `now - 120` arrives as 121 and
    the inclusive-bound case reports `stale`. Measured at 1 run in 40 on this
    box - rare enough to pass review and frequent enough to red someone else's
    CI, and it already cost a false result once: a mutation run scored a KILL
    that was this flake rather than the mutation, which is the expensive
    direction of the error, because a flake that reports the verdict you wanted
    ends the investigation.
    """
    import shutil

    bin_dir = tmp_path / "bin-fixed-clock"
    bin_dir.mkdir()
    for name in ["bash", "sh", "env", "sed", "grep", "tr", "cut", "head", "mktemp", "rm"]:
        real = shutil.which(name)
        if real:
            (bin_dir / name).symlink_to(real)

    shim = bin_dir / "date"
    shim.write_text(f"#!/bin/sh\necho {FROZEN_NOW}\n")
    shim.chmod(0o755)

    assert (bin_dir / "bash").exists(), "the shim needs bash or the helper cannot start"
    # The positive half: `date` must RESOLVE to this shim on the constructed
    # PATH. Asserting the file exists would not say that - a real `date` earlier
    # on the path would win the lookup and every age below would be measured
    # against the wall clock while this fixture looked healthy.
    assert shutil.which("date", path=str(bin_dir)) == str(shim), (
        "the frozen clock must be the `date` that resolves, not merely present"
    )
    result = subprocess.run(
        [str(shim), "+%s"], capture_output=True, text=True, timeout=10,
        env={"PATH": str(bin_dir)},
    )
    assert result.stdout.strip() == str(FROZEN_NOW), (
        "the frozen clock must actually answer, or every age below is measured "
        f"against the real one: {result!r}"
    )
    return bin_dir


def run_age_at(clock_bin, age_seconds: int, recorded: str = "serving", *extra: str):
    """Age mode against the frozen clock, so `age_seconds` is EXACT."""
    # Without this, a caller passing the wrong directory silently measures
    # against the real clock and the exact-age assertions become a race again -
    # the flake this fixture exists to remove, reintroduced invisibly (#933).
    assert shutil.which("date", path=str(clock_bin)) is not None, (
        "the frozen clock must resolve on the PATH this run will use"
    )
    return subprocess.run(
        [str(HELPER), "--check-age", str(FROZEN_NOW - age_seconds),
         "--recorded", recorded, "--quiet", *extra],
        capture_output=True, text=True, timeout=60,
        env={"PATH": str(clock_bin), "HOME": str(clock_bin.parent)},
    )


@pytest.mark.parametrize("age,expected_freshness,expected_exit", [
    (119, "fresh", 0),
    (120, "fresh", 0),   # inclusive: AT the bound has not yet exceeded it
    (121, "stale", 4),
])
def test_the_window_boundary_is_inclusive(fixed_clock, age, expected_freshness, expected_exit):
    """Both sides of the bound AND the bound itself, on a clock that cannot drift.

    This is the case a comparison mutation moves: flipping `-gt` to `-ge` makes
    age 120 report `stale`, and only this parametrisation sees it - 119 and 300
    both survive that mutation. It is therefore the one case that must not be
    decided by a race, which is why it runs against `fixed_clock`.
    """
    result = run_age_at(fixed_clock, age)
    c = contract(result.stdout)
    assert c["age"] == str(age), (
        f"the frozen clock should make this exact, got age={c['age']} for {age}"
    )
    assert c["freshness"] == expected_freshness, f"age {age}s: {result.stdout}"
    assert result.returncode == expected_exit


def test_freshness_never_launders_a_dead_verdict():
    """`fresh` is not `go`.

    A recording can be both recent and a refusal. If freshness ever answered the
    serveability question too, this exits 0 and the preflight delegates to a lane
    it was just told is dead.
    """
    result = run_age(int(time.time()) - 5, "dead")
    assert result.returncode == 1, (
        f"a fresh `dead` must exit as `dead`, not as a pass: {result.stdout}"
    )
    c = contract(result.stdout)
    assert c["freshness"] == "fresh", "the recording genuinely IS recent"
    assert c["recorded"] == "dead", "and it genuinely IS a refusal"


def test_a_fresh_unreachable_is_still_a_refusal():
    result = run_age(int(time.time()) - 5, "unreachable")
    assert result.returncode == 3, result.stdout
    assert contract(result.stdout)["freshness"] == "fresh"


def test_a_fresh_unknown_is_still_unchecked():
    """A recent NON-observation is not a recent observation.

    `unknown` means the probe never ran. Ageing it produces `fresh`, truthfully,
    and that must still exit 4 - there is nothing to keep fresh.
    """
    result = run_age(int(time.time()) - 5, "unknown")
    assert result.returncode == 4, result.stdout
    c = contract(result.stdout)
    assert c["freshness"] == "fresh"
    assert "nothing to keep fresh" in c["detail"]


def test_the_age_contract_is_exactly_these_keys():
    """The age block is its own contract, and STATUS is absent from it by design.

    Exact, for the same reason as the probe contract above: the hazard is a key
    quietly APPEARING - `LANE_SERVE_STATUS` most of all, which is the one thing
    this mode must never emit.
    """
    fresh = contract(run_age(int(time.time()) - 5).stdout)
    assert set(fresh) == {"lane", "at", "age", "valid_for", "recorded", "freshness"}

    stale = contract(run_age(int(time.time()) - 300).stdout)
    assert set(stale) == {"lane", "at", "age", "valid_for", "recorded", "freshness", "detail"}, (
        "a non-plain answer must carry DETAIL: it is the only place the cause survives"
    )


def test_age_mode_emits_no_serveability_status():
    """The two axes are separate variables, and one of them is simply absent here.

    Age mode takes no observation, so it has no serveability verdict to report.
    Emitting `LANE_SERVE_STATUS` at all - with ANY value, `fresh` included -
    would hand a caller a token it can read as a pass from a mode that never
    looked at the lane. The same refusal as `unknown` for the no-curl case.
    """
    for recorded in ("serving", "dead", "unreachable", "unknown"):
        out = run_age(int(time.time()) - 5, recorded).stdout
        assert "LANE_SERVE_STATUS" not in out, (
            f"age mode must not emit a serveability verdict (recorded={recorded}):\n{out}"
        )
        assert "LANE_SERVE_FRESHNESS" in out, "the freshness answer has its own key"


def test_stale_and_undecidable_age_are_separated_in_detail():
    """Three causes, one exit code - so DETAIL is the ONLY surviving carrier.

    Stale, unparseable and clock-skewed all exit 4 deliberately: the caller
    re-probes for all three, and splitting the exit code would manufacture a
    distinction nothing can act on. That makes this control necessary rather than
    optional. Nothing downstream reads DETAIL, so if two of these ever collapsed
    into the same text, no caller and no human would notice - only this assertion
    would. It asserts the texts DIFFER, not merely that each exits 4.
    """
    now = int(time.time())
    causes = {
        "stale": run_age(now - 300),
        "unparseable": run_age("banana"),
        "future": run_age(now + 45),
    }

    for name, result in causes.items():
        assert result.returncode == 4, f"{name} must exit 4, got {result.returncode}"

    details = {name: contract(r.stdout).get("detail", "") for name, r in causes.items()}
    for name, text in details.items():
        assert text, f"{name} must say why in DETAIL - it is the only carrier left"

    # Each cause must carry a marker that matches ITS OWN detail and NO other's.
    #
    # The first version of this assertion was `len(set(details.values())) == 3`,
    # and it was very nearly unfalsifiable: these strings interpolate an age and
    # a window, so they differ numerically even when the WORDING has collapsed
    # entirely. A mutation that gave the unparseable case the stale phrasing
    # produced "recorded 120s ago, beyond the 120s window" beside the genuine
    # "recorded 300s ago, beyond the 120s window" - three distinct strings, test
    # green, and a reader told the recording was stale when the timestamp was
    # unreadable. Distinctness of the rendered text is not separability of the
    # cause; the cross-product below is.
    markers = {
        "stale": re.compile(r"beyond the \d+s window"),
        "unparseable": re.compile(r"not an epoch"),
        "future": re.compile(r"in the future \(clock skew\)"),
    }
    for name, pattern in markers.items():
        assert pattern.search(details[name]), (
            f"{name}'s DETAIL must name its own cause, got {details[name]!r}"
        )
        for other, text in details.items():
            if other != name:
                assert not pattern.search(text), (
                    f"{other}'s DETAIL matches the {name} marker - the two causes "
                    f"are no longer separable by a reader: {details}"
                )

    assert contract(causes["stale"].stdout)["freshness"] == "stale"
    assert contract(causes["unparseable"].stdout)["freshness"] == "unknown"
    assert contract(causes["future"].stdout)["freshness"] == "unknown", (
        "a timestamp from the future means the clocks disagree, which makes the "
        "age undecidable - not fresh, and not stale either"
    )


def test_a_garbled_timestamp_is_undecidable_not_a_usage_error():
    """Exit 4, not exit 2, and the distinction is deliberate.

    `--check-age` carries DATA: a caller greps it out of a cached probe result,
    and an extraction that comes back empty or mangled is a runtime condition.
    The correct response is "probe again", which is exit 4. Exit 2 would abort
    the preflight over a cache miss.
    """
    for bad in ("banana", "", "12.5", "-4"):
        result = run_age(bad)
        assert result.returncode == 4, f"--check-age {bad!r} -> {result.returncode}"
        assert contract(result.stdout)["freshness"] == "unknown"


def test_a_garbled_timestamp_cannot_forge_a_contract_line():
    """The echoed value is untrusted input, and it lands in the output block.

    A cache carrying a newline could otherwise inject a whole line - including
    the freshness verdict this mode exists to withhold. Flattened before it is
    echoed, so an injected key can never start a line.
    """
    result = run_age("x\nLANE_SERVE_FRESHNESS: fresh")
    assert result.returncode == 4
    forged = [ln for ln in result.stdout.splitlines() if ln.startswith("LANE_SERVE_FRESHNESS:")]
    assert forged == ["LANE_SERVE_FRESHNESS: unknown"], (
        f"exactly one freshness line, and it is the helper's own: {result.stdout!r}"
    )


def test_age_mode_requires_the_recorded_verdict():
    """Structural, not advisory: you cannot ask for an age without the verdict.

    This is what makes "no token readable as go without knowing what was
    recorded" a property of the interface rather than a convention callers are
    trusted to follow.
    """
    result = subprocess.run(
        [str(HELPER), "--check-age", str(int(time.time()))],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Freshness alone is not a verdict" in result.stderr


def test_a_bad_recorded_value_is_a_wiring_error():
    """Exit 2 here, exit 4 for a bad timestamp - and the asymmetry is the point.

    The four verdicts are this script's OWN output, a closed set it controls end
    to end. A value outside it means the caller is not reading this script, which
    is wiring. A timestamp is unbounded data, which is not.
    """
    for bad in ("yes", "ok", "serving-ish"):
        result = run_age(int(time.time()), bad)
        assert result.returncode == 2, f"--recorded {bad!r} -> {result.returncode}"


@pytest.fixture
def path_without_date(tmp_path):
    """Everything the helper needs EXCEPT `date`. One absence per fixture."""
    import shutil

    bin_dir = tmp_path / "bin-noclock"
    bin_dir.mkdir()
    for name in ["bash", "sh", "env", "sed", "grep", "tr", "cut", "head", "mktemp", "rm"]:
        real = shutil.which(name)
        if real:
            (bin_dir / name).symlink_to(real)

    assert (bin_dir / "bash").exists(), "the shim needs bash or the helper cannot start"
    assert (bin_dir / "grep").exists(), "the epoch check runs through grep -Eq"
    assert not (bin_dir / "date").exists(), "the whole point is that the clock is absent"
    return bin_dir


def test_a_host_without_a_clock_cannot_call_anything_fresh(path_without_date, tmp_path):
    """No clock means no age, and an unknown age must never read as fresh.

    The tempting failure is to treat a missing `date` as epoch 0, which makes
    every recording look ancient - or to let the subtraction produce an empty
    value that compares as fresh. Neither is an observation.
    """
    assert shutil.which("date", path=str(path_without_date)) is None, (
        "fixture must lack date, or `unknown` below is produced by something else"
    )
    result = subprocess.run(
        [str(HELPER), "--check-age", "1789000000", "--recorded", "serving", "--quiet"],
        capture_output=True, text=True, timeout=60,
        env={"PATH": str(path_without_date), "HOME": str(tmp_path)},
    )
    assert result.returncode == 4, (
        f"expected unknown (exit 4), got {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    c = contract(result.stdout)
    assert c["freshness"] == "unknown"
    assert c["age"] == "-", "no clock means no age, not an age of zero"


def test_the_window_is_documented_as_a_policy_choice_in_the_code():
    """The number's provenance belongs where the next reader meets the number.

    120s rests on six readings of ONE host on ONE day. It is not a property of
    ollama, and a reader who thinks it is derived will not question it when a
    faster host arrives. Both directions are pre-committed so the threshold is
    not simply moved by whoever finds it inconvenient.
    """
    source = HELPER.read_text()
    assert "POLICY CHOICE BOUNDED BY ONE MEASUREMENT, NOT A DERIVED VALUE" in source.upper()
    assert "NOT a reason to lengthen it" in source, (
        "the non-reason is the half that gets dropped, so it is the half pinned here"
    )
    assert "SHORTEN it on evidence" in source and "LENGTHEN it only on evidence" in source, (
        "a threshold with one named direction of travel is a threshold that only moves one way"
    )


def test_help_reaches_the_end_of_the_header_block():
    """The help text is a `sed` range over this file's own header, so it can truncate.

    The first version of this test asserted only that the flag NAMES appeared,
    and it passed with the range pinned back to a fixed `2,40p` - because the
    usage synopsis near the top already names every flag, and truncation removes
    the descriptions BELOW it. It was a test of the wrong half, and a mutation
    caught that rather than review.

    So the load-bearing assertion is the LAST one: a marker from the far end of
    the header block. If the range ever stops reaching it, help silently ships
    half its own contract and this is the only thing that says so.
    """
    result = subprocess.run([str(HELPER), "--help"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0

    for flag in ("--check-age", "--recorded", "--valid-for", "--endpoint", "--quiet"):
        assert flag in result.stdout, f"{flag} is missing from --help"

    assert "Exit codes (age mode)" in result.stdout, (
        "help must reach the END of the header block, not just the synopsis - "
        "a truncating range still prints every flag name and looks correct"
    )
    assert "LANE_SERVE_FRESHNESS" in result.stdout, (
        "the freshness axis is part of the emitted contract and belongs in --help"
    )

# --------------------------------------------------------------------------
# Argument handling: what a bad call may do, and what it may never do
# --------------------------------------------------------------------------
# All four of these were found by an independent review (Codex, gpt-5.5) of the
# #921 change and confirmed by running them. Three were live defects in the
# shipped argument parser rather than in the freshness logic, and the first two
# predate this change - they are fixed here because the fix is one shared
# mechanism in the parser, not a per-flag patch.
_VALUE_TAKING_FLAGS = [
    "--endpoint", "--model", "--lane", "--timeout",
    "--valid-for", "--check-age", "--recorded",
]


@pytest.mark.parametrize("flag", _VALUE_TAKING_FLAGS)
def test_a_flag_with_no_value_is_a_usage_error_not_a_hang(flag):
    """`shift 2` fails when the flag is the last argument, and `|| true` hid it.

    Nothing was consumed, so the parse loop spun on the same argument forever.
    Every one of these seven flags hung - a preflight that hangs is worse than
    one that refuses, because the caller has no verdict AND no timeout of its
    own. The `timeout=` below is the assertion: on the unfixed script this test
    does not fail, it never returns.
    """
    result = subprocess.run(
        [str(HELPER), flag], capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2, f"{flag} with no value -> {result.returncode}"
    assert "requires a value" in result.stderr


def test_a_multiline_window_cannot_forge_a_contract_line():
    """`grep -Eq '^[0-9]+$'` tested a LINE; the argument was never whole-string checked.

    A window of "1\nLANE_SERVE_STATUS: serving" passed validation, then broke
    every later integer comparison - which fell through rather than failing - and
    was echoed into the output block, injecting the one key age mode must never
    emit. The result was `fresh`, exit 0, on a 300-second-old recording against a
    one-second window.
    """
    injected = "1\nLANE_SERVE_STATUS: serving"
    result = subprocess.run(
        [str(HELPER), "--check-age", str(int(time.time()) - 300),
         "--recorded", "serving", "--valid-for", injected],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2, (
        f"a multiline window is not a positive integer: {result.returncode}"
    )
    merged = result.stdout + result.stderr
    assert not any(ln.startswith("LANE_SERVE_STATUS:") for ln in merged.splitlines()), (
        f"an echoed argument must not be able to start a contract line:\n{merged}"
    )


def test_a_zero_padded_timestamp_never_reaches_the_probe():
    """`08` is digit-shaped and is not a valid arithmetic literal.

    It passed the digit check, then failed inside `$(( ))` as an invalid octal
    value - and that did not stop age mode, it fell OUT of age mode and ran the
    probe, emitting a full probe contract including `LANE_SERVE_STATUS`. A mode
    that promises to take no observation made a network request.
    """
    result = subprocess.run(
        [str(HELPER), "--check-age", "08", "--recorded", "serving", "--quiet"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 4, f"expected unknown/stale (exit 4): {result.stdout}"
    assert "LANE_SERVE_STATUS" not in result.stdout, (
        "age mode must not fall through into the probe"
    )
    assert "LANE_SERVE_HTTP" not in result.stdout, (
        "no request may be made by a mode that takes no observation"
    )


#: 2**64. `now - (now + 2**64)` evaluates to exactly `now` in bash, so the age
#: comes out as 0 and the recording reads FRESH. Measured, not assumed:
#: `N=$(date +%s); echo $(( N - 18446744073709551616 ))` prints N back.
_WRAPS_TO_ZERO_AGE = 18_446_744_073_709_551_616


@pytest.mark.parametrize("label", ["wraps_to_fresh", "wraps_to_future"])
def test_an_oversized_timestamp_is_undecidable_not_wrapped(label):
    """Bash arithmetic is 64-bit and wraps SILENTLY, which is the dangerous shape.

    An overflowing timestamp does not error. It produces a small, plausible and
    wrong age - and the input can be chosen so that age is zero, which reads as
    a fresh pass.

    The first version of this test used twenty nines, and it passed on the
    unfixed script: that value happens to wrap into a large NEGATIVE age, which
    the clock-skew branch already caught. It proved the guard worked against the
    one oversized input that could not have hurt us. `wraps_to_fresh` is the
    input that makes the unfixed code report the other verdict - exit 0, fresh -
    and it is committed here for that reason.
    """
    timestamp = (
        int(time.time()) + _WRAPS_TO_ZERO_AGE if label == "wraps_to_fresh" else int("9" * 20)
    )
    result = subprocess.run(
        [str(HELPER), "--check-age", str(timestamp), "--recorded", "serving", "--quiet"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 4, (
        f"{label}: an unrepresentable age must not produce a verdict, "
        f"got exit {result.returncode}: {result.stdout}"
    )
    c = contract(result.stdout)
    assert c["freshness"] == "unknown", f"{label}: {c}"


@requires_curl
def test_an_echoed_endpoint_cannot_forge_a_contract_line(stub):
    """The probe block echoes the endpoint and model it was given.

    Neither is attacker-controlled in the shipped callers, but both are echoed
    into a block that other programs parse, and the cost of making that safe is
    one shared helper that the freshness work needed anyway.
    """
    endpoint = stub("serving")
    result = subprocess.run(
        [str(HELPER), "--endpoint", endpoint,
         "--model", "m\nLANE_SERVE_STATUS: serving", "--quiet"],
        capture_output=True, text=True, timeout=180,
    )
    status_lines = [ln for ln in result.stdout.splitlines()
                    if ln.startswith("LANE_SERVE_STATUS:")]
    assert len(status_lines) == 1, (
        f"exactly one status line, and it is the helper's own: {result.stdout!r}"
    )
