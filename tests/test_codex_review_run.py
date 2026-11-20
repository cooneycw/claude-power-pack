"""`scripts/codex-review-run.sh` runs the cross-model review end to end (issue #1847).

`/codex:code_review` used to print its procedure as six fenced bash blocks that
each session copied out and concatenated by hand, and nothing checked the
assembly. The blocks now live in one helper, one function per stage. These tests
drive the helper as a caller does - one bare call, then its verdict line and its
transcript - and pin the two deviations the owner approved on #1847:

1. the reviewer prompt is built inside the helper, so a context carrying `&` or
   `${...}` reaches the reviewer literally (no template substitution step);
2. the `codex exec --json` event stream goes to the retained stream file only,
   so the marker lines are not buried in event output.

The stage tests (`tests/test_code_review_*.py`) run each stage's body through
`review_stage()` below, exactly as they used to run each document block.

TWO-SIDED where it matters:
RED   codex exec fails            -> `CODEX_REVIEW: unavailable`, exit 3, never `ran`
GREEN codex exec succeeds         -> `CODEX_REVIEW: ran`, exit 0, transcript parses
RED   a transcript with no marker -> /flow:auto's reader gets nothing, never a default
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.isolated_env import ISOLATED_PATH

REPO = Path(__file__).resolve().parent.parent
HELPER = REPO / "scripts" / "codex-review-run.sh"
RECEIPT = REPO / "scripts" / "counter-model-receipt.py"
FLOW_AUTO = REPO / ".claude" / "commands" / "flow" / "auto.md"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")
requires_python3 = pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3")

STAGES = ("review_preflight", "review_collect_diff", "review_run", "review_model", "review_relay")


def review_stage(name: str) -> str:
    """The body of one stage function in the helper, as text a test can run or mutate.

    Each stage is written at column 0 between `<name>() {` and a closing `}` alone
    on a line - the former document block, unchanged.
    """
    text = HELPER.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(name)}\(\) \{{\n(.*?)^\}}\n", text, re.S | re.M)
    assert match, f"{HELPER.name} defines no stage {name!r}"
    return match.group(1)


THREAD = "thread-for-codex-review-run-test"

CODEX_STUB = """#!/bin/sh
# Stub codex (#1847). `sandbox` runs its command; `exec` prints one JSON event,
# records its argv, writes STUB_FINDINGS where --output-last-message points and
# exits STUB_EXEC_RC.
printf '%s\\n' "$1" >> "$STUB_CALLS"
if [ "$1" = --version ]; then echo "codex-cli 0.0.0-stub"; exit 0; fi
if [ "$1" = sandbox ]; then
    [ "$2" = --help ] && exit 0
    while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done
    [ "$1" = -- ] && shift
    "$@"
    exit $?
fi
if [ "$1" = exec ]; then
    out=""; prev=""
    for a in "$@"; do [ "$prev" = --output-last-message ] && out="$a"; prev="$a"; done
    printf '%s\\n' "$@" > "$STUB_ARGS"
    cat > /dev/null
    printf '{"type":"thread.started","thread_id":"%s"}\\n' "$STUB_THREAD"
    printf '%b' "$STUB_FINDINGS" > "$out"
    exit "${STUB_EXEC_RC:-0}"
