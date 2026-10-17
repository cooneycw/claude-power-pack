"""`/codex:code_review`'s reviewer holds no GitHub credential and its network is measured (#1450).

On 2026-10-14 a `--sandbox read-only` reviewer, whose sandbox had started
(`CODEX_REVIEW_SCOPE: full`), ran `gh api .../comments --method POST` and
posted to an issue as the owner. The command doc promised "Codex cannot write
or reach the network", and nothing in the run reported otherwise. The cause was
never confirmed: (a) the read-only sandbox did not fence the network on that
host, (b) a host configuration approved a denied command into running outside
the sandbox, or (c) the caller supplied `danger-full-access`. The fix holds
under all three, so these tests pin each half rather than one cause:

- the reviewer process gets no GitHub token variable, an EMPTY `GH_CONFIG_DIR`,
  and git credential helpers that are reset, so `gh` and `git` find nothing (a
  token in a file the reviewer can read is still readable, which is why an
  open network is reported as open);
- `approval_policy="never"` is pinned on the invocation, which closes (b);
- `CODEX_REVIEW_NETWORK` is measured by a harmless GET inside the same
  sandbox, with a positive control outside it.

TWO-SIDED, by stub `codex` and `curl`:
RED   sandboxed GET succeeds              -> open (the committed negative control)
GREEN sandboxed GET fails, outside works  -> blocked
      nothing reachable even outside      -> unverified, never blocked
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.isolated_env import ISOLATED_PATH

REPO = Path(__file__).resolve().parent.parent
COMMAND = REPO / ".claude" / "commands" / "codex" / "code_review.md"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

CODEX_STUB = """#!/bin/sh
# Stub codex for #1450. `sandbox` runs the command after `--` with
# STUB_IN_SANDBOX=1 unless STUB_SANDBOX_RC says the sandbox cannot start.
# `exec` records its args and what a reviewer command would be able to use.
if [ "$1" = sandbox ]; then
    if [ "$2" = --help ]; then [ -n "$STUB_NO_SANDBOX" ] && exit 2; exit 0; fi
    # Record the invocation BEFORE `--` (#1458): both network probes must match.
    if [ -n "$STUB_SANDBOX_LOG" ]; then
        pre=""; for a in "$@"; do [ "$a" = -- ] && break; pre="$pre $a"; done
        after=""; seen=0; for a in "$@"; do [ "$seen" = 1 ] && { after="$a"; break; }; [ "$a" = -- ] && seen=1; done
        printf '%s|%s\n' "$after" "$pre" >> "$STUB_SANDBOX_LOG"
    fi
    [ "${STUB_SANDBOX_RC:-0}" != 0 ] && exit "$STUB_SANDBOX_RC"
    while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done
    [ "$1" = -- ] && shift
    STUB_IN_SANDBOX=1 "$@"
    exit $?
fi
if [ "$1" = exec ]; then
    out=""
    prev=""
    for a in "$@"; do
        [ "$prev" = --output-last-message ] && out="$a"
        prev="$a"
    done
    printf '%s\\n' "$@" > "$STUB_ARGS"
    {
        echo "GH_TOKEN=${GH_TOKEN-<unset>}"
        echo "GITHUB_TOKEN=${GITHUB_TOKEN-<unset>}"
        echo "GH_CONFIG_DIR=${GH_CONFIG_DIR-<unset>}"
        if [ -n "$GH_CONFIG_DIR" ] && [ -d "$GH_CONFIG_DIR" ]; then
            echo "GH_CONFIG_ENTRIES=$(ls -A "$GH_CONFIG_DIR" | wc -l | tr -d ' ')"
        fi
        # What a reviewer's `git push` would be handed: run the real
        # credential machinery against the configured helpers.
        echo "CREDENTIAL=$(printf 'protocol=https\\nhost=github.com\\n\\n' \\
            | git credential fill 2>/dev/null | grep '^password=' || true)"
    } > "$STUB_ENV"
    cat > /dev/null
    printf '## Findings\\n\\nNone - no defects found.\\n' > "$out"
    exit 0
