"""Canonical project provider record, registry, and targeted writer (#1607)."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ProviderError(ValueError):
    """A project has no usable, explicitly recorded provider selection."""


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    generator: str
    pipeline_file: str
    required_check: str
    ci_lane: str
    host_check: str


# Hook identities are shared with the later host/flow consumers. Generators
# resolve inside pipeline.py to avoid importing config/pydantic in the reader.
PROVIDERS = {
    "github-actions": ProviderSpec(
        "github-actions", "generate_github_actions", ".github/workflows/ci.yml",
        "github-actions-jobs", "github-actions", "github-actions-auth",
    ),
    "woodpecker": ProviderSpec(
        "woodpecker", "generate_woodpecker", ".woodpecker.yml",
        "woodpecker-pr-pipelines", "woodpecker", "woodpecker-auth",
    ),
}

REMEDY = "record pipeline.providers in .claude/cicd.yml with pipeline --providers NAME[,NAME] --record"


def normalize_providers(pipeline: dict[str, Any]) -> list[str]:
    """Validate a list, accepting the historical scalar only at this boundary."""
    legacy = pipeline.get("provider")
    old = (["github-actions", "woodpecker"] if legacy == "both" else
           [legacy] if isinstance(legacy, str) and legacy else [])
    if legacy is not None and not isinstance(legacy, str):
        raise ProviderError("pipeline.provider must be a string")
    selected = pipeline.get("providers", old)
    if selected is None:
        selected = []
    if not isinstance(selected, list) or any(not isinstance(name, str) for name in selected):
        raise ProviderError("pipeline.providers must be a list of registered names")
    if len(set(selected)) != len(selected):
        raise ProviderError("pipeline.providers contains duplicate names")
    for name in [*old, *selected]:
        if name not in PROVIDERS:
            raise ProviderError(f"unregistered CI provider {name!r}; registered: {', '.join(PROVIDERS)}")
    if "providers" in pipeline and old and set(old) != set(selected):
        raise ProviderError("pipeline.provider conflicts with pipeline.providers; keep only the list")
    return list(selected)


def require_providers(names: list[str] | tuple[str, ...]) -> list[str]:
    selected = normalize_providers({"providers": list(names)})
    if not selected:
        raise ProviderError("CI providers unknown; " + REMEDY)
    return selected


@dataclass(frozen=True)
class ProviderRecord:
    providers: tuple[str, ...]
    source: str


def parse_config_mapping(text: str, source: str) -> dict[str, Any]:
    """Reject ambiguous provider records before the shared YAML load."""
    try:
        node = yaml.compose(text)
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProviderError(f"{source}: malformed YAML") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ProviderError(f"{source}: config must be a mapping")
    assert isinstance(node, yaml.MappingNode)
    if any(key.tag == "tag:yaml.org,2002:merge" for key, _ in node.value):
        raise ProviderError(f"{source}: top-level YAML merges cannot define an unambiguous provider record")
    pipelines = [value for key, value in node.value if key.value == "pipeline"]
    if len(pipelines) > 1:
        raise ProviderError(f"{source}: duplicate pipeline sections")
    if pipelines and isinstance(pipelines[0], yaml.MappingNode):
        if any(key.tag == "tag:yaml.org,2002:merge" for key, _ in pipelines[0].value):
            raise ProviderError(f"{source}: pipeline YAML merges are unsupported; record providers explicitly")
        keys = [key.value for key, _ in pipelines[0].value if key.value in ("provider", "providers")]
        if len(keys) != len(set(keys)):
            raise ProviderError(f"{source}: duplicate provider keys")
    return data


def read_provider_record(project: str | Path) -> ProviderRecord:
    path = Path(project) / ".claude/cicd.yml"
    try:
        data = parse_config_mapping(path.read_text(), str(path))
    except FileNotFoundError:
        return ProviderRecord((), f"{path}: file missing")
    except OSError as exc:
        raise ProviderError(f"could not read {path}: {type(exc).__name__}") from exc
    pipeline = data.get("pipeline", {})
    if pipeline is None:
        pipeline = {}
    if not isinstance(pipeline, dict):
        raise ProviderError(f"{path}: pipeline must be a mapping")
    selected = normalize_providers(pipeline)
    source = ("pipeline.providers" if "providers" in pipeline else
              "pipeline.provider" if "provider" in pipeline else "providers absent")
    return ProviderRecord(tuple(selected), f"{path}: {source}")


def record_providers(project: str | Path, names: list[str]) -> None:
    """Replace only provider lines; preserve other bytes or refuse explicitly.

    PyYAML supplies syntax positions, never serialization of the user's file.
    Flow mappings and aliased/anchored records are refused rather than guessed.
    Comments in any span we would replace produce an exact line diagnostic.
    """
    selected = require_providers(names)
    path = Path(project) / ".claude/cicd.yml"
    if path.is_symlink():
        raise ProviderError(f"refusing to replace symlink {path}; edit its source explicitly")
    if path.exists():
        with path.open(newline="") as stream:
            text = stream.read()
    else:
        text = ""
    try:
        root = yaml.compose(text)
        tokens = list(yaml.scan(text))
    except yaml.YAMLError as exc:
        raise ProviderError("cannot record providers in malformed YAML") from exc
    if any(isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)) for token in tokens):
        raise ProviderError("cannot record providers in YAML with anchors/aliases; edit the record explicitly")
    if root is not None and (not isinstance(root, yaml.MappingNode) or root.flow_style):
        raise ProviderError("recording requires a block YAML mapping")
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in text else "\n"
    entry = "providers: " + json.dumps(selected)
    pipelines = [(key, value) for key, value in root.value if key.value == "pipeline"] if root else []
    if len(pipelines) > 1:
        raise ProviderError("duplicate pipeline sections; edit the record explicitly")
    if not pipelines:
        separator = newline if text and not text.endswith("\n") else ""
        updated = text + separator + "pipeline:" + newline + "  " + entry + newline
    else:
        key, pipeline = pipelines[0]
        if not isinstance(pipeline, yaml.MappingNode) or pipeline.flow_style:
            raise ProviderError(f"pipeline at line {key.start_mark.line + 1} must be a block mapping")
        pairs = [(k, v) for k, v in pipeline.value if k.value in ("provider", "providers")]
        if len({k.value for k, _ in pairs}) != len(pairs):
            raise ProviderError("duplicate provider keys; edit the record explicitly")
        replacements = []
        for k, value in pairs:
            start = k.start_mark.line
            end = value.end_mark.line
            if end < len(lines) and lines[end][:value.end_mark.column].strip():
                end += 1
            if end <= start:
                end = start + 1
            for i in range(start, end):
                if "#" in lines[i]:
                    raise ProviderError(f"refusing to discard comment at line {i + 1}; edit providers explicitly")
            replacements.append((start, end, " " * k.start_mark.column))
        if replacements:
            for index, (start, end, indent) in enumerate(sorted(replacements, reverse=True)):
                lines[start:end] = [indent + entry + newline] if index == len(replacements) - 1 else []
        else:
            # Insert immediately after the section header, retaining its comment.
            indent = pipeline.value[0][0].start_mark.column if pipeline.value else key.start_mark.column + 2
            lines[key.start_mark.line + 1:key.start_mark.line + 1] = [" " * indent + entry + newline]
        updated = "".join(lines)
    # Validate the edited record before touching disk, including multi-document
    # YAML, duplicate/conflicting selections, and accidental span damage.
    parsed = parse_config_mapping(updated, str(path))
    if normalize_providers(parsed["pipeline"]) != selected:
        raise ProviderError("provider edit did not produce the requested record")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix=".cicd-provider-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="") as stream:
            stream.write(updated)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