fi
exit 1
"""

CLEAN = "## Findings\\n\\nNone - no defects found.\\n\\n## Red cases\\n\\nNone - no instrument changed.\\n"
WITH_FINDING = (
    "## Findings\\n\\n### [MEDIUM] an edge case\\n- File: a.txt:1\\n- Issue: x\\n- Suggestion: y\\n\\n"
    "## Red cases\\n\\nNone - no instrument changed.\\n"
)


def _git(*args: str, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A clone with an origin/main base and one committed change on top, plus stubs."""
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    for name, body in (("codex", CODEX_STUB), ("curl", "#!/bin/sh\nexit 7\n")):
        (stub_dir / name).write_text(body, encoding="utf-8")
        (stub_dir / name).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    codex_home = tmp_path / "codex-home"
    rollout_dir = codex_home / "sessions" / "2026" / "11" / "15"
    rollout_dir.mkdir(parents=True)
    rollout = [
        {"type": "session_meta", "payload": {"id": THREAD,
                                             "base_instructions": {"provenance": {"model": "stub-model-1"}}}},
        {"type": "turn_context", "payload": {"model": "stub-model-1"}},
    ]
    (rollout_dir / f"rollout-{THREAD}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rollout), encoding="utf-8")
    # python3's own directory is added: the helper's model lookup runs
    # counter-model-receipt.py, and CI's image keeps python3 outside /usr/bin.
    python_dir = Path(shutil.which("python3") or "/usr/bin/python3").parent
    # negative-fixture: allow PATH is isolation plus the stubs, not an absence
    env = {**os.environ, "HOME": str(home), "PATH": f"{stub_dir}:{python_dir}:{ISOLATED_PATH}",
           "CODEX_HOME": str(codex_home), "CM_RECEIPT": str(RECEIPT),
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
           "STUB_CALLS": str(tmp_path / "calls.txt"), "STUB_ARGS": str(tmp_path / "args.txt"),
           "STUB_THREAD": THREAD, "STUB_FINDINGS": CLEAN}
    for k in ("CODEX_REVIEW_SANDBOX", "BASE", "CONTEXT"):
        env.pop(k, None)
    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    _git("init", "-q", "--bare", cwd=upstream, env=env)
    work = tmp_path / "work"
    work.mkdir()
    _git("init", "-q", "-b", "main", cwd=work, env=env)
    _git("remote", "add", "origin", str(upstream), cwd=work, env=env)
    (work / "a.txt").write_text("a\n", encoding="utf-8")
    _git("add", "-A", cwd=work, env=env)
    _git("commit", "-qm", "base", cwd=work, env=env)
    _git("push", "-q", "origin", "main", cwd=work, env=env)
    _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=upstream, env=env)
    (work / "a.txt").write_text("a\nb\n", encoding="utf-8")
    _git("commit", "-qam", "the change", cwd=work, env=env)
    return work, env