fi
exit 1
"""

# Inside the sandbox stub, exit STUB_CURL_INSIDE_RC; outside it,
# STUB_CURL_OUTSIDE_RC. Both default to "unreachable".
CURL_STUB = """#!/bin/sh
if [ -n "$STUB_IN_SANDBOX" ]; then exit "${STUB_CURL_INSIDE_RC:-7}"; fi
exit "${STUB_CURL_OUTSIDE_RC:-7}"
"""

# A real mktemp, except that `-d` fails when STUB_MKTEMP_DIR_FAILS is set.
MKTEMP_STUB = """#!/bin/sh
if [ -n "$STUB_MKTEMP_DIR_FAILS" ] && [ "$1" = -d ]; then exit 1; fi
PATH=/usr/bin:/bin exec mktemp "$@"
"""


def _block(heading: str, end: str) -> str:
    text = COMMAND.read_text(encoding="utf-8")
    section = text[text.index(heading):text.index(end)]
    m = re.search(r"```bash\n(.*?)```", section, re.S)
    assert m, f"no bash block under {heading!r}"
    return m.group(1)


def _run(tmp_path: Path, **extra: str) -> tuple[subprocess.CompletedProcess[str], str, str]:
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    for name, body in (("codex", CODEX_STUB), ("curl", CURL_STUB), ("mktemp", MKTEMP_STUB)):
        f = stub_dir / name
        f.write_text(body, encoding="utf-8")
        f.chmod(0o755)
    home = tmp_path / "home"
    (home / ".config" / "gh").mkdir(parents=True)
    # The owner's credentials, exactly where gh and git would find them.
    (home / ".config" / "gh" / "hosts.yml").write_text(
        "github.com:\n    oauth_token: gho_owner\n", encoding="utf-8")
    (home / ".gitconfig").write_text(
        "[credential]\n\thelper = \"!f() { echo username=owner; echo password=from-helper; }; f\"\n",
        encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    # negative-fixture: allow PATH is isolation plus the stubs, not an absence
    base = {"HOME": str(home), "PATH": f"{stub_dir}:{ISOLATED_PATH}"}
    genv = {**os.environ, **base, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=work, env=genv, check=True, capture_output=True)
    (work / "a.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=work, env=genv, check=True, capture_output=True)
    diff = tmp_path / "d.patch"
    diff.write_text("", encoding="utf-8")
    args_file = tmp_path / "args.txt"
    env_file = tmp_path / "env.txt"
    env = {**os.environ, **base, "DIFF_FILE": str(diff), "STUB_ARGS": str(args_file),
           "STUB_ENV": str(env_file), "GH_TOKEN": "ghp_owner", "GITHUB_TOKEN": "ghp_owner2",
           **extra}
    for k in ("CODEX_REVIEW_SANDBOX", "GH_CONFIG_DIR", "GIT_CONFIG_COUNT"):
        if k not in extra:
            env.pop(k, None)
    script = (_block("### Step 3: Run the review", "### Step 4:")
              + _block("### Step 4: Relay the findings", "### Step 5:"))
    proc = subprocess.run(["bash", "-c", script], cwd=work, env=env, capture_output=True, text=True)
    args = args_file.read_text(encoding="utf-8") if args_file.exists() else ""
    seen = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    return proc, args, seen


# --------------------------------------------------------------------------- #
# The regression: what the reviewer process can USE. Each of these fails on
# main @ 63e0698, where codex exec inherited the caller's whole environment.
# --------------------------------------------------------------------------- #

@requires_git
def test_the_reviewer_holds_no_github_token(tmp_path: Path) -> None:
    proc, _, seen = _run(tmp_path, STUB_CURL_INSIDE_RC="0", STUB_CURL_OUTSIDE_RC="0")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "GH_TOKEN=<unset>" in seen, seen
    assert "GITHUB_TOKEN=<unset>" in seen, seen


@requires_git
def test_the_reviewer_cannot_read_the_owners_gh_config(tmp_path: Path) -> None:
    proc, _, seen = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m = re.search(r"^GH_CONFIG_DIR=(.*)$", seen, re.M)
    assert m and m.group(1) not in ("<unset>", ""), seen
    assert "GH_CONFIG_ENTRIES=0" in seen, seen
    assert not Path(m.group(1)).exists(), "the empty gh config dir must be removed after the run"


@requires_git
def test_git_hands_the_reviewer_no_credential(tmp_path: Path) -> None:
    """Behavioural, not an env-name check: the owner's helper in ~/.gitconfig
    would answer `git credential fill` with a password. Reset, it answers nothing."""
    proc, _, seen = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CREDENTIAL=\n" in seen, seen
    assert "from-helper" not in seen


@requires_git
def test_no_empty_gh_config_dir_means_no_review(tmp_path: Path) -> None:
    """Counter-model finding: a failed `mktemp -d` left GH_CONFIG_DIR empty, and
    gh then reads the owner's default config. Refuse instead of running."""
    proc, args, _ = _run(tmp_path, STUB_MKTEMP_DIR_FAILS="1")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "could not create an empty gh config directory" in proc.stderr
    assert args == "", "codex exec must not run with the caller's credentials"


@requires_git
def test_approval_escalation_is_pinned_off(tmp_path: Path) -> None:
    _, args, _ = _run(tmp_path)
    assert '-c\napproval_policy="never"\n' in args, args


# --------------------------------------------------------------------------- #
# CODEX_REVIEW_NETWORK, two-sided.
# --------------------------------------------------------------------------- #

@requires_git
def test_a_sandbox_that_lets_the_get_through_reports_open(tmp_path: Path) -> None:
    """The negative control: the probe CAN say open, and the banner says so."""
    proc, args, _ = _run(tmp_path, STUB_CURL_INSIDE_RC="0", STUB_CURL_OUTSIDE_RC="0")
    assert "CODEX_REVIEW_NETWORK: open" in proc.stdout, proc.stdout + proc.stderr
    assert "network: OPEN - not a network-fenced review" in proc.stdout
    assert "Do not run any command that contacts a remote service" in args


