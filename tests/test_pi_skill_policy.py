"""Opposite source-policy cases establish refusal before source bytes escape."""
from pathlib import Path

import pytest

from lib.pi_skills import PolicyError, build, history_root, preflight
from tests.test_pi_skill_sync import source


@pytest.mark.parametrize("name", ["package.json", "payload.py", ".hidden.md", "run.sh"])
def test_non_markdown_members_refused(tmp_path, name):
    root = source(tmp_path)
    file = root / ".claude/skills/topic" / name
    file.write_text("fixture")
    assert file.exists()
    with pytest.raises(PolicyError, match="unsupported package member"):
        build(root)


@pytest.mark.parametrize("payload", ["!command fixture", "[unsafe](file:///fixture/auth.json)"])
def test_auth_helpers_refused_as_text_without_access(tmp_path, payload, monkeypatch):
    root = source(tmp_path)
    skill = root / ".claude/skills/topic/SKILL.md"
    skill.write_text(skill.read_text() + payload)
    assert payload in skill.read_text()
    with pytest.raises(PolicyError, match="outside topic policy"):
        build(root)


def test_empty_canonical_population_refused(tmp_path):
    root = tmp_path / "source"
    (root / ".claude/skills").mkdir(parents=True)
    assert not list((root / ".claude/skills").iterdir())
    with pytest.raises(PolicyError, match="empty"):
        build(root)


def test_symlink_guide_is_not_followed(tmp_path):
    root = source(tmp_path)
    guide = root / "docs/skills/topic.md"
    guide.unlink()
    guide.symlink_to(tmp_path / "unreadable-fixture")
    assert guide.is_symlink()
    with pytest.raises(PolicyError, match="symlink"):
        build(root)


