"""Consent disclosures and executable no-write/no-credential regressions (#1586)."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".claude/commands/cpp/init.md"
CASES = json.loads((ROOT / "tests/fixtures/cpp-init-consent/cases.json").read_text())


def region(text, case):
    assert text.count(case["start"]) == 1, "fixture start must identify one source region"
    remaining = text.split(case["start"], 1)[1]
    assert case["end"] in remaining, "fixture end must exist"
    return remaining.split(case["end"], 1)[0]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_disclosure_precedes_the_applicable_choice(case):
    assert_disclosed(SOURCE.read_text(), case)


def assert_disclosed(text, case):
    observed = region(text, case)
    for required in case["required"]:
        assert required in observed, f"{case['id']}: missing pre-choice disclosure {required}"


def test_shared_inventory_is_before_every_tier_confirmation():
    assert_shared_precedes_choices(SOURCE.read_text())


def assert_shared_precedes_choices(text):
    step4 = text.split("## Step 4:", 1)[1].split("## Step 5:", 1)[0]
    assert step4.count("Proceed? [y/N]") == 7, "fixture must see every tier question"
    assert "### Applicable write and credential inventory" in step4
    assert step4.index("### Applicable write and credential inventory") < step4.index("Proceed? [y/N]")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")
@pytest.mark.parametrize("document", ["init.md", "update.md"])
@pytest.mark.parametrize("served", [False, True], ids=["absent-surface", "served-surface"])
def test_locator_does_not_invoke_a_write_probe_before_consent(tmp_path, served, document):
    text = (SOURCE.parent / document).read_text()
    code = re.search(r'^```bash\n(CPP_DIR=""\n.*?)^```$', text, re.M | re.S)
    assert code, "Step 1 Bash fixture must exist"
    home = tmp_path / "home"
    scripts = home / ".claude/scripts"
    scripts.mkdir(parents=True)
    helper = scripts / "cpp-host-write.sh"
    helper.write_text('#!/bin/sh\nprintf called > "$HOME/probe-called"\nprintf yes\n')
    helper.chmod(0o755)
    if served:
        surface = home / ".claude/commands/cpp"
        surface.mkdir(parents=True)
        (surface / "init.md").write_text("# CPP surface\n")
    missing = tmp_path / "missing-checkout"
    assert not missing.exists(), "fixture must have no source checkout"
    marker = home / "probe-called"
    assert not marker.exists(), "fixture must start with no probe invocation"
    assert helper.is_file() and os.access(helper, os.X_OK), "probe stub must be executable"
    env = dict(os.environ, HOME=str(home), CPP_INIT_CANDIDATES=str(missing))
    result = subprocess.run(["bash", "-c", code[1]], env=env, capture_output=True, text=True)
    assert not marker.exists(), "locator invoked mutating helper before consent"
    assert "not probed before confirmation" in result.stdout
    assert result.returncode == (0 if served else 1)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")
def test_local_pg_output_has_no_credential_userinfo(tmp_path):
    section = SOURCE.read_text().split("### 8d. Common-Memory Store Backend", 1)[1]
    blocks = re.findall(r"^```bash\n(.*?)^```$", section, re.M | re.S)
    candidates = [block for block in blocks if block.startswith('BACKEND_FILE=')]
    assert len(candidates) == 1, "fixture must execute the real backend choice block"
    home = tmp_path / "home"
    scripts = home / ".claude/scripts"
    scripts.mkdir(parents=True)
    helper = scripts / "cpp-host-write.sh"
    helper.write_text("#!/bin/sh\nexit 0\n")
    helper.chmod(0o755)
    bins = tmp_path / "bin"
    bins.mkdir()
    docker = bins / "docker"
    docker.write_text('#!/bin/sh\nprintf called > "$HOME/docker-called"\nexit 19\n')
    docker.chmod(0o755)
    env = dict(os.environ, HOME=str(home), MEM_BACKEND_CHOICE="ii", PATH=f"{bins}:{os.environ['PATH']}")
    assert shutil.which("docker", path=env["PATH"]) == str(docker), "fixture must intercept Docker"
    assert helper.is_file() and os.access(helper, os.X_OK)
    assert not (home / "docker-called").exists(), "fixture must not start Docker"
    result = subprocess.run(["bash", "-c", candidates[0]], input="n\n", env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert not (home / "docker-called").exists(), "declining must not run Docker"
    if re.search(r"postgres(?:ql)?://[^\s/]+:[^\s@]+@", result.stdout):
        pytest.fail("local-pg output exposed credential-bearing DSN; value withheld")
    assert "POSTGRES_PASSWORD" in result.stdout


@pytest.mark.parametrize("model", ["Qwen", "Gemma"])
def test_endpoint_disclosure_redacts_credentials_before_display(model):
    text = SOURCE.read_text()
    prompt = re.search(rf"=== Optional: Persist {model} Endpoint ===\n(.*?)^```$", text, re.M | re.S)
    assert prompt, "fixture must identify endpoint confirmation"
    name = model.upper() + "_ENDPOINT"
    assert f"${{{name}}}" not in prompt[1], "prompt must not interpolate credential-bearing endpoint"
    assert f"{{{name}_REDACTED}}" in prompt[1]
    assert "redact credential values" in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")
@pytest.mark.parametrize("model", ["Qwen", "Gemma"])
@pytest.mark.parametrize("state", ["reachable", "unreachable", "tags-failed", "declined"])
def test_endpoint_output_never_displays_credential_values(tmp_path, model, state):
    text = SOURCE.read_text()
    blocks = re.findall(r"^```bash\n(.*?)^```$", text, re.M | re.S)
    name = model.upper()
    if state == "declined":
        selected = [b for b in blocks if f'{name}_OLLAMA_URL persistence skipped' in b]
    else:
        selected = [b for b in blocks if f'{name}_ENDPOINT=' in b and '/api/version' in b]
    assert len(selected) == 1, "fixture must execute the actual selected output block"
    control = "CPP-ENDPOINT-CREDENTIAL-CONTROL"
    endpoint = f"http://user:{control}@example.test:11434/?token={control}"
    assert control in endpoint, "fixture endpoint must contain the credential control"
    bins = tmp_path / "bin"
    bins.mkdir()
    marker = tmp_path / "curl-called"
    curl = bins / "curl"
    curl.write_text('''#!/bin/sh
printf called > "$CPP_TEST_MARKER"
for last do :; done
[ "$CPP_TEST_CURL" = unreachable ] && exit 7
case "$last" in
  */api/tags) [ "$CPP_TEST_CURL" = tags-failed ] && exit 7; printf '{"models":[]}' ;;
  *) printf '{"version":"fixture"}' ;;
esac
''')
    curl.chmod(0o755)
    env = dict(os.environ, PATH=f"{bins}:{os.environ['PATH']}", CPP_TEST_CURL=state, CPP_TEST_MARKER=str(marker))
    env[name + "_OLLAMA_URL"] = endpoint
    env[name + "_ENDPOINT"] = endpoint
    env[name + "_RC_DISPLAY"] = "fixture.rc"
    assert shutil.which("curl", path=env["PATH"]) == str(curl), "fixture must intercept HTTP"
    assert not marker.exists(), "fixture must start without a curl call"
    result = subprocess.run(["bash", "-c", selected[0]], env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert marker.exists() == (state != "declined"), "fixture must exercise the selected branch"
    expected = {
        "reachable": "Ollama reachable", "unreachable": "NOT reachable",
        "tags-failed": "unknown", "declined": "persistence skipped",
    }[state]
    if expected not in result.stdout:
        pytest.fail("selected endpoint output branch was not exercised; output withheld")
    if control in result.stdout + result.stderr:
        pytest.fail("endpoint output exposed credential control; value withheld")


def test_late_optional_disclosure_is_rejected():
    text = SOURCE.read_text()
    case = next(c for c in CASES if c["id"] == "happy")
    paragraph = re.search(r"Consent: if absent, install happy-coder[^\n]+", text)
    assert paragraph and text.count(paragraph[0]) == 1
    choice = "Install happy-cli? [y/N]"
    assert text.index(paragraph[0]) < text.index(choice), "fixture starts before the choice"
    bad = text.replace(paragraph[0], "").replace(choice, choice + "\n" + paragraph[0])
    assert bad.index(paragraph[0]) > bad.index(choice), "fixture must move disclosure after choice"
    with pytest.raises(AssertionError):
        assert_disclosed(bad, case)


def test_late_shared_inventory_is_rejected():
    text = SOURCE.read_text()
    start = text.index("### Applicable write and credential inventory")
    end = text.index("### Tier 1 Disclosure")
    inventory = text[start:end]
    assert inventory and start < text.index("Proceed? [y/N]", start)
    bad = text[:start] + text[end:]
    choice = bad.index("Proceed? [y/N]", bad.index("## Step 4:"))
    bad = bad[:choice] + bad[choice:].replace("Proceed? [y/N]", "Proceed? [y/N]\n" + inventory, 1)
    assert bad.index("### Applicable write and credential inventory") > choice
    with pytest.raises(AssertionError):
        assert_shared_precedes_choices(bad)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")
def test_codex_decline_creates_directory_even_without_setup_source(tmp_path):
    text = SOURCE.read_text().split("### 8b. Codex MCP Registration", 1)[1]
    blocks = re.findall(r"^```bash\n(.*?)^```$", text, re.M | re.S)
    selected = [b for b in blocks if 'Codex registration skipped' in b]
    assert len(selected) == 1, "fixture must execute the actual decline block"
    missing = tmp_path / "absent-cpp"
    assert not missing.exists(), "fixture must lack the setup source"
    project = tmp_path / "project"
    project.mkdir()
    assert not (project / ".agents").exists(), "fixture must start without generated directory"
    result = subprocess.run(["bash", "-c", selected[0]], cwd=project,
                            env=dict(os.environ, CPP_DIR=str(missing)), capture_output=True, text=True)
    assert result.returncode == 0
    assert (project / ".agents").is_dir()
    assert not (project / ".agents/CODEX_SETUP.md").exists()
