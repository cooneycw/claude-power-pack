"""AGY topic copies, with no native CLI or credential-store access."""
from __future__ import annotations

import re

from lib.antigravity_skills import build

from .host import CopyAdapter
from .models import AdapterError


def yaml_module(harness):
    """Only a selected YAML reader needs this optional runtime dependency."""
    try:
        import yaml
    except ModuleNotFoundError as error:
        if error.name != "yaml":
            raise
        raise AdapterError(f"UNAVAILABLE: {harness}: missing module yaml (PyYAML)", exit_code=4,
                           remedy="install PyYAML for this YAML adapter; stdlib components remain usable") from error
    return yaml


class AntigravityAdapter(CopyAdapter):
    harness = "antigravity"
    prefix = (".gemini", "config")

    def legacy_source(self, name, content):
        yaml = yaml_module(self.harness)
        try:
            sections = re.split(r"(?m)^---[ \t]*$", content.decode(), maxsplit=2)
            if len(sections) != 3 or sections[0]:
                return False
            metadata = yaml.safe_load(sections[1])
            source = metadata.get("metadata", {}).get("source")
            wanted = f"claude-power-pack/.claude/skills/{name}"
            if isinstance(source, str) and source.startswith("claude-power-pack/.claude/skills/") and source != wanted:
                raise AdapterError("CPP source marker and installed package name disagree", exit_code=4,
                                   remedy="review the renamed/ambiguous legacy installation")
            return source == wanted
        except (ValueError, IndexError, AttributeError, yaml.YAMLError):
            return False

    def build(self, revision, policy):
        if self._build is None or self._build.revision != revision.commit:
            yaml_module(self.harness)
            self._build = build(revision)
        return self._build
