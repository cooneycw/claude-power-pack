"""AGY topic copies, with no native CLI or credential-store access."""
from __future__ import annotations

import re

import yaml

from lib.antigravity_skills import build

from .host import CopyAdapter
from .models import AdapterError


class AntigravityAdapter(CopyAdapter):
    harness = "antigravity"
    prefix = (".gemini", "config")

    def legacy_source(self, name, content):
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
            self._build = build(revision)
        return self._build
