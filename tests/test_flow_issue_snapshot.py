"""Control for the /flow:auto as-read issue snapshot (issue #1081).

The FETCH needs `gh` and a live issue and is not controlled - stubbing the tool
whose output is the subject would test the stub. Everything downstream of the
fetch is a decision over local files, and those blocks are extracted from
`auto.md` and RUN.

EACH DOCUMENTED BLOCK RUNS IN ITS OWN PROCESS. An agent executes Step 1 and Step
4 in separate shell invocations, so state held in a shell variable is gone by the
time the writer needs it. An earlier version of this file concatenated the blocks
into one shell and passed the filename in, which hid exactly that defect.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None
    or shutil.which("sha256sum") is None,
    reason="requires git, bash and sha256sum (absent in the CI validate container)",
)

REPO = Path(__file__).resolve().parents[1]
AUTO_MD = REPO / ".claude" / "commands" / "flow" / "auto.md"
RECORD_MARKER = "Record what was read - a decision over local files"
WRITER_HEADING = "#### Also write the as-read snapshot here (issue #1081)"
VERDICT_MARKER = "Verdict - `$SNAP` is the as-read snapshot"
CAP = 16384
SNAP_REL = "docs/flow-runs/issue-42.as-read.md"


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
            f"the block after {marker!r} no longer contains {must_contain!r}:\n{snippet}"
        )
    return snippet


def record_snippet() -> str:
    return _block_after(RECORD_MARKER, must_contain="sha256sum")


def writer_snippet() -> str:
    return _block_after(WRITER_HEADING, must_contain="Body digest")


def verdict_snippet() -> str:
    return _block_after(VERDICT_MARKER, must_contain="ISSUE_DRIFT")


def sh(script: str, cwd: Path, env_lines: str = "") -> str:
    """Run ONE documented block in ITS OWN process."""
    proc = subprocess.run(
        ["bash", "-c", env_lines + "\n" + script],
        cwd=cwd, capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"block exited {proc.returncode}\n{proc.stderr}"
    return proc.stdout


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "wt"
    repo.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@e.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    (repo / "f").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True,
                   capture_output=True)
    return repo


def store_body(repo: Path, body: bytes, updated: str = "2026-09-21T11:59:00Z") -> None:
    """Stand in for the FETCH only - the one part that needs `gh`."""
    gitdir = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"],
                            capture_output=True, text=True, check=True).stdout.strip()
    base = (repo / gitdir) / "flow-as-read-42"
    base.with_suffix(".body").write_bytes(body)
    base.with_suffix(".updated").write_text(updated + "\n")


def snapshot(repo: Path, body: bytes) -> Path:
    """Fetch (stood in), then RECORD and WRITE in SEPARATE processes."""
    store_body(repo, body)
    sh(record_snippet(), repo)
    sh(writer_snippet(), repo)
    return repo / SNAP_REL


def verdict(repo: Path, live: Path | None) -> str:
    return sh(verdict_snippet(), repo,
              f'LIVE_TMP="{live}"' if live is not None else 'LIVE_TMP=""')


# --------------------------------------------------------------------- the two required cases

@requires_git
def test_an_unchanged_issue_reports_clean(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    body = b"## Acceptance\n- criterion one\n- criterion two\n"
    snapshot(repo, body)
    live = tmp_path / "live.md"
    live.write_bytes(body)
    assert "ISSUE_DRIFT: clean" in verdict(repo, live)


@requires_git
def test_an_edited_issue_reports_drift_AND_NAMES_THE_CHANGED_REGION(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    snapshot(repo, b"## Acceptance\n- criterion one\n- criterion two\n")
    live = tmp_path / "live.md"
    live.write_bytes(b"## Acceptance\n- criterion one\n- criterion two, now with a clause\n")

    out = verdict(repo, live)

    assert "ISSUE_DRIFT: drift" in out
    assert "now with a clause" in out, f"the output does not NAME the change:\n{out}"
    assert "authority model" in out, "drift must not read as an override"


# --------------------------------------------------------------------- cannot-answer

@requires_git
def test_a_missing_snapshot_is_unresolved_not_clean(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    live = tmp_path / "live.md"
    live.write_bytes(b"anything\n")
    out = verdict(repo, live)
    assert "ISSUE_DRIFT: unresolved" in out
    assert "no as-read snapshot" in out, f"reached a different unresolved branch:\n{out}"
    assert "clean" not in out


@requires_git
def test_a_failed_fetch_is_unresolved_not_clean(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    snapshot(repo, b"## Acceptance\n- one\n")
    out = verdict(repo, None)
    assert "ISSUE_DRIFT: unresolved" in out
    # Pin THIS branch. "NOT no-drift" is shared with the hash-failure message, so
    # asserting it let the case pass through that branch when the fetch guard was
    # removed entirely - verified by mutating the guard to `if False:` and
    # watching this case still pass.
    assert "could not read the issue" in out, f"reached a different unresolved branch:\n{out}"
    assert "clean" not in out


@requires_git
def test_a_snapshot_without_a_digest_is_unresolved(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    snap = repo / SNAP_REL
    snap.parent.mkdir(parents=True)
    snap.write_text("# Issue #42 as read by this run\n\nno digest line\n\n## Body as read\nx\n")
    live = tmp_path / "live.md"
    live.write_bytes(b"x\n")
    out = verdict(repo, live)
    assert "ISSUE_DRIFT: unresolved" in out
    assert "usable digests" in out, f"reached a different unresolved branch:\n{out}"
    assert "clean" not in out


@requires_git
def test_a_body_quoting_a_digest_line_does_not_report_false_drift(tmp_path: Path) -> None:
    """Issue prose must not be parsed as snapshot metadata.

    An unchanged issue whose body quotes `- Body digest: example` would otherwise
    yield two extracted values and report drift with no source change at all.
    """
    repo = make_repo(tmp_path)
    # A DIGEST-SHAPED value, not prose. The extractor requires 64 hex characters,
    # so `- Body digest: example` could never collide and a fixture using it
    # proves nothing - verified by mutating the extractor to scan the whole file
    # and watching this case still pass. The real hazard is an issue that quotes
    # a real snapshot header, which people do when reporting one.
    body = (b"## Notes\nA snapshot header looks like:\n- Body digest:  "
            + b"d" * 64 + b"   (sha256 of the FULL body)\n")
    snapshot(repo, body)
    live = tmp_path / "live.md"
    live.write_bytes(body)

    out = verdict(repo, live)

    assert "ISSUE_DRIFT: clean" in out, f"issue prose was parsed as metadata:\n{out}"


@requires_git
def test_a_body_that_cannot_be_hashed_is_unresolved_not_drift(tmp_path: Path) -> None:
    """Found by test_every_unresolved_branch_has_a_case_that_PINS_IT.

    A fetched body that exists but cannot be read gives an empty digest, which
    DIFFERS from the recorded one - so without this branch the check would report
    that the issue CHANGED because it could not look at it. That is the OTHER face
    of the cannot-answer collapse: not a false clean but a false alarm, which is
    subtler because a check that fires looks like a check that is working.

    THE SKIP PROBES THE PROPERTY, NOT THE IDENTITY. `geteuid() != 0` is the proxy
    this repository has already rejected once
    (tests/test_flow_wave_registry.py:734-742): it infers "can read anything" from
    "is root", which is false for an unprivileged container entrypoint and equally
    false the other way for CAP_DAC_OVERRIDE or a filesystem that does not enforce
    permissions. So the case ATTEMPTS the read and skips only if it SUCCEEDS -
    true whatever the cause.
    """
    repo = make_repo(tmp_path)
    snapshot(repo, b"## Acceptance\n- one\n")
    live = tmp_path / "live.md"
    live.write_bytes(b"## Acceptance\n- one\n")
    live.chmod(0o000)
    try:
        try:
            live.read_bytes()
        except OSError:
            pass                      # the state is reachable here; run the case
        else:
            pytest.skip(
                "this environment can read a 000-mode file, so the unreadable-body "
                "state is unreachable and the case would assert nothing"
            )
        out = verdict(repo, live)
    finally:
        live.chmod(0o644)

    assert "ISSUE_DRIFT: unresolved" in out
    assert "could not hash the fetched body" in out, (
        f"reached a different unresolved branch:\n{out}"
    )
    assert "drift -" not in out, "an unreadable body was reported as a source change"


# --------------------------------------------------------------------- the cap

@requires_git
def test_a_change_BEYOND_the_cap_still_reports_drift(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    head = b"A" * CAP
    snapshot(repo, head + b"\ntail criterion: original\n")
    live = tmp_path / "live.md"
    live.write_bytes(head + b"\ntail criterion: CHANGED\n")

    out = verdict(repo, live)

    assert "ISSUE_DRIFT: drift" in out, (
        "a change beyond the storage cap went undetected - the digest is being taken "
        "over the truncated copy rather than the full body"
    )
    assert "CANNOT BE LOCALISED" in out, "a truncated comparison must say what it cannot do"


@requires_git
def test_the_writer_stores_at_most_the_cap_and_says_how_much(tmp_path: Path) -> None:
    """Pins the bound EXACTLY.

    A loose assertion let `head -c 16384` be replaced by `cat` while every other
    case still passed - the suite green over a writer with no bound at all.
    """
    repo = make_repo(tmp_path)
    body = b"B" * (CAP * 4)
    snap = snapshot(repo, body)
    text = snap.read_text()

    stored = text.split("\n## Body as read\n", 1)[1].split("\n[TRUNCATED", 1)[0]
    assert len(stored.encode()) <= CAP, f"writer stored {len(stored.encode())} bytes, cap is {CAP}"
    assert f"of {len(body)}" in text, "the header does not report the FULL body length"
    shown = [ln for ln in text.splitlines() if "Stored bytes" in ln]
    assert re.search(rf"- Stored bytes: {len(stored.encode())} of {len(body)}", text), (
        f"Stored bytes must report EMITTED vs FULL, not full vs full: {shown}"
    )
    assert "TRUNCATED" in text
    assert "not an absence of further constraints" in text


@requires_git
def test_truncation_never_splits_a_multibyte_character(tmp_path: Path) -> None:
    """A byte-wise cut can land inside a UTF-8 sequence and corrupt the evidence."""
    repo = make_repo(tmp_path)
    body = b"A" * (CAP - 1) + "€".encode() + b"tail\n"
    snap = snapshot(repo, body)
    raw = snap.read_bytes()
    raw.decode("utf-8")          # raises if the writer split the character
    assert "TRUNCATED" in snap.read_text()


# --------------------------------------------------------------------- honesty of the artifact

@requires_git
def test_an_unreadable_issue_yields_an_unresolved_snapshot(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "docs" / "flow-runs").mkdir(parents=True)
    sh(writer_snippet(), repo)           # no .body, no .meta: the fetch failed
    text = (repo / SNAP_REL).read_text()
    assert "AS_READ: unresolved" in text
    assert "NOT a record that the issue was unchanged" in text


@requires_git
def test_the_snapshot_records_the_full_body_digest(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    body = b"C" * (CAP + 4096) + b"\n"
    snap = snapshot(repo, body)
    m = re.search(r"^- Body digest:\s+(\S+)", snap.read_text(), re.M)
    assert m is not None, "the snapshot records no digest line at all"
    recorded = m.group(1)
    assert recorded == hashlib.sha256(body).hexdigest(), (
        "the recorded digest is not the digest of the FULL body"
    )


@requires_git
def test_the_snapshot_denies_being_the_contract(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    text = snapshot(repo, b"## Acceptance\n- one\n").read_text()
    assert "EVIDENCE OF WHAT THIS RUN READ" in text
    assert "The issue is the authority" in text
    assert "does not graduate" in text


@requires_git
def test_the_state_survives_separate_shell_invocations(tmp_path: Path) -> None:
    """The HIGH finding, pinned.

    Step 1 and Step 4 run in different processes. If the handoff rides a shell
    variable, a SUCCESSFUL fetch produces an `unresolved` snapshot - and a test
    that ran both blocks in one shell would never show it.
    """
    repo = make_repo(tmp_path)
    store_body(repo, b"## Acceptance\n- one\n")
    sh(record_snippet(), repo)                     # process 1
    sh(writer_snippet(), repo)                     # process 2, no shared environment
    text = (repo / SNAP_REL).read_text()
    assert "AS_READ: unresolved" not in text, (
        "a successful fetch produced an unresolved snapshot - the state did not "
        "survive the process boundary"
    )
    assert re.search(r"^- Body digest:\s+[0-9a-f]{64}", text, re.M)


# --------------------------------------------------------------------- the sweep, mechanised

def test_every_unresolved_branch_has_a_case_that_PINS_IT() -> None:
    """Mechanises the rule that a case must fail for the RIGHT reason.

    Three times in one session an unresolved case asserted a phrase SHARED with a
    neighbouring branch and passed through the wrong one. Twice that was caught by
    a red run; the third time only because a red run was attempted at all. A rule
    that must be remembered at each site will be forgotten at some site, so this
    enumerates the branches from the DOCUMENTED block and requires a case naming
    each - no attention required, and a branch added later fails here until it is
    pinned.

    It found the fourth branch itself: `could not hash the fetched body` had no
    case when this was written.

    WHAT THIS GREEN DOES NOT COVER: it checks that a case EXISTS, not that the
    case RUNS. A case that always skips satisfies this enumeration perfectly, and
    the pinned behaviour would then be unverified exactly where nobody is
    watching. The suite runs under xdist, so a cross-test execution record is not
    available to assert here; the mitigation is instead that every skip in this
    file probes the PROPERTY it needs rather than a proxy for it, so a skip means
    the state is genuinely unreachable and not merely that some identity differs.
    Read a skip in this file as "unreachable here", and read this green as "each
    branch is named by a case", never as "each branch was exercised".
    """
    block = verdict_snippet()
    messages = re.findall(r'unresolved\(f?"([^"]*)"', block)
    assert len(messages) >= 4, (
        f"expected at least 4 unresolved branches in the documented block, found "
        f"{len(messages)}: {messages}"
    )
    # Search ASSERTIONS ONLY. Searching the whole file would count a phrase that
    # appears in a COMMENT - including the comment explaining that this very
    # phrase is shared between two branches - and report a branch as pinned
    # because it is discussed rather than because it is asserted.
    asserts = "\n".join(
        ln for ln in Path(__file__).read_text().splitlines() if "assert " in ln
    )
    def runs_of(msg: str) -> set[str]:
        literal = re.sub(r"\{[^}]*\}", " ", msg)
        words = [w for w in re.split(r"[^A-Za-z-]+", literal) if w]
        return {" ".join(words[i:i + 2]) for i in range(max(1, len(words) - 1))}

    all_runs = [runs_of(m) for m in messages]
    unpinned = []
    for i, msg in enumerate(messages):
        # A pin must be DISTINCTIVE. A phrase this branch shares with another -
        # "could not", "this is NOT" - is satisfied by the neighbour's case, which
        # is the exact defect this enumeration exists to prevent, one level up.
        others = set().union(*(r for j, r in enumerate(all_runs) if j != i))
        distinctive = all_runs[i] - others
        if not distinctive:
            unpinned.append(f"{msg}  [NO DISTINCTIVE PHRASE - the message itself is ambiguous]")
        elif not any(run in asserts for run in distinctive):
            unpinned.append(msg)
    assert not unpinned, (
        "these unresolved branches have no case pinning their message, so a case "
        "asserting only 'unresolved' could pass through them:\n  "
        + "\n  ".join(unpinned)
    )