def _review(work: Path, env: dict[str, str], *args: str, cwd: Path | None = None,
            **extra: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    transcript = work.parent / "transcript.md"
    proc = subprocess.run(["bash", str(HELPER), "--transcript", str(transcript), *args],
                          cwd=cwd or work, env={**env, **extra}, capture_output=True, text=True)
    return proc, transcript


def _calls(env: dict[str, str]) -> list[str]:
    path = Path(env["STUB_CALLS"])
    return path.read_text(encoding="utf-8").split() if path.exists() else []


def _cleanup_stream(stdout: str) -> None:
    m = re.search(r"^CODEX_REVIEW_STREAM: (\S+)$", stdout, re.M)
    if m:
        Path(m.group(1)).unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# The shape: every stage is defined, and sourcing runs nothing.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", STAGES)
def test_every_stage_is_a_function_the_tests_can_read(name: str) -> None:
    assert review_stage(name).strip(), f"stage {name} is empty"


def test_sourcing_defines_the_stages_without_running_them(tmp_path: Path) -> None:
    calls = tmp_path / "calls.txt"
    proc = subprocess.run(
        ["bash", "-c", f'source "{HELPER}" && type review_run >/dev/null && echo SOURCED'],
        env={**os.environ, "STUB_CALLS": str(calls)}, capture_output=True, text=True)
    assert proc.returncode == 0 and "SOURCED" in proc.stdout, proc.stdout + proc.stderr
    assert "CODEX_REVIEW" not in proc.stdout + proc.stderr, "sourcing ran a stage"


# --------------------------------------------------------------------------- #
# End to end: the verdict line, the transcript and the receipt reader.
# --------------------------------------------------------------------------- #

@requires_git
@requires_python3
def test_a_clean_review_runs_and_its_transcript_parses_clean(tmp_path: Path) -> None:
    work, env = _fixture(tmp_path)
    proc, transcript = _review(work, env, "--context", "issue #1847: test")
    try:
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, out
        assert proc.stdout.rstrip().splitlines()[-1] == "CODEX_REVIEW: ran", out
        text = transcript.read_text(encoding="utf-8")
        for marker in ("CODEX_REVIEW_BASE: origin/main", "CODEX_REVIEW_MODEL: codex/stub-model-1",
                       "CODEX_REVIEW_SCOPE: full", "CODEX_REVIEW_NETWORK: unverified",
                       "CODEX_REVIEW_LOCAL_CREDENTIALS: absent", "CODEX_REVIEW_STREAM: "):
            assert marker in text, f"{marker!r} missing from the transcript:\n{text}"
        assert "## Findings" in text
        parsed = subprocess.run(["python3", str(RECEIPT), "parse", str(transcript)],
                                capture_output=True, text=True)
        assert "COUNTER_MODEL_REVIEW: clean" in parsed.stdout, parsed.stdout + parsed.stderr
        found = re.search(r"^CODEX_REVIEW_STREAM: (\S+)$", text, re.M)
        assert found, text
        stream = found.group(1)
        assert THREAD in Path(stream).read_text(encoding="utf-8"), "the stream file was not retained"
    finally:
        _cleanup_stream(proc.stdout)


@requires_git
@requires_python3
def test_a_review_with_a_finding_parses_as_findings(tmp_path: Path) -> None:
    work, env = _fixture(tmp_path)
    proc, transcript = _review(work, env, STUB_FINDINGS=WITH_FINDING)
    try:
        assert proc.returncode == 0, proc.stdout + proc.stderr
        parsed = subprocess.run(["python3", str(RECEIPT), "parse", str(transcript)],
                                capture_output=True, text=True)
        assert "COUNTER_MODEL_REVIEW: findings" in parsed.stdout, parsed.stdout + parsed.stderr
    finally:
        _cleanup_stream(proc.stdout)


@requires_git
def test_a_failed_codex_exec_is_unavailable_never_ran(tmp_path: Path) -> None:
    """The red case for the verdict line: a reviewer that failed is not a review."""
    work, env = _fixture(tmp_path)
    proc, transcript = _review(work, env, STUB_EXEC_RC="1", STUB_FINDINGS="")
    try:
        assert proc.returncode == 3, proc.stdout + proc.stderr
        assert "CODEX_REVIEW: unavailable (codex exec exited 1" in proc.stdout
        assert "CODEX_REVIEW: ran" not in proc.stdout
        assert "CODEX_REVIEW_SCOPE:" in transcript.read_text(encoding="utf-8")
    finally:
        _cleanup_stream(proc.stdout)


@requires_git
def test_the_event_stream_is_not_on_stdout(tmp_path: Path) -> None:
    """Deviation 2: the stream goes to its file only, so markers are not buried."""
    work, env = _fixture(tmp_path)
    proc, _ = _review(work, env)
    try:
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert '"thread.started"' not in proc.stdout, "the JSON event stream reached stdout"
    finally:
        _cleanup_stream(proc.stdout)


@requires_git
def test_a_context_reaches_the_reviewer_literally(tmp_path: Path) -> None:
    """Deviation 1: no substitution step, so `&` and `${...}` are not rewritten."""
    work, env = _fixture(tmp_path)
    context = "issue #1: a & b ${HOME} $(echo no)"
    proc, _ = _review(work, env, "--context", context)
    try:
        assert proc.returncode == 0, proc.stdout + proc.stderr
        args = Path(env["STUB_ARGS"]).read_text(encoding="utf-8")
        assert f"Review intent/context: {context}." in args, args
    finally:
        _cleanup_stream(proc.stdout)


@requires_git
def test_a_caller_outside_a_checkout_is_unavailable_and_runs_nothing(tmp_path: Path) -> None:
    work, env = _fixture(tmp_path)
    elsewhere = tmp_path / "not-a-checkout"
    elsewhere.mkdir()
    proc, _ = _review(work, env, cwd=elsewhere)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "CODEX_REVIEW: unavailable" in proc.stderr
    assert "exec" not in _calls(env), "codex exec ran outside a checkout"


@requires_git
def test_a_base_with_no_common_ancestor_is_unavailable_by_name(tmp_path: Path) -> None:
    """Clone shape: an unreachable base (a shallow clone's case) is named, not reviewed.

    Without the merge-base guard a LATER refusal (the failed diff) still exits 3,
    so the exit code alone cannot tell the guard is there; the reason can.
    """
    work, env = _fixture(tmp_path)
    _git("checkout", "-q", "--orphan", "unrelated", cwd=work, env=env)
    _git("commit", "-qm", "unrelated root", cwd=work, env=env)
    no_ancestor = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=work, env=env,
                                 capture_output=True, text=True)
    assert no_ancestor.returncode != 0, "precondition: HEAD and origin/main share no ancestor"
    proc, _ = _review(work, env)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "CODEX_REVIEW: unavailable (no common ancestor between HEAD and origin/main" in proc.stderr
    assert "exec" not in _calls(env), "codex exec ran with no reviewable range"


