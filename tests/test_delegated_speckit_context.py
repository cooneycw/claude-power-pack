"""Parent context wiring: real shell/checker inputs, bounded procedure assertions.

The order check pins what the parent is told to read, not live model compliance.
The shell parser recognizes the literal new block, not arbitrary Bash grammar.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from tests.test_speckit_context import CTX, SPEC, TASKS

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "speckit-context.py"
FIXTURES = ROOT / "tests/fixtures/delegated-speckit-context"
CALL = '~/.claude/scripts/speckit-context.py check --body-file "$BODY_FILE" --root .'
FETCH = 'if ! gh issue view 42 --json body --jq .body > "$BODY_FILE"; then'
ALLOCATE = 'BODY_FILE="$(mktemp -t delegated-body-XXXXXX.md)" || exit 1'
LINK = "../../../docs/scripts/speckit-context.md"
DRIVERS = ("codex", "qwen", "gemma")

pytestmark = [pytest.mark.skipif(shutil.which(binary) is None, reason=f"requires {binary}")
              for binary in ("git", "bash", "mktemp", "python3")]


def step_tokens(document: str):
    tokens = MarkdownIt("commonmark").parse(document)
    starts = [i for i, token in enumerate(tokens[:-1]) if token.type == "heading_open"
              and token.tag == "h3" and token.level == 0 and tokens[i + 1].content.startswith("Step 2:")]
    if len(starts) != 1:
        return []
    start = starts[0]
    end = next((i for i in range(start + 3, len(tokens)) if tokens[i].type == "heading_open"
                and tokens[i].tag == "h3" and tokens[i].level == 0), len(tokens))
    return tokens[start + 3:end]


def active_lines(code: str):
    return [line.strip() for line in code.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def context_block(document: str) -> str:
    blocks = [token.content for token in step_tokens(document) if token.type == "fence" and token.info == "bash"
              and CALL in active_lines(token.content)]
    assert len(blocks) == 1, "one active parent context block is required"
    return blocks[0]


def context_contract(document: str) -> bool:
    tokens = step_tokens(document)
    try:
        code = context_block(document)
    except AssertionError:
        return False
    lines = active_lines(code)
    if ALLOCATE not in lines or FETCH not in lines or "<<" in code:
        return False
    fetch = lines.index(FETCH)
    end = next((i for i in range(fetch + 1, len(lines)) if lines[i] == "fi"), -1)
    if not (lines.index(ALLOCATE) < fetch < end < lines.index(CALL)):
        return False
    if "exit 1" not in lines[fetch + 1:end] or not any("STOP:" in line for line in lines[fetch + 1:end]):
        return False
    if 'echo "Context unchecked: checker unavailable; read the source directly."' not in lines:
        return False
    plans = [i for i, token in enumerate(tokens) if token.type == "inline"
             and token.content.startswith("**Build the ") and "prompt:" in token.content]
    reads = [i for i, token in enumerate(tokens) if token.type == "inline"
             and "otherwise read the reference source before building the prompt" in " ".join(token.content.split())]
    blocks = [i for i, token in enumerate(tokens) if token.type == "fence" and token.content == code]
    if len(plans) != 1 or len(reads) != 1 or not blocks or not blocks[0] < reads[0] < plans[0]:
        return False
    policy = tokens[reads[0]]
    return (any(child.type == "link_open" and child.attrGet("href") == LINK for child in policy.children or [])
            and "`absent` is ordinary" in " ".join(policy.content.split())
            and (ROOT / "docs/scripts/speckit-context.md").is_file())


def document(driver: str) -> str:
    return (ROOT / f".claude/commands/{driver}/auto.md").read_text()


@pytest.mark.parametrize("driver", DRIVERS)
def test_actual_parent_context_precedes_prompt(driver):
    assert context_contract(document(driver)), driver


@pytest.mark.parametrize("case", ("good", "unchecked-fetch", "fixed-body-file", "commented-checker",
                                  "missing-checker", "missing-source-read", "late-source-read"))
def test_committed_procedure_controls(case):
    text = (FIXTURES / f"{case}.md").read_text()
    if case == "unchecked-fetch":
        assert FETCH not in text
    elif case == "fixed-body-file":
        assert "mktemp" not in text
    elif case == "commented-checker":
        assert "# " + CALL in text
    elif case == "missing-checker":
        assert CALL not in text
    elif case == "missing-source-read":
        assert "otherwise read the reference source" not in text
    elif case == "late-source-read":
        assert text.index("otherwise read the reference source") > text.index("3. **Build")
    assert context_contract(text) is (case == "good")


@pytest.fixture(params=("main", "linked"))
def project(tmp_path, request):
    main = tmp_path / "project"
    main.mkdir()
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    feature = main / "specs/exports"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text(SPEC)
    (feature / "tasks.md").write_text(TASKS)
    subprocess.run(["git", "-C", str(main), "add", "."], check=True)
    subprocess.run(["git", "-C", str(main), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-qm", "fixture"], check=True)
    if request.param == "linked":
        work = tmp_path / "linked"
        subprocess.run(["git", "-C", str(main), "worktree", "add", "--detach", str(work), "HEAD"],
                       capture_output=True, check=True)
    else:
        work = main
    home = tmp_path / "home"
    scripts = home / ".claude/scripts"
    scripts.mkdir(parents=True)
    log = tmp_path / "checks.log"
    installed = scripts / "speckit-context.py"
    installed.write_text(f"#!{sys.executable}\nimport os,sys\nfrom pathlib import Path\n"
                         "with Path(os.environ['CHECK_LOG']).open('a') as out:\n"
                         " out.write(sys.argv[sys.argv.index('--body-file')+1]+'\\n')\n"
                         f"os.execv(sys.executable,[sys.executable,{str(HELPER)!r},*sys.argv[1:]])\n")
    installed.chmod(0o755)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    gh = binaries / "gh"
    gh.write_text(f"#!{sys.executable}\nimport os,sys\nfrom pathlib import Path\n"
                  "assert sys.argv[1:]==['issue','view','42','--json','body','--jq','.body']\n"
                  "Path(os.environ['GH_LOG']).write_text('called')\n"
                  "sys.stdout.write(Path(os.environ['FETCH_BODY']).read_text())\n"
                  "sys.exit(int(os.environ['FETCH_STATUS']))\n")
    gh.chmod(0o755)
    body = tmp_path / "body.md"
    body.write_text("An ordinary issue.\n")
    temp = tmp_path / "tmp"
    temp.mkdir()
    assert gh.is_file() and installed.is_file()
    env = dict(os.environ, HOME=str(home), PATH=str(binaries) + os.pathsep + os.environ["PATH"], TMPDIR=str(temp),
               CHECK_LOG=str(log), GH_LOG=str(tmp_path / "gh.log"), FETCH_BODY=str(body), FETCH_STATUS="0")
    assert shutil.which("gh", path=env["PATH"]) == str(gh)
    return work, env, log, body, installed


def execute(code, project):
    work, env, *_ = project
    return subprocess.run(["bash", "-c", code], cwd=work, env=env, text=True, capture_output=True, timeout=20)


@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("partial", (False, True))
def test_failed_fetch_stops_before_check(driver, partial, project):
    _, env, log, body, _ = project
    env["FETCH_STATUS"] = "17"
    body.write_text("partial response" if partial else "")
    assert env["FETCH_STATUS"] != "0"
    done = execute(context_block(document(driver)), project)
    assert done.returncode == 1 and "STOP:" in done.stdout
    assert not log.exists() and "SPECKIT_CONTEXT_STATE:" not in done.stdout


@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("caller", ("target", "cpp-root"))
def test_ordinary_context_uses_unique_files(driver, caller, project):
    _, _, log, _, _ = project
    code = context_block(document(driver))
    if caller == "cpp-root":
        project = (ROOT, *project[1:])
    for _ in range(2):
        done = execute(code, project)
        assert done.returncode == 0 and "SPECKIT_CONTEXT_STATE: absent" in done.stdout
    paths = log.read_text().splitlines()
    assert len(paths) == 2 and paths[0] != paths[1]
    assert all(Path(path).read_text() == "An ordinary issue.\n" for path in paths)


@pytest.mark.parametrize("driver", DRIVERS)
@pytest.mark.parametrize("changed", (False, True))
def test_real_context_and_source_read_policy(driver, changed, project):
    work, _, _, body, installed = project
    installed.unlink()
    installed.symlink_to(HELPER)
    assert installed.samefile(HELPER)
    body.write_text(CTX.render(CTX.resolve(work / "specs/exports/tasks.md", "T001", work), "specs/exports/tasks.md"))
    if changed:
        source = work / "specs/exports/spec.md"
        source.write_text(source.read_text().replace("200ms", "100ms"))
        assert "100ms" in source.read_text()
    done = execute(context_block(document(driver)), project)
    assert done.returncode == (3 if changed else 0), done.stderr
    assert f"SPECKIT_CONTEXT_STATE: {'changed-in-scope' if changed else 'current'}" in done.stdout
    assert "source=specs/exports/spec.md" in done.stdout
    assert context_contract(document(driver))  # Procedure order, not a live parent-read claim.


@pytest.mark.parametrize("driver", DRIVERS)
def test_missing_checker_is_unchecked_not_absent(driver, project):
    *_, installed = project
    installed.unlink()
    assert not installed.exists()
    done = execute(context_block(document(driver)), project)
    assert done.returncode == 0 and "Context unchecked: checker unavailable" in done.stdout
    assert "SPECKIT_CONTEXT_STATE: absent" not in done.stdout


@pytest.mark.parametrize("driver", DRIVERS)
def test_allocation_failure_stops_before_fetch(driver, project):
    _, env, log, _, _ = project
    binary = Path(env["PATH"].split(os.pathsep)[0]) / "mktemp"
    binary.write_text(f"#!{sys.executable}\nraise SystemExit(1)\n")
    binary.chmod(0o755)
    assert shutil.which("mktemp", path=env["PATH"]) == str(binary)
    done = execute(context_block(document(driver)), project)
    assert done.returncode == 1
    assert not Path(env["GH_LOG"]).exists() and not log.exists()


def test_unguarded_fetch_control_demonstrates_false_absent(project):
    _, env, log, body, _ = project
    env["FETCH_STATUS"] = "17"
    body.write_text("")
    assert not body.read_text() and env["FETCH_STATUS"] != "0"
    code = context_block((FIXTURES / "unchecked-fetch.md").read_text())
    done = execute(code, project)
    assert done.returncode == 0 and "SPECKIT_CONTEXT_STATE: absent" in done.stdout and log.exists()
