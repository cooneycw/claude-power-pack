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