def context(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    cwd.mkdir()
    agent = home / ".pi/agent"
    agent.mkdir(parents=True)
    return home, cwd, agent


@pytest.mark.parametrize("source_kind", ["cli", "environment", "global", "project", "default"])
def test_every_history_source_refuses_output_before_descendant_stat(tmp_path, source_kind, monkeypatch):
    import json
    home, cwd, agent = context(tmp_path)
    history = agent / "sessions" if source_kind == "default" else tmp_path / "external-history"
    history.mkdir()
    forbidden = history / "nested/skills"
    kwargs = {"environ": {}}
    if source_kind == "cli":
        kwargs["session_dir"] = str(history)
    elif source_kind == "environment":
        kwargs["environ"] = {"PI_CODING_AGENT_SESSION_DIR": str(history)}
    elif source_kind in {"global", "project"}:
        settings_path = agent / "settings.json" if source_kind == "global" else cwd / ".pi/settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({"sessionDir": str(history)}))
    original = Path.lstat
    calls = []

    def observe(path, *args, **kw):
        calls.append(path)
        assert history not in path.parents, "descendant metadata touch"
        return original(path, *args, **kw)

    monkeypatch.setattr(Path, "lstat", observe)
    with pytest.raises(PolicyError, match="output_root_under_sessions|trusted_config"):
        preflight(forbidden, cwd=cwd, home=home, agent=agent, **kwargs)
    assert history in calls  # selected-root metadata is the explicit allowance


def test_overridden_candidates_still_excluded_and_project_precedence(tmp_path):
    import json
    home, cwd, agent = context(tmp_path)
    project = tmp_path / "project-history"
    global_dir = tmp_path / "global-history"
    (agent / "settings.json").write_text(json.dumps({"sessionDir": str(global_dir)}))
    (cwd / ".pi").mkdir()
    (cwd / ".pi/settings.json").write_text(json.dumps({"sessionDir": str(project)}))
    allowed = tmp_path / "build/skills"
    policy = preflight(allowed, cwd=cwd, home=home, agent=agent, environ={})
    assert policy.effective_history == project
    assert {p for _, p in policy.histories} == {project, global_dir, agent / "sessions"}
    with pytest.raises(PolicyError, match="output_root_under_sessions"):
        preflight(global_dir / "skills", cwd=cwd, home=home, agent=agent, environ={})
    policy = preflight(allowed, cwd=cwd, home=home, agent=agent,
                       environ={"PI_CODING_AGENT_SESSION_DIR": str(tmp_path / "env-history")},
                       session_dir=str(tmp_path / "cli-history"))
    assert policy.histories[0][0] == "cli"
    assert len(policy.histories) == 5


def test_history_root_symlink_resolves_but_dangling_and_loop_refuse(tmp_path):
    real = tmp_path / "history"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    assert alias.is_symlink()
    assert history_root(alias) == real
    real.rmdir()
    with pytest.raises(PolicyError, match="dangling"):
        history_root(alias)
    alias.unlink()
    alias.symlink_to(alias)
    with pytest.raises(PolicyError, match="ambiguous"):
        history_root(alias)


def test_alias_output_never_descends_into_trusted_agent(tmp_path):
    home, cwd, agent = context(tmp_path)
    (agent / "extensions").mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(agent / "extensions", target_is_directory=True)
    assert alias.is_symlink()
    with pytest.raises(PolicyError, match="symlink"):
        preflight(alias / "skills", cwd=cwd, home=home, agent=agent, environ={})
    assert not (agent / "extensions/skills").exists()


@pytest.mark.parametrize("value", ['{"sessionDir":42}', '{"sessionDir":', '[]'])
def test_malformed_settings_fail_instead_of_fallback(tmp_path, value):
    home, cwd, agent = context(tmp_path)
    (agent / "settings.json").write_text(value)
    with pytest.raises(PolicyError, match="settings"):
        preflight(tmp_path / "build/skills", cwd=cwd, home=home, agent=agent, environ={})


def test_file_url_tilde_relative_normalization(tmp_path):
    home, cwd, agent = context(tmp_path)
    policy = preflight(Path("build/skills"), cwd=cwd, home=home, agent=agent,
                       session_dir="file://" + str(tmp_path / "history"), environ={})
    assert policy.destination == cwd / "build/skills"
    assert policy.effective_history == tmp_path / "history"
    policy = preflight(Path("~/build/skills"), cwd=cwd, home=home, agent=agent, environ={})
    assert policy.destination == home / "build/skills"


def test_metadata_allowance_is_closed_and_refuses_seeded_descendant_and_auth_stat(tmp_path, monkeypatch):
    history = tmp_path / "history"
    history.mkdir()
    descendant = history / "entry"
    descendant.write_text("synthetic fixture")
    credential = tmp_path / "auth.json"
    credential.write_text("synthetic fixture")
    original = Path.lstat

    def observed(path, *args, **kwargs):
        assert path.name not in {"auth.json", "mcp-auth.json"}, "credential metadata forbidden"
        assert path == history or path in history.parents, "descendant metadata forbidden"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", observed)
    assert history_root(history) == history
    with pytest.raises(AssertionError, match="descendant"):
        descendant.lstat()
    with pytest.raises(AssertionError, match="credential"):
        credential.lstat()
    # The actual resolver refuses a selected credential path before the probe.
    with pytest.raises(PolicyError, match="credential"):
        history_root(credential)


@pytest.mark.parametrize("contained", ["history", "agent", "project-config"])
def test_inverse_containment_refuses_output_ancestor(tmp_path, contained):
    home, cwd, agent = context(tmp_path)
    output = tmp_path / "build/skills"
    output.mkdir(parents=True)
    kwargs = {}
    if contained == "history":
        forbidden = output / "topic"
        forbidden.mkdir()
        kwargs["session_dir"] = str(forbidden)
    elif contained == "agent":
        agent = output / "topic"
        agent.mkdir()
        forbidden = agent
    else:
        cwd = output / "project"
        cwd.mkdir()
        forbidden = cwd / ".pi"
        forbidden.mkdir()
    assert output in forbidden.parents
    with pytest.raises(PolicyError, match="trusted_config|sessions"):
        preflight(output, cwd=cwd, home=home, agent=agent, environ={}, **kwargs)
