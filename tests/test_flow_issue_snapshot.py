"""Control for the /flow:auto as-read issue snapshot (issue #1081).

The FETCH needs `gh` and a live issue and is not controlled here - stubbing the
tool whose output is the subject would test the stub. So `auto.md` separates the
fetch from the two things that ARE decisions over local files: writing the
snapshot, and deciding drift. Those are extracted and run.

If a heading or a block goes missing these raise rather than silently testing
nothing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("sha256sum") is None,
    reason="requires bash and sha256sum",
)

REPO = Path(__file__).resolve().parents[1]
AUTO_MD = REPO / ".claude" / "commands" / "flow" / "auto.md"
WRITER_HEADING = "#### Also write the as-read snapshot here (issue #1081)"
VERDICT_MARKER = "Verdict - `$SNAP` is the as-read snapshot"
CAP = 16384


def _block_after(marker: str, *, must_contain: str) -> str:
    text = AUTO_MD.read_text()
    if text.count(marker) != 1:
        raise AssertionError(f"expected exactly one {marker!r}, found {text.count(marker)}")
    m = re.search(r"```bash\n(.*?)```", text.split(marker, 1)[1], re.DOTALL)
    if not m:
        raise AssertionError(f"no fenced bash block follows {marker!r}")
    snippet = re.sub(r"^   ", "", m.group(1), flags=re.M)
    if must_contain not in snippet:
        raise AssertionError(
            f"the block after {marker!r} no longer contains {must_contain!r}; these "
            f"cases would test something else:\n{snippet}"
        )
    return snippet


def writer_snippet() -> str:
    return _block_after(WRITER_HEADING, must_contain="Body digest:")


def verdict_snippet() -> str:
    return _block_after(VERDICT_MARKER, must_contain="ISSUE_DRIFT:")


def run(script: str, cwd: Path, env_lines: str = "") -> str:
    proc = subprocess.run(
        ["bash", "-c", env_lines + "\n" + script],
        cwd=cwd, capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"snippet exited {proc.returncode}\n{proc.stderr}"
    return proc.stdout


RECORD_MARKER = "Record what was read - a decision over a local file"


def record_snippet() -> str:
    return _block_after(RECORD_MARKER, must_contain="AS_READ_DIGEST=")


def write_snapshot(tmp: Path, body: str) -> Path:
    """Run the DOCUMENTED record+writer blocks over a body Step 1 would have fetched.

    The digest is computed by the DOCUMENTED block, never by this test. Supplying
    it here would make the full-body-digest case assert this file's own
    arithmetic - a test that cannot fail however wrong the procedure is.
    """
    src = tmp / "fetched.md"
    src.write_text(body)
    env = (
        f'AS_READ_TMP="{src}"\n'
        'AS_READ_UPDATED="2026-09-21T11:59:00Z"\n'
    )
    run(record_snippet() + "\n" + writer_snippet(), tmp, env)
    return tmp / "docs" / "flow-runs" / "issue-42.as-read.md"


def verdict(tmp: Path, live: Path | None) -> str:
    env = f'LIVE_TMP="{live}"\n' if live is not None else 'LIVE_TMP=""\n'
    return run(verdict_snippet(), tmp, env)


# --------------------------------------------------------------------------
# The two cases the issue requires, and neither is optional.
# --------------------------------------------------------------------------

@requires_bash
def test_an_unchanged_issue_reports_clean(tmp_path: Path) -> None:
    body = "## Acceptance\n- criterion one\n- criterion two\n"
    write_snapshot(tmp_path, body)
    live = tmp_path / "live.md"
    live.write_text(body)
    assert "ISSUE_DRIFT: clean" in verdict(tmp_path, live)


@requires_bash
def test_an_edited_issue_reports_drift_AND_NAMES_THE_CHANGED_REGION(tmp_path: Path) -> None:
    """Drift must NAME what changed, not merely that something did.

    Asserting only "drift was reported" would let `diff` degrade to "prints
    something" at the first refactor, and the argument for a diff over a boolean
    would be untested.
    """
    write_snapshot(tmp_path, "## Acceptance\n- criterion one\n- criterion two\n")
    live = tmp_path / "live.md"
    live.write_text("## Acceptance\n- criterion one\n- criterion two, now with a clause\n")

    out = verdict(tmp_path, live)

    assert "ISSUE_DRIFT: drift" in out
    assert "now with a clause" in out, f"the output does not NAME the change:\n{out}"
    assert "criterion two" in out
    assert "authority model" in out, "drift must not read as an override"


# --------------------------------------------------------------------------
# Cannot-answer must never render as clean.
# --------------------------------------------------------------------------

@requires_bash
def test_a_missing_snapshot_is_unresolved_not_clean(tmp_path: Path) -> None:
    (tmp_path / "docs" / "flow-runs").mkdir(parents=True)
    live = tmp_path / "live.md"
    live.write_text("anything\n")
    out = verdict(tmp_path, live)
    # Assert the case reached the branch it claims to test. Three branches print
    # "unresolved", so asserting the word alone would let this pass through the
    # wrong one - an instrument that answers nothing looks like one that found
    # nothing (worker-B, three instances in its own harnesses today).
    assert "ISSUE_DRIFT: unresolved" in out
    assert "no as-read snapshot" in out, f"reached a different unresolved branch:\n{out}"
    assert "clean" not in out


@requires_bash
def test_a_failed_fetch_is_unresolved_not_clean(tmp_path: Path) -> None:
    write_snapshot(tmp_path, "## Acceptance\n- criterion one\n")
    out = verdict(tmp_path, None)          # the fetch failed: LIVE_TMP is empty
    assert "ISSUE_DRIFT: unresolved" in out
    assert "clean" not in out
    assert "NOT no-drift" in out


@requires_bash
def test_a_snapshot_without_a_digest_is_unresolved(tmp_path: Path) -> None:
    snap = tmp_path / "docs" / "flow-runs" / "issue-42.as-read.md"
    snap.parent.mkdir(parents=True)
    snap.write_text("# Issue #42 as read by this run\n\nno digest line here\n")
    live = tmp_path / "live.md"
    live.write_text("anything\n")
    out = verdict(tmp_path, live)
    assert "ISSUE_DRIFT: unresolved" in out
    assert "carries no digest" in out, f"reached a different unresolved branch:\n{out}"
    assert "clean" not in out


# --------------------------------------------------------------------------
# The cap bounds what is STORED; the digest covers the FULL body.
# --------------------------------------------------------------------------

@requires_bash
def test_a_change_BEYOND_the_cap_still_reports_drift(tmp_path: Path) -> None:
    """The reason the digest is taken over the full body.

    Digesting the truncated copy would give an identical digest for any change
    past the cap - a blindness rendering as clean, in the one case the cap exists
    for.
    """
    head = "A" * CAP
    write_snapshot(tmp_path, head + "\ntail criterion: original\n")
    live = tmp_path / "live.md"
    live.write_text(head + "\ntail criterion: CHANGED\n")

    out = verdict(tmp_path, live)

    assert "ISSUE_DRIFT: drift" in out, (
        "a change beyond the storage cap went undetected - the digest is being "
        "taken over the truncated copy rather than the full body"
    )


@requires_bash
def test_a_truncated_snapshot_says_so_and_does_not_imply_no_constraints(tmp_path: Path) -> None:
    body = "B" * (CAP + 500) + "\n"
    assert len(body.encode()) > CAP, "fixture does not exceed the cap; nothing to truncate"
    snap = write_snapshot(tmp_path, body)
    text = snap.read_text()
    assert "TRUNCATED" in text
    assert "INCOMPLETE CONTEXT TO RESOLVE" in text
    assert "not an absence of further constraints" in text
    assert len(text.encode()) < CAP * 2


@requires_bash
def test_the_snapshot_records_the_full_body_digest_not_the_stored_one(tmp_path: Path) -> None:
    body = "C" * (CAP + 4096) + "\n"
    snap = write_snapshot(tmp_path, body)
    recorded = re.search(r"^- Body digest:\s+(\S+)", snap.read_text(), re.M).group(1)
    full = subprocess.run(
        ["sha256sum", "-"], input=body, capture_output=True, text=True
    ).stdout.split()[0]
    assert recorded == full, "the recorded digest is not the digest of the FULL body"


@requires_bash
def test_an_unreadable_issue_yields_an_unresolved_snapshot(tmp_path: Path) -> None:
    """Step 1 could not read the issue: the artifact must say so.

    It must not be a record that the issue was unchanged, and must not read as an
    absence of constraints.
    """
    (tmp_path / "docs" / "flow-runs").mkdir(parents=True)
    run(writer_snippet(), tmp_path, 'AS_READ_TMP=""\n')
    text = (tmp_path / "docs" / "flow-runs" / "issue-42.as-read.md").read_text()
    assert "AS_READ: unresolved" in text
    assert "NOT a record that the issue was unchanged" in text


@requires_bash
def test_the_snapshot_denies_being_the_contract(tmp_path: Path) -> None:
    """The fifth acceptance item: never what an implementer works from."""
    snap = write_snapshot(tmp_path, "## Acceptance\n- one\n")
    text = snap.read_text()
    assert "EVIDENCE OF WHAT THIS RUN READ" in text
    assert "The issue is the authority" in text
    assert "does not graduate" in text
