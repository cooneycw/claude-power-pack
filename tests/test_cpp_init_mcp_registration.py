"""Exercise the canonical wizard registration definitions with owned fake CLIs."""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
STATE_HELPER = ROOT / "scripts" / "cpp-mcp-state.py"
SHELL = pytest.mark.skipif(
    any(shutil.which(x) is None for x in ("bash", "python3")), reason="requires bash and python3",
)


def definitions(text=None):
    text = INIT.read_text() if text is None else text
    match = re.search(r"# CPP_MCP_ROUTINES_BEGIN\n(.*?)# CPP_MCP_ROUTINES_END", text, re.S)
    return match[1] if match else ""


def block(heading):
    return re.search(r"```bash\n(.*?)```", INIT.read_text().split(heading, 1)[1], re.S)[1]


def literal_adds(text):
    """Census literal client/add commands in executable Bash fences only.

    Conservatively reject MCP-add text combined with substitution syntax, even
    when quoting may make that text inert. Put such advice in a plain fence.
    This is a bounded source policy, not a general Bash interpreter.
    """
    active = False
    found = []
    for line in re.sub(r"\\\n", " ", text).splitlines():
        if line.strip().startswith("```"):
            active = line.strip() in {"```bash", "```sh"}
            continue
        if not active:
            continue
        if not line.lstrip().startswith("#") and ("$(" in line or "`" in line):
            hint = r"\b(?:claude|codex)\b[\"']?\s+[\"']?mcp[\"']?\s+[\"']?add\b"
            assert not re.search(hint, line), "MCP add combined with substitution syntax is not allowed"
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|(){}")
            lexer.whitespace_split = True
            args = list(lexer)
        except ValueError:
            continue  # embedded Python multiline strings are not literal client calls
        # Output arguments are not executable commands; a subsequent command is.
        segments = [[]]
        for token in args:
            if token and all(char in ";&|(){}" for char in token):
                segments.append([])
            else:
                segments[-1].append(token)
        for command in segments:
            while command and command[0] in {"if", "elif", "then", "else"}:
                command = command[1:]
            if command and command[0] in {"echo", "printf"}:
                continue
            for i in range(len(command) - 2):
                if command[i] in {"claude", "codex"} and command[i + 1:i + 3] == ["mcp", "add"]:
                    found.append(command[i])
    return found


def assert_single_definition(text):
    assert sorted(literal_adds(text)) == ["claude", "codex"]
    for client in ("claude", "codex"):
        assert text.count(f"cpp_register_{client}_mcp() {{") == 1
        assert literal_adds("```bash\n" + definitions(text) + "\n```").count(client) == 1


def test_one_registration_definition_per_client():
    assert_single_definition(INIT.read_text())