@requires_git
def test_a_sandbox_that_stops_a_reachable_get_reports_blocked(tmp_path: Path) -> None:
    proc, args, _ = _run(tmp_path, STUB_CURL_INSIDE_RC="7", STUB_CURL_OUTSIDE_RC="0")
    assert "CODEX_REVIEW_NETWORK: blocked" in proc.stdout, proc.stdout + proc.stderr
    assert "network: blocked =====" in proc.stdout
    # `blocked` measures one endpoint, so the instruction stays (codex review).
    assert "contacts a remote service" in args


# THE VERDICT TABLE (issue #1458), mirrored from the doc's network-verdict-table.
# Each row: (STUB_SANDBOX_RC, STUB_CURL_INSIDE_RC, STUB_CURL_OUTSIDE_RC, verdict).
# `blocked` needs the in-sandbox curl to have RUN and failed with a network-class
# exit while the outside control succeeds; everything else that is not `open`
# is `unverified`.
VERDICT_TABLE = [
    ("101", "0", "0", "unverified"),   # sandbox did not start (no bubblewrap): the negative control
    ("101", "7", "0", "unverified"),   # ...whatever curl would have done
    ("0", "0", "0", "open"),
    ("0", "6", "0", "blocked"),        # resolve
    ("0", "7", "0", "blocked"),        # connect
    ("0", "28", "0", "blocked"),       # timeout
    ("0", "7", "7", "unverified"),     # nothing reachable even outside
    ("0", "127", "0", "unverified"),   # curl absent inside the sandbox
    ("0", "35", "0", "unverified"),    # TLS error, not a fence
    ("0", "2", "0", "unverified"),     # a CLI usage error after a CLI change
    ("0", "56", "0", "unverified"),    # recv failure: not in the table's blocked set
]

#: The exits the table calls network-class. Widening `blocked` must edit this,
#: the doc table and the code's NET_BLOCKED_RCS together - pinned below.
BLOCKED_RCS = {"6", "7", "28"}


@requires_git
@pytest.mark.parametrize("sandbox_rc,inside_rc,outside_rc,verdict", VERDICT_TABLE)
def test_the_network_verdict_follows_the_table(tmp_path: Path, sandbox_rc: str, inside_rc: str,
                                               outside_rc: str, verdict: str) -> None:
    proc, _, _ = _run(tmp_path, STUB_SANDBOX_RC=sandbox_rc, STUB_CURL_INSIDE_RC=inside_rc,
                      STUB_CURL_OUTSIDE_RC=outside_rc)
    assert f"CODEX_REVIEW_NETWORK: {verdict}" in proc.stdout, proc.stdout + proc.stderr


def test_only_the_tables_network_class_exits_are_blocked() -> None:
    blocked_rows = {inside for _, inside, outside, v in VERDICT_TABLE if v == "blocked"}
    assert blocked_rows == BLOCKED_RCS
    text = COMMAND.read_text(encoding="utf-8")
    assert 'NET_BLOCKED_RCS="6 7 28"' in text
    table = text[text.index("<!-- network-verdict-table -->"):text.index("<!-- /network-verdict-table -->")]
    blocked = [row for row in table.splitlines() if row.rstrip().endswith("| `blocked` |")]
    expected = ("  | `curl` inside exited 6, 7 or 28 (resolve, connect, timeout) and the same GET"
                " outside succeeded | `blocked` |")
    assert blocked == [expected], blocked


@requires_git
def test_both_sandbox_probes_use_one_invocation(tmp_path: Path) -> None:
    """Master's constraint on #1458: a start-ok / curl-fail split must not be
    able to come from a flag difference between the two probes."""
    log = tmp_path / "sandbox.log"
    _run(tmp_path, STUB_SANDBOX_LOG=str(log), STUB_CURL_INSIDE_RC="7", STUB_CURL_OUTSIDE_RC="0")
    calls = dict(line.split("|", 1) for line in log.read_text(encoding="utf-8").splitlines())
    assert "true" in calls and "curl" in calls, calls
    assert calls["true"] == calls["curl"], calls


@requires_git
def test_no_sandbox_probe_is_unverified(tmp_path: Path) -> None:
    proc, _, _ = _run(tmp_path, STUB_NO_SANDBOX="1", STUB_CURL_OUTSIDE_RC="0")
    assert "CODEX_REVIEW_NETWORK: unverified" in proc.stdout, proc.stdout + proc.stderr


@requires_git
def test_caller_supplied_full_access_is_open_and_still_credential_free(tmp_path: Path) -> None:
    """Candidate (c): no sandbox at all. The network is open; the token is not there."""
    proc, _, seen = _run(tmp_path, CODEX_REVIEW_SANDBOX="danger-full-access",
                         STUB_CURL_OUTSIDE_RC="0")
    assert "CODEX_REVIEW_NETWORK: open" in proc.stdout, proc.stdout + proc.stderr
    assert "GH_TOKEN=<unset>" in seen and "GH_CONFIG_ENTRIES=0" in seen, seen


def test_the_doc_no_longer_promises_an_unmeasured_fence() -> None:
    text = COMMAND.read_text(encoding="utf-8")
    assert "cannot write or reach\n  the network" not in text
    assert "cannot modify anything" not in text
