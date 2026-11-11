"""Recorded provider contract and known-bad inputs (#1607)."""

import json
from pathlib import Path

import pytest

from lib.cicd.config import CICDConfig
from lib.cicd.models import Framework, FrameworkInfo, PackageManager
from lib.cicd.pipeline import generate_pipeline


def test_absent_provider_is_unknown(tmp_path: Path):
    config = CICDConfig.load(str(tmp_path))
    assert config.pipeline.provider == "unknown"


def test_generation_without_record_refuses_before_writing(tmp_path: Path):
    with pytest.raises(ValueError, match="record.*providers"):
        generate_pipeline(FrameworkInfo(Framework.UNKNOWN, PackageManager.UNKNOWN), CICDConfig(), output_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("value", [None, {}, {"pipeline": {}}, {"pipeline": {"providers": []}}])
def test_reader_reports_unknown(tmp_path: Path, value):
    from lib.cicd.providers import read_provider_record
    if value is not None:
        path = tmp_path / ".claude/cicd.yml"
        path.parent.mkdir()
        path.write_text(json.dumps(value))
    record = read_provider_record(tmp_path)
    assert record.providers == ()
    assert record.source


@pytest.mark.parametrize("legacy,expected", [
    ("woodpecker", ["woodpecker"]), ("github-actions", ["github-actions"]),
    ("both", ["github-actions", "woodpecker"]),
])
def test_legacy_scalar_maps_to_registered_list(legacy, expected):
    config = CICDConfig.model_validate({"pipeline": {"provider": legacy}})
    assert config.pipeline.providers == expected


@pytest.mark.parametrize("pipeline", [
    {"providers": ["unknown-ci"]}, {"providers": "woodpecker"},
    {"providers": ["woodpecker", "woodpecker"]},
    {"providers": ["woodpecker"], "provider": "github-actions"},
])
def test_invalid_or_conflicting_selection_refuses(pipeline):
    with pytest.raises(ValueError):
        CICDConfig.model_validate({"pipeline": pipeline})


def test_writer_preserves_unrelated_comments_order_and_pipeline_settings(tmp_path: Path):
    from lib.cicd.providers import read_provider_record, record_providers
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    before = ("# keep me\nhealth:\n  smoke_tests: []\npipeline:\n  provider: github-actions\n"
              "  branches: {pr: [test]} # keep too\nbuild: {}\n")
    path.write_text(before)
    record_providers(tmp_path, ["woodpecker"])
    assert path.read_text() == before.replace("  provider: github-actions", '  providers: ["woodpecker"]')
    assert read_provider_record(tmp_path).providers == ("woodpecker",)


def test_writer_refuses_comment_loss_and_keeps_original_bytes(tmp_path: Path):
    from lib.cicd.providers import record_providers
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    before = "pipeline:\n  provider: github-actions # why we chose it\n"
    path.write_text(before)
    with pytest.raises(ValueError, match="line 2"):
        record_providers(tmp_path, ["woodpecker"])
    assert path.read_text() == before


def test_writer_adds_record_without_rewriting_other_sections(tmp_path: Path):
    from lib.cicd.providers import record_providers
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    before = "# retained\nbuild:\n  required_targets: [test]\n"
    path.write_text(before)
    record_providers(tmp_path, ["woodpecker", "github-actions"])
    assert path.read_text().startswith(before)
    assert "providers:" in path.read_text()


def _shell_yaml_provider_parsers(root: Path) -> list[str]:
    """Detect inline grep/sed/awk/yq reads naming provider and cicd.yml."""
    import re
    findings = []
    for path in root.glob("flow*.sh"):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if "cicd.yml" in code and "provider" in code and re.search(r"\b(grep|sed|awk|yq)\b", code):
                findings.append(f"{path.name}:{number}")
    return findings


def test_flow_helpers_do_not_parse_provider_yaml(tmp_path: Path):
    planted = tmp_path / "flow-planted.sh"
    planted.write_text("grep provider .claude/cicd.yml\n")
    assert _shell_yaml_provider_parsers(tmp_path) == ["flow-planted.sh:1"]
    root = Path(__file__).resolve().parents[1]
    assert _shell_yaml_provider_parsers(root / "scripts") == []


def test_registry_extension_needs_no_combination_branch(monkeypatch):
    from lib.cicd import pipeline
    from lib.cicd.providers import PROVIDERS, ProviderSpec
    monkeypatch.setitem(PROVIDERS, "fixture", ProviderSpec(
        "fixture", "fixture_generator", ".fixture-ci", "fixture-jobs", "fixture", "fixture-auth"
    ))
    monkeypatch.setattr(pipeline, "fixture_generator", lambda info, config: "fixture-ci", raising=False)
    config = CICDConfig.model_validate({"pipeline": {"providers": ["fixture", "woodpecker"]}})
    files = generate_pipeline(FrameworkInfo(Framework.UNKNOWN, PackageManager.UNKNOWN), config)
    assert files[".fixture-ci"] == "fixture-ci"
    assert ".woodpecker.yml" in files


def test_cli_reader_and_record_roundtrip(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    assert main(["provider", "--path", str(tmp_path)]) == 1
    assert "CICD_PROVIDERS: unknown" in capsys.readouterr().out
    assert main(["pipeline", "--path", str(tmp_path), "--providers", "woodpecker", "--record", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["providers"] == ["woodpecker"]
    assert main(["provider", "--path", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["providers"] == ["woodpecker"]
    assert not (tmp_path / ".woodpecker.yml").exists()


def test_config_validation_names_missing_provider(tmp_path: Path):
    path = tmp_path / "cicd.yml"
    path.write_text("build: {}\n")
    assert any("pipeline.providers" in item for item in CICDConfig.validate_file(path))


@pytest.mark.parametrize("selection", ["  providers:\n    - github-actions\n", "  provider: github-actions\n"])
def test_writer_replaces_only_selection_span(tmp_path: Path, selection):
    from lib.cicd.providers import record_providers
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    before = "pipeline:\n" + selection + "  branches: {pr: [test]} # keep\nhealth: {}\n"
    path.write_text(before)
    record_providers(tmp_path, ["woodpecker"])
    assert path.read_text() == before.replace(selection, '  providers: ["woodpecker"]\n')


def test_writer_preserves_crlf_bytes(tmp_path: Path):
    from lib.cicd.providers import record_providers
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    before = b"# retained\r\npipeline:\r\n  provider: github-actions\r\nbuild: {}\r\n"
    path.write_bytes(before)
    record_providers(tmp_path, ["woodpecker"])
    assert path.read_bytes() == before.replace(b"provider: github-actions", b'providers: ["woodpecker"]')


@pytest.mark.parametrize("text", ["pipeline: {provider: github-actions}\n", "pipeline: [github-actions]\n", "[]\n"])
def test_writer_refuses_unsupported_yaml_without_changes(tmp_path: Path, text):
    from lib.cicd.providers import record_providers
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text(text)
    with pytest.raises(ValueError):
        record_providers(tmp_path, ["woodpecker"])
    assert path.read_text() == text


def test_cli_unknown_generation_writes_no_pipeline(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    assert main(["pipeline", "--path", str(tmp_path), "--write"]) == 2
    assert "record pipeline.providers" in capsys.readouterr().err
    assert not (tmp_path / ".woodpecker.yml").exists()
    assert not (tmp_path / ".github").exists()


def test_reader_invalid_record_is_unknown_with_nonzero_exit(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text("pipeline:\n  providers: [unregistered-ci]\n")
    assert main(["provider", "--path", str(tmp_path), "--json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "unknown" and result["providers"] == []
    assert "unregistered" in result["source"]


def test_list_generates_each_selected_pipeline():
    config = CICDConfig.model_validate({"pipeline": {"providers": ["woodpecker", "github-actions"]}})
    files = generate_pipeline(FrameworkInfo(Framework.UNKNOWN, PackageManager.UNKNOWN), config)
    assert set(files) == {".woodpecker.yml", ".github/workflows/ci.yml"}


def test_writer_canonicalizes_agreeing_legacy_and_list_records(tmp_path: Path):
    from lib.cicd.providers import record_providers
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text("pipeline:\n  provider: woodpecker\n  providers: [woodpecker]\n  matrix: {}\n")
    record_providers(tmp_path, ["github-actions"])
    assert path.read_text() == 'pipeline:\n  providers: ["github-actions"]\n  matrix: {}\n'


@pytest.mark.parametrize("text", [
    "pipeline: {providers: [woodpecker]}\npipeline: {providers: [github-actions]}\n",
    "pipeline:\n  providers: [woodpecker]\n  providers: [github-actions]\n",
])
def test_duplicate_provider_records_fail_closed(tmp_path: Path, text):
    from lib.cicd.providers import read_provider_record
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text(text)
    with pytest.raises(ValueError, match="duplicate"):
        read_provider_record(tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        CICDConfig.load(str(tmp_path))


def test_writer_records_example_without_dropping_template_comments(tmp_path: Path):
    from lib.cicd.providers import record_providers
    source = Path(__file__).resolve().parents[1] / "templates/cicd.yml.example"
    before = source.read_text()
    assert "  providers: []\n" in before
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text(before)
    record_providers(tmp_path, ["woodpecker"])
    assert path.read_text() == before.replace("  providers: []\n", '  providers: ["woodpecker"]\n')


def test_comment_preservation_control_rejects_roundtrip_writer(tmp_path: Path, monkeypatch):
    import yaml

    from lib.cicd import providers

    def blind_roundtrip(project, names):
        path = Path(project) / ".claude/cicd.yml"
        data = yaml.safe_load(path.read_text())
        data["pipeline"].pop("provider", None)
        data["pipeline"]["providers"] = names
        path.write_text(yaml.safe_dump(data, sort_keys=False))

    monkeypatch.setattr(providers, "record_providers", blind_roundtrip)
    with pytest.raises(AssertionError):
        test_writer_preserves_unrelated_comments_order_and_pipeline_settings(tmp_path)


def test_explicit_cli_selection_repairs_invalid_record(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text("# retained\npipeline:\n  providers: [unregistered-ci]\n  branches: {pr: [test]}\n")
    assert main(["pipeline", "--path", str(tmp_path), "--providers", "woodpecker", "--record", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["providers"] == ["woodpecker"]
    assert "# retained" in path.read_text()
    assert "branches: {pr: [test]}" in path.read_text()


def test_merged_ambiguous_provider_mapping_refuses(tmp_path: Path):
    from lib.cicd.providers import read_provider_record
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text("pipeline: {<<: {providers: [woodpecker], providers: [github-actions]}}\n")
    with pytest.raises(ValueError, match="merge|duplicate"):
        read_provider_record(tmp_path)
    with pytest.raises(ValueError, match="merge|duplicate"):
        CICDConfig.load(str(tmp_path))


def test_one_run_override_repairs_selection_without_recording(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    before = "pipeline:\n  provider: obsolete-ci\n"
    path.write_text(before)
    assert main(["pipeline", "--path", str(tmp_path), "--provider", "woodpecker", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["providers"] == ["woodpecker"]
    assert path.read_text() == before


def test_unreadable_record_has_unknown_marker(tmp_path: Path, capsys, monkeypatch):
    from lib.cicd.cli import main

    def unreadable(*args, **kwargs):
        raise PermissionError("fixture refuses read")

    monkeypatch.setattr(Path, "read_text", unreadable)
    assert main(["provider", "--path", str(tmp_path)]) == 2
    assert "CICD_PROVIDERS: unknown" in capsys.readouterr().out


def test_infra_generation_refuses_unknown_providers(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text(json.dumps({"build": {}}))
    before = path.read_bytes()
    assert main(["infra-pipeline", "--path", str(tmp_path), "--json"]) != 0
    error = capsys.readouterr().err
    assert "record pipeline.providers" in error
    assert path.read_bytes() == before
    assert not (tmp_path / ".github").exists()
    assert not (tmp_path / ".woodpecker.yml").exists()


def test_infra_explicit_single_provider_is_accepted(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    assert main(["infra-pipeline", "--path", str(tmp_path), "--provider", "woodpecker", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["provider"] == "woodpecker"
    assert not (tmp_path / ".claude/cicd.yml").exists()


def test_writer_preserves_blank_lines_after_block_list(tmp_path: Path):
    from lib.cicd.providers import record_providers
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    before = "pipeline:\n  providers:\n    - github-actions\n\n  branches: {pr: [test]}\n"
    path.write_text(before)
    record_providers(tmp_path, ["woodpecker"])
    assert path.read_text() == 'pipeline:\n  providers: ["woodpecker"]\n\n  branches: {pr: [test]}\n'


# --- Issue #1677: a linked worktree and the main checkout's untracked record ---

def _git(cwd: Path, *args: str) -> None:
    import os
    import subprocess
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, env=env)


def _repo_with_worktree(tmp_path: Path, *, ignore_claude: bool = True) -> tuple[Path, Path]:
    main, linked = tmp_path / "main", tmp_path / "linked"
    main.mkdir()
    _git(main, "init", "-q")
    (main / ".gitignore").write_text(".claude/\n" if ignore_claude else "")
    _git(main, "add", ".gitignore")
    _git(main, "commit", "-q", "-m", "init")
    _git(main, "worktree", "add", "-q", str(linked), "-b", "work")
    return main, linked


def _record(root: Path, text: str = "pipeline:\n  providers: [woodpecker]\n") -> Path:
    path = root / ".claude/cicd.yml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text)
    return path


requires_git = pytest.mark.skipif(__import__("shutil").which("git") is None, reason="requires git")


@requires_git
def test_linked_worktree_reads_untracked_main_checkout_record(tmp_path: Path):
    """THE ISSUE'S RED CASE: a worktree with no record, a main checkout with one."""
    from lib.cicd.providers import read_provider_record
    main, linked = _repo_with_worktree(tmp_path)
    assert read_provider_record(linked).providers == ()  # nothing recorded anywhere yet
    _record(main)
    record = read_provider_record(linked)
    assert record.providers == ("woodpecker",)
    assert str(main.resolve() / ".claude/cicd.yml") in record.source
    assert "main-checkout record" in record.source


@requires_git
def test_tracked_main_record_is_never_borrowed(tmp_path: Path):
    """A branch that deleted a TRACKED record must still read unknown."""
    from lib.cicd.providers import read_provider_record
    main, linked = _repo_with_worktree(tmp_path, ignore_claude=False)
    _record(main)
    _git(main, "add", ".claude/cicd.yml")
    _git(main, "commit", "-q", "-m", "record")
    record = read_provider_record(linked)  # `work` predates the record
    assert record.providers == ()
    assert "file missing" in record.source


@requires_git
def test_worktree_own_record_wins_over_main(tmp_path: Path):
    from lib.cicd.providers import read_provider_record
    main, linked = _repo_with_worktree(tmp_path)
    _record(main)
    _record(linked, "pipeline:\n  providers: [github-actions]\n")
    record = read_provider_record(linked)
    assert record.providers == ("github-actions",)
    assert "main-checkout" not in record.source


@requires_git
def test_worktree_present_but_empty_record_does_not_fall_back(tmp_path: Path):
    """Only a MISSING file borrows; a file that names no provider is an answer."""
    from lib.cicd.providers import read_provider_record
    main, linked = _repo_with_worktree(tmp_path)
    _record(main)
    _record(linked, "build: {}\n")
    assert read_provider_record(linked).providers == ()


@requires_git
def test_subdirectory_and_main_checkout_never_borrow(tmp_path: Path):
    from lib.cicd.providers import read_provider_record, shared_record_path
    main, linked = _repo_with_worktree(tmp_path)
    _record(main)
    (linked / "sub").mkdir()
    assert shared_record_path(linked / "sub") is None
    assert read_provider_record(linked / "sub").providers == ()
    assert shared_record_path(main) is None


@requires_git
def test_invalid_borrowed_record_fails_closed(tmp_path: Path):
    from lib.cicd.providers import ProviderError, read_provider_record
    main, linked = _repo_with_worktree(tmp_path)
    _record(main, "pipeline:\n  providers: [unregistered-ci]\n")
    with pytest.raises(ProviderError, match="unregistered"):
        read_provider_record(linked)


@requires_git
def test_host_preflight_proceeds_from_a_linked_worktree(tmp_path: Path, capsys):
    """The consumer that stopped kyle's merge (gh-pr-merge exit 13) reads the same record."""
    from lib.cicd.flow import provider_lanes
    main, linked = _repo_with_worktree(tmp_path)
    with pytest.raises(ValueError, match="CI providers unknown"):
        provider_lanes(linked)
    _record(main)
    assert provider_lanes(linked) == [("woodpecker", "woodpecker")]


def test_remedy_says_where_the_record_must_live():
    from lib.cicd.providers import REMEDY
    assert "commit that file" in REMEDY
    assert "main checkout" in REMEDY