@requires_git
def test_a_real_shallow_clone_with_no_reachable_ancestor_is_unavailable(tmp_path: Path) -> None:
    """Clone shape, the real thing (counter-model review): a depth-1 clone whose
    base moved on and was fetched shallow has no locally discoverable ancestor."""
    work, env = _fixture(tmp_path)
    upstream = tmp_path / "upstream.git"
    shallow = tmp_path / "shallow"
    _git("clone", "-q", "--depth", "1", f"file://{upstream}", str(shallow), cwd=tmp_path, env=env)
    (shallow / "a.txt").write_text("mine\n", encoding="utf-8")
    _git("commit", "-qam", "my change", cwd=shallow, env=env)
    # The base advances by two commits, and the clone fetches it shallow.
    _git("push", "-q", "origin", "main", cwd=work, env=env)
    (work / "a.txt").write_text("a\nb\nc\n", encoding="utf-8")
    _git("commit", "-qam", "base moves", cwd=work, env=env)
    _git("push", "-q", "origin", "main", cwd=work, env=env)
    _git("fetch", "-q", "--depth", "1", "origin", "main", cwd=shallow, env=env)
    assert (shallow / ".git" / "shallow").is_file(), "precondition: a shallow clone"
    no_ancestor = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=shallow, env=env,
                                 capture_output=True, text=True)
    assert no_ancestor.returncode != 0, "precondition: no locally discoverable ancestor"
    proc, _ = _review(shallow, env)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "no common ancestor" in proc.stderr and "git fetch --unshallow" in proc.stderr
    assert "exec" not in _calls(env)


@requires_git
def test_a_linked_worktree_is_reviewed(tmp_path: Path) -> None:
    """Checkout lane, the linked-worktree value (counter-model review)."""
    work, env = _fixture(tmp_path)
    linked = tmp_path / "linked"
    _git("worktree", "add", "-q", "-b", "issue-1-x", str(linked), cwd=work, env=env)
    (linked / "new.txt").write_text("new\n", encoding="utf-8")
    assert (linked / ".git").is_file(), "precondition: a linked worktree, not a main checkout"
    proc, transcript = _review(linked, env)
    try:
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "Untracked files included in this diff: 1" in proc.stdout, proc.stdout
        assert "CODEX_REVIEW_SCOPE: full" in transcript.read_text(encoding="utf-8")
    finally:
        _cleanup_stream(proc.stdout)


