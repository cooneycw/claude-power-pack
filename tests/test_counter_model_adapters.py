"""Schema-5 adapter/binding controls use owned runtime-shaped evidence, no model calls."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("CPP_ADAPTER_TEST_SCRIPT", ROOT / "scripts/counter-model-receipt.py"))
CASES = Path(__file__).parent / "fixtures/counter_model/adapters.json"
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="artifact binding requires git")


def load():
    spec = importlib.util.spec_from_file_location("adapters", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True, stderr=subprocess.PIPE).strip()


@pytest.fixture
def evidence(tmp_path: Path):
    if shutil.which("git") is None:
        pytest.skip("artifact binding requires git")
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    (repo / "file").write_text("before\n")
    git(repo, "add", "file")
    git(repo, "commit", "-qm", "base")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "switch", "-qc", "feature")
    (repo / "file").write_text("after\n")
    git(repo, "commit", "-qam", "change")
    head = git(repo, "rev-parse", "HEAD")
    patch = subprocess.check_output(
        [
            "git",
            "-c",
            "core.quotePath=true",
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--no-renames",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--binary",
            "origin/main",
            "HEAD",
            "--",
        ],
        cwd=repo,
    ).decode()
    return {"repo": repo, "head": head, "patch": patch, "tmp": tmp_path}


def runtime(
    e: dict, role: str, runtime_name: str, model: str, patch: str | None = None, probe: str | None = None
) -> list[str]:
    root = e["tmp"] / runtime_name
    root.mkdir(exist_ok=True)
    ident = f"fixture-{role}"
    input_text = f"<cpp-review-patch>\n{patch}</cpp-review-patch>" if patch is not None else "Review the change"
    if runtime_name == "codex":
        records = [
            {"type": "session_meta", "payload": {"id": ident}},
            {"type": "turn_context", "payload": {"model": model}},
            {
                "type": "response_item",
                "payload": {"role": "user", "content": [{"type": "input_text", "text": input_text}]},
            },
        ]
        if probe:
            records.append(
                {
                    "type": "event_msg",
                    "payload": {
                        "item": {
                            "type": "CommandExecution",
                            "command": ["/bin/bash", "-lc", "git rev-parse HEAD"],
                            "exit_code": 0,
                            "aggregated_output": probe + "\n",
                        }
                    },
                }
            )
        records.append(
            {
                "type": "response_item",
                "payload": {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "## Findings\n\nNone - no defects found."}],
                },
            }
        )
        (root / f"rollout-{ident}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
        return [f"--{role}-thread-id", ident, "--codex-sessions-dir", str(root)]
    if runtime_name == "qwen-code":
        ident = "00000000-0000-0000-0000-00000000000" + ("1" if role == "implementer" else "2")
        stream = root / f"{role}-exec.jsonl"
        stream.write_text(
            json.dumps(
                {
                    "type": "system",
                    "subtype": "init",
                    "qwen_code_version": "0.15.10",
                    "session_id": ident,
                    "model": model,
                }
            )
            + "\n"
        )
        chats = root / "project/chats"
        chats.mkdir(parents=True, exist_ok=True)
        records = [{"type": "user", "message": {"role": "user", "parts": [{"text": input_text}]}}]
        if probe:
            records += [
                {
                    "type": "assistant",
                    "model": model,
                    "message": {
                        "role": "model",
                        "parts": [
                            {
                                "functionCall": {
                                    "id": "probe",
                                    "name": "run_shell_command",
                                    "args": {"command": "git rev-parse HEAD"},
                                }
                            }
                        ],
                    },
                },
                {
                    "type": "tool_result",
                    "message": {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "id": "probe",
                                    "name": "run_shell_command",
                                    "response": {
                                        "output": (
                                            f"Command: git rev-parse HEAD\nOutput: {probe}\n"
                                            "Error: (none)\nExit Code: 0\nSignal: 0"
                                        )
                                    },
                                }
                            }
                        ],
                    },
                    "toolCallResult": {"callId": "probe", "status": "success", "resultDisplay": probe},
                },
            ]
        records += [
            {
                "type": "assistant",
                "model": model,
                "message": {"role": "model", "parts": [{"text": "## Findings\n\nNone - no defects found."}]},
            }
        ]
        (chats / f"{ident}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
        return [f"--{role}-exec-log", str(stream), "--qwen-projects-dir", str(root)]
    if runtime_name == "opencode":
        import sqlite3

        ident = f"ses_{role}"
        path = root / "opencode.db"
        with sqlite3.connect(path) as db:
            db.execute("create table if not exists session (id text, version text)")
            db.execute("create table if not exists message (id text, session_id text, data text)")
            db.execute("insert into session values (?, ?)", (ident, "1.18.32"))
            db.execute(
                "insert into message values (?, ?, ?)",
                (role, ident, json.dumps({"role": "assistant", "providerID": "fixture", "modelID": model})),
            )
        records = [{"type": "step_start", "sessionID": ident}]
        if probe:
            records += [
                {
                    "type": "tool_use",
                    "sessionID": ident,
                    "part": {
                        "type": "tool",
                        "tool": "bash",
                        "state": {
                            "status": "completed",
                            "input": {"command": "git rev-parse HEAD"},
                            "output": probe + "\n",
                            "metadata": {"exit": 0, "truncated": False},
                        },
                    },
                }
            ]
        records += [{"type": "text", "sessionID": ident, "part": {"text": "## Findings\n\nNone - no defects found."}}]
        stream = root / f"{role}-exec.jsonl"
        stream.write_text("".join(json.dumps(r) + "\n" for r in records))
        return [f"--{role}-exec-log", str(stream), "--opencode-db", str(path)]
    records = [
        {"type": "user", "message": {"role": "user", "content": input_text}},
        {"type": "assistant", "message": {"model": model, "content": []}},
    ]
    if probe:
        records += [
            {
                "type": "assistant",
                "message": {
                    "model": model,
                    "content": [
                        {"type": "tool_use", "id": "probe", "name": "Bash", "input": {"command": "git rev-parse HEAD"}}
                    ],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "probe", "content": probe + "\n", "is_error": False}
                    ],
                },
            },
        ]
    records += [
        {
            "type": "assistant",
            "message": {
                "model": model,
                "content": [{"type": "text", "text": "## Findings\n\nNone - no defects found."}],
            },
        }
    ]
    (root / f"{ident}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    return [f"--{role}-session-id", ident, "--claude-projects-dir", str(root)]


def write(e: dict, *args: str):
    if shutil.which("git") is None:
        pytest.skip("artifact binding requires git")
    env = os.environ.copy()
    env.pop("CODEX_THREAD_ID", None)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "write",
            "--dir",
            str(e["tmp"] / "out"),
            "--issue",
            "1584",
            "--branch",
            "feature",
            "--status",
            "ran",
            *args,
        ],
        cwd=e["repo"],
        env=env,
        text=True,
        capture_output=True,
    )


@requires_git
@pytest.mark.parametrize(
    "implementer,reviewer", [("codex", "claude"), ("claude", "codex"), ("codex", "codex"), ("claude", "claude")]
)
def test_independent_roles_accept_runtime_evidence(evidence, implementer, reviewer):
    e = evidence
    args = runtime(e, "implementer", implementer, "model-a")
    args += runtime(e, "reviewer", reviewer, "model-b", patch=e["patch"])
    result = write(e, *args)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(next((e["tmp"] / "out").glob("*.json")).read_text())
    assert receipt["schema"] == 5
    assert load().validate(receipt) == []
    assert receipt["head"] == e["head"]
    assert receipt["reviewed_artifact"]["method"] == "captured-patch"


@requires_git
@pytest.mark.parametrize("case", json.loads(CASES.read_text())["writer"])
def test_committed_writer_boundaries(evidence, case):
    e = evidence
    patch = e["patch"]
    assert "-before\n+after\n" in patch, "negative-fixture precondition: owned changed hunk"
    model = "model-a" if case["mutation"] == "same-model" else "model-b"
    if case["mutation"] == "missing":
        patch = None
    elif case["mutation"] == "wrong-patch":
        patch = patch.replace("+after\n", "+foreign\n")
        assert patch != e["patch"], "negative-fixture precondition: foreign patch"
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", model, patch=patch)
    result = write(e, *args)
    assert result.returncode != 0
    assert case["diagnostic"] in result.stderr, result.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


@requires_git
@pytest.mark.parametrize(
    "scope,probe,success", [("full", "correct", True), ("full", "wrong", False), ("full", "missing", False)]
)
def test_runtime_head_binding(evidence, scope, probe, success):
    e = evidence
    head = e["head"] if probe == "correct" else "f" * 40 if probe == "wrong" else None
    assert head == e["head"] if success else head != e["head"], "negative-fixture precondition: HEAD probe"
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", probe=head)
    result = write(e, *args, "--scope", scope)
    assert (result.returncode == 0) == success, result.stderr


@requires_git
@pytest.mark.parametrize("implementer", ["codex", "claude", "qwen-code", "opencode"])
@pytest.mark.parametrize("reviewer", ["codex", "claude", "qwen-code", "opencode"])
@pytest.mark.parametrize("same_model", [False, True])
def test_every_supported_runtime_pair_uses_one_independence_rule(evidence, implementer, reviewer, same_model):
    e = evidence
    args = runtime(e, "implementer", implementer, "model-a")
    args += runtime(e, "reviewer", reviewer, "model-a" if same_model else "model-b", probe=e["head"])
    result = write(e, *args, "--scope", "full")
    assert (result.returncode != 0) == same_model, result.stderr
    if same_model:
        assert "overlaps" in result.stderr


@requires_git
@pytest.mark.parametrize("case", json.loads(CASES.read_text())["validator"])
def test_committed_validator_boundaries(evidence, case):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    result = write(e, *args)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(next((e["tmp"] / "out").glob("*.json")).read_text())
    module = load()
    assert module.validate(receipt) == []
    changed = copy.deepcopy(receipt)
    parent = changed
    for key in case["path"][:-1]:
        parent = parent[key]
    key = case["path"][-1]
    if case.get("remove"):
        assert key in parent, "negative-fixture precondition: field to remove exists"
        del parent[key]
    else:
        assert type(parent[key]) is not type(case["value"]) or parent[key] != case["value"], (
            "negative-fixture precondition: mutation changes field"
        )
        parent[key] = case["value"]
    problems = module.validate(changed)
    assert any(case["diagnostic"] in problem for problem in problems), problems


def test_all_legacy_receipts_validate_without_migration():
    module = load()
    paths = list((ROOT / "docs/measurements/counter-model").glob("*.json"))
    assert len(paths) >= 287
    for path in paths:
        assert module.validate(json.loads(path.read_text()), str(path)) == []


@requires_git
def test_shipping_cli_cannot_inherit_the_identity_test_stub(evidence, monkeypatch):
    e = evidence
    # The sole test-helper variable changes which executable THE TEST launches.
    # Production must not read it or any fixture-module marker as a bypass.
    monkeypatch.setenv("CPP_ADAPTER_TEST_SCRIPT", str(ROOT / "tests/fixtures/counter_model/identity-cli.py"))
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "fixture binding isolation")
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b")
    env = os.environ.copy()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/counter-model-receipt.py"),
            "write",
            "--dir",
            str(e["tmp"] / "out"),
            "--issue",
            "1584",
            "--branch",
            "feature",
            "--status",
            "ran",
            *args,
        ],
        cwd=e["repo"],
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "missing captured reviewer patch" in result.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


@requires_git
@pytest.mark.parametrize("changed_context", [False, True])
def test_current_merge_base_binds_clean_updates_and_refuses_changed_patch(evidence, changed_context):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    repo = e["repo"]
    git(repo, "switch", "-q", "main")
    if changed_context:
        (repo / "file").write_text("main context\nbefore\n")
    else:
        (repo / "unrelated").write_text("main addition\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "main advances")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "switch", "-q", "feature")
    merged = subprocess.run(["git", "merge", "--no-edit", "main"], cwd=repo, capture_output=True)
    if merged.returncode:
        assert changed_context
        (repo / "file").write_text("main context\nafter\n")
        git(repo, "add", "file")
        git(repo, "commit", "-qm", "resolve updated context")
    fresh = subprocess.check_output(["git", "diff", "origin/main...HEAD"], cwd=repo).decode()
    assert (fresh != e["patch"]) == changed_context, "negative-fixture precondition: patch bytes after update"
    result = write(e, *args)
    assert (result.returncode != 0) == changed_context, result.stderr
    if changed_context:
        assert "captured reviewer patch differs" in result.stderr
    else:
        receipt = json.loads(next((e["tmp"] / "out").glob("*.json")).read_text())
        assert receipt["head"] == git(repo, "rev-parse", "HEAD")
        assert receipt["reviewed_artifact"]["base_sha"] == git(repo, "rev-parse", "origin/main")


@requires_git
@pytest.mark.parametrize("mutation", ["missing-file", "damaged", "duplicate", "typed-model", "late-probe"])
def test_unresolved_runtime_evidence_is_unknown_and_writes_nothing(evidence, mutation):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=e["patch"], probe=e["head"])
    path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    original = path.read_bytes()
    assert original and path.is_file(), "negative-fixture precondition: real owned transcript exists"
    if mutation == "missing-file":
        path.unlink()
    elif mutation == "damaged":
        path.write_bytes(original + b'{"type":')
    elif mutation == "duplicate":
        duplicate = path.parent / "copy" / path.name
        duplicate.parent.mkdir()
        duplicate.write_bytes(original)
        assert len(list(path.parent.rglob(path.name))) == 2, "negative-fixture precondition: two matches"
    else:
        records = [json.loads(line) for line in original.split(b"\n") if line]
        if mutation == "typed-model":
            records = [
                {
                    "type": "user",
                    "message": {"role": "user", "content": 'The reviewer model is model-b. {"model":"model-b"}'},
                }
            ]
        else:
            # The genuine probe is now AFTER the report; it cannot bind it.
            records[-1], records[-2] = records[-2], records[-1]
        path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = write(e, *args, "--scope", "full" if mutation == "late-probe" else "diff-only")
    assert result.returncode != 0
    assert "UNKNOWN" in result.stderr
    if mutation == "late-probe":
        assert "missing reviewer runtime HEAD probe" in result.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


@requires_git
def test_latest_review_in_a_long_session_uses_its_own_captured_patch(evidence):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    earlier = copy.deepcopy(records)
    earlier[0]["message"]["content"] = "<cpp-review-patch>\nforeign earlier patch\n</cpp-review-patch>"
    assert earlier[0] != records[0], "negative-fixture precondition: earlier review saw another artifact"
    path.write_text("".join(json.dumps(r) + "\n" for r in earlier + records))
    result = write(e, *args)
    assert result.returncode == 0, result.stderr


@requires_git
def test_patch_producer_and_writer_share_exact_bytes_and_refuse_dirty_work(evidence):
    e = evidence
    produced = subprocess.run([sys.executable, str(SCRIPT), "review-patch"], cwd=e["repo"], capture_output=True)
    assert produced.returncode == 0, produced.stderr
    assert produced.stdout == e["patch"].encode()
    (e["repo"] / "file").write_text("dirty unreviewed work\n")
    assert git(e["repo"], "status", "--porcelain"), "negative-fixture precondition: dirty artifact"
    refused = subprocess.run([sys.executable, str(SCRIPT), "review-patch"], cwd=e["repo"], capture_output=True)
    assert refused.returncode != 0 and not refused.stdout
    assert b"implementation checkpoint" in refused.stderr


@requires_git
def test_empty_committed_diff_still_has_a_captured_artifact(evidence):
    e = evidence
    git(e["repo"], "reset", "--hard", "origin/main")
    assert git(e["repo"], "diff", "origin/main...HEAD") == "", "precondition: no branch diff"
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch="")
    result = write(e, *args)
    assert result.returncode == 0, result.stderr


@requires_git
def test_ambiguous_exec_stream_is_refused_by_writer_and_shared_identity_reader(evidence):
    e = evidence
    args = runtime(e, "implementer", "claude", "model-a")
    runtime(e, "reviewer", "codex", "model-b", patch=e["patch"])
    stream = e["tmp"] / "ambiguous-exec.jsonl"
    events = [{"type": "thread.started", "thread_id": ident} for ident in ("fixture-reviewer", "foreign-thread")]
    assert len({event["thread_id"] for event in events}) == 2, "negative-fixture precondition: two thread identities"
    stream.write_text("".join(json.dumps(event) + "\n" for event in events))
    result = write(e, *args, "--reviewer-exec-log", str(stream), "--codex-sessions-dir", str(e["tmp"] / "codex"),
                   "--scope", "diff-only")
    assert result.returncode != 0 and "unambiguous thread.started" in result.stderr
    model, pointer, error = load()._derive_reviewer_from_exec_log(stream, e["tmp"] / "codex")
    assert model is None and pointer is None and "unambiguous thread.started" in error


@requires_git
def test_a_diff_of_the_frame_reader_can_contain_its_own_delimiter_literals(evidence):
    e = evidence
    (e["repo"] / "file").write_text('reader = "</stdin>"\nclosing = "</cpp-review-patch>"\n')
    git(e["repo"], "commit", "-qam", "reader delimiter literals")
    e["patch"] = subprocess.check_output(["git", "diff", "origin/main...HEAD"], cwd=e["repo"]).decode()
    assert '+reader = "</stdin>"' in e["patch"], "negative-fixture precondition: diff contains a closing literal"
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    result = write(e, *args)
    assert result.returncode == 0, result.stderr


@requires_git
def test_skipped_rollout_selector_cannot_fall_back_to_an_ambient_session(evidence):
    e = evidence
    runtime(e, "implementer", "codex", "explicit-model")
    runtime(e, "ambient", "codex", "ambient-model")
    root = e["tmp"] / "codex"
    explicit = root / "rollout-fixture-implementer.jsonl"
    ambient = root / "rollout-fixture-ambient.jsonl"
    assert explicit.read_bytes() != ambient.read_bytes(), "negative-fixture precondition: distinct identities"
    env = os.environ.copy()
    env["CODEX_THREAD_ID"] = "fixture-ambient"
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    result = subprocess.run([
        sys.executable, str(SCRIPT), "write", "--dir", str(e["tmp"] / "out"), "--issue", "1584",
        "--branch", "feature", "--status", "skipped", "--reason", "reviewer-unavailable",
        "--implementer-rollout", str(explicit), "--codex-sessions-dir", str(root),
    ], cwd=e["repo"], env=env, text=True, capture_output=True)
    assert result.returncode == 2, result.stderr
    assert "--implementer-rollout requires --status ran" in result.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


@requires_git
@pytest.mark.parametrize("role", ["implementer", "reviewer"])
def test_explicit_rollout_file_selects_either_role_without_a_sessions_root(evidence, role):
    e = evidence
    if role == "implementer":
        runtime(e, role, "codex", "model-a")
        args = runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    else:
        args = runtime(e, "implementer", "claude", "model-a")
        runtime(e, role, "codex", "model-b", patch=e["patch"])
    path = e["tmp"] / "codex" / f"rollout-fixture-{role}.jsonl"
    result = write(e, *args, f"--{role}-rollout", str(path))
    assert result.returncode == 0, result.stderr
    receipt = json.loads(next((e["tmp"] / "out").glob("*.json")).read_text())
    assert receipt[f"{role}_evidence"]["kind"] == "rollout"
    assert receipt[f"{role}_evidence"]["thread_id"] == f"fixture-{role}"


@requires_git
@pytest.mark.parametrize("implementer", ["codex", "claude"])
def test_codex_exec_reviewer_binds_its_runtime_captured_stdin(evidence, implementer):
    e = evidence
    args = runtime(e, "implementer", implementer, "model-a")
    runtime(e, "reviewer", "codex", "model-b", patch=e["patch"])
    path = e["tmp"] / "codex/rollout-fixture-reviewer.jsonl"
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    records[2]["payload"]["content"][0]["text"] = "Review prompt\n\n<stdin>\n" + e["patch"] + "</stdin>"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    stream = e["tmp"] / "review-exec.jsonl"
    stream.write_text(json.dumps({"type": "thread.started", "thread_id": "fixture-reviewer"}) + "\n")
    result = write(e, *args, "--reviewer-exec-log", str(stream), "--codex-sessions-dir", str(path.parent),
                   "--scope", "diff-only")
    assert result.returncode == 0, result.stderr
    receipt = json.loads(next((e["tmp"] / "out").glob("*.json")).read_text())
    assert receipt["reviewer_evidence"]["kind"] == "exec_log"
    assert len(receipt["reviewer_evidence"]["sources"]) == 2


@requires_git
def test_qwen_reviewer_binds_its_persisted_user_parts(evidence):
    e = evidence
    args = runtime(e, "implementer", "claude", "model-a")
    args += runtime(e, "reviewer", "qwen-code", "model-b", patch=e["patch"])
    result = write(e, *args, "--scope", "diff-only")
    assert result.returncode == 0, result.stderr


@requires_git
@pytest.mark.parametrize("scope", ["diff-only", "full"])
def test_a_later_report_requires_fresh_binding_evidence(evidence, scope):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b",
                    patch=e["patch"] if scope == "diff-only" else None,
                    probe=e["head"] if scope == "full" else None)
    path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    earlier = path.read_bytes()
    runtime(e, "reviewer", "claude", "model-b")
    later = path.read_bytes()
    assert b"<cpp-review-patch>" not in later and b"git rev-parse HEAD" not in later, \
        "negative-fixture precondition: later review has no fresh binding"
    assert earlier.count(b"## Findings") == later.count(b"## Findings") == 1
    path.write_bytes(earlier + later)
    result = write(e, *args, "--scope", scope)
    assert result.returncode != 0
    diagnostic = "missing captured reviewer patch" if scope == "diff-only" else "missing reviewer runtime HEAD probe"
    assert diagnostic in result.stderr, result.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


@requires_git
def test_checkpoint_guard_sees_untracked_files_hidden_by_config(evidence):
    e = evidence
    repo = e["repo"]
    git(repo, "config", "status.showUntrackedFiles", "no")
    (repo / "uncommitted.py").write_text("implementation_not_in_the_commit = True\n")
    assert "uncommitted.py" in git(repo, "ls-files", "--others", "--exclude-standard"), \
        "negative-fixture precondition: unignored untracked implementation exists"
    assert git(repo, "status", "--porcelain") == "", "precondition: default status is blinded by config"
    result = subprocess.run([sys.executable, str(SCRIPT), "review-patch"], cwd=repo, capture_output=True)
    assert result.returncode != 0
    assert not result.stdout
    assert b"implementation checkpoint" in result.stderr


@requires_git
def test_gitlink_changes_cannot_be_hidden_or_reformatted_by_hostile_config(evidence):
    e = evidence
    repo = e["repo"]
    target_b = e["head"]
    git(repo, "reset", "--hard", "origin/main")
    target_a = git(repo, "rev-parse", "HEAD")
    (repo / "dependency").mkdir()
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{target_a},dependency")
    git(repo, "commit", "-qm", "base gitlink")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "config", "diff.ignoreSubmodules", "all")
    git(repo, "config", "diff.submodule", "log")
    old_patch = git(repo, "diff", "origin/main...HEAD")
    assert old_patch == ""
    git(repo, "update-index", "--cacheinfo", f"160000,{target_b},dependency")
    git(repo, "commit", "-qm", "updated gitlink")
    assert target_a != target_b, "negative-fixture precondition: changed submodule target"
    assert git(repo, "diff", "--name-only", "--ignore-submodules=none", "origin/main...HEAD") == "dependency"
    assert git(repo, "diff", "origin/main...HEAD") == old_patch, "precondition: hostile config hides the gitlink delta"
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=old_patch)
    refused = write(e, *args, "--scope", "diff-only")
    assert refused.returncode != 0
    assert "captured reviewer patch differs" in refused.stderr
    produced = subprocess.run([sys.executable, str(SCRIPT), "review-patch"], cwd=repo, capture_output=True)
    assert produced.returncode == 0, produced.stderr
    assert f"-Subproject commit {target_a}".encode() in produced.stdout
    assert f"+Subproject commit {target_b}".encode() in produced.stdout
    runtime(e, "reviewer", "claude", "model-b", patch=produced.stdout.decode())
    accepted = write(e, *args, "--scope", "diff-only")
    assert accepted.returncode == 0, accepted.stderr


@requires_git
def test_artifact_binding_cannot_hide_sibling_changes_with_relative_diff_config(evidence):
    e = evidence
    root = e["repo"]
    subdir = root / "subdir"
    subdir.mkdir()
    git(root, "config", "diff.relative", "true")
    assert git(root, "diff", "--name-only", "origin/main...HEAD") == "file"
    assert git(subdir, "diff", "origin/main...HEAD") == "", "precondition: config hides changed sibling from subdir"
    e["repo"] = subdir
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch="")
    refused = write(e, *args, "--scope", "diff-only")
    assert refused.returncode != 0
    assert "captured reviewer patch differs" in refused.stderr
    runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    accepted = write(e, *args, "--scope", "diff-only")
    assert accepted.returncode == 0, accepted.stderr


@requires_git
@pytest.mark.parametrize("mutation", ["no-report", "failed-probe", "duplicate-frame"])
def test_review_evidence_boundaries_named_by_pass_one(evidence, mutation):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=e["patch"], probe=e["head"])
    path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    if mutation == "no-report":
        assert "## Findings" in records[-1]["message"]["content"][0]["text"]
        records[-1]["message"]["content"][0]["text"] = "Review complete without the required report"
        diagnostic = "missing runtime review report"
    elif mutation == "failed-probe":
        result = records[-2]["message"]["content"][0]
        assert result["type"] == "tool_result" and result["is_error"] is False
        result["is_error"] = True
        diagnostic = "missing reviewer runtime HEAD probe"
    else:
        content = records[0]["message"]["content"]
        records[0]["message"]["content"] = content + "\n" + content
        assert records[0]["message"]["content"].count("<cpp-review-patch>\n") == 2
        diagnostic = "ambiguous captured reviewer patch framing"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    refused = write(e, *args, "--scope", "full" if mutation == "failed-probe" else "diff-only")
    assert refused.returncode != 0 and diagnostic in refused.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


@requires_git
@pytest.mark.parametrize("runtime_name", ["qwen-code", "opencode"])
def test_a_model_changed_between_derivation_and_snapshot_is_unknown(evidence, monkeypatch, runtime_name):
    e = evidence
    flags = runtime(e, "implementer", runtime_name, "model-a")
    options = {flag.removeprefix("--").replace("-", "_"): Path(value)
               for flag, value in zip(flags[::2], flags[1::2])}
    module = load()
    if runtime_name == "qwen-code":
        transcript = next((e["tmp"] / runtime_name).rglob("*/chats/*.jsonl"))
        snapshot = module._snapshot

        def snapshot_after_model_switch(path, root=None):
            if path == transcript:
                records = [json.loads(line) for line in path.read_text().split("\n") if line]
                assistants = [r for r in records if r.get("type") == "assistant"]
                assert {r["model"] for r in assistants} == {"model-a"}, "precondition: initial model agrees"
                for record in assistants:
                    record["model"] = "changed-model"
                path.write_text("".join(json.dumps(r) + "\n" for r in records))
            return snapshot(path, root)

        monkeypatch.setattr(module, "_snapshot", snapshot_after_model_switch)
    else:
        import sqlite3
        derive = module._derive_opencode

        def derive_then_switch_model(records, path):
            result = derive(records, path)
            assert result[0] == "opencode/fixture/model-a" and result[2] is None
            with sqlite3.connect(path) as db:
                rows = db.execute("select id, data from message").fetchall()
                for ident, raw in rows:
                    message = json.loads(raw)
                    assert message["modelID"] == "model-a", "precondition: initial persisted identity agrees"
                    message["modelID"] = "changed-model"
                    db.execute("update message set data = ? where id = ?", (json.dumps(message), ident))
            return result

        monkeypatch.setattr(module, "_derive_opencode", derive_then_switch_model)
    with pytest.raises(module.EvidenceUnknown, match="changed during derivation"):
        module._adapter(SimpleNamespace(**options), "implementer")


@requires_git
@pytest.mark.parametrize("opening,closing", [("```md", "```"), ("~~~text", "~~~"),
                                             ("  ```md", "  ```"), ("````md", "`````"), ("```", "")])
@pytest.mark.parametrize("placement", ["alone", "after-report"])
def test_fenced_examples_neither_supply_nor_displace_a_review_report(evidence, opening, closing, placement):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", probe=e["head"])
    path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    example = f"{opening}\n## Findings\n\nNone - no defects found.\n{closing}"
    assert example.count("## Findings") == 1, "precondition: fenced template contains the report marker"
    if placement == "alone":
        records[-1]["message"]["content"][0]["text"] = example
    else:
        quoted = copy.deepcopy(records[-1])
        quoted["message"]["content"][0]["text"] = example
        records.append(quoted)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = write(e, *args, "--scope", "full")
    if placement == "alone":
        assert result.returncode != 0
        assert "missing runtime review report" in result.stderr
    else:
        assert result.returncode == 0, result.stderr


@requires_git
def test_fence_state_spans_assistant_text_parts(evidence):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", probe=e["head"])
    path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    records[-1]["message"]["content"] = [
        {"type": "text", "text": "```md\n"},
        {"type": "text", "text": "## Findings\n\nThis is a quoted example.\n"},
        {"type": "text", "text": "```\n\n## Findings\n\nNone - no defects found."},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = write(e, *args, "--scope", "full")
    assert result.returncode == 0, result.stderr


@requires_git
@pytest.mark.parametrize("cpp_first", [False, True])
@pytest.mark.parametrize("split_parts", [False, True])
def test_competing_patch_frame_types_in_one_input_are_unknown(evidence, cpp_first, split_parts):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    cpp = "<cpp-review-patch>\n" + e["patch"] + "</cpp-review-patch>\n"
    other_patch = e["patch"].replace("+after\n", "+foreign\n")
    assert other_patch != e["patch"], "negative-fixture precondition: competing patches differ"
    stdin = "<stdin>\n" + other_patch + "</stdin>\n"
    frames = [cpp, stdin] if cpp_first else [stdin, cpp]
    path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    records[0]["message"]["content"] = ([{"type": "text", "text": text} for text in frames]
                                        if split_parts else "".join(frames))
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = write(e, *args, "--scope", "diff-only")
    assert result.returncode != 0
    assert "competing captured patch frames" in result.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


@requires_git
@pytest.mark.parametrize("last_kind", ["stdin", "cpp-review-patch"])
@pytest.mark.parametrize("last_matches", [False, True])
def test_separate_review_inputs_select_the_latest_frame_chronologically(evidence, last_kind, last_matches):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    other = e["patch"].replace("+after\n", "+foreign\n")
    assert other != e["patch"], "negative-fixture precondition: a distinct patch"
    first_kind = "cpp-review-patch" if last_kind == "stdin" else "stdin"
    first_patch, last_patch = (other, e["patch"]) if last_matches else (e["patch"], other)
    path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    records[0]["message"]["content"] = f"<{first_kind}>\n{first_patch}</{first_kind}>"
    later_input = copy.deepcopy(records[0])
    later_input["message"]["content"] = f"<{last_kind}>\n{last_patch}</{last_kind}>"
    records.insert(-1, later_input)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = write(e, *args, "--scope", "diff-only")
    assert (result.returncode == 0) == last_matches, result.stderr
    if not last_matches:
        assert "captured reviewer patch differs" in result.stderr


@requires_git
@pytest.mark.parametrize("runtime_name", ["claude", "qwen-code"])
@pytest.mark.parametrize("mutation", ["missing-id", "null-id", "duplicate-pending-id"])
def test_malformed_command_linkage_cannot_supply_a_head_probe(evidence, runtime_name, mutation):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", runtime_name, "model-b", probe=e["head"])
    if runtime_name == "claude":
        path = e["tmp"] / "claude/fixture-reviewer.jsonl"
    else:
        path = next((e["tmp"] / "qwen-code").rglob("*/chats/*.jsonl"))
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    if runtime_name == "claude":
        call_index = 2
        call = records[call_index]["message"]["content"][0]
        result = records[call_index + 1]["message"]["content"][0]
        if mutation in ("missing-id", "null-id"):
            assert call.pop("id") == result.pop("tool_use_id") == "probe"
            if mutation == "null-id":
                call["id"] = result["tool_use_id"] = None
        else:
            earlier = copy.deepcopy(records[call_index])
            earlier["message"]["content"][0]["input"]["command"] = "echo an-untrusted-head"
            records.insert(call_index, earlier)
    else:
        call_index = 1
        call = records[call_index]["message"]["parts"][0]["functionCall"]
        result_record = records[call_index + 1]
        response = result_record["message"]["parts"][0]["functionResponse"]
        if mutation in ("missing-id", "null-id"):
            assert call.pop("id") == response.pop("id") == result_record["toolCallResult"].pop("callId") == "probe"
            if mutation == "null-id":
                call["id"] = response["id"] = result_record["toolCallResult"]["callId"] = None
        else:
            earlier = copy.deepcopy(records[call_index])
            earlier["message"]["parts"][0]["functionCall"]["args"]["command"] = "echo an-untrusted-head"
            records.insert(call_index, earlier)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = write(e, *args, "--scope", "full")
    assert result.returncode != 0
    assert "UNKNOWN" in result.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


@requires_git
@pytest.mark.parametrize("runtime_name", ["claude", "qwen-code"])
def test_resolved_command_ids_can_be_reused_sequentially(evidence, runtime_name):
    e = evidence
    args = runtime(e, "implementer", "codex", "model-a")
    args += runtime(e, "reviewer", runtime_name, "model-b", probe=e["head"])
    if runtime_name == "claude":
        path = e["tmp"] / "claude/fixture-reviewer.jsonl"
        call_index = 2
    else:
        path = next((e["tmp"] / "qwen-code").rglob("*/chats/*.jsonl"))
        call_index = 1
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    completed_pair = copy.deepcopy(records[call_index:call_index + 2])
    records[-1:-1] = completed_pair
    result_parts = ("tool_use_id" if runtime_name == "claude" else "callId")
    assert result_parts in json.dumps(completed_pair), "precondition: reused id has a preceding completed result"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = write(e, *args, "--scope", "full")
    assert result.returncode == 0, result.stderr


@requires_git
@pytest.mark.parametrize("role", ["implementer", "reviewer"])
@pytest.mark.parametrize("selector", ["thread_id", "exec_log"])
@pytest.mark.parametrize("mutation", ["mismatch", "suffix-only", "missing", "duplicate"])
def test_codex_selection_requires_its_own_session_identity(evidence, role, selector, mutation):
    e = evidence
    if role == "implementer":
        runtime(e, role, "codex", "model-a")
        args = runtime(e, "reviewer", "claude", "model-b", patch=e["patch"])
    else:
        args = runtime(e, "implementer", "claude", "model-a")
        runtime(e, role, "codex", "model-b", patch=e["patch"])
    ident = f"fixture-{role}"
    root = e["tmp"] / "codex"
    path = root / f"rollout-{ident}.jsonl"
    records = [json.loads(line) for line in path.read_text().split("\n") if line]
    assert records[0]["payload"]["id"] == ident, "precondition: original session identity matches"
    if mutation in ("mismatch", "suffix-only"):
        records[0]["payload"]["id"] = "other-" + ident
        if mutation == "suffix-only":
            path.unlink()
            path = root / f"rollout-other-{ident}.jsonl"
            assert path.name.endswith(ident + ".jsonl"), "precondition: only a suffix collision remains"
    elif mutation == "missing":
        records.pop(0)
    else:
        records.insert(0, copy.deepcopy(records[0]))
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    assert len(list(root.glob("*.jsonl"))) == 1, "precondition: unique candidate, not duplicate-file refusal"
    if selector == "thread_id":
        args += [f"--{role}-thread-id", ident]
    else:
        stream = e["tmp"] / "selected-exec.jsonl"
        stream.write_text(json.dumps({"type": "thread.started", "thread_id": ident}) + "\n")
        args += [f"--{role}-exec-log", str(stream)]
    result = write(e, *args, "--codex-sessions-dir", str(root), "--scope", "diff-only")
    assert result.returncode != 0
    assert "session_meta" in result.stderr
    assert not list((e["tmp"] / "out").glob("*.json"))


NATIVE_HEAD = Path(__file__).parent / "fixtures/counter_model/native-codex-head.json"


@pytest.mark.parametrize("mutation", ["none", "failed", "missing-exit", "text-exit"])
def test_captured_native_codex_head_result(mutation):
    records = json.loads(NATIVE_HEAD.read_text())
    item = records[0]["payload"]["item"]
    if mutation == "failed":
        item["exit_code"] = 1
    elif mutation == "missing-exit":
        del item["exit_code"]
    elif mutation == "text-exit":
        item["exit_code"] = "0"
    commands = load()._review_commands(records, "codex")
    if mutation == "none":
        assert commands == [("git rev-parse HEAD", "f85ca34546f4ec9b0b1827064778cfd886353eab\n")]
    else:
        assert commands == []


@requires_git
@pytest.mark.parametrize("failed", [False, True])
def test_native_codex_event_shape_through_receipt_writer(evidence, failed):
    e = evidence
    args = runtime(e, "implementer", "claude", "model-a")
    args += runtime(e, "reviewer", "codex", "model-b")
    rollout = e["tmp"] / "codex/rollout-fixture-reviewer.jsonl"
    records = [json.loads(line) for line in rollout.read_text().splitlines()]
    captured = json.loads(NATIVE_HEAD.read_text())[0]
    # Only the command output is adapted to this owned repository's HEAD.
    # These surrounding model/report records are synthetic, not a live review.
    captured["payload"]["item"]["aggregated_output"] = e["head"] + "\n"
    if failed:
        captured["payload"]["item"]["exit_code"] = 1
    records.insert(-1, captured)
    rollout.write_text("".join(json.dumps(record) + "\n" for record in records))
    result = write(e, *args, "--scope", "full")
    assert (result.returncode == 0) == (not failed), result.stderr
    if failed:
        assert "HEAD probe" in result.stderr