def initialize_mcp(project, env):
    """Execute the shipped initializer in its own tool-like subprocess."""
    match = re.search(r'# CPP_MCP_RUN_INIT_BEGIN\n(.*?)# CPP_MCP_RUN_INIT_END', INIT.read_text(), re.S)
    assert match, 'per-run initializer must exist'
    result = subprocess.run(['bash', '-c', match[1]], cwd=project, env=dict(env, CPP_DIR=str(ROOT)),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    paths = [x.split('=', 1)[1] for x in result.stdout.splitlines() if x.startswith('CPP_MCP_RUN_DIR=')]
    assert len(paths) == 1 and Path(paths[0]).is_absolute()
    return paths[0]


def fake_environment(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "calls.jsonl"
    cli = "#!" + sys.executable + "\n" + r'''import json, os, pathlib, sys
client = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["MCP_CALL_LOG"], "a") as f:
    f.write(json.dumps([client, *args]) + "\n")
if args[:2] == ["mcp", "list"]:
    state = pathlib.Path(os.environ["MCP_FAKE_REGISTRY"])
    default = state.read_text() if state.exists() else "[]"
    print(os.environ.get("CODEX_LIST_JSON", default) if client == "codex" and "--json" in args else "")
    sys.exit(int(os.environ.get("LIST_RC", "0")))
if args[:2] == ["mcp", "add"]:
    if os.environ.get("MCP_BREAK_RESULTS") == "1":
        path = pathlib.Path(os.environ["CPP_MCP_RUN_DIR"]) / "results.json"
        path.rename(path.with_suffix('.previous'))
        path.mkdir()
    rc = int(os.environ.get("ADD_RC", "0"))
    if not rc and client == "codex":
        state = pathlib.Path(os.environ["MCP_FAKE_REGISTRY"])
        data = json.loads(state.read_text()) if state.exists() else []
        state.write_text(json.dumps([*data, {"name": args[2]}]))
    if not rc and client == "claude":
        path = pathlib.Path(os.environ["CLAUDE_CONFIG_DIR"]) / ".claude.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        data.setdefault("mcpServers", {})[args[6]] = {"type": args[3]}
        path.write_text(json.dumps(data))
    sys.exit(rc)
sys.exit(0)
'''
    for name in ("claude", "codex"):
        path = bindir / name
        path.write_text(cli)
        path.chmod(0o755)
    for name in ("npx", "curl"):
        path = bindir / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    env = dict(os.environ, HOME=str(home), CLAUDE_CONFIG_DIR=str(home), CODEX_HOME=str(home / ".codex"),
               PATH=f"{bindir}:{os.environ['PATH']}", MCP_CALL_LOG=str(log), CPP_DIR=str(ROOT),
               MCP_FAKE_REGISTRY=str(tmp_path / "codex-list.json"),
               SECOND_OPINION_URL="http://fixture-server.invalid:9123", TAVILY_API_KEY="fixture-only-placeholder")
    for key in ("LIST_RC", "ADD_RC", "CODEX_LIST_JSON"):
        env.pop(key, None)
    return env, log


def run(tmp_path, code, **changes):
    env, log = fake_environment(tmp_path)
    env.update(changes)
    env["CPP_MCP_RUN_DIR"] = initialize_mcp(tmp_path, env)
    load = 'source "$CPP_MCP_RUN_DIR/routines.sh" || exit 3\n'
    result = subprocess.run(["bash", "-c", load + code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=20)
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


@SHELL
@pytest.mark.parametrize("heading", ["#### 5d. Register MCP Servers with Codex", "### 8b. Codex MCP Registration"])
def test_codex_entrypoint_honors_second_opinion_url(tmp_path, heading):
    result, calls = run(tmp_path, block(heading))
    assert result.returncode == 0, result.stdout + result.stderr
    adds = [c for c in calls if c[:3] == ["codex", "mcp", "add"] and "second-opinion" in c]
    assert adds == [["codex", "mcp", "add", "second-opinion", "--url", "http://fixture-server.invalid:9123/mcp"]]


def rows(code):
    return code + '\nprintf "__ROW__%s\\n" "${CPP_MCP_RESULTS[@]}"\n'


def observed(result):
    return {row["step"]: row for line in result.stdout.splitlines() if line.startswith("__ROW__") and line != "__ROW__"
            for row in [json.loads(line[len("__ROW__"):])]}  # fixed metadata, never CLI output


@SHELL
@pytest.mark.parametrize("client,server,step", [
    ("claude", "second-opinion", "second-opinion"),
    ("claude", "playwright", "playwright"), ("claude", "tavily", "tavily"),
    ("claude", "sequential-thinking", "sequential-thinking"),
    ("codex", "second-opinion", "codex-second-opinion"), ("codex", "playwright", "codex-playwright"),
])
@pytest.mark.parametrize("exit_code", [0, 19])
def test_registration_records_actual_add_exit_without_values(tmp_path, client, server, step, exit_code):
    result, calls = run(tmp_path, rows(f'cpp_register_{client}_mcp {server}'), ADD_RC=str(exit_code))
    adds = [c for c in calls if c[:3] == [client, "mcp", "add"]]
    assert len(adds) == 1
    record = observed(result)[step]
    assert record == {"step": step, "outcome": "FAILED" if exit_code else "installed", "exit_code": exit_code}
    if client == "claude":
        assert adds[0][3:7] == ["--transport", "http" if server == "second-opinion" else "stdio", "--scope", "user"]
    if server != "second-opinion":
        assert "--" in adds[0] and "npx" in adds[0]
    assert "fixture-only-placeholder" not in result.stdout + result.stderr
    assert "fixture-server.invalid" not in result.stdout + result.stderr
    if exit_code:
        assert "MCP registered" not in result.stdout


@SHELL
@pytest.mark.parametrize("client", ["claude", "codex"])
def test_failed_list_does_not_run_add_and_records_unverified(tmp_path, client):
    result, calls = run(tmp_path, rows(f'cpp_register_{client}_mcp second-opinion'), LIST_RC="19")
    assert not [c for c in calls if c[1:3] == ["mcp", "add"]]
    step = "second-opinion" if client == "claude" else "codex-second-opinion"
    assert observed(result)[step] == {"step": step, "outcome": "unverified"}
    assert "could not be read" in result.stdout


@SHELL
@pytest.mark.parametrize("raw", ["not-json", "{}", '["second-opinion"]', '[{"name": 7}]'])
def test_unreadable_codex_list_never_registers(tmp_path, raw):
    assert raw != "[]", "fixture is not the valid absent-registration list"
    result, calls = run(tmp_path, rows('cpp_register_codex_mcp second-opinion'), CODEX_LIST_JSON=raw)
    assert not [c for c in calls if c[1:3] == ["mcp", "add"]]
    assert observed(result)["codex-second-opinion"]["outcome"] == "unverified"


@SHELL
def test_codex_existing_exact_name_is_already_without_add(tmp_path):
    result, calls = run(tmp_path, rows('cpp_register_codex_mcp second-opinion'),
                        CODEX_LIST_JSON='[{"name":"second-opinion"}]')
    assert not [c for c in calls if c[1:3] == ["mcp", "add"]]
    assert observed(result)["codex-second-opinion"]["outcome"] == "already"


@SHELL
def test_codex_neighbor_name_is_not_our_registration(tmp_path):
    result, calls = run(tmp_path, rows('cpp_register_codex_mcp second-opinion'),
                        CODEX_LIST_JSON='[{"name":"second-opinion-neighbor"}]')
    assert len([c for c in calls if c[1:3] == ["mcp", "add"]]) == 1
    assert observed(result)["codex-second-opinion"]["outcome"] == "installed"


@SHELL
def test_tier5_then_extras_does_not_repeat_existing_codex_add(tmp_path):
    code = block('#### 5d. Register MCP Servers with Codex')
    code += "\n"
    code += block('### 8b. Codex MCP Registration')
    result, calls = run(tmp_path, rows(code))
    assert len([c for c in calls if c[1:3] == ["mcp", "add"]]) == 2
    assert {x["outcome"] for x in observed(result).values()} == {"already"}


@SHELL
def test_registration_failure_reaches_actual_receipt_and_summary(tmp_path):
    source = INIT.read_text()
    consumer = re.search(r'# CPP_INSTALL_RECEIPT_WRITE_BEGIN\n(.*?)# CPP_INSTALL_RECEIPT_WRITE_END', source, re.S)[1]
    consumer = consumer.replace('--cpp-dir "$CPP_DIR"', '--revision ' + 'a' * 40)
    initial = [{"step": "commands", "outcome": "installed"}, {"step": "stash-guard", "outcome": "already"},
               {"step": "codex-second-opinion", "outcome": "installed"}]
    result, calls = run(tmp_path, 'cpp_register_codex_mcp second-opinion\n' + consumer, ADD_RC="19",
                        STEP_RESULTS_JSON=json.dumps(initial),
                        OFFERED_STEPS_JSON=json.dumps([x['step'] for x in initial]),
                        SELECTED_TIER="1", PROFILE_NAME="not-selected", PERMISSION_REPORT="{}")
    assert len([c for c in calls if c[1:3] == ["mcp", "add"]]) == 1
    receipt_path = tmp_path / '.claude/cpp-install.json'
    assert receipt_path.is_file(), result.stdout + result.stderr
    receipt = json.loads(receipt_path.read_text())
    record = next(x for x in receipt['steps'] if x['step'] == 'codex-second-opinion')
    assert record['outcome'] == 'FAILED' and record['exit_code'] == 19
    assert 'CPP Installation Incomplete' in result.stdout
    assert 'CPP Installation Complete' not in result.stdout


@pytest.mark.parametrize("name", [
    "bad-duplicate-claude", "bad-duplicate-codex", "bad-continued-duplicate", "bad-duplicate-after-echo",
    "bad-duplicate-substitution",
])
def test_duplicate_registration_control_rejects_bad_and_accepts_repair(name):
    fixtures = ROOT / 'tests/fixtures/cpp-init-mcp-registration'
    bad = (fixtures / f'{name}.md').read_text()
    good = (fixtures / 'good-shared.md').read_text()
    assert bad != good and "mcp add second-opinion" in bad, "fixture must add a second registration"
    with pytest.raises(AssertionError):
        assert_single_definition(bad)
    assert_single_definition(good)


@SHELL
@pytest.mark.parametrize("client", ["claude", "codex"])
def test_repeated_registration_uses_existing_config_without_second_add(tmp_path, client):
    result, calls = run(tmp_path, rows(f'cpp_register_{client}_mcp playwright\ncpp_register_{client}_mcp playwright'))
    assert len([c for c in calls if c[1:3] == ["mcp", "add"]]) == 1
    assert {x['outcome'] for x in observed(result).values()} == {'already'}


@SHELL
def test_pool_keeps_failed_desk_when_later_desk_succeeds(tmp_path):
    code = 'cpp_register_claude_mcp custom-desk-one desk\nexport ADD_RC=0\n'
    code += 'cpp_register_claude_mcp custom-desk-two desk'
    result, calls = run(tmp_path, rows(code), ADD_RC="19")
    adds = [c for c in calls if c[1:3] == ["mcp", "add"]]
    assert len(adds) == 2
    assert all(c[-1] == '--isolated' and '@playwright/mcp@0.0.77' in c for c in adds)
    assert observed(result)['browser-pool']['outcome'] == 'FAILED'


@SHELL
@pytest.mark.parametrize("client", ["claude", "codex"])
def test_missing_npx_skips_stdio_without_add(tmp_path, client):
    code = 'command() { if [ "$1 $2" = "-v npx" ]; then return 1; else builtin command "$@"; fi; }\n'
    code += f'cpp_register_{client}_mcp playwright'
    result, calls = run(tmp_path, rows(code))
    assert not [c for c in calls if c[1:3] == ["mcp", "add"]]
    assert {x['outcome'] for x in observed(result).values()} == {'skipped'}


@SHELL
def test_missing_tavily_key_is_an_explicit_optional_skip(tmp_path):
    result, calls = run(tmp_path, rows('cpp_register_claude_mcp tavily'), TAVILY_API_KEY='')
    assert not [c for c in calls if c[1:3] == ["mcp", "add"]]
    assert observed(result)['tavily']['outcome'] == 'skipped'


@SHELL
def test_pool_keeps_unverified_desk_when_later_desk_succeeds(tmp_path):
    code = 'cpp_register_claude_mcp "not a valid name" desk\ncpp_register_claude_mcp custom-desk desk'
    result, calls = run(tmp_path, rows(code))
    assert len([c for c in calls if c[1:3] == ["mcp", "add"]]) == 1
    records = observed(result)
    assert 'browser-pool' in records, result.stdout + result.stderr
    assert records['browser-pool']['outcome'] == 'unverified'


@SHELL
@pytest.mark.parametrize("client", ["claude", "codex"])
def test_function_preserves_nonzero_add_exit_for_callers(tmp_path, client):
    result, calls = run(tmp_path, f'if cpp_register_{client}_mcp playwright; then exit 0; else exit "$?"; fi',
                        ADD_RC='19')
    assert result.returncode == 19
    assert len([c for c in calls if c[1:3] == ["mcp", "add"]]) == 1


@SHELL
@pytest.mark.skipif(shutil.which('mkdir') is None, reason='requires mkdir for pool snippet')
def test_unreadable_pool_config_still_persists_incomplete_receipt(tmp_path):
    config = tmp_path / '.claude/playwright-pool.json'
    config.parent.mkdir()
    config.write_text('{')
    with pytest.raises(ValueError):
        json.loads(config.read_text())
    consumer = re.search(r'# CPP_INSTALL_RECEIPT_WRITE_BEGIN\n(.*?)# CPP_INSTALL_RECEIPT_WRITE_END',
                         INIT.read_text(), re.S)[1]
    consumer = consumer.replace('--cpp-dir "$CPP_DIR"', '--revision ' + 'a' * 40)
    code = block('#### 3d. Register the browser desk pool') + '\n' + consumer
    initial = [{"step": "commands", "outcome": "installed"}, {"step": "stash-guard", "outcome": "already"}]
    result, calls = run(tmp_path, code, STEP_RESULTS_JSON=json.dumps(initial),
                        OFFERED_STEPS_JSON='["commands","stash-guard","browser-pool"]',
                        SELECTED_TIER="1", PROFILE_NAME="not-selected", PERMISSION_REPORT="{}")
    assert not [c for c in calls if c[1:3] == ["mcp", "add"]]
    receipt_path = tmp_path / '.claude/cpp-install.json'
    assert receipt_path.is_file(), result.stdout + result.stderr
    record = next(x for x in json.loads(receipt_path.read_text())['steps'] if x['step'] == 'browser-pool')
    assert record['outcome'] == 'unverified'
    assert 'CPP Installation Incomplete' in result.stdout


@SHELL
@pytest.mark.skipif(shutil.which('mkdir') is None, reason='requires mkdir for pool snippet')
@pytest.mark.parametrize('data', [
    {"desks": ["good-desk", "not a valid name"]}, {"desks": "not-a-list"},
    {"desks": ["good-desk", 7]}, {"desks": []}, {"missing-desks": []},
])
def test_pool_rejects_entire_invalid_population_before_any_registration(tmp_path, data):
    config = tmp_path / '.claude/playwright-pool.json'
    config.parent.mkdir()
    config.write_text(json.dumps(data))
    population = data.get('desks')
    valid = (isinstance(population, list) and bool(population)
             and all(isinstance(x, str) and re.fullmatch(r'[a-zA-Z0-9_-]+', x) for x in population))
    assert not valid, 'fixture must not contain a valid desk-name population'
    result, calls = run(tmp_path, rows(block('#### 3d. Register the browser desk pool')))
    assert not [c for c in calls if c[1:3] == ["mcp", "add"]]
    records = observed(result)
    assert 'browser-pool' in records, result.stdout + result.stderr
    assert records['browser-pool']['outcome'] == 'unverified'


@SHELL
def test_registration_block_works_in_a_fresh_shell_after_initialization(tmp_path):
    env, log = fake_environment(tmp_path)
    initial = re.search(r'# CPP_MCP_RUN_INIT_BEGIN\n(.*?)# CPP_MCP_RUN_INIT_END', INIT.read_text(), re.S)
    setup = subprocess.run(['bash', '-c', initial[1] if initial else definitions()],
                           cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    for line in setup.stdout.splitlines():
        if line.startswith('CPP_MCP_RUN_DIR='):
            env['CPP_MCP_RUN_DIR'] = line.split('=', 1)[1]
    # No functions/arrays from the first subprocess can exist in this shell.
    result = subprocess.run(['bash', '-c', block('#### 5d. Register MCP Servers with Codex')],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    assert 'command not found' not in result.stderr, result.stdout + result.stderr
    assert len([c for c in calls if c[1:3] == ['mcp', 'add']]) == 2


def consumer():
    match = re.search(r'# CPP_INSTALL_RECEIPT_WRITE_BEGIN\n(.*?)# CPP_INSTALL_RECEIPT_WRITE_END',
                      INIT.read_text(), re.S)
    assert match
    return match[1].replace('--cpp-dir "$CPP_DIR"', '--revision ' + 'a' * 40)


def invoke(project, env, code):
    return subprocess.run(['bash', '-c', code], cwd=project, env=env, capture_output=True, text=True, timeout=15)


@SHELL
@pytest.mark.parametrize('add_rc', ['0', '19'])
def test_receipt_reloads_registration_from_a_different_shell(tmp_path, add_rc):
    env, log = fake_environment(tmp_path)
    env['CPP_MCP_RUN_DIR'] = initialize_mcp(tmp_path, env)
    env['ADD_RC'] = add_rc
    registration = invoke(tmp_path, env, block('#### 5d. Register MCP Servers with Codex'))
    assert 'command not found' not in registration.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert len([c for c in calls if c[1:3] == ['mcp', 'add']]) == 2
    data = [{"step": "commands", "outcome": "installed"}, {"step": "stash-guard", "outcome": "already"},
            {"step": "codex-second-opinion", "outcome": "installed"},
            {"step": "codex-playwright", "outcome": "installed"}]
    env.update(STEP_RESULTS_JSON=json.dumps(data), OFFERED_STEPS_JSON=json.dumps([x['step'] for x in data]),
               SELECTED_TIER='1', PROFILE_NAME='not-selected', PERMISSION_REPORT='{}')
    summary = invoke(tmp_path, env, consumer())
    receipt = json.loads((tmp_path / '.claude/cpp-install.json').read_text())
    codex = [x for x in receipt['steps'] if x['step'].startswith('codex-')]
    assert {x['outcome'] for x in codex} == ({'FAILED'} if add_rc == '19' else {'installed'})
    assert {x['exit_code'] for x in codex} == {int(add_rc)}
    assert ('CPP Installation Complete' in summary.stdout) is (add_rc == '0')
    run = Path(env['CPP_MCP_RUN_DIR'])
    assert run.stat().st_mode & 0o777 == 0o700
    assert all((run / name).stat().st_mode & 0o777 == 0o600 for name in ('routines.sh', 'results.json'))
    assert 'fixture-only-placeholder' not in (run / 'routines.sh').read_text()
    assert 'fixture-only-placeholder' not in (run / 'results.json').read_text()


@SHELL
def test_runs_in_one_project_do_not_share_results(tmp_path):
    env, _ = fake_environment(tmp_path)
    first = initialize_mcp(tmp_path, env)
    second = initialize_mcp(tmp_path, env)
    assert first != second
    failed = invoke(tmp_path, dict(env, CPP_MCP_RUN_DIR=first, ADD_RC='19'),
                    block('#### 5d. Register MCP Servers with Codex'))
    succeeded = invoke(tmp_path, dict(env, CPP_MCP_RUN_DIR=second, ADD_RC='0'),
                       block('#### 5d. Register MCP Servers with Codex'))
    assert 'FAILED' in failed.stdout and 'MCP registered' in succeeded.stdout
    assert {x['outcome'] for x in json.loads((Path(first) / 'results.json').read_text())} == {'FAILED'}
    assert {x['outcome'] for x in json.loads((Path(second) / 'results.json').read_text())} == {'installed'}


@SHELL
def test_failed_result_write_leaves_pending_and_refuses_later_receipt(tmp_path):
    env, _ = fake_environment(tmp_path)
    env['CPP_MCP_RUN_DIR'] = initialize_mcp(tmp_path, env)
    env['MCP_BREAK_RESULTS'] = '1'
    result = invoke(tmp_path, env, block('#### 5d. Register MCP Servers with Codex'))
    run = Path(env['CPP_MCP_RUN_DIR'])
    assert (run / 'results.json').is_dir(), 'fixture must block atomic result replacement'
    assert (run / 'pending').is_file(), 'unrecorded attempt must remain pending'
    assert 'result persistence failed' in result.stderr
    assert 'MCP registered' not in result.stdout
    later = invoke(tmp_path, env, consumer())
    assert 'CPP Installation Incomplete' in later.stdout
    assert 'CPP Installation Complete' not in later.stdout
    assert not (tmp_path / '.claude/cpp-install.json').exists()


@SHELL
@pytest.mark.parametrize('fault', ['missing', 'invalid', 'pending'])
def test_later_shell_refuses_unavailable_or_interrupted_run(tmp_path, fault):
    env, log = fake_environment(tmp_path)
    env['CPP_MCP_RUN_DIR'] = initialize_mcp(tmp_path, env)
    run = Path(env['CPP_MCP_RUN_DIR'])
    if fault == 'missing':
        (run / 'results.json').unlink()
        assert not (run / 'results.json').exists()
    elif fault == 'invalid':
        (run / 'results.json').write_text('{')
        with pytest.raises(ValueError):
            json.loads((run / 'results.json').read_text())
    else:
        (run / 'pending').write_text('interrupted')
        assert (run / 'pending').is_file()
    result = invoke(tmp_path, env, block('#### 5d. Register MCP Servers with Codex'))
    assert result.returncode != 0
    assert 'CPP Installation Incomplete' in result.stdout
    assert not log.exists(), 'refused state must prevent every client call'


@pytest.mark.parametrize('rows_data', [
    [{"step": "second-opinion", "outcome": "installed", "endpoint": "must-not-store"}],
    [{"step": "not-our-server", "outcome": "installed"}],
    [{"step": "playwright", "outcome": "installed", "exit_code": True}],
])
def test_state_helper_rejects_invalid_metadata_without_values(tmp_path, rows_data):
    (tmp_path / 'results.json').write_text(json.dumps(rows_data))
    result = subprocess.run([sys.executable, str(STATE_HELPER), 'load', '--run-dir', str(tmp_path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 3
    assert not result.stdout
    assert 'must-not-store' not in result.stderr


def test_state_helper_stays_outside_executable_host_link_population():
    assert STATE_HELPER.is_file()
    assert STATE_HELPER.stat().st_mode & 0o111 == 0