@requires_git
@pytest.mark.parametrize("enrolled", [True, False], ids=["enrolled", "not-enrolled"])
def test_a_transcript_inside_the_work_tree_is_refused_before_the_review(tmp_path: Path, enrolled: bool) -> None:
    """Counter-model review, passes 1 and 2: a transcript in the checkout is an
    untracked file the NEXT run's diff stage marks - an enrolled repository then
    blocks a clean checkpoint, and any other reviews its own previous report."""
    work, env = _fixture(tmp_path)
    if enrolled:
        (work / "docs" / "measurements" / "counter-model").mkdir(parents=True)
        (work / "docs" / "measurements" / "counter-model" / ".keep").write_text("", encoding="utf-8")
        _git("add", "-A", cwd=work, env=env)
        _git("commit", "-qm", "enrol", cwd=work, env=env)
    (work / "sub").mkdir()
    for inside in (work / "review-transcript.md", work / "sub" / "t.md"):
        proc = subprocess.run(["bash", str(HELPER), "--transcript", str(inside)], cwd=work, env=env,
                              capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "is inside the work tree" in proc.stderr
        assert not inside.exists(), "the refusal created the file it refused"
    assert _calls(env) == [], "the review ran with a transcript inside the work tree"


@requires_git
@pytest.mark.parametrize("dangling", [False, True], ids=["to-a-tracked-file", "dangling"])
def test_a_symlinked_transcript_is_refused(tmp_path: Path, dangling: bool) -> None:
    """Counter-model review, pass 3: a link from outside into the checkout passed
    the parent-directory check, and the relay overwrote the file it named."""
    work, env = _fixture(tmp_path)
    target = work / ("not-yet.md" if dangling else "a.txt")
    before = None if dangling else target.read_bytes()
    assert target.exists() is not dangling  # the precondition
    link = tmp_path / "outside" / "t.md"
    link.parent.mkdir()
    link.symlink_to(target)
    proc = subprocess.run(["bash", str(HELPER), "--transcript", str(link)], cwd=work, env=env,
                          capture_output=True, text=True)
    _cleanup_stream(proc.stdout)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "is a symlink" in proc.stderr
    assert _calls(env) == [], "the review ran with a symlinked transcript"
    if dangling:
        assert not target.exists(), "the refusal created the file the link names"
    else:
        assert target.read_bytes() == before, "a tracked file was overwritten through the link"


@requires_git
def test_a_transcript_beside_the_checkout_is_not_inside_it(tmp_path: Path) -> None:
    """The other verdict: a sibling directory whose name extends the root's is outside."""
    work, env = _fixture(tmp_path)
    sibling = tmp_path / "work-reviews"
    sibling.mkdir()
    proc = subprocess.run(["bash", str(HELPER), "--transcript", str(sibling / "t.md")], cwd=work, env=env,
                          capture_output=True, text=True)
    try:
        assert proc.returncode == 0, proc.stdout + proc.stderr
    finally:
        _cleanup_stream(proc.stdout)


@requires_git
@requires_python3
def test_the_verdict_decides_before_the_parse(tmp_path: Path) -> None:
    """Counter-model review, pass 2: a failed exec can leave a clean report.

    The parse alone reads it `clean`; only the verdict line says the review did
    not run. /flow:auto 1b must therefore branch on the verdict first.
    """
    work, env = _fixture(tmp_path)
    proc, transcript = _review(work, env, STUB_EXEC_RC="1")
    try:
        assert proc.returncode == 3 and "CODEX_REVIEW: unavailable (codex exec exited 1" in proc.stdout
        parsed = subprocess.run(["python3", str(RECEIPT), "parse", str(transcript)], capture_output=True, text=True)
        assert "COUNTER_MODEL_REVIEW: clean" in parsed.stdout, "precondition: the report itself looks clean"
        step = FLOW_AUTO.read_text(encoding="utf-8")
        step = " ".join(step[step.index("**1b. Run the review**"):step.index("**1c.")].split())
        assert "parse only `ran`" in step and "`unavailable` is a `reviewer-unavailable` skip" in step, step
    finally:
        _cleanup_stream(proc.stdout)


@requires_git
@pytest.mark.parametrize("case", ["no-ancestor", "outside-checkout"])
def test_every_early_refusal_carries_a_verdict_line(tmp_path: Path, case: str) -> None:
    """Counter-model review, pass 2: an early refusal's verdict is its
    `CODEX_REVIEW:` line on stderr, which a hint line may follow - never assume
    the last line."""
    work, env = _fixture(tmp_path)
    cwd = work
    if case == "no-ancestor":
        _git("checkout", "-q", "--orphan", "unrelated", cwd=work, env=env)
        _git("commit", "-qm", "unrelated root", cwd=work, env=env)
    else:
        cwd = tmp_path / "not-a-checkout"
        cwd.mkdir()
    proc, _ = _review(work, env, cwd=cwd)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    verdicts = [ln for ln in proc.stderr.splitlines() if ln.startswith("CODEX_REVIEW: ")]
    assert len(verdicts) == 1 and verdicts[0].startswith("CODEX_REVIEW: unavailable ("), proc.stderr
    # The family exit line (#1031) survives a stage's own `exit` and cleanup trap.
    assert proc.stderr.rstrip().splitlines()[-1] == "CODEX_REVIEW_EXIT=3", proc.stderr


@pytest.mark.skipif(not Path("/dev/full").exists(), reason="needs /dev/full")
def test_a_transcript_that_cannot_be_written_is_never_ran(tmp_path: Path) -> None:
    """Counter-model review: writes that fail mid-relay used to end in `ran`.

    /dev/full accepts the open and fails every write (ENOSPC), so it passes the
    pre-review check and fails exactly where a disk filling up would. The stages
    before the relay are stubbed; the relay and the verdict are the helper's own.
    """
    findings = tmp_path / "findings.md"
    findings.write_text("## Findings\n\nNone - no defects found.\n", encoding="utf-8")
    script = (
        f'source "{HELPER}"\n'
        "review_preflight() { :; }; review_collect_diff() { :; }; review_run() { :; }; review_model() { :; }\n"
        f'FINDINGS="{findings}"; DIFF_FILE="{tmp_path / "d.patch"}"; STREAM=/nonexistent; CODEX_EXIT=0\n'
        'codex_review_main --transcript /dev/full\n'
    )
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "CODEX_REVIEW: unavailable (the transcript '/dev/full' could not be written" in proc.stdout
    assert "CODEX_REVIEW: ran" not in proc.stdout


@requires_git
def test_a_subdirectory_caller_reviews_the_whole_change(tmp_path: Path) -> None:
    work, env = _fixture(tmp_path)
    (work / "sub").mkdir()
    proc, _ = _review(work, env, cwd=work / "sub")
    try:
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "1 file changed" in proc.stdout, proc.stdout
    finally:
        _cleanup_stream(proc.stdout)


@pytest.mark.parametrize("args", [[], ["--transcript"], ["--bogus"]], ids=["none", "no-value", "unknown"])
def test_a_usage_error_exits_2(tmp_path: Path, args: list[str]) -> None:  # binary-guard: allow exits pre-git
    calls = tmp_path / "calls.txt"
    proc = subprocess.run(["bash", str(HELPER), *args], cwd=tmp_path,
                          env={**os.environ, "STUB_CALLS": str(calls)}, capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert not calls.exists()


def test_an_unwritable_transcript_is_refused(tmp_path: Path) -> None:  # binary-guard: allow exits pre-git
    calls = tmp_path / "calls.txt"
    proc = subprocess.run(["bash", str(HELPER), "--transcript", str(tmp_path / "no" / "such" / "t.md")],
                          cwd=tmp_path, env={**os.environ, "STUB_CALLS": str(calls)},
                          capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "cannot write transcript" in proc.stderr
    assert not calls.exists()


# --------------------------------------------------------------------------- #
# The reader: /flow:auto Step 5 1d reads every receipt flag from the transcript.
# --------------------------------------------------------------------------- #

RECEIPT_FLAGS = ("STREAM", "SCOPE", "BASE", "NETWORK", "LOCAL_CREDENTIALS")


def _flow_auto_reader(transcript: Path) -> str:
    """The `m()` line /flow:auto 1d defines, pointed at `transcript`."""
    lines = [ln.strip() for ln in FLOW_AUTO.read_text(encoding="utf-8").splitlines()
             if ln.strip().startswith("m() {")]
    assert len(lines) == 1, f"/flow:auto 1d no longer defines one marker reader: {lines}"
    assert "/path/to/transcript.md" in lines[0]
    return lines[0].replace("/path/to/transcript.md", str(transcript))


def _read_flags(transcript: Path) -> dict[str, str]:
    script = _flow_auto_reader(transcript) + "\n" + "".join(
        f'printf "{flag}=%s\\n" "$(m {flag})"\n' for flag in RECEIPT_FLAGS)
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout
    return dict(line.split("=", 1) for line in out.splitlines())


@requires_git
def test_flow_autos_reader_gets_every_receipt_flag_from_a_real_transcript(tmp_path: Path) -> None:
    """Reader: /flow:auto 1d, fed the helper's real output, not a stand-in."""
    work, env = _fixture(tmp_path)
    proc, transcript = _review(work, env)
    try:
        assert proc.returncode == 0, proc.stdout + proc.stderr
        flags = _read_flags(transcript)
        found = re.search(r"^CODEX_REVIEW_STREAM: (\S+)$", proc.stdout, re.M)
        assert found, proc.stdout
        stream = found.group(1)
        assert flags == {"STREAM": stream, "SCOPE": "full", "BASE": "origin/main",
                         "NETWORK": "unverified", "LOCAL_CREDENTIALS": "absent"}, flags
    finally:
        _cleanup_stream(proc.stdout)


def test_a_marker_missing_from_the_transcript_reads_empty_never_a_default(tmp_path: Path) -> None:
    """The red case: an absent marker must reach the receipt writer as nothing.

    The writer's own choices then refuse the write; a reader that supplied a
    default here would record a measurement nobody took.
    """
    t = tmp_path / "t.md"
    t.write_text("CODEX_REVIEW_SCOPE: full\n", encoding="utf-8")
    assert "CODEX_REVIEW_NETWORK" not in t.read_text(encoding="utf-8")  # the precondition
    flags = _read_flags(t)
    assert flags["SCOPE"] == "full" and flags["NETWORK"] == "", flags
